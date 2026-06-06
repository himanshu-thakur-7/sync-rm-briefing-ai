"""Voice command router — /api/v1/voice/*

Endpoints:
  POST /transcribe              — multipart audio → transcript text
  POST /commands/parse          — transcript + context → ParsedCommand
  POST /commands/execute        — tool + args + confirm → CRM action
  GET  /commands/history        — recent CommandLog rows
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from db import get_session
from db.models import CommandLog
from services.voice_command_engine import (
    CommandContext, parse_command, execute_command, transcribe,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/voice", tags=["voice-commands"])


# ─── Request / response models ─────────────────────────────────────────────

class TranscribeResponse(BaseModel):
    transcript: str
    confidence: Optional[float] = None


class ParseRequest(BaseModel):
    transcript: str
    context: dict = {}


class ParseResponse(BaseModel):
    tool: str
    args: dict
    confirmation_required: bool
    dry_run_preview: str


class ExecuteRequest(BaseModel):
    tool: str
    args: dict
    confirm: bool = False
    connection_id: str = ""
    client_id: Optional[str] = None


class ExecuteResponse(BaseModel):
    status: str
    action_id: Optional[str] = None
    tool: str
    error: Optional[str] = None


# ─── Transcription ─────────────────────────────────────────────────────────

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(audio: UploadFile = File(...)):
    """Accept multipart audio file, return transcript text via Whisper."""
    try:
        audio_bytes = await audio.read()
        text = await transcribe(audio_bytes, audio.content_type or "audio/webm")
        return TranscribeResponse(transcript=text)
    except Exception as e:
        raise HTTPException(502, f"Transcription failed: {e}")


# ─── Parse ─────────────────────────────────────────────────────────────────

@router.post("/commands/parse", response_model=ParseResponse)
async def parse_voice_command(body: ParseRequest):
    """Parse a transcript into a CRM tool call using GPT-4o function calling."""
    ctx_data = body.context
    ctx = CommandContext(
        active_connection_id=ctx_data.get("active_connection_id", ""),
        active_client_id=ctx_data.get("active_client_id"),
        active_client_name=ctx_data.get("active_client_name"),
        rm_name=ctx_data.get("rm_name"),
        recent_briefing_summary=ctx_data.get("recent_briefing_summary"),
    )
    # Enrich with client name if not provided but client_id is
    if ctx.active_client_id and not ctx.active_client_name and ctx.active_connection_id:
        try:
            from services import connection_registry
            adapter = await connection_registry.crm_for(ctx.active_connection_id)
            client = await adapter.get_client(ctx.active_client_id)
            if client:
                ctx.active_client_name = client.profile.name
        except Exception:
            pass

    cmd = await parse_command(body.transcript, ctx)
    return ParseResponse(
        tool=cmd.tool,
        args=cmd.args,
        confirmation_required=cmd.confirmation_required,
        dry_run_preview=cmd.dry_run_preview,
    )


# ─── Execute ───────────────────────────────────────────────────────────────

@router.post("/commands/execute", response_model=ExecuteResponse)
async def execute_voice_command(body: ExecuteRequest):
    """Execute a confirmed CRM action and log to CommandLog."""
    if not body.confirm:
        raise HTTPException(400, "Set confirm=true to execute the command")

    connection_id = body.args.pop("connection_id", None) or body.connection_id or ""
    client_id = body.args.pop("client_id", None) or body.client_id

    # Persist to CommandLog
    log_row = CommandLog(
        connection_id=connection_id,
        client_id=client_id,
        raw_transcript="",  # transcript stored on parse, not here
        parsed_tool=body.tool,
        parsed_args=body.args,
        status="executing",
        created_at=datetime.now(timezone.utc),
    )
    async with get_session() as session:
        session.add(log_row)
        await session.flush()
        log_id = log_row.id

    try:
        action_id = await execute_command(body.tool, body.args, connection_id, client_id)

        # Update log
        async with get_session() as session:
            from sqlmodel import select
            row = (await session.exec(select(CommandLog).where(CommandLog.id == log_id))).first()
            if row:
                row.status = "executed"
                row.action_id_in_crm = str(action_id) if action_id else None
                row.executed_at = datetime.now(timezone.utc)
                session.add(row)

        # Broadcast WS
        from routers.webhooks import broadcast_event
        await broadcast_event({
            "type": "command_executed",
            "data": {
                "tool": body.tool,
                "client_id": client_id,
                "connection_id": connection_id,
                "action_id": str(action_id) if action_id else None,
            },
        })

        return ExecuteResponse(status="executed", action_id=str(action_id) if action_id else None, tool=body.tool)

    except Exception as e:
        logger.error("Command execution failed: %s", e)
        async with get_session() as session:
            from sqlmodel import select
            row = (await session.exec(select(CommandLog).where(CommandLog.id == log_id))).first()
            if row:
                row.status = "failed"
                row.error = str(e)[:500]
                session.add(row)

        from routers.webhooks import broadcast_event
        await broadcast_event({"type": "command_failed", "data": {"tool": body.tool, "error": str(e)}})

        return ExecuteResponse(status="failed", tool=body.tool, error=str(e))


# ─── History ───────────────────────────────────────────────────────────────

@router.get("/commands/history")
async def command_history(
    client_id: Optional[str] = None,
    limit: int = 50,
):
    """Return recent voice command log entries."""
    from sqlmodel import select
    async with get_session() as session:
        q = select(CommandLog).order_by(CommandLog.created_at.desc()).limit(limit)
        if client_id:
            q = q.where(CommandLog.client_id == client_id)
        rows = list((await session.exec(q)).all())
    return [
        {
            "id": r.id,
            "client_id": r.client_id,
            "connection_id": r.connection_id,
            "parsed_tool": r.parsed_tool,
            "status": r.status,
            "error": r.error,
            "action_id": r.action_id_in_crm,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "executed_at": r.executed_at.isoformat() if r.executed_at else None,
        }
        for r in rows
    ]
