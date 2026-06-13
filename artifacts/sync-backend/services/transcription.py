"""Transcription provider abstraction for SYNC coached calls.

Configure via SYNC_STT_PROVIDER env var:
  "openai"  (default) — OpenAI Whisper API
  "ringg"             — Ringg Parrot STT via ringglabs SDK
"""
from __future__ import annotations

import io
import logging
from abc import ABC, abstractmethod

from config import settings

logger = logging.getLogger(__name__)


class TranscriptionProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_wav: bytes) -> str:
        """Transcribe a WAV audio blob (mono PCM16 8kHz) and return the text."""
        ...


class OpenAITranscriber(TranscriptionProvider):
    async def transcribe(self, audio_wav: bytes) -> str:
        if not settings.openai_api_key:
            return ""
        import openai
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        buf = io.BytesIO(audio_wav)
        buf.name = "chunk.wav"
        resp = await client.audio.transcriptions.create(
            model="whisper-1", file=buf, language="en",
        )
        return resp.text.strip()


class RinggTranscriber(TranscriptionProvider):
    async def transcribe(self, audio_wav: bytes) -> str:
        stt_key = settings.ringg_stt_api_key or settings.ringg_api_key
        if not stt_key:
            raise RuntimeError("No Ringg STT key configured")
        from ringglabs.stt import AsyncClient  # type: ignore
        async with AsyncClient(api_key=stt_key) as client:
            result = await client.transcribe(
                audio_wav,
                language=settings.ringg_stt_language or "en",
                enable_cap_punc=True,
                content_type="audio/wav",
            )
        return (getattr(result, "transcription", "") or "").strip()


_provider: TranscriptionProvider | None = None


def get_transcriber() -> TranscriptionProvider:
    global _provider
    if _provider is None:
        import os
        choice = os.environ.get("SYNC_STT_PROVIDER", "openai").lower()
        if choice == "ringg":
            _provider = RinggTranscriber()
            logger.info("STT provider: Ringg Parrot")
        else:
            _provider = OpenAITranscriber()
            logger.info("STT provider: OpenAI Whisper")
    return _provider
