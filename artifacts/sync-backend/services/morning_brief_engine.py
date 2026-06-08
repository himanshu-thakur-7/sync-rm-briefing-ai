"""Daily-Standup agenda assembler + payload generator.

`assemble_agenda` aggregates today's relevant context across:
  - upcoming/recent CRM interactions (for the client book)
  - queued Risk Radar plays (overnight flags)
  - recent CallAnalysis commitments coming due today/tomorrow

`generate_brief_payload` turns that agenda into custom_args for the
conversational Ringg agent, honouring the per-RM language style.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlmodel import select

from db import get_session
from db.models import CallAnalysis, SaveCallPlay
from models import ClientProfile

logger = logging.getLogger(__name__)

MAX_CLIENTS_FANNED = 12  # cap to keep agenda assembly fast


@dataclass
class AgendaItem:
    kind: str  # meeting | task | flag | commitment
    when: str  # ISO datetime or human-readable
    client_id: str
    client_name: str
    summary: str
    urgency: str = "MEDIUM"


@dataclass
class Agenda:
    rm_name: str
    for_date: str  # ISO
    meetings: list[AgendaItem] = field(default_factory=list)
    tasks: list[AgendaItem] = field(default_factory=list)
    flagged: list[AgendaItem] = field(default_factory=list)  # Risk Radar plays
    commitments: list[AgendaItem] = field(default_factory=list)
    headline: str = ""

    @property
    def total(self) -> int:
        return len(self.meetings) + len(self.tasks) + len(self.flagged) + len(self.commitments)


# ─────────────────────────────── assembly ─────────────────────────────────

async def _gather_interactions(adapter, profiles: list[ClientProfile]) -> list[tuple[ClientProfile, list, list, int]]:
    """Fan out get_interactions concurrently across (capped) profiles."""
    sem = asyncio.Semaphore(6)

    async def one(p: ClientProfile):
        async with sem:
            try:
                ix, comps, days = await adapter.get_interactions(p.client_id)
                return (p, ix, comps, days)
            except Exception:
                return (p, [], [], 0)

    return await asyncio.gather(*[one(p) for p in profiles[:MAX_CLIENTS_FANNED]])


async def assemble_agenda(
    connection_id: str,
    rm_name: str,
    for_date: Optional[date] = None,
) -> Agenda:
    """Build today's agenda from CRM interactions + Radar + analyses."""
    from services import connection_registry

    target_day = for_date or date.today()
    agenda = Agenda(rm_name=rm_name, for_date=target_day.isoformat())

    adapter = await connection_registry.crm_for(connection_id)
    profiles = await adapter.list_all()

    # Pull interactions (recent + upcoming dates near today)
    triples = await _gather_interactions(adapter, profiles)
    horizon_start = target_day - timedelta(days=1)
    horizon_end = target_day + timedelta(days=2)
    for prof, ix, comps, _days in triples:
        for inter in ix:
            try:
                d = datetime.strptime(inter.date[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            if not (horizon_start <= d <= horizon_end):
                continue
            kind = "meeting" if d >= target_day else "task"
            agenda_kind_list = agenda.meetings if kind == "meeting" else agenda.tasks
            agenda_kind_list.append(AgendaItem(
                kind=kind, when=d.isoformat(),
                client_id=prof.client_id, client_name=prof.name,
                summary=inter.summary[:160],
                urgency="HIGH" if any(c.status == "open" for c in comps) else "MEDIUM",
            ))

    # Risk Radar plays (queued — overnight flags)
    try:
        async with get_session() as session:
            plays = list((await session.exec(
                select(SaveCallPlay)
                .where(SaveCallPlay.connection_id == connection_id)
                .where(SaveCallPlay.status == "queued")
            )).all())
        for p in plays:
            agenda.flagged.append(AgendaItem(
                kind="flag", when="today", client_id=p.client_id,
                client_name=p.client_name, summary=p.objective, urgency=p.urgency,
            ))
    except Exception as e:
        logger.warning("Radar plays fetch failed: %s", e)

    # Commitments coming due today/tomorrow from recent post-call analyses
    try:
        async with get_session() as session:
            recent = list((await session.exec(
                select(CallAnalysis).where(CallAnalysis.connection_id == connection_id)
            )).all())
        for an in recent:
            for cm in (an.commitments or []):
                due = cm.get("due") if isinstance(cm, dict) else None
                if due:
                    try:
                        d = datetime.strptime(due[:10], "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    if target_day <= d <= target_day + timedelta(days=1):
                        agenda.commitments.append(AgendaItem(
                            kind="commitment", when=d.isoformat(),
                            client_id=an.client_id or "",
                            client_name=cm.get("client_name", "(client)"),
                            summary=cm.get("text", ""),
                        ))
                else:
                    # Undated commitments from yesterday — still surface
                    if (an.created_at and an.created_at.date() == target_day - timedelta(days=1)):
                        agenda.commitments.append(AgendaItem(
                            kind="commitment", when="due soon",
                            client_id=an.client_id or "",
                            client_name=cm.get("client_name", "(client)"),
                            summary=cm.get("text", ""),
                        ))
    except Exception as e:
        logger.warning("Commitments scan failed: %s", e)

    agenda.headline = _headline(agenda)
    return agenda


def _headline(a: Agenda) -> str:
    bits = []
    if a.meetings:
        bits.append(f"{len(a.meetings)} meeting{'s' if len(a.meetings) != 1 else ''} today")
    if a.flagged:
        crit = sum(1 for f in a.flagged if f.urgency == "CRITICAL")
        bits.append(f"{len(a.flagged)} thing{'s' if len(a.flagged) != 1 else ''} SYNC flagged overnight"
                    + (f" ({crit} critical)" if crit else ""))
    if a.commitments:
        bits.append(f"{len(a.commitments)} commitment{'s' if len(a.commitments) != 1 else ''} coming due")
    return " · ".join(bits) if bits else "A quiet day on the book."


# ─────────────────────────────── payload ──────────────────────────────────

def _format_list(items: list[AgendaItem], max_n: int = 5) -> str:
    """Render an agenda section as a short, readable string for the agent."""
    if not items:
        return "(none)"
    lines = []
    for it in items[:max_n]:
        when = it.when if it.when not in ("today", "due soon") else it.when
        lines.append(f"- {when}: {it.client_name} — {it.summary[:120]}")
    if len(items) > max_n:
        lines.append(f"- (+ {len(items) - max_n} more)")
    return "\n".join(lines)


def _template_payload(agenda: Agenda, language_style: str, company_name: str) -> dict:
    first = agenda.rm_name.split()[0] if agenda.rm_name else "there"
    # Default language style is english_only; "auto" mirrors the RM's tone.
    opening = (
        f"Good morning {first} — "
        f"{agenda.headline.lower() if agenda.headline else 'a quiet day on your book today'}."
        " Ready for the rundown?"
    )
    closer = "That's it for today. Have a great one."
    return {
        "rm_name": agenda.rm_name,
        "company_name": company_name,
        "language_style": language_style,
        "opening_line": opening,
        "agenda_summary": agenda.headline or "A light day.",
        "meeting_list": _format_list(agenda.meetings),
        "flagged_list": _format_list(agenda.flagged),
        "commitments_list": _format_list(agenda.commitments),
        "tasks_list": _format_list(agenda.tasks),
        "closer": closer,
    }


async def generate_brief_payload(
    agenda: Agenda,
    language_style: str = "english_only",
    company_name: str = "Acme",
) -> dict:
    """Produce custom_args for the conversational Morning Brief Ringg agent.

    Uses GPT-4o to humanise the opening_line if a key is configured;
    falls back to a clean deterministic template otherwise.
    """
    template = _template_payload(agenda, language_style, company_name)

    # Back-compat: morning-brief agents created before R4-A still declare
    # `hinglish_closer` in custom_vars. Mirror the closer value into it so
    # Ringg's required-variables check passes for both old + new agents.
    if "closer" in template and "hinglish_closer" not in template:
        template["hinglish_closer"] = template["closer"]
    if "friendly_closer" not in template:
        template["friendly_closer"] = template["closer"]

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        return template

    try:
        from openai import AsyncOpenAI

        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL") or "https://api.openai.com/v1"
        oc = AsyncOpenAI(api_key=openai_key, base_url=base_url)

        style_note = {
            "english_only": "natural professional English",
            "auto": "natural professional English; mirror the user's tone",
        }.get(language_style, "natural English")

        user = f"""
RM first name: {agenda.rm_name.split()[0] if agenda.rm_name else 'there'}
Today's headline: {agenda.headline}
Meetings ({len(agenda.meetings)}): {_format_list(agenda.meetings, 3)}
Flagged overnight ({len(agenda.flagged)}): {_format_list(agenda.flagged, 3)}
Commitments due ({len(agenda.commitments)}): {_format_list(agenda.commitments, 3)}

Write a single warm opening line under 30 words a voice agent will say to start
the call. Style: {style_note}. End the sentence by inviting them into the
rundown (e.g. "ready for the rundown?"). Return only the line — no quotes.
"""
        resp = await oc.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": user}],
            max_tokens=80,
            temperature=0.7,
        )
        line = resp.choices[0].message.content.strip().strip('"').strip("'")
        if line:
            template["opening_line"] = line
        return template
    except Exception as e:
        logger.warning("Brief opening line generation failed: %s", e)
        return template
