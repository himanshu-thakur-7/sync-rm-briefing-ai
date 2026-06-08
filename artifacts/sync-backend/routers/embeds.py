"""CRM embed router — serves embed specs and the SYNC-hosted contact views.

Endpoints:
  GET /api/v1/embeds/sandbox/contact/{client_id}
      → Server-rendered HTML contact view for the default sandbox connection

  GET /api/v1/embeds/native/{connection_id}/{client_id}
      → Server-rendered HTML contact view for ANY connection (Pipedrive,
        HubSpot, etc.). Uses the real adapter to pull live CRM data and
        renders it through the same editorial template — works around the
        X-Frame-Options: DENY wall that real CRM web apps put up.

  GET /api/v1/embeds/{connection_id}/contact/{client_id}
      → EmbedSpec JSON (url, sandbox_attrs, may_block_frame, …)

  POST /api/v1/embeds/{connection_id}/handoff
      → For providers that need a session-bound URL (future: HubSpot UI Extension)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/embeds", tags=["embeds"])


# ─── Template rendering ───────────────────────────────────────────────────

_PROVIDER_LABEL = {
    "fake_leadsquared": "LeadSquared (Sandbox)",
    "leadsquared":      "LeadSquared",
    "pipedrive":        "Pipedrive",
    "hubspot":          "HubSpot",
    "salesforce":       "Salesforce",
    "zoho":             "Zoho CRM",
    "dynamics":         "Dynamics 365",
    "freshworks":       "Freshworks CRM",
    "mock":             "Demo CRM",
}


def _render_contact(client, provider: str, external_url: str | None = None) -> HTMLResponse:
    """Render the editorial contact view for a client. Shared by the sandbox
    + native paths. Always iframe-friendly (we serve it, so no X-Frame block)."""
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path

    templates_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
    try:
        tmpl = env.get_template("sandbox_contact.html")
    except Exception as e:
        logger.error("Template load error: %s", e)
        return HTMLResponse(f"<p>Template error: {e}</p>", status_code=500)

    html = tmpl.render(
        client=client,
        provider_label=_PROVIDER_LABEL.get(provider, provider.title()),
        provider=provider,
        external_url=external_url,
    )
    return HTMLResponse(content=html)


# ─── Sandbox HTML view (default connection) ──────────────────────────────

@router.get("/sandbox/contact/{client_id}", response_class=HTMLResponse)
async def sandbox_contact_view(client_id: str):
    """Render the SYNC-hosted contact view for the default connection."""
    from services import connection_registry

    try:
        default_id = await connection_registry.default_connection_id()
        adapter = await connection_registry.crm_for(default_id)
        client = await adapter.get_client(client_id)
        conn = await connection_registry.get_connection(default_id)
        provider = conn.provider if conn else "mock"
    except Exception as e:
        logger.exception("Sandbox view error: %s", e)
        client = None
        provider = "mock"

    if client is None:
        return HTMLResponse("<p style='font-family:sans-serif;padding:20px'>Client not found.</p>", status_code=404)

    return _render_contact(client, provider)


# ─── Native HTML view (any connection — including Pipedrive) ─────────────

@router.get("/native/{connection_id}/{client_id}", response_class=HTMLResponse)
async def native_contact_view(connection_id: str, client_id: str):
    """Render any connection's contact in SYNC's editorial format.

    This is how we 'embed' providers that block iframing (Pipedrive,
    HubSpot, Salesforce, etc.) — we render real CRM data through our
    own template, which IS iframe-friendly because we serve it.
    """
    from services import connection_registry
    from services.embed_resolver import resolve_embed_url

    try:
        adapter = await connection_registry.crm_for(connection_id)
        client = await adapter.get_client(client_id)
        conn = await connection_registry.get_connection(connection_id)
        provider = conn.provider if conn else "mock"
    except KeyError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception("Native view error: %s", e)
        return HTMLResponse(
            f"<p style='font-family:sans-serif;padding:20px;color:#a00'>Failed to load: {e}</p>",
            status_code=500,
        )

    if client is None:
        return HTMLResponse(
            f"<p style='font-family:sans-serif;padding:20px'>Client {client_id} not found in {provider}.</p>",
            status_code=404,
        )

    # Look up the external CRM URL so the template can show an "Open in X ↗" link
    external_url = None
    try:
        spec = await resolve_embed_url(connection_id, client_id, settings.backend_url)
        external_url = spec.metadata.get("external_url")
    except Exception:
        pass

    return _render_contact(client, provider, external_url=external_url)


# ─── Embed spec ───────────────────────────────────────────────────────────

@router.get("/{connection_id}/contact/{client_id}")
async def get_embed_spec(connection_id: str, client_id: str):
    """Return the embed URL spec for a given connection + client."""
    from services.embed_resolver import resolve_embed_url

    try:
        spec = await resolve_embed_url(connection_id, client_id, settings.backend_url)
    except ValueError as e:
        raise HTTPException(404, str(e))

    return {
        "url": spec.url,
        "provider": spec.provider,
        "label": spec.label,
        "sandbox_attrs": spec.sandbox_attrs,
        "may_block_frame": spec.may_block_frame,
        "requires_auth_handoff": spec.requires_auth_handoff,
        "external_url": spec.metadata.get("external_url"),
    }


# ─── Auth handoff (stub) ──────────────────────────────────────────────────

@router.post("/{connection_id}/handoff")
async def auth_handoff(connection_id: str):
    """
    Generate a session-bound embed URL for providers that require it.
    Currently: stub — in production this would use HubSpot's app token
    or Salesforce's frontdoor.jsp flow.
    """
    conn = None
    from services import connection_registry
    try:
        conn = await connection_registry.get_connection(connection_id)
    except Exception:
        pass

    if not conn:
        raise HTTPException(404, f"Connection {connection_id} not found")

    return {
        "message": f"Auth handoff for {conn.provider} not implemented yet — use the direct embed URL or open in a new tab.",
        "provider": conn.provider,
    }
