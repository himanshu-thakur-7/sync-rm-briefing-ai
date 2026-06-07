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
    else:
        print("No en-IN voices returned from Ringg")

    # Pick a sane default voice_id from the voices response and inject it
    # into agent configs if missing. Ringg returns voice objects with keys
    # like 'voice_id', 'id' or 'voiceId' — handle the common shapes.
    def _pick_voice_id(voices_list):
        """Pick a sensible voice id from Ringg's voices response.

        Accepts:
        - a list of voice dicts
        - a dict like {"voices": [...]} or {"data": [...]} 
        - a dict mapping ids -> voice objects
        """
        if not voices_list:
            return None

        # Normalize common envelope shapes
        if isinstance(voices_list, dict):
            for candidate_key in ("voices", "data", "items", "results"):
                if candidate_key in voices_list and voices_list[candidate_key]:
                    voices_list = voices_list[candidate_key]
                    break

            # If still a dict, take the first value (e.g. {id: {...}})
            if isinstance(voices_list, dict):
                try:
                    first = next(iter(voices_list.values()))
                except StopIteration:
                    return None
            else:
                # now it's likely a list
                first = voices_list[0]
        else:
            # assume list-like
            try:
                first = voices_list[0]
            except Exception:
                return None

        if isinstance(first, dict):
            for key in ("voice_id", "voiceId", "id", "name"):
                if key in first and first[key]:
                    return first[key]
            # fallback: if the dict itself has an 'id' nested under some key
            for v in first.values():
                if isinstance(v, (str, int)):
                    return v
            return None

        if isinstance(first, (str, int)):
            return first

        return None

    default_voice_id = _pick_voice_id(voices)
    if default_voice_id:
        print(f"Using voice_id: {default_voice_id}")
        # inject into primary agent config if absent
        if "voice_id" not in config:
            config["voice_id"] = default_voice_id

    agent_id = await ringg_service.create_agent(config)
    print(f"RINGG_AGENT_ID={agent_id}")

    webhook_url = f"{settings.backend_url}/api/v1/webhooks/ringg" if settings.backend_url else ""
    from_number_id = settings.ringg_from_number_id

    if agent_id and from_number_id:
        await ringg_service.attach_from_number(agent_id, from_number_id)
    if agent_id and webhook_url:
        ok = await ringg_service.setup_webhooks(agent_id, webhook_url)
        if ok:
            print("Webhooks configured for briefing agent")

    # ── Round 2: create the client-facing SYNC Outreach agent ──────────────
    outreach_path = ROOT / "ringg" / "outreach-agent-config.json"
    if outreach_path.exists():
        outreach_config = json.loads(outreach_path.read_text(encoding="utf-8"))
        if default_voice_id and "voice_id" not in outreach_config:
            outreach_config["voice_id"] = default_voice_id
        outreach_id = await ringg_service.create_agent(outreach_config)
        print(f"RINGG_OUTREACH_AGENT_ID={outreach_id}")
        if outreach_id and from_number_id:
            await ringg_service.attach_from_number(outreach_id, from_number_id)
        if outreach_id and webhook_url:
            ok = await ringg_service.setup_webhooks(outreach_id, webhook_url)
            if ok:
                print("Webhooks configured for outreach agent")

    # ── Round 3: create the conversational SYNC Morning Brief agent ────────
    brief_path = ROOT / "ringg" / "morning-brief-agent-config.json"
    if brief_path.exists():
        brief_config = json.loads(brief_path.read_text(encoding="utf-8"))
        if default_voice_id and "voice_id" not in brief_config:
            brief_config["voice_id"] = default_voice_id
        brief_id = await ringg_service.create_agent(brief_config)
        print(f"RINGG_MORNING_BRIEF_AGENT_ID={brief_id}")
        if brief_id and from_number_id:
            await ringg_service.attach_from_number(brief_id, from_number_id)
        if brief_id and webhook_url:
            ok = await ringg_service.setup_webhooks(brief_id, webhook_url)
            if ok:
                print("Webhooks configured for morning brief agent")
        print(
            "\nNOTE: The Morning Brief agent uses mid-call function tools "
            "(ask_crm, log_action). Their endpoints are templated as "
            "{{mid_call_tool_url}}/{{call_id}}/ask and /act — they're filled "
            "in by ringg_service.initiate_morning_brief_call at call time."
        )


if __name__ == "__main__":
    asyncio.run(main())
