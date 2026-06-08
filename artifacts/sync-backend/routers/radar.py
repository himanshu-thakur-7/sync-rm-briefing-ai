"""Risk Radar router — autonomous save-call orchestration.

  POST /api/v1/radar/scan?connection=        run radar, upsert plays
  GET  /api/v1/radar/plays?connection=&status= list plays
  POST /api/v1/radar/plays/{id}/call          place the outbound save call
  POST /api/v1/radar/plays/{id}/dismiss        dismiss a play
  POST /api/v1/radar/autopilot                 toggle the autonomous scanner
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select

from config import settings
from db import get_session
from db.models import SaveCallPlay
from services import connection_registry, risk_radar
from services.briefing_engine import generate_outreach_brief
from services.ringg_service import ringg_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/radar", tags=["radar"])


# ─────────────────────────────── models ───────────────────────────────────

class PlayOut(BaseModel):
    id: int
    connection_id: str
    client_id: str
    client_name: str
    trigger_type: str
    urgency: str
    objective: str
    talking_points: list[str]
    rationale: str
    matched_triggers: list[str]
    status: str
    call_id: Optional[str] = None
    outcome: Optional[str] = None
    called_at: Optional[str] = None


class CallRequest(BaseModel):
    client_phone: Optional[str] = None   # override the demo phone
    rm_phone: Optional[str] = None       # warm-transfer target


class AutopilotRequest(BaseModel):
    enabled: bool
    connection_id: str


def _to_out(p: SaveCallPlay) -> PlayOut:
    return PlayOut(
        id=p.id,
        connection_id=p.connection_id,
        client_id=p.client_id,
        client_name=p.client_name,
        trigger_type=p.trigger_type,
        urgency=p.urgency,
        objective=p.objective,
        talking_points=p.talking_points or [],
        rationale=p.rationale,
        matched_triggers=p.matched_triggers or [],
        status=p.status,
        call_id=p.call_id,
        outcome=p.outcome,
        called_at=p.called_at.isoformat() if p.called_at else None,
    )


# ─────────────────────────────── scan ─────────────────────────────────────

@router.post("/scan", response_model=list[PlayOut])
async def scan_radar(connection: Optional[str] = Query(default=None)):
    """Run the Risk Radar and upsert plays (one active play per client)."""
    connection_id = connection or await connection_registry.default_connection_id()
    detected = await risk_radar.scan(connection_id)

    out: list[SaveCallPlay] = []
    async with get_session() as session:
        # Existing non-terminal plays for this connection, keyed by client.
        existing = list((await session.exec(
            select(SaveCallPlay).where(SaveCallPlay.connection_id == connection_id)
        )).all())
        by_client = {p.client_id: p for p in existing}

        for d in detected:
            prev = by_client.get(d.client_id)
            # Don't disturb a play that's mid-flight or already actioned.
            if prev and prev.status in ("calling", "transferred", "completed"):
                out.append(prev)
                continue
            if prev:  # refresh a queued/dismissed/failed play
                prev.trigger_type = d.trigger_type
                prev.urgency = d.urgency
                prev.objective = d.objective
                prev.talking_points = d.talking_points
                prev.rationale = d.rationale
                prev.matched_triggers = d.matched_triggers
                prev.status = "queued"
                prev.client_name = d.client_name
                session.add(prev)
                out.append(prev)
            else:
                row = SaveCallPlay(
                    connection_id=connection_id,
                    client_id=d.client_id,
                    client_name=d.client_name,
                    trigger_type=d.trigger_type,
                    urgency=d.urgency,
                    objective=d.objective,
                    talking_points=d.talking_points,
                    rationale=d.rationale,
                    matched_triggers=d.matched_triggers,
                    status="queued",
                    created_at=datetime.now(timezone.utc),
                )
                session.add(row)
                out.append(row)
        await session.flush()
        result = [_to_out(p) for p in out]

    from routers.webhooks import broadcast_event
    await broadcast_event({"type": "radar_scan", "data": {"connection_id": connection_id, "count": len(result)}})
    return result


@router.get("/plays", response_model=list[PlayOut])
async def list_plays(
    connection: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
):
    connection_id = connection or await connection_registry.default_connection_id()
    async with get_session() as session:
        q = select(SaveCallPlay).where(SaveCallPlay.connection_id == connection_id)
        if status:
            q = q.where(SaveCallPlay.status == status)
        rows = list((await session.exec(q.order_by(SaveCallPlay.created_at.desc()))).all())
    # Sort by urgency for display
    rank = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
    rows.sort(key=lambda p: rank.get(p.urgency, 0), reverse=True)
    return [_to_out(p) for p in rows]


# ─────────────────────────────── place call ───────────────────────────────

@router.post("/plays/{play_id}/call", response_model=PlayOut)
async def place_save_call(play_id: int, body: Optional[CallRequest] = None):
    # Treat missing/empty body the same as one with all-None overrides.
    body = body or CallRequest()
    """Generate the outreach brief and place the outbound save call."""
    async with get_session() as session:
        play = (await session.exec(select(SaveCallPlay).where(SaveCallPlay.id == play_id))).first()
        if not play:
            raise HTTPException(404, f"Play {play_id} not found")
        connection_id = play.connection_id
        client_id = play.client_id
        play_dict = {
            "objective": play.objective,
            "talking_points": play.talking_points or [],
            "trigger_type": play.trigger_type,
            "urgency": play.urgency,
            "rationale": play.rationale,
        }
        client_name = play.client_name

    # Resolve the full client + build the outreach brief
    adapter = await connection_registry.crm_for(connection_id)
    client = await adapter.get_client(client_id)
    if client is None:
        raise HTTPException(404, f"Client {client_id} not found")

    custom_args = await generate_outreach_brief(client, play_dict)

    client_phone = body.client_phone or settings.demo_client_phone
    rm_phone = body.rm_phone or settings.demo_rm_phone
    callback_url = f"{settings.backend_url}/api/v1/webhooks/ringg"

    try:
        call_id = await ringg_service.initiate_outreach_call(
            outreach_agent_id=settings.ringg_outreach_agent_id or settings.ringg_agent_id,
            from_number_id=settings.ringg_from_number_id,
            client_phone=client_phone,
            client_name=client_name,
            custom_args=custom_args,
            callback_url=callback_url,
            transfer_to_number=rm_phone,
        )
    except Exception as e:
        logger.error("Outreach call failed: %s", e)
        import uuid
        call_id = f"sim_outreach_{uuid.uuid4().hex[:8]}"

    now = datetime.now(timezone.utc)
    async with get_session() as session:
        play = (await session.exec(select(SaveCallPlay).where(SaveCallPlay.id == play_id))).first()
        play.status = "calling"
        play.call_id = call_id
        play.called_at = now
        session.add(play)
        result = _to_out(play)

    from routers.webhooks import broadcast_event
    await broadcast_event({
        "type": "save_call_started",
        "data": {"play_id": play_id, "call_id": call_id, "client_name": client_name,
                 "objective": play_dict["objective"], "urgency": play_dict["urgency"]},
    })

    # No Ringg key → simulate the whole client conversation + handoff + analysis.
    if not settings.ringg_api_key:
        asyncio.create_task(_simulate_outreach(play_id, call_id, connection_id, client_id, client_name, custom_args))

    return result


async def _simulate_outreach(play_id, call_id, connection_id, client_id, client_name, custom_args):
    """Stream a scripted client conversation, then a transfer, then analysis —
    so the full autonomous loop is demoable with zero Ringg credentials."""
    from routers.webhooks import broadcast_event, _transcript_queues, run_post_call_analysis

    first = client_name.split()[0]
    objective = custom_args.get("objective", "a quick check-in")
    offer = custom_args.get("offer", "")
    company = custom_args.get("company_name", "Acme")
    lines = [
        f"SYNC: {custom_args.get('opening_line', f'Hi {first}, this is SYNC calling on behalf of {company}. This call may be recorded.')}",
        f"{first}: Oh, okay — sure, go ahead.",
        f"SYNC: {offer or objective}",
        f"{first}: Hmm. I've been a bit worried about that, honestly.",
        "SYNC: Completely understand. I've actually found a way that could save you a fair bit this year. Would you like me to connect you to your relationship manager to walk through the specifics?",
        f"{first}: Yes, that would be good. Maybe later this week though.",
        "SYNC: Perfect — I'll set that up and have them call you. Have a great day!",
    ]
    q = _transcript_queues.get(call_id)
    full_lines = []
    for ln in lines:
        full_lines.append(ln)
        if q:
            await q.put(ln)
        await broadcast_event({"type": "transcript_chunk", "data": {"call_id": call_id, "text": ln}})
        await asyncio.sleep(1.1)

    transcript = "\n".join(full_lines)

    # Mark transferred
    async with get_session() as session:
        play = (await session.exec(select(SaveCallPlay).where(SaveCallPlay.id == play_id))).first()
        if play:
            play.status = "transferred"
            play.outcome = "Client agreed to an RM callback this week"
            session.add(play)
    await broadcast_event({"type": "save_call_transferred", "data": {"play_id": play_id, "call_id": call_id}})

    # Run post-call analysis on the simulated transcript
    await run_post_call_analysis(call_id, transcript_override=transcript, call_kind="save_call",
                                 connection_id=connection_id, client_id=client_id)


@router.post("/plays/{play_id}/dismiss", response_model=PlayOut)
async def dismiss_play(play_id: int):
    async with get_session() as session:
        play = (await session.exec(select(SaveCallPlay).where(SaveCallPlay.id == play_id))).first()
        if not play:
            raise HTTPException(404, f"Play {play_id} not found")
        play.status = "dismissed"
        session.add(play)
        return _to_out(play)


# ─────────────────────────────── autopilot ────────────────────────────────

_autopilot_tasks: dict[str, asyncio.Task] = {}


@router.post("/autopilot")
async def toggle_autopilot(body: AutopilotRequest):
    """Enable/disable the autonomous scanner for a connection."""
    cid = body.connection_id
    if body.enabled:
        if cid not in _autopilot_tasks or _autopilot_tasks[cid].done():
            _autopilot_tasks[cid] = asyncio.create_task(_autopilot_loop(cid))
        return {"enabled": True, "connection_id": cid}
    else:
        task = _autopilot_tasks.pop(cid, None)
        if task:
            task.cancel()
        return {"enabled": False, "connection_id": cid}


async def _autopilot_loop(connection_id: str):
    """Scan periodically and auto-place CRITICAL save calls."""
    from routers.webhooks import broadcast_event
    interval = max(1, settings.radar_scan_interval_min) * 60
    try:
        while True:
            try:
                detected = await risk_radar.scan(connection_id)
                await broadcast_event({"type": "radar_scan", "data": {"connection_id": connection_id, "count": len(detected), "autopilot": True}})
                # Auto-place calls for CRITICAL plays not already in flight
                for d in detected:
                    if d.urgency != "CRITICAL":
                        continue
                    async with get_session() as session:
                        existing = (await session.exec(
                            select(SaveCallPlay).where(
                                SaveCallPlay.connection_id == connection_id,
                                SaveCallPlay.client_id == d.client_id,
                            )
                        )).first()
                        if existing and existing.status in ("calling", "transferred", "completed"):
                            continue
                        if not existing:
                            existing = SaveCallPlay(
                                connection_id=connection_id, client_id=d.client_id,
                                client_name=d.client_name, trigger_type=d.trigger_type,
                                urgency=d.urgency, objective=d.objective,
                                talking_points=d.talking_points, rationale=d.rationale,
                                matched_triggers=d.matched_triggers, status="queued",
                            )
                            session.add(existing)
                            await session.flush()
                        pid = existing.id
                    await place_save_call(pid, CallRequest())
            except Exception as e:
                logger.warning("Autopilot scan error for %s: %s", connection_id, e)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Autopilot stopped for %s", connection_id)
        raise
