import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import clients, briefings, calls, webhooks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SYNC backend starting up...")
    logger.info(f"CRM adapter: {os.environ.get('CRM_ADAPTER', 'mock')}")
    logger.info(f"Ringg configured: {bool(os.environ.get('RINGG_API_KEY'))}")
    logger.info(f"OpenAI configured: {bool(os.environ.get('OPENAI_API_KEY'))}")
    yield
    logger.info("SYNC backend shutting down.")


app = FastAPI(
    title="SYNC — RM Briefing Voice AI Co-Pilot",
    description=(
        "Before every client meeting, your RM knows everything. "
        "Not because they read a CRM — because they made a 30-second phone call to SYNC."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow dashboard and dev environments
frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers — all under /api prefix (proxy strips nothing)
app.include_router(clients.router, prefix="/api")
app.include_router(briefings.router, prefix="/api")
app.include_router(calls.router, prefix="/api")
app.include_router(webhooks.router)  # WebSocket and webhook have their own full paths


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
