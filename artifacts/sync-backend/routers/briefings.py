from datetime import date
from fastapi import APIRouter, Query
from models import BriefingLog, BriefingStats
import database

router = APIRouter(prefix="/v1/briefings", tags=["briefings"])


@router.get("", response_model=list[BriefingLog])
async def list_briefings(limit: int = Query(20, ge=1, le=100)):
    """Return recent briefing logs in reverse chronological order."""
    logs = sorted(database.BRIEFING_LOGS, key=lambda b: b.timestamp, reverse=True)
    return logs[:limit]


@router.get("/stats", response_model=BriefingStats)
async def get_briefing_stats():
    """Dashboard KPI metrics."""
    today_str = date.today().isoformat()
    today_logs = [b for b in database.BRIEFING_LOGS if b.timestamp.startswith(today_str)]

    syncs_today = len(today_logs)

    # Each sync saves ~18 minutes of manual prep on average
    avg_time_saved = 18.0

    # Count cross-sells that have a non-empty suggested_pitch
    cross_sells_surfaced = sum(
        1 for b in database.BRIEFING_LOGS if b.suggested_pitch and len(b.suggested_pitch) > 10
    )

    # Count logs that had a complaint flag
    complaints_flagged = sum(
        1 for b in database.BRIEFING_LOGS
        if any("complaint" in f for f in b.key_flags)
    )

    latencies = [b.latency_ms for b in database.BRIEFING_LOGS if b.latency_ms is not None]
    avg_latency = int(sum(latencies) / len(latencies)) if latencies else None

    return BriefingStats(
        syncs_today=syncs_today,
        avg_time_saved_minutes=avg_time_saved,
        cross_sells_surfaced=cross_sells_surfaced,
        complaints_flagged=complaints_flagged,
        avg_latency_ms=avg_latency,
    )
