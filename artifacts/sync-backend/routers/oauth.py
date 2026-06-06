"""OAuth 2.0 flow router.

Endpoints:
  GET  /api/v1/oauth/providers                        — list all CRM providers + configured flag
  GET  /api/v1/oauth/{provider}/authorize?label=...   — start OAuth dance, returns authorize_url
  GET  /api/v1/oauth/callback/{provider}              — code→token exchange, store, redirect
  POST /api/v1/oauth/{connection_id}/refresh          — manual token refresh
  DELETE /api/v1/oauth/{connection_id}                — disconnect (revoke best-effort + soft-delete)

API-key providers (freshworks, leadsquared) use:
  POST /api/v1/oauth/{provider}/connect body {access_key, secret_key, ...}
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlmodel import select

from config import settings, oauth_redirect_uri
from db import get_session
from db.models import CRMConnection, OAuthState
from services import connection_registry
from services.oauth_clients import PROVIDER_REGISTRY, get_oauth_client
from services.secret_store import secret_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/oauth", tags=["oauth"])


# ------------------------------------------------------------------ #
# Models
# ------------------------------------------------------------------ #

class ApiKeyConnectRequest(BaseModel):
    label: str = ""
    access_key: str = ""
    secret_key: str = ""
    region: str = ""
    instance_url: str = ""
    subdomain: str = ""
    api_key: str = ""
    extra: dict = {}


class ProviderInfo(BaseModel):
    provider: str
    display_name: str
    auth_method: str
    configured: bool


# ------------------------------------------------------------------ #
# Provider listing
# ------------------------------------------------------------------ #

@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers():
    """List all CRM providers with their configured status."""
    from services.oauth_clients import provider_info
    return provider_info()


# ------------------------------------------------------------------ #
# OAuth2 dance
# ------------------------------------------------------------------ #

@router.get("/{provider}/authorize")
async def authorize(provider: str, label: str = Query(default="")):
    """Kick off the OAuth dance. Returns the provider's authorize URL."""
    meta = PROVIDER_REGISTRY.get(provider)
    if not meta:
        raise HTTPException(404, f"Unknown provider: {provider}")
    if meta["auth_method"] != "oauth2":
        raise HTTPException(400, f"{provider} uses {meta['auth_method']}, not OAuth2. Use /connect instead.")
    if not meta["configured"]():
        raise HTTPException(400, f"OAuth credentials for {provider} not configured — set client_id/secret in env.")

    state = secrets.token_urlsafe(32)
    async with get_session() as session:
        session.add(OAuthState(
            state=state,
            provider=provider,
            label=label or meta["display_name"],
            created_at=datetime.now(timezone.utc),
        ))

    client = get_oauth_client(provider)
    url, _ = client.create_authorization_url(meta["authorize_url"], state=state)
    return {"authorize_url": url, "state": state}


@router.get("/callback/{provider}")
async def oauth_callback(provider: str, code: str = Query(...), state: str = Query(...)):
    """Exchange code for token, persist, redirect to dashboard."""
    # Verify CSRF state.
    async with get_session() as session:
        state_row = (
            await session.exec(select(OAuthState).where(OAuthState.state == state))
        ).first()
        if not state_row or state_row.provider != provider:
            raise HTTPException(400, "Invalid or expired OAuth state")
        label = state_row.label
        await session.delete(state_row)

    meta = PROVIDER_REGISTRY.get(provider, {})
    client = get_oauth_client(provider)
    try:
        token = await client.fetch_token(
            meta["token_url"],
            code=code,
            redirect_uri=oauth_redirect_uri(provider),
        )
    except Exception as e:
        logger.error("Token exchange failed for %s: %s", provider, e)
        raise HTTPException(502, f"Token exchange failed: {e}")

    # Build connection_id
    conn_id = f"conn_{provider}_{secrets.token_hex(4)}"

    # Provider-specific metadata from token response
    meta_data: dict = {}
    if provider == "hubspot":
        meta_data["portal_id"] = token.get("hub_id", "") or token.get("hub_domain", "")
        meta_data["instance_url"] = "https://api.hubapi.com"
    elif provider == "salesforce":
        meta_data["instance_url"] = token.get("instance_url", "")
    elif provider == "zoho":
        meta_data["api_domain"] = token.get("api_domain", "https://www.zohoapis.in")

    async with get_session() as session:
        session.add(CRMConnection(
            id=conn_id,
            provider=provider,
            label=label,
            status="active",
            auth_method="oauth2",
            metadata_json=meta_data,
            is_default=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))

    await secret_store().put_token(conn_id, dict(token))
    connection_registry.invalidate(conn_id)

    redirect_url = f"{settings.frontend_url}/settings/integrations?connected={conn_id}"
    return RedirectResponse(url=redirect_url)


# ------------------------------------------------------------------ #
# API-key providers
# ------------------------------------------------------------------ #

@router.post("/{provider}/connect")
async def connect_api_key(provider: str, body: ApiKeyConnectRequest):
    """Connect an API-key–based CRM (LeadSquared, Freshworks)."""
    meta = PROVIDER_REGISTRY.get(provider)
    if not meta:
        raise HTTPException(404, f"Unknown provider: {provider}")
    if meta["auth_method"] == "oauth2":
        raise HTTPException(400, f"{provider} uses OAuth2. Use /{provider}/authorize instead.")

    conn_id = f"conn_{provider}_{secrets.token_hex(4)}"
    conn_meta: dict = {}

    if provider == "leadsquared":
        if not body.access_key or not body.secret_key:
            raise HTTPException(400, "access_key and secret_key required for LeadSquared")
        conn_meta = {"access_key": body.access_key, "secret_key": body.secret_key, "region": body.region or settings.leadsquared_region}
        await secret_store().put_token(conn_id, {"access_key": body.access_key, "secret_key": body.secret_key})

    elif provider == "freshworks":
        if not body.api_key or not body.subdomain:
            raise HTTPException(400, "api_key and subdomain required for Freshworks")
        conn_meta = {"subdomain": body.subdomain}
        await secret_store().put_token(conn_id, {"api_key": body.api_key})

    else:
        conn_meta = body.extra

    async with get_session() as session:
        session.add(CRMConnection(
            id=conn_id,
            provider=provider,
            label=body.label or meta["display_name"],
            status="active",
            auth_method=meta["auth_method"],
            metadata_json=conn_meta,
            is_default=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))

    connection_registry.invalidate(conn_id)
    return {"connection_id": conn_id, "status": "connected", "provider": provider}


# ------------------------------------------------------------------ #
# Refresh + disconnect
# ------------------------------------------------------------------ #

@router.post("/{connection_id}/refresh")
async def refresh_token(connection_id: str):
    """Manually refresh the OAuth token for a connection."""
    conn = await connection_registry.get_connection(connection_id)
    if not conn:
        raise HTTPException(404, f"Connection {connection_id} not found")
    if conn.auth_method != "oauth2":
        raise HTTPException(400, "Only OAuth2 connections support token refresh")

    token = await secret_store().get_token(connection_id)
    if not token:
        raise HTTPException(404, "No token found for this connection")

    meta = PROVIDER_REGISTRY.get(conn.provider, {})
    client = get_oauth_client(conn.provider)
    try:
        new_token = await client.refresh_token(meta["token_url"], refresh_token=token.get("refresh_token"))
        await secret_store().put_token(connection_id, dict(new_token))
        connection_registry.invalidate(connection_id)
        return {"status": "refreshed"}
    except Exception as e:
        raise HTTPException(502, f"Token refresh failed: {e}")


@router.delete("/{connection_id}")
async def disconnect(connection_id: str):
    """Disconnect a CRM — revoke token (best-effort) and soft-delete the row."""
    async with get_session() as session:
        conn = (
            await session.exec(select(CRMConnection).where(CRMConnection.id == connection_id))
        ).first()
        if not conn:
            raise HTTPException(404, f"Connection {connection_id} not found")
        conn.status = "disconnected"
        conn.updated_at = datetime.now(timezone.utc)
        session.add(conn)

    await secret_store().delete_token(connection_id)
    connection_registry.invalidate(connection_id)
    return {"status": "disconnected", "connection_id": connection_id}
