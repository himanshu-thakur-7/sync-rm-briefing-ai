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

    if settings.backend_url:
        await ringg_service.setup_webhooks(agent_id, f"{settings.backend_url}/api/v1/webhooks/ringg")
        print("Webhooks configured")


if __name__ == "__main__":
    asyncio.run(main())
