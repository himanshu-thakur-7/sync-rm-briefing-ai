"""Async scheduler for the Daily Standup feature.

Each enabled MorningBriefSchedule gets its own asyncio task that:
  1. computes the next fire time honouring HH:MM + weekday_mask + IANA timezone
  2. sleeps until then
  3. fires the standup call via routers.morning_brief.place_morning_brief_call
  4. persists last_called_at + next_call_at
  5. loops forever (cancelled when the schedule is updated/deleted/disabled)

Survives process restarts because next_call_at is persisted; on startup
load_all() resumes every enabled schedule from its stored next_call_at.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlmodel import select

from db import get_session
from db.models import MorningBriefSchedule

logger = logging.getLogger(__name__)

# Registry: schedule_id → asyncio.Task
_tasks: dict[int, asyncio.Task] = {}


def _tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def compute_next_fire(
    hour: int,
    minute: int,
    weekday_mask: int,
    tz_name: str,
    now: Optional[datetime] = None,
) -> datetime:
    """Return the next UTC datetime the schedule should fire.

    weekday_mask: bit 0=Mon ... bit 6=Sun. A mask of 0 means "never fire" —
    we return a sentinel one year out.
    """
    if weekday_mask == 0:
        return (now or datetime.now(timezone.utc)) + timedelta(days=365)

    tz = _tz(tz_name)
    now_utc = now or datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)

    # Try today, then each of the next 7 days; pick the first one whose
    # weekday is allowed AND whose time is in the future (in local tz).
    for delta in range(0, 8):
        candidate_local = (now_local + timedelta(days=delta)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if not ((weekday_mask >> candidate_local.weekday()) & 1):
            continue
        if candidate_local <= now_local:
            continue
        return candidate_local.astimezone(timezone.utc)

    # Fallback (shouldn't reach): one week out
    return now_utc + timedelta(days=7)


async def _loop(schedule_id: int) -> None:
    """Per-schedule loop: sleep → fire → update DB → repeat."""
    try:
        while True:
            # Reload to pick up updates between fires
            async with get_session() as session:
                sched = (await session.exec(
                    select(MorningBriefSchedule).where(MorningBriefSchedule.id == schedule_id)
                )).first()
                if not sched or not sched.enabled:
                    logger.info("Morning brief schedule %s disabled/removed — stopping loop", schedule_id)
                    return

                # Compute or honor stored next fire (SQLite may return naive datetimes)
                now_utc = datetime.now(timezone.utc)
                next_at = sched.next_call_at
                if next_at is not None and next_at.tzinfo is None:
                    next_at = next_at.replace(tzinfo=timezone.utc)
                if next_at is None or next_at <= now_utc:
                    next_at = compute_next_fire(
                        sched.hour_local, sched.minute_local, sched.weekday_mask, sched.timezone,
                    )
                    sched.next_call_at = next_at
                    session.add(sched)

            sleep_s = max(1.0, (next_at - datetime.now(timezone.utc)).total_seconds())
            logger.info("Morning brief #%s sleeping %.0fs until %s",
                        schedule_id, sleep_s, next_at.isoformat())
            await asyncio.sleep(sleep_s)

            # Fire — import here to avoid circular at module load
            try:
                from routers.morning_brief import place_morning_brief_call
                await place_morning_brief_call(schedule_id, source="scheduler")
            except Exception as e:
                logger.warning("Morning brief fire #%s failed: %s", schedule_id, e)

            # Mark fired + compute new next_call_at
            async with get_session() as session:
                sched = (await session.exec(
                    select(MorningBriefSchedule).where(MorningBriefSchedule.id == schedule_id)
                )).first()
                if sched:
                    sched.last_called_at = datetime.now(timezone.utc)
                    sched.next_call_at = compute_next_fire(
                        sched.hour_local, sched.minute_local, sched.weekday_mask, sched.timezone,
                    )
                    session.add(sched)
    except asyncio.CancelledError:
        logger.info("Morning brief loop %s cancelled", schedule_id)
        raise


def register(schedule_id: int) -> None:
    """Spawn (or restart) the loop task for a schedule."""
    existing = _tasks.get(schedule_id)
    if existing and not existing.done():
        existing.cancel()
    _tasks[schedule_id] = asyncio.create_task(_loop(schedule_id))


def unregister(schedule_id: int) -> None:
    """Cancel the loop task for a schedule."""
    t = _tasks.pop(schedule_id, None)
    if t and not t.done():
        t.cancel()


async def load_all() -> None:
    """At app startup: register every enabled schedule."""
    try:
        async with get_session() as session:
            rows = list((await session.exec(
                select(MorningBriefSchedule).where(MorningBriefSchedule.enabled == True)  # noqa: E712
            )).all())
            ids = [r.id for r in rows]
    except Exception as e:
        logger.warning("Morning brief load_all failed (DB not ready?): %s", e)
        return
    for sid in ids:
        register(sid)
    if ids:
        logger.info("Morning brief scheduler resumed %d schedule(s)", len(ids))
