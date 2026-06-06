import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ringg_api_key: str = ""
    ringg_base_url: str = "https://prod-api.ringg.ai/ca/api/v0"
    ringg_agent_id: str = ""
    ringg_from_number_id: str = ""

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    crm_adapter: str = "mock"

    hubspot_api_key: str = ""

    salesforce_instance_url: str = ""
    salesforce_access_token: str = ""

    webhook_secret: str = "sync-webhook-secret"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    demo_rm_phone: str = "+919876543210"
    demo_rm_name: str = "Himanshu"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
