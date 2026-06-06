import json
import logging
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from models import RinggWebhookPayload
import database

router = APIRouter(tags=["webhooks"])
logger = logging.getLogger(__name__)

# Active WebSocket connections
_ws_clients: list[WebSocket] = []

# Idempotency: track processed event keys
_processed_events: set[str] = set()


async def broadcast_event(event: dict) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    disconnected = []
    for ws in _ws_clients:
        try:
            await ws.send_text(json.dumps(event))
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _ws_clients.remove(ws)


@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await websocket.accept()
    _ws_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(_ws_clients)}")
    try:
        # Send recent history on connect
        recent = sorted(database.BRIEFING_LOGS, key=lambda b: b.timestamp, reverse=True)[:5]
        await websocket.send_text(json.dumps({
            "type": "history",
            "data": [b.model_dump() for b in recent],
        }))
        # Keep alive — receive ping/pong
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


@router.post("/v1/webhooks/ringg")
async def ringg_webhook(request: Request):
    """
    Ringg webhook receiver.
    Events: call_started, call_completed, platform_analysis_completed, all_processing_completed
    Always returns 200 quickly — processing is async.
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "ok"}

    call_id = body.get("call_id", "")
    event_type = body.get("event_type", "")
    idempotency_key = f"{call_id}:{event_type}"

    if idempotency_key in _processed_events:
        return {"status": "duplicate"}
    _processed_events.add(idempotency_key)

    logger.info(f"Ringg webhook: {event_type} for call {call_id}")

    if event_type == "call_completed":
        duration = float(body.get("duration_seconds", 0))
        latency = body.get("latency_ms")

        # Update matching briefing log
        for log in database.BRIEFING_LOGS:
            if log.call_id == call_id:
                log.duration_seconds = duration
                if latency:
                    log.latency_ms = int(latency)
                break

        matching = next((b for b in database.BRIEFING_LOGS if b.call_id == call_id), None)
        if matching:
            await broadcast_event({
                "type": "sync_completed",
                "data": matching.model_dump(),
            })

    elif event_type == "call_started":
        await broadcast_event({
            "type": "call_started",
            "data": {"call_id": call_id},
        })

    return {"status": "ok"}
