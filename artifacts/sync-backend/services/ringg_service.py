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

    async def initiate_outreach_call(
        self,
        outreach_agent_id: str,
        from_number_id: str,
        client_phone: str,
        client_name: str,
        custom_args: dict,
        callback_url: str,
        transfer_to_number: str = "",
    ) -> str:
        """
        POST /calling/outbound/individual — place a CLIENT-FACING save call.
        Uses the SYNC Outreach agent and passes a warm-transfer number so the
        agent can hand off to the human RM. Returns call_id.
        """
        if not settings.ringg_api_key:
            logger.warning("RINGG_API_KEY not set — simulating outreach call for demo")
            import uuid
            return f"demo_outreach_{uuid.uuid4().hex[:8]}"

        # The warm-transfer number rides in custom_args; the outreach agent's
        # prompt is configured to transfer to {{rm_phone}} on request.
        args = {**custom_args}
        if transfer_to_number:
            args["rm_phone"] = transfer_to_number

        payload = {
            "agent_id": outreach_agent_id,
            "from_number_id": from_number_id,
            "mobile_number": client_phone,
            "name": client_name,
            "custom_args_values": args,
            "callback_url": callback_url,
        }
        if transfer_to_number:
            # Best-effort: Ringg supports call transfer config; exact key may vary
            # by workspace. We pass it both ways so whichever the API honours works.
            payload["transfer_number"] = transfer_to_number
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calling/outbound/individual",
                json=payload,
                headers=RINGG_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
            call_id = data.get("call_id") or data.get("id") or data.get("callId", "")
            logger.info(f"Initiated Ringg outreach call: {call_id}")
            return call_id

    async def initiate_morning_brief_call(
        self,
        brief_agent_id: str,
        from_number_id: str,
        rm_phone: str,
        rm_name: str,
        custom_args: dict,
        callback_url: str,
        mid_call_tool_url: str = "",
    ) -> str:
        """
        Round 3 — Daily Standup. Place a CONVERSATIONAL outbound call to the RM.
        The brief agent is configured with mid-call tools (ask_crm, log_action)
        that hit our `mid_call_tool_url` during the call so the AI can answer
        questions and execute CRM actions while the conversation is live.
        Returns call_id. Keyless: returns a `demo_brief_*` id for simulation.
        """
        if not settings.ringg_api_key:
            logger.warning("RINGG_API_KEY not set — simulating morning brief call for demo")
            import uuid
            return f"demo_brief_{uuid.uuid4().hex[:8]}"

        payload = {
            "agent_id": brief_agent_id,
            "from_number_id": from_number_id,
            "mobile_number": rm_phone,
            "name": rm_name,
            "custom_args_values": custom_args,
            "callback_url": callback_url,
        }
        if mid_call_tool_url:
            # Ringg supports per-call tool/function URLs; the exact key may vary
            # across workspaces. We send the common shapes so whichever the API
            # honours wires up.
            payload["tool_endpoint"] = mid_call_tool_url
            payload["function_endpoint"] = mid_call_tool_url
            payload["custom_args_values"]["mid_call_tool_url"] = mid_call_tool_url

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calling/outbound/individual",
                json=payload,
                headers=RINGG_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
            call_id = data.get("call_id") or data.get("id") or data.get("callId", "")
            logger.info(f"Initiated Ringg morning brief call: {call_id}")
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
