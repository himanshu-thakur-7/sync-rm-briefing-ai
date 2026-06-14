"""
Patch the live SYNC Concierge agent prompt without recreating it.
Self-contained — no pydantic_settings, no backend imports needed.

Usage (from repo root):
  RINGG_CONCIERGE_AGENT_ID=<id> python3 scripts/patch_concierge_prompt.py

Or just run it — if RINGG_CONCIERGE_AGENT_ID is in .env it will be picked up.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


# ── Load .env without any dependencies ───────────────────────────────────────

def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:   # env vars override .env
            os.environ[key] = val


load_env(ROOT / ".env")
load_env(ROOT / "artifacts" / "sync-backend" / ".env")


# ── Config ───────────────────────────────────────────────────────────────────

API_KEY   = os.environ.get("RINGG_API_KEY", "")
BASE_URL  = os.environ.get("RINGG_BASE_URL", "https://prod-api.ringg.ai/ca/api/v0").rstrip("/")
AGENT_ID  = os.environ.get("RINGG_CONCIERGE_AGENT_ID", "")

HEADERS = {
    "X-API-KEY": API_KEY,
    "Content-Type": "application/json",
}


# ── Prompt assembly ───────────────────────────────────────────────────────────

def assemble_prompt(config: dict) -> str:
    parts = []
    if v := config.get("introduction_and_objective", "").strip():
        parts.append(v)
    if v := config.get("guardrails", "").strip():
        parts.append("\n# GUARDRAILS\n\n" + v)
    if v := config.get("task", "").strip():
        parts.append("\n# TASK\n\n" + v)
    if v := config.get("response_guidelines", "").strip():
        parts.append("\n# RESPONSE GUIDELINES\n\n" + v)
    if v := config.get("faq", "").strip():
        parts.append("\n# FAQ\n\n" + v)
    if v := config.get("sample_conversations", "").strip():
        parts.append("\n# SAMPLE CONVERSATIONS\n\n" + v)
    return "\n".join(parts).strip()


# ── Ringg PATCH helper ────────────────────────────────────────────────────────

async def patch_agent(agent_id: str, operation: str, **fields) -> bool:
    payload = {"operation": operation, "agent_id": agent_id, **fields}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.patch(
                f"{BASE_URL}/agent/v1/",
                json=payload,
                headers=HEADERS,
            )
            if 200 <= resp.status_code < 300:
                return True
            print(f"  [WARN] {operation}: HTTP {resp.status_code} — {resp.text[:200]}")
            return False
        except Exception as e:
            print(f"  [ERROR] {operation}: {e}")
            return False


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    if not API_KEY:
        sys.exit("✗  RINGG_API_KEY not set — add it to .env or export it.")
    if not AGENT_ID:
        sys.exit(
            "✗  RINGG_CONCIERGE_AGENT_ID not set.\n"
            "   Run: RINGG_CONCIERGE_AGENT_ID=<id> python3 scripts/patch_concierge_prompt.py"
        )

    config_path = ROOT / "ringg" / "concierge-agent-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    prompt = assemble_prompt(config)
    intro  = config.get("intro_message", "")

    print(f"Agent  : {AGENT_ID}")
    print(f"API key: {API_KEY[:8]}…")
    print(f"Prompt : {len(prompt)} chars across {len(prompt.splitlines())} lines")
    print()

    ok_prompt = await patch_agent(AGENT_ID, "edit_prompt", agent_prompt=prompt)
    print(f"  edit_prompt        : {'✓' if ok_prompt else '✗ FAILED'}")

    if intro:
        ok_intro = await patch_agent(AGENT_ID, "edit_intro_message", intro_message=intro)
        print(f"  edit_intro_message : {'✓' if ok_intro else '✗ FAILED'}")

    print()
    if ok_prompt:
        print("✓ Done — prompt live. Make an inbound call to test.")
    else:
        print("✗ Prompt patch failed — double-check your API key and agent ID.")


if __name__ == "__main__":
    asyncio.run(main())
