"""compute_next_fire correctness across timezone + weekday rollover."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from services.morning_brief_scheduler import compute_next_fire


IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


def _ist(y, m, d, h, mi):
    return datetime(y, m, d, h, mi, tzinfo=IST).astimezone(UTC)


def test_same_day_future_hour_fires_today():
    """Now = Mon 06:00 IST; schedule 07:45 Mon-Fri → fires Mon 07:45 IST."""
    now = _ist(2026, 6, 8, 6, 0)  # Monday 06:00 IST
    nxt = compute_next_fire(7, 45, 31, "Asia/Kolkata", now)  # mask 31 = Mon-Fri
    assert nxt == _ist(2026, 6, 8, 7, 45)


def test_past_hour_today_rolls_to_next_allowed_day():
    """Now = Mon 09:00 IST; 07:45 Mon-Fri → fires Tue 07:45 IST."""
    now = _ist(2026, 6, 8, 9, 0)
    nxt = compute_next_fire(7, 45, 31, "Asia/Kolkata", now)
    assert nxt == _ist(2026, 6, 9, 7, 45)


def test_weekend_skip_to_monday():
    """Now = Fri 23:00 IST; mask Mon-Fri only → fires Mon 07:45 IST."""
    now = _ist(2026, 6, 12, 23, 0)  # Friday
    nxt = compute_next_fire(7, 45, 31, "Asia/Kolkata", now)
    assert nxt == _ist(2026, 6, 15, 7, 45)


def test_weekend_only_mask():
    """Mask 96 = bit 5 (Sat) + bit 6 (Sun). Now = Sun 10:00 IST → fires Sat 09:00 next week."""
    now = _ist(2026, 6, 14, 10, 0)  # Sunday
    nxt = compute_next_fire(9, 0, 96, "Asia/Kolkata", now)
    assert nxt == _ist(2026, 6, 20, 9, 0)


def test_disabled_mask_returns_far_future():
    """Mask 0 means never fire — function returns ~1 year out."""
    now = _ist(2026, 6, 8, 6, 0)
    nxt = compute_next_fire(7, 45, 0, "Asia/Kolkata", now)
    delta_days = (nxt - now).days
    assert 360 <= delta_days <= 366


def test_us_pacific_timezone():
    """A schedule in America/Los_Angeles fires in local PT."""
    now_pt = datetime(2026, 6, 8, 5, 0, tzinfo=ZoneInfo("America/Los_Angeles")).astimezone(UTC)
    nxt = compute_next_fire(8, 30, 31, "America/Los_Angeles", now_pt)
    expected = datetime(2026, 6, 8, 8, 30, tzinfo=ZoneInfo("America/Los_Angeles")).astimezone(UTC)
    assert nxt == expected


def test_unknown_timezone_falls_back_to_utc():
    """Bad TZ name doesn't crash; falls back to UTC."""
    now = datetime(2026, 6, 8, 6, 0, tzinfo=UTC)
    nxt = compute_next_fire(7, 45, 31, "Mars/Olympus_Mons", now)
    # Same calendar day in UTC: Mon 07:45 UTC
    assert nxt == datetime(2026, 6, 8, 7, 45, tzinfo=UTC)
