"""Risk Radar — the autonomous brain behind Save Calls.

Scans every client in a CRM connection and detects trigger conditions that
warrant a proactive outbound 'save call'. Each detection becomes a
SaveCallPlay with an objective, urgency, talking points, and a rationale.

Trigger rules (highest urgency wins per client, all matches recorded):
  npa_risk           CRITICAL  risk=high + factor mentions NPA/missed/maxed
  aging_complaint    HIGH      open|escalated complaint >= 14 days old
  emi_overdue_soon   MEDIUM    a product next_due within 5 days AND history has misses
  winback            MEDIUM    last RM contact >= 60 days ago
  proactive_crosssell LOW      a cross-sell tied to a life event (ESOP/SIP/education)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from models import ClientFullProfile

logger = logging.getLogger(__name__)

# Urgency ordering for dedup (higher = wins)
_URGENCY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@dataclass
class DetectedPlay:
    client_id: str
    client_name: str
    trigger_type: str
    urgency: str
    objective: str
    talking_points: list[str]
    rationale: str
    matched_triggers: list[str] = field(default_factory=list)


# ─────────────────────────────── helpers ──────────────────────────────────

def _complaint_age_days(complaint_date: str) -> Optional[int]:
    try:
        d = datetime.strptime(complaint_date[:10], "%Y-%m-%d").date()
        return (date.today() - d).days
    except (ValueError, TypeError):
        return None


def _days_until(due_date: str) -> Optional[int]:
    try:
        d = datetime.strptime(due_date[:10], "%Y-%m-%d").date()
        return (d - date.today()).days
    except (ValueError, TypeError):
        return None


def _has_misses(payment_history: list[str]) -> bool:
    return any(h != "on_time" for h in (payment_history or []))


# ─────────────────────────────── rules ────────────────────────────────────

def _rule_npa_risk(c: ClientFullProfile) -> Optional[DetectedPlay]:
    if c.risk.score != "high":
        return None
    factors_blob = " ".join(c.risk.factors).lower()
    if not any(kw in factors_blob for kw in ("npa", "missed", "maxed", "utilization at 9", "stress")):
        return None
    # Find the best restructure cross-sell if present
    offer = next((cs.product for cs in c.cross_sell), "a restructuring option")
    return DetectedPlay(
        client_id=c.profile.client_id,
        client_name=c.profile.name,
        trigger_type="npa_risk",
        urgency="CRITICAL",
        objective="Pre-empt NPA classification — offer a restructuring lifeline before it's too late",
        talking_points=[
            f"{c.profile.name.split()[0]} is showing acute repayment stress: {c.risk.factors[0]}",
            f"Lead with savings, not alarm: position {offer} as 'I've found a way to save you money this year'",
            "Offer a warm transfer to the RM if they want to talk specifics",
        ],
        rationale=f"Risk is HIGH with factors: {', '.join(c.risk.factors[:2])}. Acting now can prevent an NPA.",
    )


def _rule_aging_complaint(c: ClientFullProfile) -> Optional[DetectedPlay]:
    for comp in c.complaints:
        if comp.status in ("open", "escalated"):
            age = _complaint_age_days(comp.date)
            if age is not None and age >= 14:
                return DetectedPlay(
                    client_id=c.profile.client_id,
                    client_name=c.profile.name,
                    trigger_type="aging_complaint",
                    urgency="HIGH",
                    objective=f"Proactively apologize for the aging '{comp.category}' complaint and signal resolution",
                    talking_points=[
                        f"Acknowledge the {comp.category} complaint filed {age} days ago — unprompted",
                        f"Context: {comp.summary[:100]}",
                        "Reassure it's being escalated; offer a callback with the RM",
                    ],
                    rationale=f"An {comp.status} complaint has been unresolved for {age} days — churn risk.",
                )
    return None


def _rule_emi_overdue_soon(c: ClientFullProfile) -> Optional[DetectedPlay]:
    for prod in c.products:
        days = _days_until(prod.next_due_date)
        if days is not None and 0 <= days <= 5 and _has_misses(prod.payment_history):
            return DetectedPlay(
                client_id=c.profile.client_id,
                client_name=c.profile.name,
                trigger_type="emi_overdue_soon",
                urgency="MEDIUM",
                objective=f"Friendly EMI reminder — {prod.product_type.replace('_', ' ')} due in {days} days",
                talking_points=[
                    f"{prod.product_type.replace('_', ' ').title()} EMI of around the usual amount is due in {days} days",
                    "This client has a history of misses — a gentle nudge avoids another bounce",
                    "Offer auto-pay setup or a date adjustment",
                ],
                rationale=f"EMI due in {days} days and prior payment misses on record.",
            )
    return None


def _rule_winback(c: ClientFullProfile) -> Optional[DetectedPlay]:
    if c.last_rm_interaction_days_ago >= 60:
        return DetectedPlay(
            client_id=c.profile.client_id,
            client_name=c.profile.name,
            trigger_type="winback",
            urgency="MEDIUM",
            objective="Re-engage a client who's gone quiet for over two months",
            talking_points=[
                f"No contact in {c.last_rm_interaction_days_ago} days — a warm check-in, no hard pitch",
                f"Reference their profile: {c.profile.occupation} at {c.profile.company}",
                "Ask if anything's changed; offer a portfolio review with the RM",
            ],
            rationale=f"Last RM interaction was {c.last_rm_interaction_days_ago} days ago.",
        )
    return None


def _rule_proactive_crosssell(c: ClientFullProfile) -> Optional[DetectedPlay]:
    for cs in c.cross_sell:
        blob = f"{cs.product} {cs.pitch_angle}".lower()
        if any(kw in blob for kw in ("esop", "sip", "education", "child", "daughter", "school", "home loan")):
            return DetectedPlay(
                client_id=c.profile.client_id,
                client_name=c.profile.name,
                trigger_type="proactive_crosssell",
                urgency="LOW",
                objective=f"Life-event cross-sell: {cs.product}",
                talking_points=[
                    f"Tie it to their life context, not eligibility: {cs.pitch_angle[:120]}",
                    "Soft, consultative tone — plant the seed, offer an RM follow-up",
                ],
                rationale=f"A life-event-linked opportunity exists: {cs.product}.",
            )
    return None


_RULES = [
    _rule_npa_risk,
    _rule_aging_complaint,
    _rule_emi_overdue_soon,
    _rule_winback,
    _rule_proactive_crosssell,
]


# ─────────────────────────────── scan ─────────────────────────────────────

async def scan(connection_id: str) -> list[DetectedPlay]:
    """Scan all clients in a connection, return one play per flagged client.

    Per-client lookups fire in PARALLEL (asyncio.gather). Sequential awaits
    over 5+ Pipedrive persons were taking 7-10s wall-clock and pushing the
    on-call tool past Ringg's timeout. Concurrency collapses that to the
    slowest single client (~1-2s).
    """
    import asyncio as _asyncio
    from services import connection_registry

    adapter = await connection_registry.crm_for(connection_id)
    profiles = await adapter.list_all()

    async def _safe_get(prof):
        try:
            return prof, await adapter.get_client(prof.client_id)
        except Exception as e:
            logger.warning("Radar get_client(%s) failed: %s", prof.client_id, e)
            return prof, None

    fulls = await _asyncio.gather(*(_safe_get(p) for p in profiles))

    plays: list[DetectedPlay] = []
    for prof, full in fulls:
        if full is None:
            continue
        matched: list[DetectedPlay] = []
        for rule in _RULES:
            try:
                hit = rule(full)
            except Exception as e:  # a bad rule shouldn't kill the scan
                logger.warning("Radar rule %s failed for %s: %s", rule.__name__, prof.client_id, e)
                hit = None
            if hit:
                matched.append(hit)

        if not matched:
            continue

        matched.sort(key=lambda p: _URGENCY_RANK.get(p.urgency, 0), reverse=True)
        winner = matched[0]
        winner.matched_triggers = [m.trigger_type for m in matched]
        plays.append(winner)

    plays.sort(key=lambda p: _URGENCY_RANK.get(p.urgency, 0), reverse=True)
    logger.info("Risk Radar scan(%s): %d plays detected", connection_id, len(plays))
    return plays
