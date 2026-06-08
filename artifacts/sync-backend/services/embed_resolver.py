"""Embed URL resolver for micro-frontend CRM panels.

For each CRM provider, returns an EmbedSpec with:
  - url: the CRM's native contact view URL
  - sandbox_attrs: iframe sandbox attribute string
  - may_block_frame: True if the provider is known to set X-Frame-Options: SAMEORIGIN
    (HubSpot, Salesforce, Zoho all do in production — we document this honestly)
  - requires_auth_handoff: True if a session-bound URL is needed

For FakeLeadSquared: returns SYNC's own sandbox contact view
(served by the embeds router from a Jinja template), which is fully
embeddable and stays offline-safe for the hackathon demo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EmbedSpec:
    url: str
    provider: str
    label: str
    sandbox_attrs: str = "allow-scripts allow-same-origin allow-forms"
    may_block_frame: bool = False
    requires_auth_handoff: bool = False
    metadata: dict = field(default_factory=dict)


async def resolve_embed_url(connection_id: str, client_id: str, backend_url: str) -> EmbedSpec:
    """Return the embed spec for a given connection + client."""
    from services import connection_registry

    conn = await connection_registry.get_connection(connection_id)
    if conn is None:
        raise ValueError(f"Connection {connection_id} not found")

    provider = conn.provider
    meta = conn.metadata_json or {}

    if provider in ("fake_leadsquared", "mock"):
        # Serve SYNC's own sandboxed contact view — always works, no CSP issues
        return EmbedSpec(
            url=f"{backend_url}/api/v1/embeds/sandbox/contact/{client_id}",
            provider=provider,
            label="LeadSquared (Sandbox)" if provider == "fake_leadsquared" else "Demo",
            sandbox_attrs="allow-scripts allow-same-origin",
            may_block_frame=False,
        )

    # All of these real-CRM web apps set X-Frame-Options: DENY|SAMEORIGIN, so
    # we route every embed through SYNC's own /native view (which pulls live
    # data via the adapter) and keep the actual CRM URL as external_url for
    # the "Open in {provider} ↗" link.

    if provider == "hubspot":
        portal_id = meta.get("portal_id", "")
        external_url = (
            f"https://app.hubspot.com/contacts/{portal_id}/contact/{client_id}"
            if portal_id else f"https://app.hubspot.com/contacts/contact/{client_id}"
        )
        return EmbedSpec(
            url=f"/api/v1/embeds/native/{connection_id}/{client_id}",
            provider="hubspot",
            label="HubSpot",
            sandbox_attrs="allow-scripts allow-same-origin",
            may_block_frame=False,
            metadata={"external_url": external_url},
        )

    if provider == "salesforce":
        instance_url = meta.get("instance_url", "").rstrip("/")
        external_url = f"{instance_url}/lightning/r/Contact/{client_id}/view" if instance_url else None
        return EmbedSpec(
            url=f"/api/v1/embeds/native/{connection_id}/{client_id}",
            provider="salesforce",
            label="Salesforce",
            sandbox_attrs="allow-scripts allow-same-origin",
            may_block_frame=False,
            metadata={"external_url": external_url} if external_url else {},
        )

    if provider == "zoho":
        org_id = meta.get("org_id", "")
        api_domain = meta.get("api_domain", "https://crm.zoho.in")
        base = api_domain.replace("www.zohoapis.", "crm.zoho.").replace("api-", "")
        external_url = f"{base}/crm/{org_id}/tab/Contacts/{client_id}" if org_id else None
        return EmbedSpec(
            url=f"/api/v1/embeds/native/{connection_id}/{client_id}",
            provider="zoho",
            label="Zoho CRM",
            sandbox_attrs="allow-scripts allow-same-origin",
            may_block_frame=False,
            metadata={"external_url": external_url} if external_url else {},
        )

    if provider == "dynamics":
        instance_url = meta.get("instance_url", "").rstrip("/")
        external_url = (
            f"{instance_url}/main.aspx?pagetype=entityrecord&etn=contact&id={client_id}"
            if instance_url else None
        )
        return EmbedSpec(
            url=f"/api/v1/embeds/native/{connection_id}/{client_id}",
            provider="dynamics",
            label="Dynamics 365",
            sandbox_attrs="allow-scripts allow-same-origin",
            may_block_frame=False,
            metadata={"external_url": external_url} if external_url else {},
        )

    if provider == "freshworks":
        subdomain = meta.get("subdomain", "")
        external_url = (
            f"https://{subdomain}.myfreshworks.com/crm/sales/contacts/{client_id}"
            if subdomain else None
        )
        return EmbedSpec(
            url=f"/api/v1/embeds/native/{connection_id}/{client_id}",
            provider="freshworks",
            label="Freshworks CRM",
            sandbox_attrs="allow-scripts allow-same-origin",
            may_block_frame=False,
            metadata={"external_url": external_url} if external_url else {},
        )

    if provider == "leadsquared":
        region = meta.get("region", "in21")
        external_url = f"https://{region}.leadsquared.com/Pages/LeadDetails.aspx?LeadId={client_id}"
        return EmbedSpec(
            url=f"/api/v1/embeds/native/{connection_id}/{client_id}",
            provider="leadsquared",
            label="LeadSquared",
            sandbox_attrs="allow-scripts allow-same-origin",
            may_block_frame=False,
            metadata={"external_url": external_url},
        )

    if provider == "pipedrive":
        from config import settings
        domain = meta.get("company_domain") or settings.pipedrive_company_domain
        external_url = f"https://{domain}.pipedrive.com/person/{client_id}" if domain else None
        # Pipedrive sets X-Frame-Options: DENY, so the real web app can't be
        # iframed. Instead, point at SYNC's native view which pulls live data
        # from the Pipedrive REST API and renders it through our template —
        # the external Pipedrive URL is preserved for the "Open in CRM ↗" link.
        return EmbedSpec(
            url=f"/api/v1/embeds/native/{connection_id}/{client_id}",
            provider="pipedrive",
            label="Pipedrive",
            sandbox_attrs="allow-scripts allow-same-origin",
            may_block_frame=False,
            metadata={"external_url": external_url} if external_url else {},
        )

    # Unknown provider — return a blank spec so the UI can show an "open in CRM" link
    return EmbedSpec(
        url="#",
        provider=provider,
        label=provider.title(),
        may_block_frame=True,
    )
