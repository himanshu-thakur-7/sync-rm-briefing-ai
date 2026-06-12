"""Universal Ringg custom-tool endpoints — the agent's hands and eyes.

Ringg's public API has NO operation for attaching on-call tools; they are
configured in the Ringg dashboard (Agent → Tools → custom API tool). These
endpoints are the targets for that config:

    POST/GET /api/v1/ringg-tools/ask_crm      → live client briefing
    POST/GET /api/v1/ringg-tools/log_action   → create task / note / meeting …

Design constraints (learned the hard way):
- The dashboard tool-builder decides the request shape, so we accept params
  from query string, flat JSON body, or nested under arguments/parameters/
  args/input — whatever it sends.
- A non-200 or empty answer makes the agent say "I can't do that", so we
  ALWAYS return 200 with a `spoken` sentence (plus aliases answer/response/
  message/confirmation so any responseSelectedKeys choice works).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Request

from services import connection_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ringg-tools", tags=["ringg-tools"])


async def _params(request: Request) -> dict:
    """Merge query params + JSON body + common nesting wrappers into one dict."""
    out: dict = dict(request.query_params)
    try:
        body = await request.json()
        if isinstance(body, dict):
            out.update({k: v for k, v in body.items() if not isinstance(v, dict)})
            for wrapper in ("arguments", "parameters", "args", "input", "data"):
                inner = body.get(wrapper)
                if isinstance(inner, dict):
                    out.update(inner)
    except Exception:
        pass
    return out


def _ok(spoken: str, **extra) -> dict:
    return {
        "status": "success",
        "spoken": spoken,
        "answer": spoken,
        "response": spoken,
        "message": spoken,
        "confirmation": spoken,
        **extra,
    }


async def _connection_id() -> str:
    try:
        return await connection_registry.default_connection_id()
    except Exception:
        return "conn_pipedrive_demo"


# ─── ask_crm ───────────────────────────────────────────────────────────────

@router.api_route("/ask_crm", methods=["GET", "POST"])
async def ask_crm(request: Request):
    p = await _params(request)
    question = str(p.get("question") or p.get("query") or p.get("q") or "").strip()
    hint = str(p.get("client_hint") or p.get("client") or p.get("name") or "").strip()
    call_id = str(p.get("call_id") or "ringg_live")

    if not question and not hint:
        return _ok("Who do you need a sync on? Say the client's name.")

    try:
        from routers.concierge import _lookup_and_summarise
        connection_id = await _connection_id()
        answer = await _lookup_and_summarise(connection_id, hint or question)
    except Exception as e:
        logger.warning("ringg-tools ask_crm failed: %s", e)
        answer = "I'm having trouble reaching the CRM right now — give me a second and ask again."

    try:
        from routers.webhooks import broadcast_event
        await broadcast_event({"type": "concierge_question", "data": {
            "call_id": call_id, "question": question or hint, "answer_preview": answer[:140],
        }})
    except Exception:
        pass
    return _ok(answer)


# ─── log_action ────────────────────────────────────────────────────────────

@router.api_route("/log_action", methods=["GET", "POST"])
async def log_action(request: Request):
    p = await _params(request)
    intent = str(p.get("intent") or p.get("action") or "create_task").strip()
    details = str(p.get("details") or p.get("description") or p.get("text") or "").strip()
    hint = str(p.get("client_hint") or p.get("client") or p.get("name") or "").strip()
    call_id = str(p.get("call_id") or "ringg_live")

    if not details and not intent:
        return _ok("Tell me what to log — for example, create a follow-up task with Vikram for Thursday at 4 PM.")

    connection_id = await _connection_id()

    # Resolve the client: explicit hint first, else scan the details for a known first name.
    target = None
    try:
        adapter = await connection_registry.crm_for(connection_id)
        if hint:
            matches = await adapter.search_client(hint)
            target = matches[0] if matches else None
        if target is None and details:
            for c in await adapter.list_all():
                first = c.name.split(" ")[0].lower()
                if first and first in details.lower():
                    target = c
                    break
    except Exception as e:
        logger.warning("ringg-tools client resolve failed: %s", e)

    if target is None:
        return _ok("I couldn't tell which client that's for — say the name, like 'for Vikram'.")

    try:
        from services.voice_command_engine import CommandContext, execute_command, parse_command
        ctx = CommandContext(
            active_connection_id=connection_id,
            active_client_id=target.client_id,
            active_client_name=target.name,
        )
        parsed = await parse_command(f"{intent}: {details}", ctx)
        args = dict(parsed.args)
        for k in ("due_date", "when"):
            if k in args and not args[k]:
                args[k] = date.today().isoformat()
        action_id = await execute_command(parsed.tool, args, connection_id, target.client_id)
    except Exception as e:
        logger.warning("ringg-tools log_action failed: %s", e)
        return _ok("I tried to log that but the CRM pushed back — try once more, or do it from the dashboard.")

    try:
        from routers.webhooks import broadcast_event
        await broadcast_event({"type": "concierge_action_executed", "data": {
            "call_id": call_id, "tool": parsed.tool, "client_id": target.client_id,
            "client_name": target.name, "action_id": str(action_id),
        }})
    except Exception:
        pass

    spoken = f"Done — {parsed.dry_run_preview or parsed.tool.replace('_', ' ')} for {target.name}. It's in the CRM."
    return _ok(spoken, action_id=str(action_id), tool=parsed.tool, client=target.name)
