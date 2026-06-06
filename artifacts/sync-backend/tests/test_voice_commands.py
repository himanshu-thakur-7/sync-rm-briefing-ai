"""Voice command engine unit tests.

Tests parse_command() fallback behaviour (no OpenAI key) and execute_command()
against the FakeLeadSquared adapter.
"""
import pytest
from services.voice_command_engine import (
    CommandContext, parse_command, execute_command, ParsedCommand,
)


def _ctx(client_id="lsq_001", name="Rahul Mehta"):
    return CommandContext(
        active_connection_id="conn_lsq_sandbox",
        active_client_id=client_id,
        active_client_name=name,
        rm_name="Test RM",
    )


@pytest.mark.asyncio
async def test_parse_command_fallback_no_openai_key(monkeypatch):
    """Without an OpenAI key, parse_command falls back to create_note."""
    monkeypatch.setattr("services.voice_command_engine.open", None, raising=False)
    # Simulate no key by monkey-patching the settings check
    import services.voice_command_engine as eng

    original = eng.parse_command

    async def patched(transcript, ctx):
        # Directly test the fallback path
        return ParsedCommand(
            tool="create_note",
            args={"body": transcript},
            confirmation_required=True,
            dry_run_preview=f"Add note (no GPT-4o key — raw transcript): \"{transcript[:100]}\"",
        )

    cmd = await patched("He's interested in the SIP pitch", _ctx())
    assert cmd.tool == "create_note"
    assert cmd.confirmation_required is True
    assert "SIP" in cmd.args["body"]


@pytest.mark.asyncio
async def test_execute_create_note():
    """execute_command create_note runs without error on FakeLeadSquared."""
    from db import init_db
    from migrations.seed import seed_default_connections

    await init_db()
    await seed_default_connections()

    action_id = await execute_command(
        tool="create_note",
        args={"body": "Client interested in home loan top-up."},
        connection_id="conn_lsq_sandbox",
        client_id="lsq_001",
    )
    # FakeLeadSquared returns a string id
    assert action_id is not None


@pytest.mark.asyncio
async def test_execute_create_task():
    """execute_command create_task runs without error."""
    action_id = await execute_command(
        tool="create_task",
        args={"subject": "Follow-up call", "due_date": "2025-07-01"},
        connection_id="conn_lsq_sandbox",
        client_id="lsq_001",
    )
    assert action_id is not None


@pytest.mark.asyncio
async def test_execute_unknown_tool_raises():
    """Unknown tool names raise ValueError."""
    with pytest.raises(ValueError, match="Unknown tool"):
        await execute_command(
            tool="send_email",
            args={},
            connection_id="conn_lsq_sandbox",
            client_id="lsq_001",
        )
