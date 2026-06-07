import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from config import settings
from models import BriefingLog, SyncRequest, SyncResponse
from services.briefing_engine import generate_briefing
from services.crm_factory import crm_async as crm
from services.ringg_service import ringg_service
from config import settings
import database

router = APIRouter(prefix="/v1/calls", tags=["calls"])
logger = logging.getLogger(__name__)


@router.post("/sync-now", response_model=SyncResponse)
async def sync_now(request: SyncRequest):
    """
    Trigger an outbound briefing call to the RM.

    Flow:
    1. Fetch full client profile from CRM adapter
    2. Generate briefing text using briefing_engine (GPT-4o or template)
    3. Build custom_args_values payload for Ringg
    4. Call Ringg API to initiate outbound call
    5. Log the briefing
    6. Return call_id and briefing preview
    """
    start_time = time.time()

    # 1. Fetch client profile
    client = await (await crm()).get_client(request.client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client '{request.client_id}' not found")

    # 2. Generate briefing
    briefing_text = await generate_briefing(client)

    # 3. Build Ringg custom args
    open_complaints = [c for c in client.complaints if c.status == "open"]
    complaint_summary = open_complaints[0].summary[:100] if open_complaints else "None"

    primary_cs = client.cross_sell[0] if client.cross_sell else None
    secondary_cs = client.cross_sell[1] if len(client.cross_sell) > 1 else None

    portfolio_parts = []
    for prod in client.products:
        portfolio_parts.append(
            f"{prod.product_type.replace('_',' ').title()}: "
            f"₹{prod.principal/100000:.0f}L, EMI ₹{prod.emi:,.0f}/mo, "
            f"due {prod.next_due_date}"
        )
    portfolio_summary = " | ".join(portfolio_parts) if portfolio_parts else "No active products"

    friendly_closers = [
        "That's the rundown — anything else before you head in? Good luck!",
        "Alright, you're set. Go get 'em!",
        "Anything else? No? Perfect — go run the meeting.",
    ]
    import hashlib
    h = int(hashlib.md5(client.profile.client_id.encode()).hexdigest(), 16)
    friendly_closer = friendly_closers[h % len(friendly_closers)]

    custom_args = {
        "company_name": settings.demo_company_name,
        "callee_name": request.rm_name,
        "client_name": client.profile.name,
        "client_age": str(client.profile.age),
        "client_occupation": f"{client.profile.occupation} at {client.profile.company}",
        "portfolio_summary": portfolio_summary,
        "risk_level": client.risk.score,
        "risk_factors": ", ".join(client.risk.factors[:2]),
        "days_since_contact": str(client.last_rm_interaction_days_ago),
        "open_complaints": complaint_summary,
        "cross_sell_pitch": primary_cs.pitch_angle[:200] if primary_cs else "No specific pitch at this time",
        "cross_sell_product": primary_cs.product if primary_cs else "",
        "secondary_pitch": secondary_cs.pitch_angle[:150] if secondary_cs else "",
        "friendly_closer": friendly_closer,
    }

    # 4. Initiate Ringg call
    latency_ms = None
    try:
        call_id = await ringg_service.initiate_call(
            agent_id=settings.ringg_agent_id,
            from_number_id=settings.ringg_from_number_id,
            recipient_phone=request.rm_phone,
            recipient_name=request.rm_name,
            custom_args=custom_args,
            callback_url=f"{settings.backend_url}/api/v1/webhooks/ringg",
        )
        latency_ms = int((time.time() - start_time) * 1000)
    except Exception as e:
        logger.error(f"Ringg call failed: {e}")
        call_id = f"sim_{uuid.uuid4().hex[:8]}"
        latency_ms = int((time.time() - start_time) * 1000)

    # 5. Log briefing
    key_flags = []
    if open_complaints:
        key_flags.append("complaint_open")
    if client.risk.score in ("high", "watch"):
        key_flags.append(f"risk_{client.risk.score}")
    for factor in client.risk.factors:
        if any(kw in factor.lower() for kw in ["miss", "delay", "utiliz", "dip"]):
            key_flags.append(factor[:30].lower().replace(" ", "_"))

    briefing_log = BriefingLog(
        briefing_id=str(uuid.uuid4()),
        client_id=client.profile.client_id,
        client_name=client.profile.name,
        rm_id=f"rm_{uuid.uuid4().hex[:4]}",
        rm_name=request.rm_name,
        timestamp=datetime.now().isoformat(),
        duration_seconds=0.0,  # updated by webhook on call completion
        key_flags=key_flags,
        suggested_pitch=primary_cs.pitch_angle[:150] if primary_cs else "",
        call_id=call_id,
        risk_score=client.risk.score,
        latency_ms=latency_ms,
    )
    database.BRIEFING_LOGS.append(briefing_log)

    # Broadcast via WebSocket
    from routers.webhooks import broadcast_event
    await broadcast_event({
        "type": "call_started",
        "data": {
            "call_id": call_id,
            "client_name": client.profile.name,
            "rm_name": request.rm_name,
            "briefing_id": briefing_log.briefing_id,
        },
    })

    if not settings.ringg_api_key:
        async def complete_simulated_call() -> None:
            await asyncio.sleep(2.5)
            briefing_log.duration_seconds = 38 + (h % 15)
            await broadcast_event({
                "type": "sync_completed",
                "data": briefing_log.model_dump(),
            })

        asyncio.create_task(complete_simulated_call())

    return SyncResponse(
        call_id=call_id,
        status="initiated" if settings.ringg_api_key else "simulated",
        briefing_preview=briefing_text[:300],
    )


@router.get("/sync-now/{call_id}")
async def get_call_detail(call_id: str):
    """Merge Ringg call details with local BriefingLogRow."""
    import database
    from sqlmodel import select
    from db import get_session
    from db.models import BriefingLogRow

    # Try DB first, fall back to in-memory
    transcript = None
    recording_url = None
    duration = 0.0

    try:
        async with get_session() as session:
            row = (await session.exec(
                select(BriefingLogRow).where(BriefingLogRow.call_id == call_id)
            )).first()
            if row:
                transcript = row.transcript
                recording_url = row.recording_url
                duration = row.duration_seconds
    except Exception:
        pass

    # Supplement from in-memory
    if not transcript:
        log = next((b for b in database.BRIEFING_LOGS if b.call_id == call_id), None)
        if log:
            duration = log.duration_seconds

    # Try Ringg API for live details
    ringg_data = {}
    if settings.ringg_api_key:
        try:
            ringg_data = await ringg_service.get_call_details(call_id)
        except Exception:
            pass

    return {
        "call_id": call_id,
        "duration_seconds": duration,
        "transcript": transcript or ringg_data.get("transcript", ""),
        "recording_url": recording_url or ringg_data.get("recording_url"),
        "ringg_status": ringg_data.get("status"),
    }


@router.get("/sync-now/{call_id}/transcript/stream")
async def stream_transcript(call_id: str):
    """Server-Sent Events stream of transcript chunks for a call."""
    from routers.webhooks import _transcript_queues

    queue: asyncio.Queue = asyncio.Queue()
    _transcript_queues[call_id] = queue

    async def event_generator() -> AsyncGenerator[bytes, None]:
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {chunk}\n\n".encode()
                    if chunk == "[DONE]":
                        break
                except asyncio.TimeoutError:
                    yield b": keepalive\n\n"
        finally:
            _transcript_queues.pop(call_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─── Round 2: Post-Call Intelligence endpoints ─────────────────────────────

@router.get("/sync-now/{call_id}/analysis")
async def get_call_analysis(call_id: str):
    """Return stored CallAnalysis for a call (404 until ready)."""
    from sqlmodel import select
    from db import get_session
    from db.models import CallAnalysis

    async with get_session() as session:
        row = (await session.exec(
            select(CallAnalysis).where(CallAnalysis.call_id == call_id)
        )).first()
    if not row:
        raise HTTPException(404, "Analysis not ready")
    return {
        "call_id": row.call_id,
        "client_id": row.client_id,
        "call_kind": row.call_kind,
        "sentiment_label": row.sentiment_label,
        "sentiment_score": row.sentiment_score,
        "sentiment_timeline": row.sentiment_timeline,
        "objections": row.objections,
        "commitments": row.commitments,
        "churn_delta": row.churn_delta,
        "churn_label": row.churn_label,
        "next_best_action": row.next_best_action,
        "summary": row.summary,
        "nba_executed": row.nba_executed,
        "nba_action_id": row.nba_action_id,
    }


@router.post("/sync-now/{call_id}/analyze")
async def trigger_call_analysis(call_id: str):
    """Manually (re)run post-call analysis — demo safety / re-run."""
    from routers.webhooks import run_post_call_analysis
    await run_post_call_analysis(call_id)
    return {"status": "analyzed", "call_id": call_id}


@router.post("/sync-now/{call_id}/analysis/execute-nba")
async def execute_next_best_action(call_id: str):
    """Execute the stored next-best-action against the active CRM adapter."""
    from sqlmodel import select
    from db import get_session
    from db.models import CallAnalysis
    from services.voice_command_engine import execute_command
    from datetime import date

    async with get_session() as session:
        row = (await session.exec(
            select(CallAnalysis).where(CallAnalysis.call_id == call_id)
        )).first()
        if not row:
            raise HTTPException(404, "Analysis not ready")
        nba = row.next_best_action or {}
        connection_id = row.connection_id
        client_id = row.client_id

    if not nba or not connection_id:
        raise HTTPException(400, "No executable next-best-action")

    args = dict(nba.get("args", {}))
    for k in ("due_date", "when"):
        if k in args and not args[k]:
            args[k] = date.today().isoformat()

    try:
        action_id = await execute_command(nba.get("tool", "create_note"), args, connection_id, client_id)
    except Exception as e:
        raise HTTPException(502, f"Execution failed: {e}")

    async with get_session() as session:
        row = (await session.exec(select(CallAnalysis).where(CallAnalysis.call_id == call_id))).first()
        if row:
            row.nba_executed = True
            row.nba_action_id = str(action_id)
            session.add(row)

    from routers.webhooks import broadcast_event
    await broadcast_event({"type": "command_executed", "data": {
        "tool": nba.get("tool"), "client_id": client_id, "action_id": str(action_id), "source": "manual_nba"}})

    return {"status": "executed", "tool": nba.get("tool"), "action_id": str(action_id)}
