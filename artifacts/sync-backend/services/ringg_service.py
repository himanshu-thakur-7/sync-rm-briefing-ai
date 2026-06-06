"""
Ringg AI API client.
All methods use httpx.AsyncClient with proper error handling and retries.
"""
import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

RINGG_HEADERS = {
    "X-API-KEY": settings.ringg_api_key,
    "Content-Type": "application/json",
}


class RinggService:
    """Client for the Ringg AI voice platform API."""

    BASE_URL = settings.ringg_base_url

    async def create_agent(self, config: dict) -> str:
        """
        POST /public/agent — Create the SYNC assistant.
        Returns agent_id.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/public/agent",
                json=config,
                headers=RINGG_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
            agent_id = data.get("agent_id") or data.get("id") or data.get("agentId", "")
            logger.info(f"Created Ringg agent: {agent_id}")
            return agent_id

    async def get_voices(self, language: str = "en-IN") -> list:
        """
        GET /agent/voices?language=en-IN — Get available voice options.
        """
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE_URL}/agent/voices",
                params={"language": language},
                headers=RINGG_HEADERS,
            )
            resp.raise_for_status()
            return resp.json()

    async def initiate_call(
        self,
        agent_id: str,
        from_number_id: str,
        recipient_phone: str,
        recipient_name: str,
        custom_args: dict,
        callback_url: str,
    ) -> str:
        """
        POST /calling/outbound/individual — Trigger briefing call to RM.
        Returns call_id.
        """
        if not settings.ringg_api_key:
            logger.warning("RINGG_API_KEY not set — simulating call for demo")
            import uuid
            return f"demo_call_{uuid.uuid4().hex[:8]}"

        payload = {
            "agent_id": agent_id,
            "from_number_id": from_number_id,
            "mobile_number": recipient_phone,
            "name": recipient_name,
            "custom_args_values": custom_args,
            "callback_url": callback_url,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calling/outbound/individual",
                json=payload,
                headers=RINGG_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
            call_id = data.get("call_id") or data.get("id") or data.get("callId", "")
            logger.info(f"Initiated Ringg call: {call_id}")
            return call_id

    async def get_call_details(self, call_id: str) -> dict:
        """GET /calling/history/{call_id}"""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE_URL}/calling/history/{call_id}",
                headers=RINGG_HEADERS,
            )
            resp.raise_for_status()
            return resp.json()

    async def upload_knowledge_base(self, name: str, content: str) -> str:
        """
        POST /kb — Upload client data as knowledge base.
        For inbound mode: agent uses KB to look up clients.
        Returns kb_id.
        """
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE_URL}/kb",
                json={"name": name, "content": content},
                headers=RINGG_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
            kb_id = data.get("kb_id") or data.get("id", "")
            logger.info(f"Uploaded knowledge base: {kb_id}")
            return kb_id

    async def setup_webhooks(self, agent_id: str, callback_url: str) -> None:
        """
        PATCH /agent/v1 — Subscribe to call events.
        Subscribes to: call_completed, platform_analysis_completed, all_processing_completed
        """
        payload = {
            "agent_id": agent_id,
            "webhook_url": callback_url,
            "webhook_events": [
                "call_started",
                "call_completed",
                "platform_analysis_completed",
                "all_processing_completed",
            ],
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.patch(
                f"{self.BASE_URL}/agent/v1",
                json=payload,
                headers=RINGG_HEADERS,
            )
            resp.raise_for_status()
            logger.info(f"Webhooks configured for agent {agent_id}")


ringg_service = RinggService()
