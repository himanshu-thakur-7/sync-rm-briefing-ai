from pathlib import Path
from pydantic_settings import BaseSettings

# Look for .env files at: backend folder → repo root. Repo root wins (loaded last)
# so the user's canonical .env always takes precedence over any stale per-folder one.
_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent.parent
_ENV_FILES = tuple(str(p) for p in (_BACKEND_DIR / ".env", _REPO_ROOT / ".env") if p.exists())


class Settings(BaseSettings):
    # Ringg
    ringg_api_key: str = ""
    ringg_base_url: str = "https://prod-api.ringg.ai/ca/api/v0"
    ringg_agent_id: str = ""
    ringg_from_number_id: str = ""
    ringg_outreach_agent_id: str = ""  # client-facing "SYNC Outreach" agent
    ringg_morning_brief_agent_id: str = ""  # RM-facing "SYNC Morning Brief" conversational agent
    ringg_concierge_agent_id: str = ""      # R4: inbound "SYNC Concierge" — RM dials in, asks about any client
    ringg_inbound_number: str = ""          # The DID printed in the dashboard (display only — Ringg routes by agent)
    # Ringg Parrot STT — standalone speech-to-text (ringglabs SDK). Separate
    # product key (often "rk_live_..."). If unset, we try ringg_api_key, then
    # fall back to OpenAI Whisper for the dashboard-mic server path.
    ringg_stt_api_key: str = ""
    ringg_stt_language: str = "en"          # "en" | "hi" — Parrot supports code-mixed too

    # Twilio — click-to-call bridge for Coached Calls (RM ↔ client with SYNC
    # listening via Media Streams and whispering coaching to the dashboard).
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""            # E.164, e.g. +15005550006

    # Risk Radar
    radar_autopilot_default: bool = False
    radar_scan_interval_min: int = 15

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # Legacy CRM adapter switch — kept for back-compat with old env files.
    # The connection_registry now resolves per-connection adapters; this is the
    # fallback when no CRMConnection rows exist.
    crm_adapter: str = "mock"

    # Legacy single-tenant credentials. The OAuth-aware adapters prefer
    # SecretStore-backed tokens keyed by connection_id; these remain for
    # the `mock` and one-shot env-driven flows.
    hubspot_api_key: str = ""
    salesforce_instance_url: str = ""
    salesforce_access_token: str = ""

    # SYNC platform secrets
    secret_key: str = ""  # Fernet key for SecretStore; auto-generated on first boot if blank.
    database_url: str = "sqlite+aiosqlite:///./sync.db"
    webhook_secret: str = "sync-webhook-secret"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    oauth_redirect_base: str = ""  # If unset, falls back to backend_url. Set to ngrok URL in dev.

    # Per-provider OAuth app credentials. Empty values flag the provider as un-configured.
    hubspot_client_id: str = ""
    hubspot_client_secret: str = ""
    salesforce_client_id: str = ""
    salesforce_client_secret: str = ""
    zoho_client_id: str = ""
    zoho_client_secret: str = ""
    zoho_accounts_base: str = "https://accounts.zoho.in"
    dynamics_client_id: str = ""
    dynamics_client_secret: str = ""
    dynamics_tenant_id: str = ""
    dynamics_instance_url: str = ""
    freshworks_subdomain: str = ""
    freshworks_api_key: str = ""
    leadsquared_access_key: str = ""
    leadsquared_secret_key: str = ""
    leadsquared_region: str = "api-in21"
    # Pipedrive (R4 — primary demo CRM)
    pipedrive_client_id: str = ""
    pipedrive_client_secret: str = ""
    pipedrive_api_token: str = ""       # Personal API token, fast-path auth
    pipedrive_company_domain: str = ""  # e.g. "acmedemo" → acmedemo.pipedrive.com

    # Demo defaults
    demo_rm_phone: str = "+919876543210"
    demo_rm_name: str = "Himanshu"
    # Tenant-templated company name used in all client-facing voice scripts.
    # In production each connection would carry its own; for the demo we
    # default to "Acme" so the voice never says "your bank" unprompted.
    demo_company_name: str = "Acme"
    # Save calls target this number on stage (presenter's second phone). In
    # production the client phone would come from the CRM contact record.
    demo_client_phone: str = "+919876543210"

    class Config:
        env_file = _ENV_FILES or (".env",)
        extra = "ignore"


settings = Settings()


def oauth_redirect_uri(provider: str) -> str:
    """Build the OAuth callback URI for a given provider."""
    base = (settings.oauth_redirect_base or settings.backend_url).rstrip("/")
    return f"{base}/api/v1/oauth/callback/{provider}"
