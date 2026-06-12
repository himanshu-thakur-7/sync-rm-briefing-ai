"""_parse_when — spoken meeting times → Pipedrive (due_date, due_time) in UTC."""
from datetime import date, timedelta

from adapters.pipedrive import PipedriveCRMAdapter

parse = PipedriveCRMAdapter._parse_when


def test_weekday_and_time_converts_ist_to_utc():
    d, t = parse("Thursday 4:00 PM")
    assert date.fromisoformat(d).weekday() == 3
    assert date.fromisoformat(d) > date.today()
    assert t == "10:30"  # 16:00 IST → UTC


def test_bare_business_hour_defaults_pm():
    _, t = parse("monday 3")
    assert t == "09:30"  # 15:00 IST → UTC


def test_midnight_crossing_shifts_date_back():
    d, t = parse("Friday 2 am")
    assert t == "20:30"
    assert date.fromisoformat(d).weekday() == 3  # Thursday UTC


def test_tomorrow_no_time():
    d, t = parse("tomorrow")
    assert d == (date.today() + timedelta(days=1)).isoformat()
    assert t is None


def test_iso_passthrough_with_time():
    d, t = parse("2030-01-15 16:30")
    assert d == "2030-01-15" and t == "11:00"  # 16:30 IST → UTC
