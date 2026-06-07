"""Morning brief agenda + payload assembly against FakeLeadSquared fixtures."""
from __future__ import annotations

import pytest

from services import morning_brief_engine


@pytest.mark.asyncio
async def test_assemble_agenda_returns_structured_shape():
    """Agenda has the right top-level fields populated from the sandbox data."""
    agenda = await morning_brief_engine.assemble_agenda(
        "conn_lsq_sandbox", rm_name="Test RM",
    )
    assert agenda.rm_name == "Test RM"
    assert agenda.for_date
    # Headline is non-empty (either real or "A quiet day")
    assert agenda.headline
    # Sections are lists (may be empty depending on fixture dates)
    assert isinstance(agenda.meetings, list)
    assert isinstance(agenda.flagged, list)
    assert isinstance(agenda.commitments, list)
    assert isinstance(agenda.tasks, list)


@pytest.mark.asyncio
async def test_generate_brief_payload_template_fallback():
    """Without OPENAI_API_KEY the deterministic template fires."""
    import os
    os.environ.pop("OPENAI_API_KEY", None)
    agenda = await morning_brief_engine.assemble_agenda("conn_lsq_sandbox", rm_name="Himanshu")
    payload = await morning_brief_engine.generate_brief_payload(
        agenda, language_style="english_only", company_name="Acme",
    )
    # Required custom_args for the conversational agent
    for key in (
        "rm_name", "company_name", "language_style",
        "opening_line", "agenda_summary",
        "meeting_list", "flagged_list", "commitments_list", "tasks_list",
        "closer",
    ):
        assert key in payload, f"Missing {key}"
    assert payload["rm_name"] == "Himanshu"
    assert payload["company_name"] == "Acme"
    assert "Himanshu" in payload["opening_line"]
    # English-only by default — closer is a plain greeting, no Hindi
    assert "great" in payload["closer"].lower()


@pytest.mark.asyncio
async def test_payload_english_only_is_clean():
    """language_style=english_only produces only English copy."""
    import os
    os.environ.pop("OPENAI_API_KEY", None)
    agenda = await morning_brief_engine.assemble_agenda("conn_lsq_sandbox", rm_name="Sarah")
    payload = await morning_brief_engine.generate_brief_payload(
        agenda, language_style="english_only", company_name="Northwind",
    )
    assert "shubh" not in payload["closer"].lower()
    assert "chalo" not in payload["opening_line"].lower()
    assert "great" in payload["closer"].lower()
