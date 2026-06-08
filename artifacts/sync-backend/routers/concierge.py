"""SYNC Concierge — inbound voice flow.

The RM dials a phone number. SYNC answers as a conversational concierge:
they say a client name, SYNC pulls the live profile from the active CRM
and delivers a tight briefing. Then handles follow-ups + mid-call actions
(create task, log note, etc.) via the same machinery the Morning Brief
agent uses.

  POST /api/v1/concierge/start         — bootstrap a call session (Ringg
                                          calls this from a webhook OR our
                                          backend creates it when an inbound
                                          call lands)
  POST /api/v1/concierge/{call_id}/ask — mid-call lookup tool (Ringg agent
                                          calls this when the user names a
                                          client or asks a question)
  POST /api/v1/concierge/{call_id}/act — mid-call CRM action tool
  GET  /api/v1/concierge/info           — returns the inbound number to dial
                                          + the concierge agent id for the UI
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from config import settings
from db import get_session
from db.models import MorningBriefCall, MorningBriefSchedule
from services import connection_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/concierge", tags=["concierge"])


# ──────────────────────────── Request models ─────────────────────────────

class AskIn(BaseModel):
    question: str
    client_hint: Optional[str] = None


class ActIn(BaseModel):
    intent: str
    details: str
    client_hint: Optional[str] = None


class StartIn(BaseModel):
    """Optional bootstrap if the Ringg inbound webhook hits us first."""
    rm_phone: Optional[str] = None
    rm_name: Optional[str] = None


# ──────────────────────── Concierge call registry ────────────────────────
# A lightweight in-memory map of inbound call_id → {connection_id, rm_name}.
# Survives a process restart by re-using the MorningBriefCall table with
# `schedule_id=0` as a sentinel for "this was a concierge call, no schedule".

_INBOUND_SENTINEL_SCHEDULE_ID = 0


async def _resolve_call(call_id: str) -> dict:
    """Look up an inbound call session, creating one on first reference."""
    async with get_session() as session:
        row = (await session.exec(
            select(MorningBriefCall).where(MorningBriefCall.call_id == call_id)
        )).first()
        if row:
            return {
                "schedule_id": row.schedule_id,
                "call_id": row.call_id,
                "connection_id": (row.agenda_json or {}).get("connection_id") or _default_connection_id(),
                "rm_name": (row.agenda_json or {}).get("rm_name") or "RM",
                "questions_asked": row.questions_asked or 0,
                "actions_executed": row.actions_executed or 0,
            }
        # First touch — create a sentinel row
        new = MorningBriefCall(
            schedule_id=_INBOUND_SENTINEL_SCHEDULE_ID,
            call_id=call_id,
            agenda_json={
                "kind": "concierge",
                "connection_id": _default_connection_id(),
                "rm_name": settings.demo_rm_name,
            },
            started_at=datetime.now(timezone.utc),
        )
        session.add(new)
        return {
            "schedule_id": _INBOUND_SENTINEL_SCHEDULE_ID,
            "call_id": call_id,
            "connection_id": _default_connection_id(),
            "rm_name": settings.demo_rm_name,
            "questions_asked": 0,
            "actions_executed": 0,
        }


def _default_connection_id() -> str:
    # Order of preference: live Pipedrive (the demo CRM) → sandbox.
    # In a multi-tenant world this would be tied to the RM's identity.
    if settings.pipedrive_api_token:
        return "conn_pipedrive_demo"
    return "conn_lsq_sandbox"


# ────────────────────────────── /info ─────────────────────────────────────

@router.get("/info")
async def info():
    """Tells the dashboard which phone number to display + agent details."""
    return {
        "agent_id": settings.ringg_concierge_agent_id,
        "inbound_number": settings.ringg_inbound_number or "",
        "configured": bool(settings.ringg_concierge_agent_id and settings.ringg_inbound_number),
    }


# ────────────────────────────── /start ────────────────────────────────────

@router.post("/start")
async def start(body: StartIn):
    """Manual session bootstrap (mostly for the simulated keyless demo path)."""
    import uuid
    call_id = f"sim_concierge_{uuid.uuid4().hex[:8]}"
    await _resolve_call(call_id)
    from routers.webhooks import broadcast_event
    await broadcast_event({
        "type": "concierge_call_started",
        "data": {"call_id": call_id, "rm_name": body.rm_name or settings.demo_rm_name},
    })
    return {"call_id": call_id}


# ────────────────────────── /{call_id}/ask ────────────────────────────────

@router.post("/{call_id}/ask")
async def mid_call_ask(call_id: str, body: AskIn):
    """Called by the Ringg concierge agent when the RM names a client OR
    asks a follow-up. Pulls the live client snapshot from the active CRM
    and returns a one-sentence spoken answer."""
    ctx = await _resolve_call(call_id)
    connection_id = ctx["connection_id"]
    answer = await _lookup_and_summarise(connection_id, body.client_hint or body.question)

    # Bump Q counter
    async with get_session() as session:
        row = (await session.exec(
            select(MorningBriefCall).where(MorningBriefCall.call_id == call_id)
        )).first()
        if row:
            row.questions_asked = (row.questions_asked or 0) + 1
            session.add(row)

    from routers.webhooks import broadcast_event
    await broadcast_event({
        "type": "concierge_question",
        "data": {"call_id": call_id, "question": body.question, "answer_preview": answer[:140]},
    })
    return {"answer": answer, "spoken": answer}


async def _lookup_and_summarise(connection_id: str, query: str) -> str:
    """Find the named client in the active CRM and render a 30-second briefing."""
    try:
        adapter = await connection_registry.crm_for(connection_id)
    except Exception as e:
        logger.warning("Concierge adapter resolve failed: %s", e)
        return "I'm having trouble reaching the CRM right now — try again in a moment."

    # Strip leading verbs/fillers so "tell me about Vikram" / "what about Vikram" / "Vikram" all work
    name = (query or "").strip()
    for prefix in ("tell me about ", "what about ", "give me a sync on ", "brief me on ",
                   "what's the deal with ", "anything on ", "who's ", "who is "):
        if name.lower().startswith(prefix):
            name = name[len(prefix):].strip(" ?.,")
            break

    try:
        matches = await adapter.search_client(name)
    except Exception as e:
        logger.warning("Concierge search failed: %s", e)
        matches = []
    if not matches:
        return f"I'm not finding anyone matching {name}. Try a last name or the company they're at?"

    profile = matches[0]
    try:
        full = await adapter.get_client(profile.client_id)
    except Exception:
        full = None
    if not full:
        return f"{profile.name} — couldn't pull the full profile, give me a second and try again."

    bits = []
    bits.append(f"{full.profile.name}'s risk is {full.risk.score.replace('_',' ').upper()}.")
    if full.risk.factors:
        bits.append("Main factors: " + ", ".join(full.risk.factors[:2]) + ".")
    if full.products:
        p = full.products[0]
        kind = p.product_type.replace("_", " ")
        amt_l = int(p.principal / 100000)
        bits.append(f"He's got a {kind} of {amt_l} lakhs, EMI about {int(p.emi/1000)} thousand per month.")
    open_c = [c for c in full.complaints if c.status in ("open", "escalated")]
    if open_c:
        bits.append(f"And there's an open complaint about {open_c[0].category} — don't get blindsided.")
    bits.append(f"Last contact was {full.last_rm_interaction_days_ago} days ago.")
    if full.cross_sell:
        cs = full.cross_sell[0]
        bits.append(f"The play: {cs.pitch_angle[:140]}")
    return " ".join(bits)


# ────────────────────────── /{call_id}/act ────────────────────────────────

@router.post("/{call_id}/act")
async def mid_call_act(call_id: str, body: ActIn):
    """Called by the Ringg concierge agent when the RM asks to log a note,
    create a task, schedule a follow-up, or update a field."""
    from services.voice_command_engine import parse_command, execute_command, CommandContext

    ctx = await _resolve_call(call_id)
    connection_id = ctx["connection_id"]

    # Find the client referenced — prefer the explicit hint, otherwise look in details
    target = None
    name_query = body.client_hint or ""
    if name_query:
        try:
            adapter = await connection_registry.crm_for(connection_id)
            matches = await adapter.search_client(name_query)
            if matches:
                target = matches[0]
        except Exception:
            pass

    if not target:
        return {
            "confirmation": "I couldn't tell which client that was for — could you say the name first?",
            "spoken": "I couldn't tell which client that was for — could you say the name first?",
        }

    command_ctx = CommandContext(
        active_connection_id=connection_id,
        active_client_id=target.client_id,
        active_client_name=target.name,
    )
    transcript = f"{body.intent}: {body.details}"
    parsed = await parse_command(transcript, command_ctx)

    # Make sure date fields aren't empty (the parser sometimes returns blank)
    args = dict(parsed.args)
    for k in ("due_date", "when"):
        if k in args and not args[k]:
            args[k] = date.today().isoformat()

    try:
        action_id = await execute_command(parsed.tool, args, connection_id, target.client_id)
    except Exception as e:
        logger.warning("Concierge action failed: %s", e)
        return {
            "confirmation": "I tried to log that but something went wrong on the CRM side. I'll flag it for review.",
            "spoken": "I tried to log that but something went wrong on the CRM side. I'll flag it for review.",
        }

    # Bump action counter
    async with get_session() as session:
        row = (await session.exec(
            select(MorningBriefCall).where(MorningBriefCall.call_id == call_id)
        )).first()
        if row:
            row.actions_executed = (row.actions_executed or 0) + 1
            session.add(row)

    from routers.webhooks import broadcast_event
    await broadcast_event({"type": "concierge_action_executed", "data": {
        "call_id": call_id, "tool": parsed.tool, "client_id": target.client_id,
        "client_name": target.name, "action_id": str(action_id),
    }})

    confirmation = parsed.dry_run_preview or f"Done — {parsed.tool} logged for {target.name}."
    return {"confirmation": f"Done — {confirmation}", "spoken": f"Done — {confirmation}", "action_id": str(action_id)}
