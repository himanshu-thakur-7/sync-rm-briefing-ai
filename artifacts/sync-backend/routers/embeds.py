"""CRM embed router — serves embed specs and the sandbox contact view.

Endpoints:
  GET /api/v1/embeds/sandbox/contact/{client_id}
      → Server-rendered HTML contact view for FakeLeadSquared (always embeddable)

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

# ─── Sandbox HTML view ────────────────────────────────────────────────────

@router.get("/sandbox/contact/{client_id}", response_class=HTMLResponse)
async def sandbox_contact_view(client_id: str):
    """Render the SYNC-hosted LeadSquared-style contact view."""
    from services import connection_registry
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path

    # Fetch client from the default FakeLeadSquared connection
    try:
        default_id = await connection_registry.default_connection_id()
        adapter = await connection_registry.crm_for(default_id)
        client = await adapter.get_client(client_id)
    except Exception:
        client = None

    if client is None:
        return HTMLResponse("<p style='font-family:sans-serif;padding:20px'>Client not found.</p>", status_code=404)

    templates_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
    try:
        tmpl = env.get_template("sandbox_contact.html")
    except Exception as e:
        logger.error("Template load error: %s", e)
        return HTMLResponse(f"<p>Template error: {e}</p>", status_code=500)

    html = tmpl.render(client=client)
    return HTMLResponse(content=html)


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
