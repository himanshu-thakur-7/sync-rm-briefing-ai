"""
Upload SYNC client data as a Ringg knowledge base for inbound calls.

Usage:
  RINGG_API_KEY=xxx RINGG_AGENT_ID=xxx python scripts/upload_knowledge_base.py
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "artifacts" / "sync-backend"
sys.path.insert(0, str(BACKEND))

import database  # noqa: E402
from config import settings  # noqa: E402
from knowledge_base.client_kb_generator import generate_kb_document  # noqa: E402
from services.ringg_service import ringg_service  # noqa: E402


async def main() -> None:
    """Generate and upload the Ringg knowledge base document."""
    if not settings.ringg_api_key:
        raise SystemExit("RINGG_API_KEY is required")

    content = generate_kb_document(list(database.CLIENTS.values()))
    kb_id = await ringg_service.upload_knowledge_base("SYNC Client Briefing KB", content)
    print(f"RINGG_KB_ID={kb_id}")
    print("Attach this KB to the SYNC agent in the Ringg dashboard if your workspace requires manual linking.")


if __name__ == "__main__":
    asyncio.run(main())
