"""Live whisper-coaching — real-time nudges to the RM during a live call.

As transcript chunks stream in (from a real Ringg call or a simulated demo
call), we accumulate them per call and periodically ask GPT-4o for a single,
short coaching nudge the RM should hear *right now* — pivot suggestions,
risk flags, cross-sell openings.

Falls back to a fast keyword heuristic when OpenAI is not configured, so the
demo still produces believable nudges with zero credentials.

A nudge has a `tone`:
  - "suggest"      → a tactical move (pivot, ask, offer)
  - "warn"         → a risk to defuse (hesitation, competitor, complaint)
  - "opportunity"  → an opening to seize (life event, upsell signal)
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Nudge:
    text: str
    tone: str  # suggest | warn | opportunity

    def as_dict(self) -> dict:
        return {"text": self.text, "tone": self.tone}


# Per-call rolling state so we don't re-nudge on every chunk.
@dataclass
class _CallState:
    lines: list[str]
    last_nudge_at_line: int
    fired: set[str]  # de-dup nudge texts we've already sent


_CALLS: dict[str, _CallState] = {}

# Only ask the model every N new lines, to keep latency + cost sane.
_NUDGE_EVERY_N_LINES = 2

COACH_SYSTEM_PROMPT = """You are a live sales-coaching co-pilot whispering to a
Relationship Manager while they are ON a call with a client. You see the
running transcript. Your job: decide if RIGHT NOW there is one high-value thing
the RM should do, and say it in <= 12 words, like a teammate murmuring in their
ear.

Return STRICT JSON: {"nudge": "<text or empty>", "tone": "suggest|warn|opportunity"}

Rules:
- Only nudge when it genuinely helps. If nothing is worth saying, return
  {"nudge": "", "tone": "suggest"}.
- Never repeat advice already obvious from earlier in the transcript.
- "warn" for hesitation, objections, competitor mentions, complaints, churn signals.
- "opportunity" for life events, upsell openings, positive buying signals.
- "suggest" for a tactical next move (a question to ask, an offer to make).
- Be specific to THIS client and THIS moment. No generic platitudes.
- <= 12 words. Imperative voice. No quotes around the nudge."""


async def observe(call_id: str, line: str, client_summary: str = "") -> Optional[Nudge]:
    """Feed one transcript line. Returns a Nudge if one should fire now, else None."""
    st = _CALLS.get(call_id)
    if st is None:
        st = _CallState(lines=[], last_nudge_at_line=0, fired=set())
        _CALLS[call_id] = st

    st.lines.append(line)

    # Throttle: only evaluate every N new lines, and only on a client turn
    # (the most coachable moments follow what the *client* just said).
    new_since = len(st.lines) - st.last_nudge_at_line
    if new_since < _NUDGE_EVERY_N_LINES:
        return None

    st.last_nudge_at_line = len(st.lines)
    transcript = "\n".join(st.lines[-12:])  # last ~12 lines is plenty of context

    nudge = await _coach(transcript, client_summary)
    if nudge is None or not nudge.text.strip():
        return None

    key = nudge.text.strip().lower()
    if key in st.fired:
        return None
    st.fired.add(key)
    return nudge


def end_call(call_id: str) -> None:
    """Drop a finished call's rolling state."""
    _CALLS.pop(call_id, None)
    _ACTIONS_FIRED.pop(call_id, None)


# ─── Model + heuristic ────────────────────────────────────────────────────

async def _coach(transcript: str, client_summary: str) -> Optional[Nudge]:
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not openai_key:
        return _heuristic(transcript)

    try:
        from openai import AsyncOpenAI

        base_url = os.environ.get("OPENAI_BASE_URL") or None
        oc = AsyncOpenAI(api_key=openai_key, base_url=base_url)
        user = transcript
        if client_summary:
            user = f"CLIENT CONTEXT: {client_summary}\n\nTRANSCRIPT SO FAR:\n{transcript}"
        resp = await oc.chat.completions.create(
            model="gpt-4o-mini",  # fast + cheap; coaching is latency-sensitive
            messages=[
                {"role": "system", "content": COACH_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            max_tokens=60,
            temperature=0.4,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        text = (data.get("nudge") or "").strip()
        tone = (data.get("tone") or "suggest").strip()
        if tone not in ("suggest", "warn", "opportunity"):
            tone = "suggest"
        if not text:
            return None
        return Nudge(text=text, tone=tone)
    except Exception as e:
        logger.warning("Coaching model error, falling back to heuristic: %s", e)
        return _heuristic(transcript)


# Keyword → nudge table for the keyless demo path. Checked against the most
# recent client line only (lowercased).
_HEURISTICS: list[tuple[tuple[str, ...], str, str]] = [
    (("worried", "worry", "anxious", "nervous", "not sure", "hesitant", "concerned"),
     "Acknowledge the worry, then pivot to the relief angle.", "warn"),
    (("expensive", "costly", "too much", "afford", "cost"),
     "Reframe on value and EMI relief, not headline price.", "warn"),
    (("competitor", "another bank", "hdfc", "icici", "axis", "better rate", "switching"),
     "Competitor signal — flag for retention, counter on service.", "warn"),
    (("complaint", "issue", "problem", "unhappy", "frustrat", "disappoint"),
     "Defuse first: confirm you'll resolve it on this call.", "warn"),
    (("later", "busy", "no time", "call back", "some other"),
     "Offer a fixed 10-min slot, not an open-ended callback.", "suggest"),
    (("interested", "tell me more", "sounds good", "go ahead", "yes please"),
     "Buying signal — move to the specific offer now.", "opportunity"),
    (("new job", "promotion", "bonus", "esop", "married", "house", "child", "school"),
     "Life event — open the matched cross-sell.", "opportunity"),
    (("maybe", "think about", "let me see", "not now"),
     "Soft no — surface one concrete benefit to re-engage.", "suggest"),
]


# ─── Action suggestions ───────────────────────────────────────────────────
# Beyond advice, SYNC spots COMMITMENTS in the conversation ("Thursday at four
# works", "I'll send the details") and proposes the matching CRM action. The
# RM approves with one click and the activity lands in the live CRM.

@dataclass
class ActionSuggestion:
    tool: str          # matches the voice-command execute tools
    args: dict
    preview: str       # human-readable, shown on the approval card

    def as_dict(self) -> dict:
        return {"tool": self.tool, "args": self.args, "preview": self.preview}


_ACTIONS_FIRED: dict[str, set] = {}  # call_id → tools already suggested

_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_AGREEMENT = ("works", "sounds good", "okay", "ok ", "fine", "perfect", "sure", "deal", "see you", "confirmed")
_WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}

import re as _re


def _extract_when(low: str, day: str) -> str:
    """Build a spoken-style time like 'Thursday 4:00 PM' from the line."""
    m = _re.search(r"\bat\s+(\d{1,2}(?::\d{2})?|" + "|".join(_WORD_NUM) + r")\s*(am|pm)?\b", low)
    if not m:
        return day.capitalize()
    raw, meridiem = m.group(1), m.group(2)
    hour = _WORD_NUM.get(raw, None)
    if hour is None:
        hour = int(raw.split(":")[0])
    minutes = raw.split(":")[1] if ":" in raw else "00"
    if not meridiem:
        # Business-hours default: 1–7 reads as PM, 8–12 as AM.
        meridiem = "pm" if 1 <= hour <= 7 else "am"
    return f"{day.capitalize()} {hour}:{minutes} {meridiem.upper()}"


async def detect_action(call_id: str, line: str) -> Optional[ActionSuggestion]:
    """Inspect one transcript line for an actionable commitment.

    Heuristic-driven (works keyless); each tool fires at most once per call.
    A GPT pass can replace this later — the contract (tool/args/preview)
    already matches the voice-command execute schema.
    """
    fired = _ACTIONS_FIRED.setdefault(call_id, set())
    low = line.lower()

    # Meeting agreed: a weekday + an agreement word on the same line.
    if "schedule_follow_up" not in fired:
        day = next((d for d in _DAYS if d in low), None)
        if day and any(a in low for a in _AGREEMENT):
            fired.add("schedule_follow_up")
            when = _extract_when(low, day)
            return ActionSuggestion(
                tool="schedule_follow_up",
                args={"when": when, "kind": "meeting",
                      "notes": "Agreed during a SYNC-coached call"},
                preview=f"Schedule a follow-up meeting — {when}",
            )

    # Deliverable promised: "I'll send the details / proposal / numbers".
    if "create_task" not in fired:
        if _re.search(r"\b(i(?:'| wi)ll send|send (?:me|you|him|her|them|over) the)\b", low) and \
           _re.search(r"\b(details|numbers|proposal|brochure|documents?)\b", low):
            fired.add("create_task")
            from datetime import date, timedelta
            due = (date.today() + timedelta(days=1)).isoformat()
            return ActionSuggestion(
                tool="create_task",
                args={"subject": "Send the discussed details to the client", "due_date": due},
                preview="Create a task — send the discussed details (due tomorrow)",
            )

    return None


def _heuristic(transcript: str) -> Optional[Nudge]:
    # Look at the last non-SYNC line (what the human just said).
    last_client = ""
    for ln in reversed(transcript.splitlines()):
        low = ln.strip().lower()
        if not low:
            continue
        if low.startswith("sync:") or low.startswith("agent:"):
            continue
        last_client = low
        break
    if not last_client:
        return None
    for keys, text, tone in _HEURISTICS:
        if any(k in last_client for k in keys):
            return Nudge(text=text, tone=tone)
    return None
