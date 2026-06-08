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
    def _client(self, timeout: int = 30) -> httpx.AsyncClient:
        """Create an AsyncClient that follows redirects (Ringg may send 307)."""
        return httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    def _log_and_raise(self, resp: httpx.Response) -> None:
        """Log response body for non-2xx responses, then raise HTTPStatusError."""
        if resp.is_error:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            logger.error("Ringg API error %s %s: %s", resp.status_code, resp.url, body)
            resp.raise_for_status()
    async def create_agent(self, config: dict) -> str:
        """
        POST /public/agent — Create the SYNC assistant.
        Returns agent_id.
        """
        async with self._client(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/public/agent",
                json=config,
                headers=RINGG_HEADERS,
            )
            self._log_and_raise(resp)
            # Parse body safely — Ringg may return different envelopes.
            try:
                data = resp.json()
            except Exception:
                data = None

            agent_id = ""

            def _find_id(d):
                if not d:
                    return None
                if isinstance(d, dict):
                    for k in ("agent_id", "agentId", "id", "_id"):
                        v = d.get(k)
                        if v:
                            return v
                    # common envelope keys
                    for key in ("data", "agent", "result"):
                        if key in d:
                            found = _find_id(d[key])
                            if found:
                                return found
                    # if dict maps ids to objects, take first key
                    for k, v in d.items():
                        if isinstance(k, str) and len(k) > 8 and (isinstance(v, dict) or isinstance(v, str)):
                            # treat key as id candidate
                            return k
                return None

            agent_id = _find_id(data) or ""

            # Fallback: Location header sometimes contains the created resource URL
            if not agent_id:
                loc = resp.headers.get("Location") or resp.headers.get("location")
                if loc:
                    agent_id = loc.rstrip("/").split("/")[-1]

            if not agent_id:
                # Log full response body for debugging (already logged on error, but helpful)
                logger.warning("Could not parse agent id from Ringg response: %s", data or resp.text)

            logger.info(f"Created Ringg agent: {agent_id}")
            return agent_id

    async def get_voices(self, language: str = "en-IN") -> list:
        """
        GET /agent/voices?language=en-IN — Get available voice options.
        """
        async with self._client(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE_URL}/agent/voices",
                params={"language": language},
                headers=RINGG_HEADERS,
            )
            self._log_and_raise(resp)
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
        async with self._client(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calling/outbound/individual",
                json=payload,
                headers=RINGG_HEADERS,
            )
            self._log_and_raise(resp)
            data = resp.json()
            # Ringg wraps the response in {"status": "success", "data": {...}}
            envelope = data.get("data") if isinstance(data, dict) else None
            payload = envelope if isinstance(envelope, dict) else data
            call_id = (payload.get("call_id") or payload.get("id") or payload.get("callId", "")) if isinstance(payload, dict) else ""
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
        async with self._client(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calling/outbound/individual",
                json=payload,
                headers=RINGG_HEADERS,
            )
            self._log_and_raise(resp)
            data = resp.json()
            # Ringg wraps the response in {"status": "success", "data": {...}}
            envelope = data.get("data") if isinstance(data, dict) else None
            payload = envelope if isinstance(envelope, dict) else data
            call_id = (payload.get("call_id") or payload.get("id") or payload.get("callId", "")) if isinstance(payload, dict) else ""
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

        async with self._client(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calling/outbound/individual",
                json=payload,
                headers=RINGG_HEADERS,
            )
            self._log_and_raise(resp)
            data = resp.json()
            # Ringg wraps the response in {"status": "success", "data": {...}}
            envelope = data.get("data") if isinstance(data, dict) else None
            payload = envelope if isinstance(envelope, dict) else data
            call_id = (payload.get("call_id") or payload.get("id") or payload.get("callId", "")) if isinstance(payload, dict) else ""
            logger.info(f"Initiated Ringg morning brief call: {call_id}")
            return call_id

    async def get_call_details(self, call_id: str) -> dict:
        """GET /calling/history/{call_id}"""
        async with self._client(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE_URL}/calling/history/{call_id}",
                headers=RINGG_HEADERS,
            )
            self._log_and_raise(resp)
            return resp.json()

    async def upload_knowledge_base(self, name: str, content: str) -> str:
        """
        POST /kb — Upload client data as knowledge base.
        For inbound mode: agent uses KB to look up clients.
        Returns kb_id.
        """
        async with self._client(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE_URL}/kb",
                json={"name": name, "content": content},
                headers=RINGG_HEADERS,
            )
            self._log_and_raise(resp)
            data = resp.json()
            kb_id = data.get("kb_id") or data.get("id", "")
            logger.info(f"Uploaded knowledge base: {kb_id}")
            return kb_id

    async def patch_agent(self, agent_id: str, operation: str, **fields) -> bool:
        """Generic PATCH /agent/v1/ wrapper for Ringg's operation-based update API.
        Use for `edit_prompt`, `edit_intro_message`, `edit_voice`, etc.

        Ringg's API works via a single endpoint with an `operation` field; each
        operation has its own additional required fields (e.g. edit_prompt needs
        `agent_prompt`, edit_intro_message needs `intro_message`).
        """
        if not agent_id:
            return False
        payload = {"operation": operation, "agent_id": agent_id, **fields}
        async with self._client(timeout=15) as client:
            try:
                resp = await client.patch(
                    f"{self.BASE_URL}/agent/v1/",
                    json=payload, headers=RINGG_HEADERS,
                )
                if 200 <= resp.status_code < 300:
                    return True
                logger.warning("patch_agent %s on %s failed: %s %s",
                               operation, agent_id, resp.status_code, resp.text[:200])
            except Exception as e:
                logger.warning("patch_agent %s on %s error: %s", operation, agent_id, e)
        return False

    async def attach_from_number(self, agent_id: str, from_number_id: str) -> bool:
        """
        PATCH /agent/v1 (operation=edit_outbound_from_number_ids).
        Ringg requires the from_number to be EXPLICITLY ATTACHED to the agent's
        active version; passing it per call isn't enough. Without this the agent
        accepts the call payload (200 OK) but never actually dials.
        """
        if not from_number_id:
            return False
        payload = {
            "operation": "edit_outbound_from_number_ids",
            "agent_id": agent_id,
            "outbound_from_number_ids": [from_number_id],
        }
        async with self._client(timeout=15) as client:
            try:
                resp = await client.patch(
                    f"{self.BASE_URL}/agent/v1/",
                    json=payload, headers=RINGG_HEADERS,
                )
                if 200 <= resp.status_code < 300:
                    logger.info(f"Attached from-number {from_number_id} to agent {agent_id}")
                    return True
                logger.warning(
                    "Failed to attach from-number to %s: %s %s",
                    agent_id, resp.status_code,
                    resp.text[:200],
                )
            except Exception as e:
                logger.warning("attach_from_number error for %s: %s", agent_id, e)
        return False

    async def setup_webhooks(self, agent_id: str, callback_url: str) -> bool:
        """
        PATCH /agent/v1 — Subscribe to call events.
        Subscribes to: call_completed, platform_analysis_completed, all_processing_completed
        """
        base = {
            "agent_id": agent_id,
            "webhook_url": callback_url,
            "webhook_events": [
                "call_started",
                "call_completed",
                "platform_analysis_completed",
                "all_processing_completed",
            ],
        }

        # Try several payload shapes the Ringg API may expect.
        candidates = [
            base,
            {"operation": "subscribe", **base},
            {"operation": "update", **base},
            {"agent_id": agent_id, "operations": [{"operation": "subscribe", "webhook_url": callback_url, "events": base["webhook_events"]}]},
            {"agent_id": agent_id, "webhook": {"url": callback_url, "events": base["webhook_events"]}},
        ]

        last_resp = None
        async with self._client(timeout=15) as client:
            for payload in candidates:
                try:
                    resp = await client.patch(
                        f"{self.BASE_URL}/agent/v1",
                        json=payload,
                        headers=RINGG_HEADERS,
                    )
                except Exception as exc:
                    logger.debug("Webhook attempt exception: %s", exc)
                    last_resp = None
                    continue

                last_resp = resp
                if resp.status_code >= 200 and resp.status_code < 300:
                    logger.info(f"Webhooks configured for agent {agent_id} (payload: %s)", payload)
                    return True
                # Try next candidate
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                logger.debug("Webhook attempt failed (%s): %s", resp.status_code, body)

        # If we reach here none of the payloads worked — log and continue.
        if last_resp is not None:
            try:
                body = last_resp.json()
            except Exception:
                body = last_resp.text
            logger.warning("Failed to configure Ringg webhooks for %s: %s %s", agent_id, last_resp.status_code, body)
        else:
            logger.warning("Failed to configure Ringg webhooks for %s: no response", agent_id)
        return False


ringg_service = RinggService()
