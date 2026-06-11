"""Coached Calls — a real RM ↔ client phone call with SYNC listening live.

Two routes to get SYNC's ear onto the call:

  PRIMARY · "twilio" — click-to-call bridging. Twilio dials the RM first,
  then bridges in the client. A <Start><Stream> fork sends both legs' audio
  to our WebSocket in real time; we transcribe rolling windows (Ringg STT →
  Whisper cascade) and feed lines into the existing emit_transcript_chunk()
  pipeline — which streams the transcript to the dashboard AND fires the
  whisper-coaching engine. Both parties are on ordinary phone calls.

  BACKUP · "ringg" — the silent chaperone. SYNC's Ringg outreach agent dials
  the client ("Connecting you to your relationship manager…"), transfers in
  the RM, and — if Ringg's transfer is conference-style — stays on the line
  transcribing, so transcript_chunk webhooks keep flowing and coaching keeps
  firing. Validate on a real call before relying on it.

Endpoints:
  GET  /api/v1/coached-calls/status         → which routes are configured
  POST /api/v1/coached-calls/start          → place a coached call
  GET|POST /api/v1/coached-calls/twiml      → TwiML for the Twilio RM leg
  WS   /api/v1/coached-calls/media/{key}    → Twilio Media Streams sink
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import struct
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/coached-calls", tags=["coached-calls"])

# ─── In-memory session registry (keyed by our call_key) ───────────────────

_SESSIONS: dict[str, dict] = {}

# ─── μ-law → 16-bit PCM decode table (pure Python; audioop is gone in 3.13) ─

def _build_mulaw_table() -> list[int]:
    table = []
    for byte in range(256):
        u = ~byte & 0xFF
        sign = u & 0x80
        exponent = (u >> 4) & 0x07
        mantissa = u & 0x0F
        sample = ((mantissa << 3) + 0x84) << exponent
        sample -= 0x84
        table.append(-sample if sign else sample)
    return table

_MULAW = _build_mulaw_table()


def _mulaw_to_pcm16(data: bytes) -> bytes:
    return struct.pack(f"<{len(data)}h", *(_MULAW[b] for b in data))


def _pcm16_to_wav(pcm: bytes, sample_rate: int = 8000) -> bytes:
    """Wrap raw mono PCM16 in a minimal WAV container."""
    buf = io.BytesIO()
    byte_rate = sample_rate * 2
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + len(pcm)))
    buf.write(b"WAVEfmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, byte_rate, 2, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", len(pcm)))
    buf.write(pcm)
    return buf.getvalue()


def _mean_abs(pcm: bytes) -> float:
    if not pcm:
        return 0.0
    samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    return sum(abs(s) for s in samples) / len(samples)


# ─── Request/response models ───────────────────────────────────────────────

class StartRequest(BaseModel):
    client_id: str = ""
    client_name: str = "the client"
    client_phone: Optional[str] = None    # falls back to DEMO_CLIENT_PHONE
    rm_phone: Optional[str] = None        # falls back to DEMO_RM_PHONE
    rm_name: str = "the RM"
    connection_id: Optional[str] = None
    route: str = "auto"                   # auto | twilio | ringg


def _twilio_ready() -> bool:
    return bool(settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number)


@router.get("/status")
async def coached_status():
    return {
        "twilio": {"configured": _twilio_ready(), "from_number": settings.twilio_from_number or None},
        "ringg_chaperone": {"configured": bool(settings.ringg_api_key and settings.ringg_outreach_agent_id)},
        "active_route": "twilio" if _twilio_ready() else (
            "ringg" if settings.ringg_api_key else "none"
        ),
    }


# ─── Start a coached call ──────────────────────────────────────────────────

@router.post("/start")
async def start_coached_call(body: StartRequest):
    client_phone = body.client_phone or settings.demo_client_phone
    rm_phone = body.rm_phone or settings.demo_rm_phone
    route = body.route
    if route == "auto":
        route = "twilio" if _twilio_ready() else "ringg"

    if route == "twilio":
        if not _twilio_ready():
            raise HTTPException(400, "Twilio is not configured — set TWILIO_ACCOUNT_SID / AUTH_TOKEN / FROM_NUMBER")
        return await _start_twilio_bridge(body, client_phone, rm_phone)

    if route == "ringg":
        return await _start_ringg_chaperone(body, client_phone, rm_phone)

    raise HTTPException(400, f"Unknown route {route!r}")


async def _start_twilio_bridge(body: StartRequest, client_phone: str, rm_phone: str) -> dict:
    """Dial the RM first; TwiML then forks media to our WS and dials the client."""
    call_key = uuid.uuid4().hex[:12]
    _SESSIONS[call_key] = {
        "client_id": body.client_id,
        "client_name": body.client_name,
        "rm_name": body.rm_name,
        "connection_id": body.connection_id,
        "client_phone": client_phone,
        "lines": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    base = settings.backend_url.rstrip("/")
    twiml_url = f"{base}/api/v1/coached-calls/twiml?key={call_key}"

    sid = settings.twilio_account_sid
    async with httpx.AsyncClient(timeout=20, auth=(sid, settings.twilio_auth_token)) as client:
        resp = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
            data={
                "To": rm_phone,
                "From": settings.twilio_from_number,
                "Url": twiml_url,
                "Method": "GET",
            },
        )
        if resp.status_code >= 400:
            logger.error("Twilio call create failed: %s %s", resp.status_code, resp.text[:300])
            raise HTTPException(502, f"Twilio error {resp.status_code}: {resp.text[:200]}")
        twilio_sid = resp.json().get("sid", "")

    _SESSIONS[call_key]["twilio_sid"] = twilio_sid

    from routers.webhooks import broadcast_event
    await broadcast_event({"type": "coached_call_started", "data": {
        "call_id": call_key, "route": "twilio", "client_name": body.client_name,
    }})
    logger.info("Coached call (twilio) %s → RM %s, client %s", call_key, rm_phone, client_phone)
    return {"call_id": call_key, "route": "twilio", "twilio_sid": twilio_sid,
            "message": f"Calling {body.rm_name}'s phone now; the client is bridged in when you answer."}


async def _start_ringg_chaperone(body: StartRequest, client_phone: str, rm_phone: str) -> dict:
    """Backup: Ringg outreach agent greets the client, transfers the RM in,
    and (if the transfer is conference-style) stays on the line transcribing."""
    from services.ringg_service import RinggService

    if not settings.ringg_outreach_agent_id:
        raise HTTPException(400, "RINGG_OUTREACH_AGENT_ID not configured")

    first = (body.client_name or "there").split()[0]
    custom_args = {
        "client_name": body.client_name,
        "opening_line": (
            f"Hi {first}! This is SYNC from {settings.demo_company_name}. "
            f"I have {body.rm_name} on the line for you — connecting you now, one moment."
        ),
        "objective": (
            "Transfer this call to the relationship manager immediately after the greeting. "
            "After the transfer, remain completely silent — do not speak again for the rest "
            "of the call unless directly addressed by name."
        ),
        "key_points": "",
        "offer": "",
        "rm_name": body.rm_name,
        "company_name": settings.demo_company_name,
        "compliance_disclaimer": "This call may be recorded for quality.",
        "friendly_closer": "Have a great day.",
        "hinglish_closer": "Have a great day.",
    }

    ringg = RinggService()
    call_id = await ringg.initiate_outreach_call(
        outreach_agent_id=settings.ringg_outreach_agent_id,
        from_number_id=settings.ringg_from_number_id,
        client_phone=client_phone,
        client_name=body.client_name,
        custom_args=custom_args,
        callback_url=f"{settings.backend_url.rstrip('/')}/api/v1/webhooks/ringg",
        transfer_to_number=rm_phone,
    )

    from routers.webhooks import broadcast_event
    await broadcast_event({"type": "coached_call_started", "data": {
        "call_id": call_id, "route": "ringg", "client_name": body.client_name,
    }})
    return {"call_id": call_id, "route": "ringg",
            "message": "SYNC is dialing the client and will transfer you in. "
                       "If Ringg keeps transcribing post-transfer, coaching stays live."}


# ─── TwiML for the RM leg ──────────────────────────────────────────────────

@router.api_route("/twiml", methods=["GET", "POST"])
async def coached_twiml(key: str = Query(...)):
    sess = _SESSIONS.get(key)
    if sess is None:
        return Response(content="<Response><Say>Session not found.</Say></Response>",
                        media_type="application/xml")

    ws_base = settings.backend_url.rstrip("/")
    ws_base = ws_base.replace("https://", "wss://").replace("http://", "ws://")
    stream_url = f"{ws_base}/api/v1/coached-calls/media/{key}"
    client_phone = sess["client_phone"]

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Start>
    <Stream url="{stream_url}" track="both_tracks" />
  </Start>
  <Say voice="alice">Sync is on the line. Whisper coaching is live on your dashboard. Connecting your client now.</Say>
  <Dial callerId="{settings.twilio_from_number}">
    <Number>{client_phone}</Number>
  </Dial>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


# ─── Twilio Media Streams sink ─────────────────────────────────────────────

# Flush a track's buffer for transcription once it holds ~3 s of audio.
_FLUSH_BYTES = 8000 * 3           # μ-law = 1 byte/sample @ 8 kHz
_ENERGY_GATE = 250.0              # mean |sample| below this ≈ silence — skip STT


@router.websocket("/media/{call_key}")
async def media_sink(websocket: WebSocket, call_key: str):
    await websocket.accept()
    sess = _SESSIONS.get(call_key)
    if sess is None:
        await websocket.close()
        return

    logger.info("Coached call %s: media stream connected", call_key)
    buffers: dict[str, bytearray] = {"inbound": bytearray(), "outbound": bytearray()}
    client_first = (sess.get("client_name") or "Client").split()[0]
    labels = {"inbound": sess.get("rm_name") or "RM", "outbound": client_first}
    summary = f"Live coached call between {labels['inbound']} (RM) and {sess.get('client_name')}"

    async def flush(track: str) -> None:
        data = bytes(buffers[track])
        buffers[track].clear()
        if not data:
            return
        pcm = _mulaw_to_pcm16(data)
        if _mean_abs(pcm) < _ENERGY_GATE:
            return  # silence window — don't burn an STT call
        wav = _pcm16_to_wav(pcm)
        try:
            from services.voice_command_engine import transcribe
            text = (await transcribe(wav, "audio/wav")).strip()
        except Exception as e:
            logger.warning("Coached call %s: STT failed: %s", call_key, e)
            return
        if not text or text.startswith("["):
            return
        line = f"{labels[track]}: {text}"
        sess["lines"].append(line)
        from routers.webhooks import emit_transcript_chunk
        await emit_transcript_chunk(call_key, line, client_summary=summary)

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event = msg.get("event")

            if event == "media":
                media = msg.get("media", {})
                track = media.get("track", "inbound")
                if track not in buffers:
                    buffers[track] = bytearray()
                    labels.setdefault(track, track)
                buffers[track].extend(base64.b64decode(media.get("payload", "")))
                if len(buffers[track]) >= _FLUSH_BYTES:
                    # Fire-and-forget so a ~1s STT round-trip never stalls the
                    # 20 ms media frame cadence.
                    asyncio.create_task(flush(track))

            elif event == "stop":
                break
            # "connected" / "start" / "mark" frames need no handling.
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("Coached call %s: media stream error: %s", call_key, e)
    finally:
        # Final flush of whatever's left, then close out the call.
        for track in list(buffers):
            try:
                await flush(track)
            except Exception:
                pass
        await _finish(call_key)


# ─── Simulation ("theater mode") ───────────────────────────────────────────
# Judges won't place real phone calls. The frontend plays a scripted RM↔client
# conversation with two TTS voices, but EVERY line is posted back here and runs
# through the real emit_transcript_chunk → coaching pipeline — so the whisper
# nudges in the demo are computed live, not pre-scripted.

def _build_sim_script(client_first: str, rm_first: str, company: str) -> list[dict]:
    return [
        {"speaker": "rm",     "text": f"Hi {client_first}, this is {rm_first} from {company}. Do you have two minutes?"},
        {"speaker": "client", "text": f"Oh hi {rm_first}. Yes, I have a few minutes."},
        {"speaker": "rm",     "text": "I was looking at your account this morning and wanted to talk about the business loan EMIs."},
        {"speaker": "client", "text": "To be honest, I have been a bit worried about the repayments lately. Cash flow has been tight."},
        {"speaker": "rm",     "text": "I completely understand. There is actually a way to bring your monthly outgo down quite a bit."},
        {"speaker": "client", "text": "Hmm. Last week another bank offered me a better rate on a balance transfer."},
        {"speaker": "rm",     "text": "Rates matter, but so does having everything under one roof with someone who knows your business."},
        {"speaker": "client", "text": "That's fair. Okay, tell me more about your option, that sounds good."},
        {"speaker": "rm",     "text": "We move your credit card balance into a personal loan. Same payment date, and you save about three lakh in interest this year."},
        {"speaker": "client", "text": "Three lakh? Let me think about it, maybe after this quarter."},
        {"speaker": "rm",     "text": "How about this — I will hold a slot Thursday at four PM and walk you through the numbers. No commitment."},
        {"speaker": "client", "text": "Okay, Thursday at four works."},
        {"speaker": "rm",     "text": f"Perfect, locking it in. I will send the details. Thanks {client_first}, talk Thursday!"},
    ]


class SimStartRequest(BaseModel):
    client_id: str = ""
    client_name: str = "Vikram Desai"
    rm_name: str = "Himanshu"
    connection_id: Optional[str] = None


class SimLineRequest(BaseModel):
    speaker: str   # "rm" | "client"
    text: str


@router.post("/simulate/start")
async def simulate_start(body: SimStartRequest):
    call_key = f"sim_{uuid.uuid4().hex[:10]}"
    client_first = (body.client_name or "the client").split()[0]
    rm_first = (body.rm_name or "the RM").split()[0]
    _SESSIONS[call_key] = {
        "client_id": body.client_id,
        "client_name": body.client_name,
        "rm_name": body.rm_name,
        "connection_id": body.connection_id,
        "client_phone": "",
        "lines": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "simulated": True,
    }

    from routers.webhooks import broadcast_event
    await broadcast_event({"type": "coached_call_started", "data": {
        "call_id": call_key, "route": "simulation", "client_name": body.client_name,
    }})
    return {
        "call_id": call_key,
        "script": _build_sim_script(client_first, rm_first, settings.demo_company_name),
        "labels": {"rm": rm_first, "client": client_first},
        "premium_tts": bool(settings.elevenlabs_api_key),
    }


# ─── Natural TTS for the theater (ElevenLabs, server-cached) ──────────────

class TTSRequest(BaseModel):
    text: str
    speaker: str  # "rm" | "client"


# In-memory audio cache — the sim script is fixed per (names, voice, model),
# so after the first full play every replay is served from RAM: zero credits.
_TTS_CACHE: dict[str, bytes] = {}
_TTS_CACHE_MAX = 200


@router.post("/tts")
async def theater_tts(body: TTSRequest):
    """Generate one dialogue line as natural speech via ElevenLabs.

    Returns audio/mpeg. 503 when no key is configured — the frontend then
    falls back to browser speechSynthesis, so the sim always works.
    """
    if not settings.elevenlabs_api_key:
        raise HTTPException(503, "ElevenLabs not configured (set ELEVENLABS_API_KEY)")
    if body.speaker not in ("rm", "client"):
        raise HTTPException(400, "speaker must be 'rm' or 'client'")
    text = body.text.strip()
    if not text or len(text) > 600:
        raise HTTPException(400, "text must be 1–600 chars")

    voice_id = settings.elevenlabs_voice_rm if body.speaker == "rm" else settings.elevenlabs_voice_client
    # Lower stability + style exaggeration = audibly human intonation, not a
    # flat screen-reader cadence. Settings ride in the cache key so tuning
    # them invalidates stale audio automatically.
    voice_settings = {
        "stability": 0.4,
        "similarity_boost": 0.8,
        "style": 0.4,
        "use_speaker_boost": True,
    }
    import hashlib
    settings_tag = f"s{voice_settings['stability']}-st{voice_settings['style']}"
    cache_key = hashlib.sha1(
        f"{voice_id}|{settings.elevenlabs_model}|{settings_tag}|{text}".encode()
    ).hexdigest()
    cached = _TTS_CACHE.get(cache_key)
    if cached:
        return Response(content=cached, media_type="audio/mpeg",
                        headers={"X-TTS-Cache": "hit"})

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            params={"output_format": "mp3_44100_64"},
            headers={"xi-api-key": settings.elevenlabs_api_key},
            json={"text": text, "model_id": settings.elevenlabs_model,
                  "voice_settings": voice_settings},
        )
    if resp.status_code >= 400:
        logger.warning("ElevenLabs TTS failed: %s %s", resp.status_code, resp.text[:200])
        raise HTTPException(502, f"TTS provider error {resp.status_code}")

    audio = resp.content
    if len(_TTS_CACHE) >= _TTS_CACHE_MAX:
        _TTS_CACHE.pop(next(iter(_TTS_CACHE)))
    _TTS_CACHE[cache_key] = audio
    return Response(content=audio, media_type="audio/mpeg",
                    headers={"X-TTS-Cache": "miss"})


@router.post("/simulate/{call_key}/line")
async def simulate_line(call_key: str, body: SimLineRequest):
    sess = _SESSIONS.get(call_key)
    if sess is None:
        raise HTTPException(404, "Simulation not found (or already ended)")
    label = (sess.get("rm_name") if body.speaker == "rm" else sess.get("client_name") or "Client").split()[0]
    line = f"{label}: {body.text}"
    sess["lines"].append(line)
    from routers.webhooks import emit_transcript_chunk
    await emit_transcript_chunk(
        call_key, line,
        client_summary=f"Live coached call between {sess.get('rm_name')} (RM) and {sess.get('client_name')}",
    )
    return {"ok": True}


@router.post("/simulate/{call_key}/end")
async def simulate_end(call_key: str):
    if call_key not in _SESSIONS:
        return {"ok": True, "note": "already ended"}
    await _finish(call_key)
    return {"ok": True}


async def _finish(call_key: str) -> None:
    sess = _SESSIONS.pop(call_key, None)
    if sess is None:
        return
    try:
        from services import coaching_engine
        coaching_engine.end_call(call_key)
    except Exception:
        pass

    from routers.webhooks import broadcast_event, run_post_call_analysis
    await broadcast_event({"type": "coached_call_completed", "data": {
        "call_id": call_key, "client_name": sess.get("client_name"),
        "lines": len(sess.get("lines", [])),
    }})

    transcript = "\n".join(sess.get("lines", []))
    if transcript:
        asyncio.create_task(run_post_call_analysis(
            call_key,
            transcript_override=transcript,
            call_kind="coached_call",
            connection_id=sess.get("connection_id"),
            client_id=sess.get("client_id"),
        ))
    logger.info("Coached call %s finished (%d transcript lines)", call_key, len(sess.get("lines", [])))
