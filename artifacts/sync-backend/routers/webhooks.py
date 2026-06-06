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
from db.models import BriefingLogRow, WebhookEvent

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
                q = _transcript_queues.get(call_id)
                if q:
                    await q.put(transcript)
                await broadcast_event({
                    "type": "transcript_chunk",
                    "data": {"call_id": call_id, "text": transcript},
                })

        elif event_type == "transcript_chunk":
            chunk = body.get("text", "")
            q = _transcript_queues.get(call_id)
            if q:
                await q.put(chunk)
            await broadcast_event({
                "type": "transcript_chunk",
                "data": {"call_id": call_id, "text": chunk},
            })

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
