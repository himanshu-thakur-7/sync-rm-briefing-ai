"""Daily Standup — schedule CRUD + conversational mid-call endpoints.

  POST   /api/v1/morning-brief/schedules           create + register scheduler task
  GET    /api/v1/morning-brief/schedules           list
  PATCH  /api/v1/morning-brief/schedules/{id}      update + re-register
  DELETE /api/v1/morning-brief/schedules/{id}      soft-delete (enabled=false)
  POST   /api/v1/morning-brief/schedules/{id}/trigger   manual fire now (demo)
  GET    /api/v1/morning-brief/calls?schedule_id=&limit=   history

  Mid-call (called BY the Ringg conversational agent during a live call):
  POST   /api/v1/morning-brief/{call_id}/ask       answer a question from the agenda + CRM
  POST   /api/v1/morning-brief/{call_id}/act       execute a CRM action via voice_command_engine
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select

from config import settings
from db import get_session
from db.models import MorningBriefCall, MorningBriefSchedule
from services import connection_registry, morning_brief_engine, morning_brief_scheduler
from services.ringg_service import ringg_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/morning-brief", tags=["morning-brief"])


# ─────────────────────────────── models ───────────────────────────────────

class ScheduleIn(BaseModel):
    rm_name: str
    rm_phone: str
    connection_id: str
    hour_local: int = 7
    minute_local: int = 45
    weekday_mask: int = 31
    timezone: str = "Asia/Kolkata"
    company_name: str = "Acme"
    language_style: str = "english_only"
    enabled: bool = True


class ScheduleOut(BaseModel):
    id: int
    rm_name: str
    rm_phone: str
    connection_id: str
    hour_local: int
    minute_local: int
    weekday_mask: int
    timezone: str
    company_name: str
    language_style: str
    enabled: bool
    last_called_at: Optional[str] = None
    next_call_at: Optional[str] = None


class ScheduleUpdate(BaseModel):
    rm_name: Optional[str] = None
    rm_phone: Optional[str] = None
    hour_local: Optional[int] = None
    minute_local: Optional[int] = None
    weekday_mask: Optional[int] = None
    timezone: Optional[str] = None
    company_name: Optional[str] = None
    language_style: Optional[str] = None
    enabled: Optional[bool] = None


class AskIn(BaseModel):
    question: str
    client_hint: Optional[str] = None  # the agent may pass a name hint


class ActIn(BaseModel):
    intent: str            # short phrase like "create_task" or "log_note"
    details: str           # natural-language details ("follow-up call thursday at 4")
    client_hint: Optional[str] = None


def _to_out(s: MorningBriefSchedule) -> ScheduleOut:
    return ScheduleOut(
        id=s.id, rm_name=s.rm_name, rm_phone=s.rm_phone, connection_id=s.connection_id,
        hour_local=s.hour_local, minute_local=s.minute_local, weekday_mask=s.weekday_mask,
        timezone=s.timezone, company_name=s.company_name, language_style=s.language_style,
        enabled=s.enabled,
        last_called_at=s.last_called_at.isoformat() if s.last_called_at else None,
        next_call_at=s.next_call_at.isoformat() if s.next_call_at else None,
    )


# ─────────────────────────────── CRUD ─────────────────────────────────────

@router.post("/schedules", response_model=ScheduleOut)
async def create_schedule(body: ScheduleIn):
    now_utc = datetime.now(timezone.utc)
    next_at = morning_brief_scheduler.compute_next_fire(
        body.hour_local, body.minute_local, body.weekday_mask, body.timezone, now_utc,
    ) if body.enabled else None

    async with get_session() as session:
        row = MorningBriefSchedule(
            rm_name=body.rm_name, rm_phone=body.rm_phone,
            connection_id=body.connection_id,
            hour_local=body.hour_local, minute_local=body.minute_local,
            weekday_mask=body.weekday_mask, timezone=body.timezone,
            company_name=body.company_name, language_style=body.language_style,
            enabled=body.enabled, next_call_at=next_at, created_at=now_utc,
        )
        session.add(row)
        await session.flush()
        sid = row.id
        out = _to_out(row)

    if body.enabled:
        morning_brief_scheduler.register(sid)

    from routers.webhooks import broadcast_event
    await broadcast_event({"type": "morning_brief_scheduled", "data": {"id": sid, "next_call_at": out.next_call_at}})
    return out


@router.get("/schedules", response_model=list[ScheduleOut])
async def list_schedules():
    async with get_session() as session:
        rows = list((await session.exec(select(MorningBriefSchedule).order_by(MorningBriefSchedule.id))).all())
    return [_to_out(r) for r in rows]


@router.patch("/schedules/{schedule_id}", response_model=ScheduleOut)
async def update_schedule(schedule_id: int, body: ScheduleUpdate):
    async with get_session() as session:
        row = (await session.exec(select(MorningBriefSchedule).where(MorningBriefSchedule.id == schedule_id))).first()
        if not row:
            raise HTTPException(404, f"Schedule {schedule_id} not found")
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        if row.enabled:
            row.next_call_at = morning_brief_scheduler.compute_next_fire(
                row.hour_local, row.minute_local, row.weekday_mask, row.timezone,
            )
        session.add(row)
        out = _to_out(row)

    if row.enabled:
        morning_brief_scheduler.register(schedule_id)
    else:
        morning_brief_scheduler.unregister(schedule_id)
    return out


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: int):
    async with get_session() as session:
        row = (await session.exec(select(MorningBriefSchedule).where(MorningBriefSchedule.id == schedule_id))).first()
        if not row:
            raise HTTPException(404, f"Schedule {schedule_id} not found")
        row.enabled = False
        session.add(row)
    morning_brief_scheduler.unregister(schedule_id)
    return {"status": "disabled", "id": schedule_id}


@router.post("/schedules/{schedule_id}/trigger")
async def trigger_now(schedule_id: int):
    """Demo button — fire the standup call right now."""
    call_id = await place_morning_brief_call(schedule_id, source="manual_trigger")
    return {"status": "calling", "call_id": call_id}


@router.get("/calls")
async def list_calls(schedule_id: Optional[int] = Query(default=None), limit: int = 20):
    async with get_session() as session:
        q = select(MorningBriefCall).order_by(MorningBriefCall.started_at.desc()).limit(limit)
        if schedule_id is not None:
            q = q.where(MorningBriefCall.schedule_id == schedule_id)
        rows = list((await session.exec(q)).all())
    return [
        {
            "id": r.id, "schedule_id": r.schedule_id, "call_id": r.call_id,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "ended_at": r.ended_at.isoformat() if r.ended_at else None,
            "questions_asked": r.questions_asked,
            "actions_executed": r.actions_executed,
            "summary": r.summary,
        }
        for r in rows
    ]


# ─────────────────────────────── place call ───────────────────────────────

async def place_morning_brief_call(schedule_id: int, source: str = "scheduler") -> str:
    """Assemble agenda → place outbound Ringg call → persist MorningBriefCall."""
    async with get_session() as session:
        sched = (await session.exec(select(MorningBriefSchedule).where(MorningBriefSchedule.id == schedule_id))).first()
        if not sched:
            raise HTTPException(404, f"Schedule {schedule_id} not found")
        connection_id = sched.connection_id
        rm_name = sched.rm_name
        rm_phone = sched.rm_phone
        company_name = sched.company_name
        language_style = sched.language_style

    agenda = await morning_brief_engine.assemble_agenda(connection_id, rm_name)

    # Demo safety: if the agenda is empty (e.g. first run, no radar scan yet),
    # auto-scan + seed a few flagged plays so the standup has substance.
    if agenda.total == 0:
        try:
            from services import risk_radar
            from db.models import SaveCallPlay
            scan = await risk_radar.scan(connection_id)
            if scan:
                async with get_session() as session:
                    for d in scan[:3]:
                        session.add(SaveCallPlay(
                            connection_id=connection_id, client_id=d.client_id,
                            client_name=d.client_name, trigger_type=d.trigger_type,
                            urgency=d.urgency, objective=d.objective,
                            talking_points=d.talking_points, rationale=d.rationale,
                            matched_triggers=d.matched_triggers, status="queued",
                            created_at=datetime.now(timezone.utc),
                        ))
                # Re-assemble after seeding
                agenda = await morning_brief_engine.assemble_agenda(connection_id, rm_name)
        except Exception as e:
            logger.warning("Auto radar seed failed: %s", e)

    custom_args = await morning_brief_engine.generate_brief_payload(
        agenda, language_style=language_style, company_name=company_name,
    )

    backend = settings.backend_url.rstrip("/")
    callback_url = f"{backend}/api/v1/webhooks/ringg"

    try:
        call_id = await ringg_service.initiate_morning_brief_call(
            brief_agent_id=settings.ringg_morning_brief_agent_id or settings.ringg_agent_id,
            from_number_id=settings.ringg_from_number_id,
            rm_phone=rm_phone, rm_name=rm_name,
            custom_args=custom_args,
            callback_url=callback_url,
            # Mid-call tool URL prefix; the agent's functions append /{call_id}/ask or /act
            mid_call_tool_url=f"{backend}/api/v1/morning-brief",
        )
    except Exception as e:
        logger.error("Morning brief call placement failed: %s", e)
        import uuid
        call_id = f"sim_brief_{uuid.uuid4().hex[:8]}"

    # Persist the call row
    now_utc = datetime.now(timezone.utc)
    async with get_session() as session:
        row = MorningBriefCall(
            schedule_id=schedule_id, call_id=call_id,
            agenda_json={
                "headline": agenda.headline, "for_date": agenda.for_date,
                "meetings": [it.__dict__ for it in agenda.meetings],
                "flagged": [it.__dict__ for it in agenda.flagged],
                "commitments": [it.__dict__ for it in agenda.commitments],
                "tasks": [it.__dict__ for it in agenda.tasks],
            },
            started_at=now_utc,
        )
        session.add(row)

    from routers.webhooks import broadcast_event
    await broadcast_event({
        "type": "morning_brief_started",
        "data": {"schedule_id": schedule_id, "call_id": call_id, "rm_name": rm_name,
                 "headline": agenda.headline, "source": source},
    })

    # Keyless / sim path: stream a scripted 2-way standup conversation
    if not settings.ringg_api_key or call_id.startswith(("demo_brief_", "sim_brief_")):
        asyncio.create_task(_simulate_standup(schedule_id, call_id, connection_id, agenda, custom_args, rm_name))

    return call_id


async def _simulate_standup(schedule_id, call_id, connection_id, agenda, custom_args, rm_name):
    """Stream a believable 2-way standup conversation: SYNC briefs → RM asks →
    SYNC answers (via /ask) → RM asks for action → SYNC executes (via /act)."""
    from routers.webhooks import broadcast_event, emit_transcript_chunk, run_post_call_analysis

    first = rm_name.split()[0] if rm_name else "there"
    lines = [
        f"SYNC: {custom_args.get('opening_line', f'Good morning {first}.')}",
        f"{first}: Yeah, go ahead.",
    ]

    if agenda.meetings:
        m = agenda.meetings[0]
        lines.append(f"SYNC: First meeting today — {m.client_name}. {m.summary[:100]}.")
    elif agenda.flagged:
        f = agenda.flagged[0]
        lines.append(f"SYNC: Top of the watchlist — {f.client_name}. {f.summary[:100]}.")

    # Always include a flagged client mention so the Q&A makes sense
    target = (agenda.flagged[0] if agenda.flagged else agenda.meetings[0] if agenda.meetings else None)
    if target:
        lines.append(f"SYNC: SYNC flagged {target.client_name} overnight — {target.summary[:120]}.")
        lines.append(f"{first}: Tell me more about {target.client_name.split()[0]}'s situation.")

        # RM-side question → simulated /ask call
        try:
            answer = await _answer_question(call_id, target.client_name, connection_id, agenda)
        except Exception as e:
            logger.warning("Sim /ask failed: %s", e)
            answer = "I don't have more on that yet."
        lines.append(f"SYNC: {answer}")

        # RM asks for an action → simulated /act call
        lines.append(f"{first}: Create a follow-up task with {target.client_name.split()[0]} for tomorrow at 10 AM.")
        try:
            confirmation = await _execute_intent(
                call_id, intent="create_task",
                details=f"follow-up call with {target.client_name} tomorrow at 10 AM",
                connection_id=connection_id, agenda=agenda,
            )
        except Exception as e:
            logger.warning("Sim /act failed: %s", e)
            confirmation = "Logged."
        lines.append(f"SYNC: {confirmation}")

    lines.append(f"SYNC: {custom_args.get('closer', 'Have a great day.')}")

    # Stream line-by-line at ~1s pacing
    full = []
    for ln in lines:
        full.append(ln)
        await emit_transcript_chunk(call_id, ln, client_summary=f"Morning standup for {rm_name}")
        await asyncio.sleep(1.0)
    try:
        from services import coaching_engine
        coaching_engine.end_call(call_id)
    except Exception:
        pass

    # Finalize MorningBriefCall row
    transcript = "\n".join(full)
    async with get_session() as session:
        row = (await session.exec(select(MorningBriefCall).where(MorningBriefCall.call_id == call_id))).first()
        if row:
            row.ended_at = datetime.now(timezone.utc)
            row.summary = f"Standup with {first}: {len(agenda.meetings)} meetings, {len(agenda.flagged)} flagged."
            session.add(row)

    await broadcast_event({"type": "morning_brief_completed", "data": {"call_id": call_id, "schedule_id": schedule_id}})

    # Run post-call analysis on the transcript (existing pipeline)
    try:
        await run_post_call_analysis(
            call_id, transcript_override=transcript, call_kind="morning_brief",
            connection_id=connection_id, client_id=None,
        )
    except Exception as e:
        logger.warning("Morning brief analysis failed: %s", e)


# ─────────────────────────────── mid-call /ask ────────────────────────────

async def _answer_question(
    call_id: str, client_hint: Optional[str], connection_id: str, agenda
) -> str:
    """Answer a question grounded in the agenda + a fresh CRM lookup if a
    client name is hinted."""
    name_hint = (client_hint or "").lower()
    candidate = None
    for it in (agenda.flagged + agenda.meetings + agenda.commitments + agenda.tasks):
        if it.client_name and name_hint and it.client_name.split()[0].lower() in name_hint:
            candidate = it
            break
    if not candidate and (agenda.flagged or agenda.meetings):
        candidate = (agenda.flagged or agenda.meetings)[0]

    client_summary = ""
    if candidate:
        try:
            adapter = await connection_registry.crm_for(connection_id)
            full = await adapter.get_client(candidate.client_id)
            if full:
                factors = ", ".join(full.risk.factors[:2]) if full.risk.factors else "no flagged factors"
                prod = full.products[0] if full.products else None
                prod_str = f"{prod.product_type.replace('_',' ')} ₹{int(prod.principal/100000)}L" if prod else "no active product"
                open_comp = next((c for c in full.complaints if c.status in ("open", "escalated")), None)
                comp_str = f"open complaint about {open_comp.category}" if open_comp else "no open complaints"
                client_summary = (
                    f"{full.profile.name} is {full.risk.score.replace('_', ' ')} risk — {factors}. "
                    f"Holds {prod_str}; {comp_str}. Last RM contact {full.last_rm_interaction_days_ago} days ago."
                )
        except Exception as e:
            logger.warning("Mid-call CRM lookup failed: %s", e)

    # Increment Q counter on the call row
    async with get_session() as session:
        row = (await session.exec(select(MorningBriefCall).where(MorningBriefCall.call_id == call_id))).first()
        if row:
            row.questions_asked = (row.questions_asked or 0) + 1
            session.add(row)

    # GPT-4o for natural phrasing if a key is present; otherwise the deterministic summary
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key or not client_summary:
        return client_summary or "I don't have more on that yet."
    try:
        from openai import AsyncOpenAI
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL") or "https://api.openai.com/v1"
        oc = AsyncOpenAI(api_key=openai_key, base_url=base_url)
        resp = await oc.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Re-phrase the following client snapshot into a single warm sentence a voice agent will speak. No filler. Keep it under 35 words."},
                {"role": "user", "content": client_summary},
            ],
            max_tokens=80, temperature=0.5,
        )
        return resp.choices[0].message.content.strip().strip('"')
    except Exception:
        return client_summary


@router.post("/{call_id}/ask")
async def mid_call_ask(call_id: str, body: AskIn):
    """Called by the Ringg agent mid-call. Returns text the agent speaks."""
    # Find the schedule + agenda for this call
    async with get_session() as session:
        row = (await session.exec(select(MorningBriefCall).where(MorningBriefCall.call_id == call_id))).first()
        if not row:
            raise HTTPException(404, "Call not found")
        sched = (await session.exec(select(MorningBriefSchedule).where(MorningBriefSchedule.id == row.schedule_id))).first()
        if not sched:
            raise HTTPException(404, "Schedule not found")
        agenda_json = row.agenda_json or {}

    # Rehydrate a thin Agenda-shaped object from the persisted JSON
    from services.morning_brief_engine import Agenda, AgendaItem
    agenda = Agenda(rm_name=sched.rm_name, for_date=agenda_json.get("for_date", ""),
                    meetings=[AgendaItem(**it) for it in agenda_json.get("meetings", [])],
                    flagged=[AgendaItem(**it) for it in agenda_json.get("flagged", [])],
                    commitments=[AgendaItem(**it) for it in agenda_json.get("commitments", [])],
                    tasks=[AgendaItem(**it) for it in agenda_json.get("tasks", [])],
                    headline=agenda_json.get("headline", ""))

    hint = body.client_hint or body.question
    answer = await _answer_question(call_id, hint, sched.connection_id, agenda)
    return {"answer": answer, "spoken": answer}


# ─────────────────────────────── mid-call /act ────────────────────────────

async def _execute_intent(
    call_id: str, intent: str, details: str, connection_id: str, agenda
) -> str:
    """Parse a natural-language intent into a CRM tool call and execute."""
    from services.voice_command_engine import parse_command, execute_command, CommandContext

    # Try to find a client mention in the details
    target_client = None
    name_blob = details.lower()
    for it in (agenda.flagged + agenda.meetings + agenda.commitments + agenda.tasks):
        if it.client_name and it.client_name.split()[0].lower() in name_blob:
            target_client = it
            break
    if not target_client and (agenda.flagged or agenda.meetings):
        target_client = (agenda.flagged or agenda.meetings)[0]

    if not target_client:
        return "I couldn't tell which client that was for — could you say the name?"

    ctx = CommandContext(
        active_connection_id=connection_id,
        active_client_id=target_client.client_id,
        active_client_name=target_client.client_name,
    )
    transcript = f"{intent}: {details}"
    parsed = await parse_command(transcript, ctx)

    # Resolve any blank date with today's date so the call doesn't fail
    args = dict(parsed.args)
    for k in ("due_date", "when"):
        if k in args and not args[k]:
            args[k] = date.today().isoformat()

    try:
        action_id = await execute_command(parsed.tool, args, connection_id, target_client.client_id)
    except Exception as e:
        logger.warning("Mid-call action failed: %s", e)
        return "I tried to log that but something went wrong — I'll flag it for review."

    # Increment action counter
    async with get_session() as session:
        row = (await session.exec(select(MorningBriefCall).where(MorningBriefCall.call_id == call_id))).first()
        if row:
            row.actions_executed = (row.actions_executed or 0) + 1
            session.add(row)

    from routers.webhooks import broadcast_event
    await broadcast_event({"type": "morning_brief_action_executed", "data": {
        "call_id": call_id, "tool": parsed.tool, "client_id": target_client.client_id,
        "action_id": str(action_id),
    }})

    confirmation = parsed.dry_run_preview or f"Done — {parsed.tool} logged for {target_client.client_name}."
    return f"Done — {confirmation}"


@router.post("/{call_id}/act")
async def mid_call_act(call_id: str, body: ActIn):
    """Called by the Ringg agent mid-call when the RM asks for a CRM action."""
    async with get_session() as session:
        row = (await session.exec(select(MorningBriefCall).where(MorningBriefCall.call_id == call_id))).first()
        if not row:
            raise HTTPException(404, "Call not found")
        sched = (await session.exec(select(MorningBriefSchedule).where(MorningBriefSchedule.id == row.schedule_id))).first()
        if not sched:
            raise HTTPException(404, "Schedule not found")
        agenda_json = row.agenda_json or {}

    from services.morning_brief_engine import Agenda, AgendaItem
    agenda = Agenda(rm_name=sched.rm_name, for_date=agenda_json.get("for_date", ""),
                    meetings=[AgendaItem(**it) for it in agenda_json.get("meetings", [])],
                    flagged=[AgendaItem(**it) for it in agenda_json.get("flagged", [])],
                    commitments=[AgendaItem(**it) for it in agenda_json.get("commitments", [])],
                    tasks=[AgendaItem(**it) for it in agenda_json.get("tasks", [])],
                    headline=agenda_json.get("headline", ""))

    details = body.details if body.details else f"{body.intent} for {body.client_hint or 'today'}"
    confirmation = await _execute_intent(call_id, body.intent, details, sched.connection_id, agenda)
    return {"confirmation": confirmation, "spoken": confirmation}
