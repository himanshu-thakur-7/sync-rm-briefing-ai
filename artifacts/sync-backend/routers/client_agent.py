"""OpenAI-driven role-play client agent for the live whisper demo.

For the live submission demo we need a believable "client" speaking on the
call without scripting every dialogue line. This router stands up an
ephemeral persona per bridge: it's primed with the actual CRM profile (risk,
complaints, the bank's intended cross-sell) and converses in character.

  POST /api/v1/client-agent/{bridge_id}/start
       body: {client_id, client_name, brief, connection_id}
       → opens a per-bridge session; voice + opener returned

  POST /api/v1/client-agent/{bridge_id}/turn
       body: {rm_text}
       → next client reply (text + mp3 url)

  POST /api/v1/client-agent/{bridge_id}/end

Falls back gracefully when no OpenAI key — returns generic empathetic lines
so the demo never dead-ends.
"""
from __future__ import annotations

import io
import json
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/client-agent", tags=["client-agent"])

# bridge_id → {persona, history, voice, audio_cache:{turn_id: bytes}}
_SESSIONS: dict[str, dict] = {}

# OpenAI TTS voices that sound naturally human; tuned per gender hint.
_VOICE_MALE = "onyx"
_VOICE_FEMALE = "shimmer"


def _persona_for(first: str, female: bool) -> str:
    pronoun = "she" if female else "he"
    return (
        f"You are role-playing {first.title()}, a customer who is on a live "
        f"phone call with their relationship manager from a bank. {first.title()}'s "
        f"profile and current situation are below.\n\n"
        f"Stay strictly in character as {first.title()}. Reply ONLY with what "
        f"{pronoun} would say — never narrate, never break character, never reveal "
        "you are an AI. Keep each reply under 35 words, in spoken English, "
        "honest and a bit hesitant — you have real concerns. Mention specific "
        "details (your business, your worries, the EMIs, complaints) when they "
        "fit. If the RM proposes a meeting or a follow-up, AGREE on a time that "
        "sounds natural in conversation (e.g. 'Thursday at four works'). If the "
        "RM offers something genuinely helpful, soften your tone."
    )


class StartReq(BaseModel):
    client_id: str = ""
    client_name: str = "Customer"
    brief: str = ""
    connection_id: Optional[str] = None


class TurnReq(BaseModel):
    rm_text: str = ""


def _is_female(name: str) -> bool:
    first = (name or "").split(" ")[0].lower()
    return first in {"priya", "sneha"}


@router.post("/{bridge_id}/start")
async def start(bridge_id: str, body: StartReq):
    first = (body.client_name or "Customer").split(" ")[0]
    female = _is_female(body.client_name)
    persona = _persona_for(first, female)
    if body.brief:
        persona += f"\n\nCONTEXT FROM CRM:\n{body.brief}"

    _SESSIONS[bridge_id] = {
        "persona": persona,
        "history": [],            # list of {"role": "user"|"assistant", "content": str}
        "voice": _VOICE_FEMALE if female else _VOICE_MALE,
        "audio_cache": {},        # turn_id → mp3 bytes
        "client_name": body.client_name,
        "client_id": body.client_id,
        "started_at": time.time(),
    }

    opener = f"Hi, this is {first} — what's this about?"
    # Pre-generate the opener so the bridge UI plays it instantly.
    audio = await _tts(opener, _VOICE_FEMALE if female else _VOICE_MALE)
    turn_id = uuid.uuid4().hex[:10]
    if audio:
        _SESSIONS[bridge_id]["audio_cache"][turn_id] = audio
    _SESSIONS[bridge_id]["history"].append({"role": "assistant", "content": opener})

    return {
        "ok": True,
        "voice": _SESSIONS[bridge_id]["voice"],
        "opener": {"text": opener, "turn_id": turn_id, "audio_ready": bool(audio)},
    }


@router.post("/{bridge_id}/turn")
async def turn(bridge_id: str, body: TurnReq):
    sess = _SESSIONS.get(bridge_id)
    if sess is None:
        raise HTTPException(404, "bridge session not found (or already ended)")
    rm = (body.rm_text or "").strip()
    if rm:
        sess["history"].append({"role": "user", "content": rm})

    reply = await _client_reply(sess)
    sess["history"].append({"role": "assistant", "content": reply})

    turn_id = uuid.uuid4().hex[:10]
    audio = await _tts(reply, sess["voice"])
    if audio:
        sess["audio_cache"][turn_id] = audio
        # cap to last 8 turns of cached audio
        if len(sess["audio_cache"]) > 8:
            sess["audio_cache"].pop(next(iter(sess["audio_cache"])))

    return {"ok": True, "text": reply, "turn_id": turn_id, "audio_ready": bool(audio)}


@router.get("/{bridge_id}/audio/{turn_id}.mp3")
async def audio(bridge_id: str, turn_id: str):
    sess = _SESSIONS.get(bridge_id)
    if not sess or turn_id not in sess.get("audio_cache", {}):
        raise HTTPException(404, "audio not found")
    return Response(content=sess["audio_cache"][turn_id], media_type="audio/mpeg")


@router.post("/{bridge_id}/end")
async def end(bridge_id: str):
    _SESSIONS.pop(bridge_id, None)
    return {"ok": True}


# ─── OpenAI calls (best-effort, with deterministic fallbacks) ──────────────

async def _client_reply(sess: dict) -> str:
    key = (settings.openai_api_key or "").strip()
    if key:
        try:
            from openai import AsyncOpenAI
            oc = AsyncOpenAI(api_key=key,
                             base_url=settings.openai_base_url or None)
            messages = [{"role": "system", "content": sess["persona"]}] + sess["history"][-10:]
            resp = await oc.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=80,
                temperature=0.7,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
        except Exception as e:
            logger.warning("client-agent OpenAI reply failed: %s", e)
    # Fallback: a small bank of in-character lines so the demo always plays.
    n = len([m for m in sess["history"] if m["role"] == "assistant"])
    fallbacks = [
        "Honestly, things have been tight this quarter. The EMIs are a real pressure.",
        "Another bank actually offered me a better rate last week — I'm thinking about it.",
        "If you can really save me three lakh, I'd want to see the numbers.",
        "Okay, Thursday at four works for me.",
        "Thanks for jumping on this. Appreciate it.",
    ]
    return fallbacks[min(n - 1, len(fallbacks) - 1)] if n > 0 else "Hello?"


async def _tts(text: str, voice: str) -> bytes:
    key = (settings.openai_api_key or "").strip()
    if not key or not text.strip():
        return b""
    try:
        from openai import AsyncOpenAI
        oc = AsyncOpenAI(api_key=key,
                         base_url=settings.openai_base_url or None)
        resp = await oc.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice=voice,
            input=text,
            response_format="mp3",
        )
        return await resp.aread() if hasattr(resp, "aread") else resp.read()
    except Exception as e:
        logger.warning("client-agent TTS failed: %s", e)
        return b""
