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

    if provider == "hubspot":
        portal_id = meta.get("portal_id", "")
        url = (
            f"https://app.hubspot.com/contacts/{portal_id}/contact/{client_id}"
            if portal_id else f"https://app.hubspot.com/contacts/contact/{client_id}"
        )
        return EmbedSpec(
            url=url,
            provider="hubspot",
            label="HubSpot",
            may_block_frame=True,  # HubSpot blocks framing; prod would use UI Extension SDK
            requires_auth_handoff=False,
        )

    if provider == "salesforce":
        instance_url = meta.get("instance_url", "").rstrip("/")
        url = f"{instance_url}/lightning/r/Contact/{client_id}/view"
        return EmbedSpec(
            url=url,
            provider="salesforce",
            label="Salesforce",
            sandbox_attrs="allow-scripts allow-same-origin allow-forms allow-popups",
            may_block_frame=True,  # SF Lightning blocks framing; prod would use Canvas App
            requires_auth_handoff=True,
        )

    if provider == "zoho":
        org_id = meta.get("org_id", "")
        api_domain = meta.get("api_domain", "https://crm.zoho.in")
        base = api_domain.replace("www.zohoapis.", "crm.zoho.").replace("api-", "")
        url = f"{base}/crm/{org_id}/tab/Contacts/{client_id}"
        return EmbedSpec(
            url=url,
            provider="zoho",
            label="Zoho CRM",
            may_block_frame=True,
        )

    if provider == "dynamics":
        instance_url = meta.get("instance_url", "").rstrip("/")
        url = f"{instance_url}/main.aspx?pagetype=entityrecord&etn=contact&id={client_id}"
        return EmbedSpec(
            url=url,
            provider="dynamics",
            label="Dynamics 365",
            may_block_frame=True,
        )

    if provider == "freshworks":
        subdomain = meta.get("subdomain", "")
        url = f"https://{subdomain}.myfreshworks.com/crm/sales/contacts/{client_id}"
        return EmbedSpec(
            url=url,
            provider="freshworks",
            label="Freshworks CRM",
            may_block_frame=True,
        )

    if provider == "leadsquared":
        region = meta.get("region", "in21")
        url = f"https://{region}.leadsquared.com/Pages/LeadDetails.aspx?LeadId={client_id}"
        return EmbedSpec(
            url=url,
            provider="leadsquared",
            label="LeadSquared",
            may_block_frame=True,
        )

    if provider == "pipedrive":
        from config import settings
        domain = meta.get("company_domain") or settings.pipedrive_company_domain
        url = f"https://{domain}.pipedrive.com/person/{client_id}" if domain else "#"
        return EmbedSpec(
            url=url,
            provider="pipedrive",
            label="Pipedrive",
            may_block_frame=True,  # Pipedrive sets X-Frame-Options: DENY
        )

    # Unknown provider — return a blank spec so the UI can show an "open in CRM" link
    return EmbedSpec(
        url="#",
        provider=provider,
        label=provider.title(),
        may_block_frame=True,
    )
