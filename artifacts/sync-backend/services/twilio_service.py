"""Thin Twilio wrapper — outbound dial + Voice JS access tokens."""
from __future__ import annotations

import logging

from twilio.rest import Client
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant

from config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            raise RuntimeError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not set")
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


def create_outbound_call(to: str, twiml_url: str, status_callback: str | None = None) -> str:
    """Dial *to* (E.164) with TwiML served from *twiml_url*. Returns the Call SID."""
    client = _get_client()
    kwargs: dict = dict(
        to=to,
        from_=settings.twilio_from_number,
        url=twiml_url,
    )
    if status_callback:
        kwargs["status_callback"] = status_callback
        kwargs["status_callback_event"] = ["initiated", "ringing", "answered", "completed"]
    call = client.calls.create(**kwargs)
    logger.info("Twilio call created: %s → %s (SID %s)", settings.twilio_from_number, to, call.sid)
    return call.sid


def mint_voice_token(identity: str = "rm") -> str:
    """Return a short-lived Twilio access token so the browser can place calls via Voice JS."""
    if not settings.twilio_api_key or not settings.twilio_api_secret:
        raise RuntimeError("TWILIO_API_KEY / TWILIO_API_SECRET not set — needed for Voice JS tokens")
    if not settings.twilio_twiml_app_sid:
        raise RuntimeError("TWILIO_TWIML_APP_SID not set — needed for Voice JS outbound dialing")

    token = AccessToken(
        settings.twilio_account_sid,
        settings.twilio_api_key,
        settings.twilio_api_secret,
        identity=identity,
        ttl=3600,
    )
    token.add_grant(VoiceGrant(
        outgoing_application_sid=settings.twilio_twiml_app_sid,
        incoming_allow=False,
    ))
    return token.to_jwt()
