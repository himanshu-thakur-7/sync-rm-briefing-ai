from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ringg
    ringg_api_key: str = ""
    ringg_base_url: str = "https://prod-api.ringg.ai/ca/api/v0"
    ringg_agent_id: str = ""
    ringg_from_number_id: str = ""

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

    # Demo defaults
    demo_rm_phone: str = "+919876543210"
    demo_rm_name: str = "Himanshu"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


def oauth_redirect_uri(provider: str) -> str:
    """Build the OAuth callback URI for a given provider."""
    base = (settings.oauth_redirect_base or settings.backend_url).rstrip("/")
    return f"{base}/api/v1/oauth/callback/{provider}"
