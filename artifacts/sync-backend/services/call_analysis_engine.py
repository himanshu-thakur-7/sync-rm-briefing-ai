"""Post-Call Intelligence — GPT-4o analysis of a completed call transcript.

Extracts sentiment, objections, commitments, churn-risk delta, a 2-sentence
summary, and a concrete next-best-action mapped to the voice-command tool
schema (so it can be executed against the active CRM adapter verbatim).

Falls back to a deterministic heuristic when OpenAI is not configured.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from models import ClientFullProfile

logger = logging.getLogger(__name__)

# Valid next-best-action tools (must match voice_command_engine execute tools)
_NBA_TOOLS = [
    "create_note", "create_task", "schedule_follow_up",
    "mark_complaint_resolved", "mark_complaint_escalated",
    "update_contact_field", "flag_for_manager_review",
]

ANALYSIS_SYSTEM_PROMPT = f"""
You analyze a transcript of a phone call between a business and a customer or
prospect (or between the business's AI and a customer). Produce a tight,
structured analysis.

Return ONLY a JSON object with these keys:
  sentiment_label   one of: positive, cautiously_positive, neutral, concerned, negative
  sentiment_score   integer 0-100 (0 = very negative, 100 = very positive)
  sentiment_timeline array of {{"point": short label, "label": one of the sentiment labels}}
  objections        array of short strings (customer concerns/objections raised)
  commitments       array of {{"party": "client"|"business", "text": short string, "due": optional ISO date}}
  churn_delta       number from -1 to 1 (-1 = call strongly reduced churn risk, +1 = increased it)
  churn_label       one of: reduced, unchanged, increased
  next_best_action  {{"title": short imperative, "tool": one of {_NBA_TOOLS}, "args": object, "reason": short}}
  summary           two sentences, plain English

For next_best_action.tool use the exact tool name and matching args:
  create_task -> {{"subject": str, "due_date": ISO date}}
  create_note -> {{"body": str}}
  schedule_follow_up -> {{"when": ISO datetime, "kind": "call"|"meeting", "notes": str}}
  mark_complaint_resolved / mark_complaint_escalated -> {{}}
  flag_for_manager_review -> {{"reason": str}}
Pick the single most valuable follow-up. Never invent facts not in the transcript.
"""


@dataclass
class CallAnalysisResult:
    sentiment_label: str = "neutral"
    sentiment_score: int = 50
    sentiment_timeline: list = field(default_factory=list)
    objections: list = field(default_factory=list)
    commitments: list = field(default_factory=list)
    churn_delta: float = 0.0
    churn_label: str = "unchanged"
    next_best_action: dict = field(default_factory=dict)
    summary: str = ""


def _heuristic(transcript: str, client: Optional[ClientFullProfile]) -> CallAnalysisResult:
    """Deterministic fallback when no OpenAI key is present."""
    t = transcript.lower()
    positive = any(w in t for w in ("yes", "good", "great", "agree", "sure", "perfect", "thank"))
    negative = any(w in t for w in ("no ", "worried", "angry", "frustrat", "not happy", "cancel"))
    if positive and not negative:
        label, score, churn, clabel = "cautiously_positive", 68, -0.4, "reduced"
    elif negative and not positive:
        label, score, churn, clabel = "concerned", 38, 0.3, "increased"
    else:
        label, score, churn, clabel = "neutral", 52, -0.1, "unchanged"

    objections = []
    if "worried" in t or "credit score" in t:
        objections.append("Concerned about impact / risk")
    if "busy" in t or "later" in t:
        objections.append("Time / scheduling")

    name = client.profile.name if client else "the client"
    commitments = []
    if "call" in t and ("week" in t or "later" in t or "thursday" in t or "monday" in t):
        commitments.append({"party": "client", "text": f"{name} agreed to an RM callback this week"})

    nba = {
        "title": "Schedule the RM follow-up the client agreed to",
        "tool": "create_task",
        "args": {"subject": f"Follow-up call with {name} (from save call)", "due_date": ""},
        "reason": "Client agreed to a callback; lock it in so it doesn't slip.",
    }
    return CallAnalysisResult(
        sentiment_label=label, sentiment_score=score, churn_delta=churn, churn_label=clabel,
        objections=objections, commitments=commitments, next_best_action=nba,
        summary=f"Call with {name} completed. Heuristic read: {label.replace('_', ' ')}; "
                f"recommended a follow-up task.",
    )


async def analyze_call(
    transcript: str,
    client: Optional[ClientFullProfile] = None,
    call_kind: str = "briefing",
) -> CallAnalysisResult:
    """Analyze a call transcript with GPT-4o; fall back to a heuristic."""
    if not transcript or not transcript.strip():
        return CallAnalysisResult(summary="No transcript available to analyze.")

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        return _heuristic(transcript, client)

    try:
        from openai import AsyncOpenAI

        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL") or "https://api.openai.com/v1"
        oc = AsyncOpenAI(api_key=openai_key, base_url=base_url)

        ctx = ""
        if client:
            ctx = (f"\nContext — client: {client.profile.name}, {client.profile.occupation} "
                   f"at {client.profile.company}; risk {client.risk.score}; "
                   f"{len(client.complaints)} complaint(s) on file.")

        resp = await oc.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": f"CALL KIND: {call_kind}{ctx}\n\nTRANSCRIPT:\n{transcript}\n\nReturn the analysis JSON now."},
            ],
            response_format={"type": "json_object"},
            max_tokens=700,
            temperature=0.3,
        )
        data = json.loads(resp.choices[0].message.content)

        # Validate the NBA tool; fall back to create_note if model picks an unknown tool.
        nba = data.get("next_best_action") or {}
        if nba.get("tool") not in _NBA_TOOLS:
            nba = {"title": "Log a follow-up note", "tool": "create_note",
                   "args": {"body": data.get("summary", "Call completed.")}, "reason": "Default action."}

        return CallAnalysisResult(
            sentiment_label=data.get("sentiment_label", "neutral"),
            sentiment_score=int(data.get("sentiment_score", 50)),
            sentiment_timeline=data.get("sentiment_timeline", []),
            objections=data.get("objections", []),
            commitments=data.get("commitments", []),
            churn_delta=float(data.get("churn_delta", 0.0)),
            churn_label=data.get("churn_label", "unchanged"),
            next_best_action=nba,
            summary=data.get("summary", ""),
        )
    except Exception as e:
        logger.warning("GPT-4o call analysis failed: %s. Using heuristic.", e)
        return _heuristic(transcript, client)
