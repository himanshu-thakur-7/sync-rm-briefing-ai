"""Live whisper-coaching engine — heuristic nudges + commitment detection."""
import pytest

from services import coaching_engine as ce


@pytest.fixture(autouse=True)
def _clean_state():
    yield
    ce.end_call("t-nudge")
    ce.end_call("t-action")
    ce.end_call("t-dedup")


@pytest.mark.asyncio
async def test_worry_line_fires_warn_nudge():
    await ce.observe("t-nudge", "SYNC: Hi there!")
    n = await ce.observe("t-nudge", "Client: honestly I've been worried about the EMIs")
    assert n is not None and n.tone == "warn"


@pytest.mark.asyncio
async def test_nudges_throttled_and_deduped():
    n1 = await ce.observe("t-dedup", "A: I'm worried")          # line 1 — throttled
    assert n1 is None
    n2 = await ce.observe("t-dedup", "B: I'm worried again")    # line 2 — fires
    assert n2 is not None
    n3 = await ce.observe("t-dedup", "A: ok")
    n4 = await ce.observe("t-dedup", "B: still worried here")   # same nudge text → deduped
    assert n3 is None and n4 is None


@pytest.mark.asyncio
async def test_meeting_commitment_detected_with_time():
    a = await ce.detect_action("t-action", "Client: Okay, Thursday at four works.")
    assert a is not None and a.tool == "schedule_follow_up"
    assert "Thursday 4:00 PM" in a.preview
    # one fire per tool per call
    again = await ce.detect_action("t-action", "Client: yes Thursday works fine")
    assert again is None


@pytest.mark.asyncio
async def test_send_details_creates_task_third_person():
    a = await ce.detect_action("t-action", "RM: Create a task to send him the restructuring proposal tomorrow.")
    assert a is not None and a.tool == "create_task"
    assert a.args.get("due_date")
