"""Ringg webhook receiver + WebSocket dashboard hub.

Phase 3 enhancements:
- Every incoming Ringg webhook is persisted as a WebhookEvent row with a
  received → processing → processed | error lifecycle.
- A `webhook_event` WS broadcast fires at each status transition so the
  dashboard activity panel can animate the pill.
- `transcript_chunk` events from Ringg are forwarded via SSE-style WS message.
- `recording_url` from `all_processing_completed` is stored on BriefingLogRow.
- HMAC-SHA256 signature verification using settings.webhook_secret (skipped
  when the secret is the default placeholder — safe for dev/hackathon).
"""
import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

import database
from config import settings
from db import get_session
from db.models import BriefingLogRow, CallAnalysis, SaveCallPlay, WebhookEvent

router = APIRouter(tags=["webhooks"])
logger = logging.getLogger(__name__)

# ─── Active WebSocket connections ─────────────────────────────────────────
_ws_clients: list[WebSocket] = []

# ─── Idempotency ──────────────────────────────────────────────────────────
_processed_events: set[str] = set()

# ─── Per-call transcript queues (for SSE-style streaming) ──────────────────
_transcript_queues: dict[str, asyncio.Queue] = {}


# ─── Broadcast helper ─────────────────────────────────────────────────────

async def broadcast_event(event: dict) -> None:
    """Broadcast to all connected WS clients; prune disconnected."""
    dead: list[WebSocket] = []
    payload = json.dumps(event, default=str)
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


async def emit_transcript_chunk(call_id: str, text: str, client_summary: str = "",
                                coach: bool = True) -> None:
    """Single funnel for every transcript line, real or simulated.

    Does three things:
      1. Pushes to the per-call SSE queue (transcript drawer streaming)
      2. Broadcasts a `transcript_chunk` WS message (live feed ticker)
      3. Feeds the live-coaching engine; if it returns a nudge, broadcasts a
         `coaching_nudge` WS message so the dashboard can whisper to the RM.

    Centralizing here means the real Ringg path and the keyless simulation
    paths (radar save-calls, morning-brief standups) all get coaching for free.
    """
    q = _transcript_queues.get(call_id)
    if q:
        await q.put(text)
    await broadcast_event({"type": "transcript_chunk", "data": {"call_id": call_id, "text": text}})

    # Live coaching — best-effort, never block the transcript stream on it.
    try:
        from services import coaching_engine
        nudge = (await coaching_engine.observe(call_id, text, client_summary=client_summary)
                 if coach else None)
        if nudge is not None:
            await broadcast_event({
                "type": "coaching_nudge",
                "data": {"call_id": call_id, **nudge.as_dict()},
            })
    except Exception as e:
        logger.debug("coaching skipped for %s: %s", call_id, e)

    # Commitment detection — propose a CRM action the RM can one-click approve.
    try:
        from services import coaching_engine
        suggestion = await coaching_engine.detect_action(call_id, text)
        if suggestion is not None:
            import uuid as _uuid
            await broadcast_event({
                "type": "coaching_action_suggestion",
                "data": {"call_id": call_id, "suggestion_id": _uuid.uuid4().hex[:8],
                         **suggestion.as_dict()},
            })
    except Exception as e:
        logger.debug("action detection skipped for %s: %s", call_id, e)


# ─── WebSocket endpoint ────────────────────────────────────────────────────

@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    logger.info("WS client connected. Total: %d", len(_ws_clients))
    try:
        # Send recent briefing history on connect
        recent = sorted(database.BRIEFING_LOGS, key=lambda b: b.timestamp, reverse=True)[:5]
        await websocket.send_text(json.dumps({
            "type": "history",
            "data": [b.model_dump() for b in recent],
        }, default=str))

        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                data = {"type": msg}
            if data.get("type") == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": data.get("timestamp"),
                }))
    except WebSocketDisconnect:
        logger.info("WS client disconnected")
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


# ─── HMAC signature verification ──────────────────────────────────────────

def _verify_signature(body: bytes, header: Optional[str]) -> bool:
    """Verify Ringg HMAC-SHA256 signature. Passes when secret is dev default."""
    dev_secret = "sync-webhook-secret"
    if settings.webhook_secret == dev_secret or not settings.webhook_secret:
        return True  # dev mode: skip verification
    if not header:
        return False
    expected = "sha256=" + hmac.new(
        settings.webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)


# ─── Webhook DB helpers ────────────────────────────────────────────────────

async def _persist_event(call_id: str, event_type: str, payload: dict) -> Optional[int]:
    """Create a WebhookEvent row in received state; return its id."""
    try:
        async with get_session() as session:
            row = WebhookEvent(
                source="ringg",
                event_type=event_type,
                call_id=call_id or None,
                status="received",
                payload=payload,
                received_at=datetime.now(timezone.utc),
            )
            session.add(row)
            await session.flush()
            return row.id
    except Exception as e:
        logger.warning("Failed to persist webhook event: %s", e)
        return None


async def _update_event_status(event_id: Optional[int], status: str, error: Optional[str] = None):
    if event_id is None:
        return
    try:
        from sqlmodel import select
        async with get_session() as session:
            row = (await session.exec(
                select(WebhookEvent).where(WebhookEvent.id == event_id)
            )).first()
            if row:
                row.status = status
                row.error = error
                row.processed_at = datetime.now(timezone.utc)
                session.add(row)
    except Exception as e:
        logger.warning("Failed to update webhook event %s: %s", event_id, e)


async def _update_briefing_log(call_id: str, duration: float, latency: Optional[int],
                                recording_url: Optional[str], transcript: Optional[str]):
    """Update in-memory + DB briefing log rows."""
    # In-memory
    for log in database.BRIEFING_LOGS:
        if log.call_id == call_id:
            log.duration_seconds = duration
            if latency:
                log.latency_ms = latency
            break
    # DB
    try:
        from sqlmodel import select
        async with get_session() as session:
            row = (await session.exec(
                select(BriefingLogRow).where(BriefingLogRow.call_id == call_id)
            )).first()
            if row:
                row.duration_seconds = duration
                if latency:
                    row.latency_ms = latency
                if recording_url:
                    row.recording_url = recording_url
                if transcript:
                    row.transcript = transcript
                session.add(row)
    except Exception as e:
        logger.warning("Failed to update BriefingLogRow for %s: %s", call_id, e)


# ─── Round 2: Post-Call Intelligence ───────────────────────────────────────

async def run_post_call_analysis(
    call_id: str,
    transcript_override: Optional[str] = None,
    call_kind: str = "briefing",
    connection_id: Optional[str] = None,
    client_id: Optional[str] = None,
) -> None:
    """Analyze a completed call, store CallAnalysis, broadcast, and (for save
    calls) auto-execute the next-best-action against the CRM."""
    from sqlmodel import select
    from services.call_analysis_engine import analyze_call

    # Resolve transcript
    transcript = transcript_override
    if not transcript:
        try:
            async with get_session() as session:
                row = (await session.exec(
                    select(BriefingLogRow).where(BriefingLogRow.call_id == call_id)
                )).first()
                if row and row.transcript:
                    transcript = row.transcript
        except Exception:
            pass
    if not transcript:
        logger.info("No transcript for %s — skipping analysis", call_id)
        return

    # Resolve the linked SaveCallPlay (if this was a save call)
    play = None
    try:
        async with get_session() as session:
            play = (await session.exec(
                select(SaveCallPlay).where(SaveCallPlay.call_id == call_id)
            )).first()
    except Exception:
        pass
    if play:
        call_kind = "save_call"
        connection_id = connection_id or play.connection_id
        client_id = client_id or play.client_id

    # Resolve the client profile for richer analysis
    client = None
    if connection_id and client_id:
        try:
            from services import connection_registry
            adapter = await connection_registry.crm_for(connection_id)
            client = await adapter.get_client(client_id)
        except Exception:
            pass

    result = await analyze_call(transcript, client, call_kind)

    # Persist CallAnalysis (upsert by call_id)
    async with get_session() as session:
        existing = (await session.exec(
            select(CallAnalysis).where(CallAnalysis.call_id == call_id)
        )).first()
        target = existing or CallAnalysis(call_id=call_id)
        target.client_id = client_id
        target.connection_id = connection_id
        target.call_kind = call_kind
        target.sentiment_label = result.sentiment_label
        target.sentiment_score = result.sentiment_score
        target.sentiment_timeline = result.sentiment_timeline
        target.objections = result.objections
        target.commitments = result.commitments
        target.churn_delta = result.churn_delta
        target.churn_label = result.churn_label
        target.next_best_action = result.next_best_action
        target.summary = result.summary
        session.add(target)

    await broadcast_event({
        "type": "call_analysis_ready",
        "data": {
            "call_id": call_id,
            "client_id": client_id,
            "call_kind": call_kind,
            "sentiment_label": result.sentiment_label,
            "sentiment_score": result.sentiment_score,
            "churn_label": result.churn_label,
            "objections": result.objections,
            "commitments": result.commitments,
            "next_best_action": result.next_best_action,
            "summary": result.summary,
        },
    })

    # For save calls, auto-execute the next-best-action and finalize the play.
    if play and result.next_best_action and connection_id and client_id:
        try:
            from services.voice_command_engine import execute_command
            from datetime import date as _date
            nba = result.next_best_action
            args = dict(nba.get("args", {}))
            # Fill a sensible default date if the model left it blank
            for k in ("due_date", "when"):
                if k in args and not args[k]:
                    args[k] = _date.today().isoformat()
            action_id = await execute_command(nba.get("tool", "create_note"), args, connection_id, client_id)
            async with get_session() as session:
                a = (await session.exec(select(CallAnalysis).where(CallAnalysis.call_id == call_id))).first()
                if a:
                    a.nba_executed = True
                    a.nba_action_id = str(action_id)
                    session.add(a)
                pl = (await session.exec(select(SaveCallPlay).where(SaveCallPlay.call_id == call_id))).first()
                if pl:
                    pl.status = "completed"
                    if not pl.outcome:
                        pl.outcome = result.summary[:200]
                    session.add(pl)
            await broadcast_event({"type": "command_executed", "data": {
                "tool": nba.get("tool"), "client_id": client_id, "action_id": str(action_id), "source": "save_call_nba"}})
        except Exception as e:
            logger.warning("Auto-NBA execution failed for %s: %s", call_id, e)


# ─── Ringg webhook endpoint ────────────────────────────────────────────────

@router.post("/api/v1/webhooks/ringg")
@router.post("/v1/webhooks/ringg")
async def ringg_webhook(request: Request):
    """
    Receives Ringg webhook events and processes them asynchronously.
    Always returns 200 immediately.

    Supported event_type values:
      call_started, call_completed, platform_analysis_completed,
      all_processing_completed, transcript_chunk
    """
    raw_body = await request.body()
    sig_header = request.headers.get("X-Ringg-Signature")

    if not _verify_signature(raw_body, sig_header):
        logger.warning("Webhook signature mismatch — rejected")
        return {"status": "unauthorized"}

    try:
        body = json.loads(raw_body)
    except Exception:
        return {"status": "ok"}

    call_id = body.get("call_id", "")
    event_type = body.get("event_type", "")
    idempotency_key = f"{call_id}:{event_type}"

    if idempotency_key in _processed_events:
        return {"status": "duplicate"}
    _processed_events.add(idempotency_key)

    logger.info("Ringg webhook: %s for call %s", event_type, call_id)

    # Persist the event and start processing in the background
    event_id = await _persist_event(call_id, event_type, body)

    # Broadcast "received" to dashboard
    await broadcast_event({
        "type": "webhook_event",
        "data": {
            "id": event_id,
            "source": "ringg",
            "event_type": event_type,
            "call_id": call_id,
            "status": "received",
            "received_at": datetime.now(timezone.utc).isoformat(),
        },
    })

    # Process asynchronously
    asyncio.create_task(_process_ringg_event(event_id, call_id, event_type, body))
    return {"status": "ok"}


async def _process_ringg_event(
    event_id: Optional[int],
    call_id: str,
    event_type: str,
    body: dict,
):
    """Background task: update lifecycle + broadcast outcomes."""
    try:
        await _update_event_status(event_id, "processing")
        await broadcast_event({
            "type": "webhook_event",
            "data": {
                "id": event_id,
                "source": "ringg",
                "event_type": event_type,
                "call_id": call_id,
                "status": "processing",
                "received_at": datetime.now(timezone.utc).isoformat(),
            },
        })

        if event_type == "call_completed":
            duration = float(body.get("duration_seconds", 0))
            latency = body.get("latency_ms")
            await _update_briefing_log(call_id, duration, latency, None, None)
            matching = next((b for b in database.BRIEFING_LOGS if b.call_id == call_id), None)
            if matching:
                await broadcast_event({"type": "sync_completed", "data": matching.model_dump()})

        elif event_type == "call_started":
            await broadcast_event({"type": "call_started", "data": {"call_id": call_id}})

        elif event_type == "all_processing_completed":
            recording_url = body.get("recording_url")
            transcript = body.get("transcript")
            await _update_briefing_log(call_id, 0, None, recording_url, transcript)
            if transcript:
                await emit_transcript_chunk(call_id, transcript)
                # Call is over — drop coaching state for this call.
                try:
                    from services import coaching_engine
                    coaching_engine.end_call(call_id)
                except Exception:
                    pass
                # Round 2: kick off post-call intelligence
                asyncio.create_task(run_post_call_analysis(call_id, transcript_override=transcript))

        elif event_type == "call_transferred":
            from sqlmodel import select
            async with get_session() as session:
                pl = (await session.exec(
                    select(SaveCallPlay).where(SaveCallPlay.call_id == call_id)
                )).first()
                if pl:
                    pl.status = "transferred"
                    pl.outcome = "Warm-transferred to RM"
                    session.add(pl)
            await broadcast_event({"type": "save_call_transferred", "data": {"call_id": call_id}})

        elif event_type == "transcript_chunk":
            chunk = body.get("text", "")
            await emit_transcript_chunk(call_id, chunk)

        await _update_event_status(event_id, "processed")
        await broadcast_event({
            "type": "webhook_event",
            "data": {
                "id": event_id,
                "source": "ringg",
                "event_type": event_type,
                "call_id": call_id,
                "status": "processed",
                "received_at": datetime.now(timezone.utc).isoformat(),
            },
        })

    except Exception as e:
        logger.error("Webhook processing error for %s %s: %s", event_type, call_id, e)
        await _update_event_status(event_id, "error", str(e))
        await broadcast_event({
            "type": "webhook_event",
            "data": {
                "id": event_id,
                "source": "ringg",
                "event_type": event_type,
                "call_id": call_id,
                "status": "error",
                "received_at": datetime.now(timezone.utc).isoformat(),
            },
        })
