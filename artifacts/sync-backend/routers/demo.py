"""Demo control surface — stage-safe seeding + ROI ledger.

Two endpoints power the "always looks alive + quantified" demo experience:

  POST /api/v1/demo/seed
      Pre-populate a believable working day: a handful of completed briefings
      timestamped to *today* (so the KPI strip and Live Feed are never empty
      when you walk on stage). Idempotent-ish — replaces today's demo rows.

  GET  /api/v1/demo/roi
      Aggregate ROI ledger the dashboard renders as a running counter:
      hours saved, cross-sell value surfaced, complaints caught, calls handled.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

import database
from models import BriefingLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

# Minutes of manual prep saved per briefing (matches briefings stats).
_MINUTES_SAVED_PER_SYNC = 18.0

# A believable "today so far" — names match the Pipedrive / sandbox dataset.
_DEMO_BRIEFINGS = [
    dict(client_id="client_005", client_name="Vikram Desai", rm_name="Himanshu",
         minutes_ago=14, duration=52, risk="high",
         flags=["risk_high", "cc_utilization_92%", "2_missed_emis", "complaint_open"],
         pitch="CC debt restructure to Personal Loan — saves ₹3L in interest",
         cross_sell_value=300000),
    dict(client_id="client_001", client_name="Rahul Mehta", rm_name="Himanshu",
         minutes_ago=63, duration=41, risk="low",
         flags=["emi_due_4_days"],
         pitch="SIP for daughter's education — ₹10K/month, 2028 goal",
         cross_sell_value=120000),
    dict(client_id="client_002", client_name="Priya Sharma", rm_name="Himanshu",
         minutes_ago=121, duration=36, risk="very_low",
         flags=["upsell_ready"],
         pitch="Wealth-management upgrade — portfolio crossed ₹50L",
         cross_sell_value=85000),
    dict(client_id="client_004", client_name="Sneha Reddy", rm_name="Himanshu",
         minutes_ago=158, duration=44, risk="medium",
         flags=["complaint_open", "winback_60d"],
         pitch="Home-loan top-up at preferential rate — renovation intent",
         cross_sell_value=210000),
]


def _today_seeded() -> list[BriefingLog]:
    now = datetime.now(timezone.utc)
    out: list[BriefingLog] = []
    for i, d in enumerate(_DEMO_BRIEFINGS):
        ts = (now - timedelta(minutes=d["minutes_ago"])).isoformat()
        out.append(BriefingLog(
            briefing_id=str(uuid.uuid4()),
            client_id=d["client_id"],
            client_name=d["client_name"],
            rm_id="rm_demo",
            rm_name=d["rm_name"],
            timestamp=ts,
            duration_seconds=d["duration"],
            key_flags=d["flags"],
            suggested_pitch=d["pitch"],
            call_id=f"demo_seed_{i}_{uuid.uuid4().hex[:6]}",
            risk_score=d["risk"],
            latency_ms=280 + i * 25,
            extra={"cross_sell_value": d["cross_sell_value"], "demo": True},
        ))
    return out


@router.post("/seed")
async def seed_demo():
    """Drop believable 'today' briefings into the live feed + KPI strip."""
    # Remove any prior demo-seeded rows so re-seeding doesn't pile up.
    database.BRIEFING_LOGS = [
        b for b in database.BRIEFING_LOGS if not b.call_id.startswith("demo_seed_")
    ]
    seeded = _today_seeded()
    database.BRIEFING_LOGS.extend(seeded)

    # Broadcast each as a sync_completed so connected dashboards animate them in.
    try:
        from routers.webhooks import broadcast_event
        for b in sorted(seeded, key=lambda x: x.timestamp):
            await broadcast_event({"type": "sync_completed", "data": b.model_dump()})
    except Exception as e:
        logger.debug("demo seed broadcast skipped: %s", e)

    return {"seeded": len(seeded), "total_briefings": len(database.BRIEFING_LOGS)}


@router.post("/reset")
async def reset_demo():
    """Remove demo-seeded briefings (leaves organic ones intact)."""
    before = len(database.BRIEFING_LOGS)
    database.BRIEFING_LOGS = [
        b for b in database.BRIEFING_LOGS if not b.call_id.startswith("demo_seed_")
    ]
    return {"removed": before - len(database.BRIEFING_LOGS)}


@router.get("/roi")
async def roi_ledger():
    """Running ROI ledger for the dashboard counter.

    Aggregates across ALL briefings (organic + demo): time saved, cross-sell
    value surfaced, complaints caught, calls handled.
    """
    logs = database.BRIEFING_LOGS
    calls_handled = len(logs)
    minutes_saved = calls_handled * _MINUTES_SAVED_PER_SYNC
    hours_saved = round(minutes_saved / 60, 1)

    complaints_caught = sum(
        1 for b in logs if any("complaint" in f.lower() for f in b.key_flags)
    )

    # Cross-sell value: prefer an explicit metadata value, else a heuristic
    # (every briefing with a real pitch is worth ~₹1L of surfaced opportunity).
    cross_sell_value = 0
    cross_sells = 0
    for b in logs:
        meta = getattr(b, "extra", None) or {}
        v = meta.get("cross_sell_value") if isinstance(meta, dict) else None
        if b.suggested_pitch and len(b.suggested_pitch) > 10:
            cross_sells += 1
            cross_sell_value += int(v) if v else 100000

    return {
        "calls_handled": calls_handled,
        "hours_saved": hours_saved,
        "minutes_saved": int(minutes_saved),
        "cross_sells_surfaced": cross_sells,
        "cross_sell_value_inr": cross_sell_value,
        "complaints_caught": complaints_caught,
    }
