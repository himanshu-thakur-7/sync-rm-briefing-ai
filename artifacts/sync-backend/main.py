import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db import init_db
from db.engine import dispose as dispose_db
from migrations.seed import seed_default_connections
from routers import briefings, calls, clients, webhooks
from routers import oauth as oauth_router
from routers import integrations as integrations_router
from routers import embeds as embeds_router
from routers import voice_commands as voice_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SYNC backend starting up...")
    await init_db()
    await seed_default_connections()
    logger.info("Legacy CRM_ADAPTER env: %s", settings.crm_adapter)
    logger.info("Ringg configured: %s", bool(settings.ringg_api_key))
    logger.info("OpenAI configured: %s", bool(settings.openai_api_key))
    yield
    logger.info("SYNC backend shutting down.")
    await dispose_db()


app = FastAPI(
    title="SYNC — RM Briefing Voice AI Co-Pilot",
    description=(
        "SYNC is the voice-AI layer for your existing CRM. Connect HubSpot, "
        "Salesforce, Zoho, Microsoft Dynamics, Freshworks — SYNC briefs your "
        "RMs in 45 seconds, then logs the touchpoint back to the CRM."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


# CORS — frontend URL + common local dev ports.
_frontend = settings.frontend_url.rstrip("/")
_allowed_origins = list({
    _frontend,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:18929",
    "http://127.0.0.1:18929",
})
# In dev, also allow the env-supplied FRONTEND_URL without trailing slash.
extra_origin = os.environ.get("CORS_EXTRA_ORIGIN", "").strip().rstrip("/")
if extra_origin:
    _allowed_origins.append(extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount routers — all under /api prefix (proxy strips nothing)
app.include_router(clients.router, prefix="/api")
app.include_router(briefings.router, prefix="/api")
app.include_router(calls.router, prefix="/api")
app.include_router(webhooks.router)  # WebSocket and webhook have their own full paths
app.include_router(oauth_router.router)
app.include_router(integrations_router.router)
app.include_router(embeds_router.router)
app.include_router(voice_router.router)


@app.get("/api/healthz", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/v1/ringg/agent-config", tags=["ringg"])
async def get_ringg_agent_config():
    """Returns the Ringg agent configuration for manual setup."""
    return {
        "agent_name": "SYNC - RM Briefing Co-Pilot",
        "agent_type": "outbound_inbound",
        "primary_language": "en-IN",
        "secondary_language": "hi-IN",
        "intro_message": "Hey! This is SYNC. Which client are you meeting today?",
        "introduction_and_objective": (
            "You are SYNC, a voice AI co-pilot for Relationship Managers at an Indian bank. "
            "When an RM calls you or you call an RM, your job is to deliver a crisp, warm, "
            "45-second briefing about their client so they walk into the meeting fully prepared. "
            "You sound like a sharp, friendly colleague — never a bot."
        ),
        "custom_variables": [
            "callee_name", "client_name", "client_age", "client_occupation",
            "portfolio_summary", "risk_level", "risk_factors", "days_since_contact",
            "open_complaints", "cross_sell_pitch", "cross_sell_product",
            "secondary_pitch", "hinglish_closer",
        ],
    }
