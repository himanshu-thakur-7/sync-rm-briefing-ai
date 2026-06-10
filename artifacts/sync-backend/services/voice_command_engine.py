"""Voice command engine — transcription + GPT-4o function-call parsing.

Pipeline:
  1. transcribe(audio_bytes) → str
       OpenAI Whisper first; Deepgram fallback if DEEPGRAM_API_KEY set.

  2. parse_command(transcript, context) → ParsedCommand
       GPT-4o with function calling. Resolves anaphora from CommandContext
       (which client is active, recent briefing log, RM identity).
       Returns tool name + args + confirmation_required + dry_run_preview.

Tools exposed to GPT-4o:
  create_note, create_task, update_contact_field,
  mark_complaint_resolved, mark_complaint_escalated,
  schedule_follow_up, log_meeting_outcome, flag_for_manager_review

Destructive or date-inferred actions set confirmation_required=True.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Data models ──────────────────────────────────────────────────────────

@dataclass
class CommandContext:
    active_connection_id: str
    active_client_id: Optional[str] = None
    active_client_name: Optional[str] = None
    rm_name: Optional[str] = None
    recent_briefing_summary: Optional[str] = None


@dataclass
class ParsedCommand:
    tool: str
    args: dict[str, Any]
    confirmation_required: bool
    dry_run_preview: str


# ─── GPT-4o tool schemas ──────────────────────────────────────────────────

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "create_note",
            "description": "Add a note to the active client's CRM record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "body": {"type": "string", "description": "Note text"},
                },
                "required": ["body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a follow-up task or reminder for the active client.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Task title"},
                    "due_date": {"type": "string", "description": "ISO 8601 date, e.g. 2025-06-15"},
                    "notes": {"type": "string", "description": "Additional notes for the task"},
                },
                "required": ["subject", "due_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_contact_field",
            "description": "Update a specific field on the active client's CRM contact record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "description": "CRM field name"},
                    "value": {"type": "string", "description": "New value"},
                },
                "required": ["field", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_complaint_resolved",
            "description": "Mark the client's open complaint as resolved.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_complaint_escalated",
            "description": "Escalate the client's open complaint to senior management.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_follow_up",
            "description": "Schedule a follow-up call or meeting with the active client.",
            "parameters": {
                "type": "object",
                "properties": {
                    "when": {"type": "string", "description": "ISO 8601 datetime, e.g. 2025-06-15T10:00:00"},
                    "kind": {"type": "string", "enum": ["call", "meeting", "email", "branch_visit"]},
                    "notes": {"type": "string"},
                },
                "required": ["when", "kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_meeting_outcome",
            "description": "Log the outcome or key points from a just-completed client meeting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "outcome": {"type": "string", "description": "Summary of meeting outcome"},
                    "next_action": {"type": "string"},
                },
                "required": ["outcome"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_for_manager_review",
            "description": "Flag the active client's account for manager review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                },
                "required": ["reason"],
            },
        },
    },
]

# Which tools require explicit confirmation before execution
_REQUIRES_CONFIRMATION = {
    "mark_complaint_escalated",
    "update_contact_field",
    "flag_for_manager_review",
}
# Tools that involve date inference also get confirmation_required=True


def _dry_run_preview(tool: str, args: dict, ctx: CommandContext) -> str:
    client = ctx.active_client_name or ctx.active_client_id or "the client"
    today = date.today().strftime("%a %b %d")
    previews = {
        "create_note": f"Add note to {client}: \"{args.get('body', '')}\"",
        "create_task": f"Create task '{args.get('subject', '')}' for {client}, due {args.get('due_date', '')}.",
        "update_contact_field": f"Update {client}'s {args.get('field', '')} → \"{args.get('value', '')}\"",
        "mark_complaint_resolved": f"Mark {client}'s open complaint as resolved.",
        "mark_complaint_escalated": f"Escalate {client}'s complaint to senior management.",
        "schedule_follow_up": f"Schedule {args.get('kind', 'follow-up')} with {client} on {args.get('when', '')}.",
        "log_meeting_outcome": f"Log meeting outcome for {client}: \"{args.get('outcome', '')}\"",
        "flag_for_manager_review": f"Flag {client} for manager review: \"{args.get('reason', '')}\"",
    }
    return previews.get(tool, f"Execute {tool} on {client}.")


# ─── Transcription ────────────────────────────────────────────────────────

async def transcribe(audio_bytes: bytes, content_type: str = "audio/webm") -> str:
    """Transcribe audio for the dashboard mic's server path.

    Priority:
      1. Ringg Parrot STT (ringglabs SDK) — keeps voice on Ringg end-to-end,
         supports Hindi/English/code-mixed. Uses ringg_stt_api_key, falling
         back to ringg_api_key in case the same key works.
      2. OpenAI Whisper — only if Ringg STT is unavailable/fails.
      3. A clear message if neither is configured.

    (Note: the live phone calls never reach here — Ringg transcribes those
    inside the call pipeline. This is only the push-to-talk dashboard mic on
    browsers without the Web Speech API.)
    """
    from config import settings

    # ── 1. Ringg Parrot STT ────────────────────────────────────────────────
    stt_key = settings.ringg_stt_api_key or settings.ringg_api_key
    if stt_key:
        try:
            text = await _ringg_transcribe(audio_bytes, content_type, stt_key)
            if text:
                logger.info("Transcribed via Ringg Parrot STT (%d chars)", len(text))
                return text
        except Exception as e:
            logger.warning("Ringg STT failed, falling back to Whisper: %s", e)

    # ── 2. OpenAI Whisper fallback ─────────────────────────────────────────
    if settings.openai_api_key:
        try:
            import io
            import openai
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "recording.webm"
            response = await client.audio.transcriptions.create(
                model="whisper-1", file=audio_file, language="en",
            )
            return response.text.strip()
        except Exception as e:
            logger.error("Whisper transcription failed: %s", e)
            raise

    return "[transcription unavailable — set RINGG_STT_API_KEY or OPENAI_API_KEY]"


async def _ringg_transcribe(audio_bytes: bytes, content_type: str, api_key: str) -> str:
    """Transcribe a single audio blob via Ringg Parrot STT (ringglabs)."""
    from config import settings

    # Lazy import so a missing SDK never blocks startup — we just fall back.
    from ringglabs.stt import AsyncClient  # type: ignore

    async with AsyncClient(api_key=api_key) as client:
        result = await client.transcribe(
            audio_bytes,
            language=settings.ringg_stt_language or "en",
            enable_cap_punc=True,
            content_type=content_type or "audio/webm",
        )
    # RestTranscriptionResult.transcription holds the text.
    return (getattr(result, "transcription", "") or "").strip()


# ─── Command parsing ──────────────────────────────────────────────────────

async def parse_command(transcript: str, ctx: CommandContext) -> ParsedCommand:
    """Use GPT-4o function calling to extract the intended CRM action."""
    from config import settings
    if not settings.openai_api_key:
        # Graceful fallback: create a note with the raw transcript
        return ParsedCommand(
            tool="create_note",
            args={"body": transcript},
            confirmation_required=True,
            dry_run_preview=f"Add note (no GPT-4o key — raw transcript): \"{transcript[:100]}\"",
        )

    try:
        import openai
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        system = f"""You are SYNC, a voice AI assistant helping Relationship Managers and Advisors log CRM actions hands-free.

Today is {date.today().isoformat()}.
Active client: {ctx.active_client_name or "unknown"} (ID: {ctx.active_client_id or "unknown"}).
RM: {ctx.rm_name or "unknown"}.
{f"Recent briefing: {ctx.recent_briefing_summary}" if ctx.recent_briefing_summary else ""}

When the RM says a command, map it to the best available function call.
- Resolve relative dates ("next Tuesday", "end of week") to ISO 8601 absolute dates.
- "him", "her", "them", "the client" all refer to the active client above.
- If you infer a date or time the RM didn't explicitly speak, set confirmation_required=true.
- Prefer create_note for vague or multi-intent commands you can't cleanly map.
- Always return exactly one function call.
"""

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": transcript},
            ],
            tools=_TOOL_SCHEMAS,
            tool_choice="required",
            max_tokens=300,
        )

        msg = response.choices[0].message
        if not msg.tool_calls:
            raise ValueError("GPT-4o returned no tool call")

        tc = msg.tool_calls[0]
        tool_name = tc.function.name
        try:
            args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            args = {}

        # Determine if confirmation is required
        needs_confirm = tool_name in _REQUIRES_CONFIRMATION
        # Also require confirmation when date was inferred
        if tool_name in ("create_task", "schedule_follow_up"):
            raw_date = args.get("when", args.get("due_date", ""))
            # If transcript doesn't contain the date string literally, it was inferred
            if raw_date and raw_date not in transcript:
                needs_confirm = True

        preview = _dry_run_preview(tool_name, args, ctx)
        return ParsedCommand(
            tool=tool_name,
            args=args,
            confirmation_required=needs_confirm,
            dry_run_preview=preview,
        )

    except Exception as e:
        logger.error("GPT-4o command parse failed: %s", e)
        # Fallback to create_note
        return ParsedCommand(
            tool="create_note",
            args={"body": transcript},
            confirmation_required=True,
            dry_run_preview=f"Add note (parse failed): \"{transcript[:100]}\"",
        )


# ─── Command execution ────────────────────────────────────────────────────

async def execute_command(
    tool: str,
    args: dict,
    connection_id: str,
    client_id: Optional[str],
) -> str:
    """Execute the parsed command on the active CRM adapter. Returns action_id."""
    from services import connection_registry

    adapter = await connection_registry.crm_for(connection_id)

    if tool == "create_note":
        return await adapter.create_note(client_id or "", args.get("body", ""))

    if tool == "create_task":
        return await adapter.create_task(
            client_id or "",
            args.get("subject", "SYNC Task"),
            args.get("due_date", date.today().isoformat()),
        )

    if tool == "update_contact_field":
        await adapter.update_contact_field(client_id or "", args.get("field", ""), args.get("value", ""))
        return "updated"

    if tool == "mark_complaint_resolved":
        clients = await adapter.get_client(client_id or "")
        if clients and clients.complaints:
            cid = next((c.id for c in clients.complaints if c.status in ("open", "escalated")), None)
            if cid:
                await adapter.update_complaint_status(cid, "resolved")
                return cid
        return "no_open_complaint"

    if tool == "mark_complaint_escalated":
        clients = await adapter.get_client(client_id or "")
        if clients and clients.complaints:
            cid = next((c.id for c in clients.complaints if c.status == "open"), None)
            if cid:
                await adapter.update_complaint_status(cid, "escalated")
                return cid
        return "no_open_complaint"

    if tool == "schedule_follow_up":
        return await adapter.schedule_follow_up(
            client_id or "",
            args.get("when", date.today().isoformat()),
            args.get("kind", "call"),
            args.get("notes", ""),
        )

    if tool in ("log_meeting_outcome", "flag_for_manager_review"):
        note = args.get("outcome", "") or args.get("reason", "")
        return await adapter.create_note(client_id or "", f"[{tool}] {note}")

    raise ValueError(f"Unknown tool: {tool}")
