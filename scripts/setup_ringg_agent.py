"""
Create the SYNC Ringg AI agent.

Usage:
  RINGG_API_KEY=xxx python scripts/setup_ringg_agent.py
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "artifacts" / "sync-backend"
sys.path.insert(0, str(BACKEND))

from config import settings  # noqa: E402
from services.ringg_service import ringg_service  # noqa: E402


async def main() -> None:
    """Create the Ringg agent and print the generated agent id."""
    if not settings.ringg_api_key:
        raise SystemExit("RINGG_API_KEY is required")

    config_path = ROOT / "ringg" / "agent-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    voices = await ringg_service.get_voices("en-IN")
    if voices:
        print(f"Found {len(voices)} en-IN voices")

    agent_id = await ringg_service.create_agent(config)
    print(f"RINGG_AGENT_ID={agent_id}")

    webhook_url = f"{settings.backend_url}/api/v1/webhooks/ringg" if settings.backend_url else ""
    if webhook_url:
        await ringg_service.setup_webhooks(agent_id, webhook_url)
        print("Webhooks configured for briefing agent")

    # ── Round 2: create the client-facing SYNC Outreach agent ──────────────
    outreach_path = ROOT / "ringg" / "outreach-agent-config.json"
    if outreach_path.exists():
        outreach_config = json.loads(outreach_path.read_text(encoding="utf-8"))
        outreach_id = await ringg_service.create_agent(outreach_config)
        print(f"RINGG_OUTREACH_AGENT_ID={outreach_id}")
        if webhook_url:
            await ringg_service.setup_webhooks(outreach_id, webhook_url)
            print("Webhooks configured for outreach agent")

    # ── Round 3: create the conversational SYNC Morning Brief agent ────────
    brief_path = ROOT / "ringg" / "morning-brief-agent-config.json"
    if brief_path.exists():
        brief_config = json.loads(brief_path.read_text(encoding="utf-8"))
        brief_id = await ringg_service.create_agent(brief_config)
        print(f"RINGG_MORNING_BRIEF_AGENT_ID={brief_id}")
        if webhook_url:
            await ringg_service.setup_webhooks(brief_id, webhook_url)
            print("Webhooks configured for morning brief agent")
        print(
            "\nNOTE: The Morning Brief agent uses mid-call function tools "
            "(ask_crm, log_action). Their endpoints are templated as "
            "{{mid_call_tool_url}}/{{call_id}}/ask and /act — they're filled "
            "in by ringg_service.initiate_morning_brief_call at call time."
        )


if __name__ == "__main__":
    asyncio.run(main())
