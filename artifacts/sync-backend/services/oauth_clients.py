"""Per-provider Authlib OAuth2 sessions.

Each function returns a fresh `StarletteIntegration`-compatible Authlib
client configured for the provider. Token refresh is centralized — every
adapter call wraps with `with_token_refresh` which retries once on 401.
"""
from __future__ import annotations

import logging
from typing import Optional

from authlib.integrations.httpx_client import AsyncOAuth2Client
from config import settings, oauth_redirect_uri

logger = logging.getLogger(__name__)


# Provider metadata
PROVIDER_REGISTRY: dict[str, dict] = {
    "hubspot": {
        "display_name": "HubSpot",
        "auth_method": "oauth2",
        "authorize_url": "https://app.hubspot.com/oauth/authorize",
        "token_url": "https://api.hubapi.com/oauth/v1/token",
        "scopes": "crm.objects.contacts.read crm.objects.contacts.write crm.objects.deals.read crm.objects.tickets.read crm.schemas.contacts.write",
        "configured": lambda: bool(settings.hubspot_client_id and settings.hubspot_client_secret),
    },
    "salesforce": {
        "display_name": "Salesforce",
        "auth_method": "oauth2",
        "authorize_url": "https://login.salesforce.com/services/oauth2/authorize",
        "token_url": "https://login.salesforce.com/services/oauth2/token",
        "scopes": "api refresh_token",
        "configured": lambda: bool(settings.salesforce_client_id and settings.salesforce_client_secret),
    },
    "zoho": {
        "display_name": "Zoho CRM",
        "auth_method": "oauth2",
        "authorize_url": f"{settings.zoho_accounts_base}/oauth/v2/auth",
        "token_url": f"{settings.zoho_accounts_base}/oauth/v2/token",
        "scopes": "ZohoCRM.modules.ALL ZohoCRM.settings.ALL",
        "configured": lambda: bool(settings.zoho_client_id and settings.zoho_client_secret),
    },
    "dynamics": {
        "display_name": "Microsoft Dynamics 365",
        "auth_method": "oauth2",
        "authorize_url": f"https://login.microsoftonline.com/{settings.dynamics_tenant_id}/oauth2/v2.0/authorize",
        "token_url": f"https://login.microsoftonline.com/{settings.dynamics_tenant_id}/oauth2/v2.0/token",
        "scopes": f"{settings.dynamics_instance_url}/.default offline_access",
        "configured": lambda: bool(settings.dynamics_client_id and settings.dynamics_client_secret and settings.dynamics_tenant_id),
    },
    "freshworks": {
        "display_name": "Freshworks CRM",
        "auth_method": "api_key",
        "authorize_url": "",
        "token_url": "",
        "scopes": "",
        "configured": lambda: bool(settings.freshworks_api_key and settings.freshworks_subdomain),
    },
    "leadsquared": {
        "display_name": "LeadSquared",
        "auth_method": "api_key",
        "authorize_url": "",
        "token_url": "",
        "scopes": "",
        "configured": lambda: bool(settings.leadsquared_access_key and settings.leadsquared_secret_key),
    },
    "pipedrive": {
        "display_name": "Pipedrive",
        "auth_method": "api_key",  # also supports OAuth 2.0; api_key is the demo path
        "authorize_url": "https://oauth.pipedrive.com/oauth/authorize",
        "token_url": "https://oauth.pipedrive.com/oauth/token",
        "scopes": "deals:full contacts:full activities:full",
        "configured": lambda: bool(settings.pipedrive_api_token and settings.pipedrive_company_domain),
    },
    "fake_leadsquared": {
        "display_name": "LeadSquared (Sandbox)",
        "auth_method": "none",
        "authorize_url": "",
        "token_url": "",
        "scopes": "",
        "configured": lambda: True,
    },
    "mock": {
        "display_name": "Mock CRM",
        "auth_method": "none",
        "authorize_url": "",
        "token_url": "",
        "scopes": "",
        "configured": lambda: True,
    },
}


def get_oauth_client(provider: str) -> AsyncOAuth2Client:
    """Return a configured Authlib async OAuth2 client for the provider."""
    meta = PROVIDER_REGISTRY.get(provider)
    if not meta or meta["auth_method"] != "oauth2":
        raise ValueError(f"Provider {provider!r} does not use OAuth2")
    if provider == "hubspot":
        client_id = settings.hubspot_client_id
        client_secret = settings.hubspot_client_secret
    elif provider == "salesforce":
        client_id = settings.salesforce_client_id
        client_secret = settings.salesforce_client_secret
    elif provider == "zoho":
        client_id = settings.zoho_client_id
        client_secret = settings.zoho_client_secret
    elif provider == "dynamics":
        client_id = settings.dynamics_client_id
        client_secret = settings.dynamics_client_secret
    else:
        raise ValueError(f"No client_id/secret config for provider {provider!r}")

    return AsyncOAuth2Client(
        client_id=client_id,
        client_secret=client_secret,
        scope=meta["scopes"],
        redirect_uri=oauth_redirect_uri(provider),
        token_endpoint=meta["token_url"],
    )


def provider_info() -> list[dict]:
    """Return the full list of providers with configured status."""
    return [
        {
            "provider": key,
            "display_name": meta["display_name"],
            "auth_method": meta["auth_method"],
            "configured": meta["configured"](),
        }
        for key, meta in PROVIDER_REGISTRY.items()
    ]
