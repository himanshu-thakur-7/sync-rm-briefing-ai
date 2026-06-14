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
import time
from datetime import date
from typing import Optional

from fastapi import APIRouter, Request

from services import connection_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ringg-tools", tags=["ringg-tools"])

# Risk Radar takes ~5-15 Pipedrive HTTP calls per scan (3-10s wall-clock). Ringg's
# on-call tool timeout is ~5-10s, so an uncached scan during a live call frequently
# times out → the agent falls back to its apology line. A short cache lets the
# second-and-subsequent calls return instantly while keeping the data fresh.
_RADAR_CACHE: dict[str, tuple[float, list]] = {}
# 10 min — comfortably above the keep-alive cron interval (5 min), so the
# agent's tool call always lands on a warm cache. For the demo the underlying
# Pipedrive data won't change in 10 min.
_RADAR_CACHE_TTL = 600


async def _cached_radar(connection_id: str) -> list:
    now = time.time()
    hit = _RADAR_CACHE.get(connection_id)
    if hit and (now - hit[0]) < _RADAR_CACHE_TTL:
        return hit[1]
    from services.risk_radar import scan
    plays = list(await scan(connection_id))
    _RADAR_CACHE[connection_id] = (now, plays)
    return plays


async def prewarm_radar() -> None:
    """Pre-run the radar on the default connection so the first agent call
    after a Render cold-start gets an instant cache hit."""
    try:
        cid = await connection_registry.default_connection_id()
        await _cached_radar(cid)
        logger.info("Radar cache prewarmed for %s", cid)
    except Exception as e:
        logger.warning("Radar prewarm skipped: %s", e)


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


# ─── top_priority ──────────────────────────────────────────────────────────
# "What's my top priority right now?" — runs the Risk Radar on the live CRM
# and returns the highest-urgency client with a one-paragraph spoken brief.

_URGENCY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


@router.api_route("/top_priority", methods=["GET", "POST"])
async def top_priority(request: Request):
    p = await _params(request)
    call_id = str(p.get("call_id") or "ringg_live")
    connection_id = await _connection_id()

    try:
        # Cached (TTL 60s) — keeps tool calls under Ringg's timeout.
        plays = list(await _cached_radar(connection_id))
    except Exception as e:
        logger.warning("ringg-tools top_priority scan failed: %s", e)
        plays = []
    plays.sort(key=lambda x: -_URGENCY_RANK.get(x.urgency, 0))

    if not plays:
        return _ok("Good news — no critical accounts flagged right now. Want me to pull a specific client?")

    top = plays[0]
    # Tight, callable. 2 sentences max + a closer. Verbose answers on a phone
    # feel robotic and get truncated by TTS.
    first = top.client_name.split(" ")[0]
    headline = f"Your top priority is {top.client_name} — {top.urgency.lower()} urgency."
    # Skip the full rationale (often 1-2 sentences) — keep it punchy.
    obj = (top.objective or "").strip()
    if obj and len(obj) <= 140:
        play = f" The play: {obj}."
    else:
        play = ""
    closer = f" Want the full brief, or shall I get {first} on the line?"
    spoken = (headline + play + closer).strip()
    # Safety cap.
    if len(spoken) > 480:
        spoken = spoken[:477].rsplit(" ", 1)[0] + "…"

    try:
        from routers.webhooks import broadcast_event
        await broadcast_event({"type": "concierge_question", "data": {
            "call_id": call_id, "question": "top priority", "answer_preview": spoken[:140],
            "client_id": top.client_id, "client_name": top.client_name,
        }})
    except Exception:
        pass

    return _ok(spoken, client_id=top.client_id, client_name=top.client_name,
               urgency=top.urgency)


# ─── start_call_with ───────────────────────────────────────────────────────
# "Yes, connect me with him" — opens the bridge UI on the dashboard. We don't
# actually merge two PSTN legs here (Ringg's API doesn't expose conference);
# instead, the dashboard listens for a `bridge_open` WS event and renders the
# Whisper-Coached Bridge: RM speaks live via the open Ringg web-call, the
# CLIENT is voiced by an OpenAI role-play agent in the browser, and SYNC's
# coaching engine listens to both transcripts under one shared call_id.

@router.api_route("/start_call_with", methods=["GET", "POST"])
async def start_call_with(request: Request):
    p = await _params(request)
    hint = str(p.get("client_hint") or p.get("client") or p.get("name") or "").strip()
    call_id = str(p.get("call_id") or "ringg_live")
    # Live mode: when the dashboard toggles this on (or when an explicit
    # client_phone is passed) we actually DIAL the client's phone via Ringg's
    # outreach agent. Otherwise we fall back to the in-browser bridge with the
    # OpenAI client-agent role-playing the client.
    live_mode = str(p.get("live_mode", "")).lower() in ("1", "true", "yes")
    forced_phone = str(p.get("client_phone") or "").strip()
    connection_id = await _connection_id()

    target = None
    try:
        adapter = await connection_registry.crm_for(connection_id)
        if hint:
            matches = await adapter.search_client(hint)
            target = matches[0] if matches else None
        if target is None:
            # No client mentioned — fall back to the current top priority.
            plays = list(await _cached_radar(connection_id))
            if plays:
                matches = await adapter.search_client(plays[0].client_name)
                target = matches[0] if matches else None
    except Exception as e:
        logger.warning("ringg-tools start_call_with resolve failed: %s", e)

    if target is None:
        return _ok("I'm not sure which client to connect — say the name and I'll dial right away.")

    # Pull a tight client brief so the OpenAI client-agent role-plays accurately.
    brief = ""
    try:
        full = await adapter.get_client(target.client_id)
        if full:
            factors = ", ".join(full.risk.factors[:3]) if full.risk.factors else "no fresh flags"
            complaints = next((c for c in full.complaints if c.status in ("open", "escalated")), None)
            comp = f" Open complaint: {complaints.summary[:140]}." if complaints else ""
            cs = full.cross_sell[0].pitch_angle if full.cross_sell else ""
            brief = (f"{full.profile.name}, {full.profile.occupation} at {full.profile.company}. "
                     f"Risk {full.risk.score.replace('_',' ')}: {factors}.{comp} "
                     f"The bank wants to pitch: {cs[:140]}").strip()
    except Exception:
        pass

    bridge_id = f"bridge_{target.client_id}_{call_id[-6:]}"

    # ── Place a REAL call to the client phone via Twilio (or Ringg fallback) ──
    from config import settings as _settings
    from routers.demo import get_demo_phone_override
    twilio_ready = bool(_settings.twilio_account_sid and _settings.twilio_auth_token)
    # Priority: UI-entered phone (stored via /demo/phone) > request param > env var
    ui_phone = get_demo_phone_override()
    if live_mode or forced_phone or ui_phone or twilio_ready:
        client_phone = (forced_phone or ui_phone or _settings.demo_client_phone or "").strip()
        if not client_phone:
            return _ok("I have Twilio ready but no phone number to dial. Enter a number in the phone field on the dashboard and try again.")

        # Prefer Twilio direct dial (RM browser ↔ client phone via Voice JS).
        if _settings.twilio_account_sid and _settings.twilio_auth_token:
            import uuid as _uuid
            call_key = _uuid.uuid4().hex[:12]

            # Register a coached-call session so the media stream WS + coaching work.
            from routers.coached_calls import _SESSIONS
            _SESSIONS[call_key] = {
                "client_id": target.client_id,
                "client_name": target.name,
                "rm_name": _settings.demo_rm_name,
                "connection_id": connection_id,
                "client_phone": client_phone,
                "lines": [],
                "started_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
            }

            from routers.webhooks import broadcast_event
            await broadcast_event({"type": "bridge_open", "data": {
                "call_id": call_key, "bridge_id": bridge_id,
                "client_id": target.client_id, "client_name": target.name,
                "client_brief": brief, "connection_id": connection_id,
                "mode": "twilio", "call_key": call_key,
                "client_phone": client_phone,
            }})
            return _ok(
                f"Connecting you to {target.name.split(' ')[0]} now. "
                "Your browser will place the call — I'll listen and coach on your dashboard.",
                bridge_id=bridge_id, mode="twilio",
                client_id=target.client_id, client_name=target.name,
                call_key=call_key,
            )

        # Fallback: Ringg outreach agent (legacy path).
        if not _settings.ringg_outreach_agent_id or not _settings.ringg_api_key:
            return _ok("Live mode needs Twilio or Ringg outreach configured — falling back to the in-browser bridge.")

        try:
            from services.ringg_service import RinggService
            ringg = RinggService()
            custom_args = {
                "client_name": target.name,
                "opening_line": (
                    f"Hi {target.name.split(' ')[0]}, this is SYNC calling on behalf of "
                    f"{_settings.demo_company_name}. I have your relationship manager on the line — "
                    "is this a good time to talk for a few minutes?"
                ),
                "objective": "Briefly identify the customer and hand off to the relationship manager.",
                "rm_name": "Himanshu",
                "company_name": _settings.demo_company_name,
                "friendly_closer": "Have a great day.",
                "hinglish_closer": "Have a great day.",
            }
            outbound_call_id = await ringg.initiate_outreach_call(
                outreach_agent_id=_settings.ringg_outreach_agent_id,
                from_number_id=_settings.ringg_from_number_id,
                client_phone=client_phone,
                client_name=target.name,
                custom_args=custom_args,
                callback_url=f"{_settings.backend_url.rstrip('/')}/api/v1/webhooks/ringg",
                transfer_to_number=_settings.demo_rm_phone or "",
            )
            from routers.webhooks import broadcast_event
            await broadcast_event({"type": "bridge_open", "data": {
                "call_id": call_id, "bridge_id": bridge_id,
                "client_id": target.client_id, "client_name": target.name,
                "client_brief": brief, "connection_id": connection_id,
                "mode": "live", "outbound_call_id": outbound_call_id,
                "client_phone": client_phone,
            }})
            return _ok(
                f"Dialing {target.name.split(' ')[0]} on {client_phone[-4:].rjust(len(client_phone), '*')} now. "
                "I'll stay on the line and listen — tips show up on your screen as we talk.",
                bridge_id=bridge_id, mode="live",
                client_id=target.client_id, client_name=target.name,
                outbound_call_id=outbound_call_id,
            )
        except Exception as e:
            logger.warning("ringg-tools live-mode dial failed: %s", e)
            # Fall through to the simulated bridge so the demo never dies.

    # ── Simulated mode: dashboard opens the OpenAI client-agent bridge ──
    try:
        from routers.webhooks import broadcast_event
        await broadcast_event({"type": "bridge_open", "data": {
            "call_id": call_id, "bridge_id": bridge_id,
            "client_id": target.client_id, "client_name": target.name,
            "client_brief": brief, "connection_id": connection_id, "mode": "simulated",
        }})
    except Exception:
        pass

    spoken = (f"Connecting you to {target.name.split(' ')[0]} now. "
              "I'll stay on the line and listen — you'll see my tips on screen as we go.")
    return _ok(spoken, bridge_id=bridge_id, mode="simulated",
               client_id=target.client_id, client_name=target.name)
