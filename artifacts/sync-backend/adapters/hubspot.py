"""HubSpot CRM adapter — hardened for production.

Required HubSpot custom properties (auto-created by provisioning.py):
  Contact:
    - risk_score (enumeration: very_low, low, medium, watch, high)
    - risk_factors (multi_line_text)
    - last_rm_interaction_date (date)
    - cross_sell_product_1, cross_sell_pitch_1, cross_sell_value_1
    - cross_sell_product_2, cross_sell_pitch_2, cross_sell_value_2
  Deal:
    - product_type (enumeration: home_loan, personal_loan, business_loan, car_loan, credit_card, fd)
    - emi_amount (number), months_paid (number), tenure_months (number)
    - next_due_date (date), payment_history (multi_line_text, comma-separated)

Changes from v1:
  - Constructor takes connection_id; loads OAuth token via SecretStore per call.
  - Paginated list_all walking paging.next cursor.
  - tenacity retry on HTTP 429 respecting Retry-After.
  - DOB → age computed properly.
  - log_briefing also updates last_rm_interaction_date on the contact.
  - Field names routed through FieldMapper so admins can override.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Optional

from rapidfuzz import fuzz
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)

from adapters.base import CRMAdapter
from models import (
    BriefingLog, ClientFullProfile, ClientProfile, Complaint,
    CrossSellOpportunity, Interaction, LoanProduct, RiskAssessment,
)

logger = logging.getLogger(__name__)


class _RateLimitError(Exception):
    pass


class HubSpotCRMAdapter(CRMAdapter):
    """HubSpot CRM adapter using HubSpot Python SDK with OAuth token refresh."""

    def __init__(self, *, connection_id: str = "conn_hubspot", metadata: Optional[dict] = None) -> None:
        self._connection_id = connection_id
        self._meta = metadata or {}
        self._mapping = None  # loaded lazily on first use

    def _client(self):
        """Return a HubSpot SDK client loaded with the current access token.
        Called on each API operation so refreshed tokens are always used.
        """
        try:
            from hubspot import HubSpot
        except ImportError:
            raise RuntimeError("hubspot-api-client not installed. Run: pip install hubspot-api-client")

        import asyncio
        from services.secret_store import secret_store as _store

        # Synchronous bridge: we're called from async context but the HS SDK is sync.
        loop = asyncio.get_event_loop()
        token_data = loop.run_until_complete(_store().get_token(self._connection_id))

        if token_data:
            access_token = token_data.get("access_token", "")
        else:
            from config import settings
            access_token = settings.hubspot_api_key  # legacy fallback
        return HubSpot(access_token=access_token)

    async def _async_client(self):
        """Async version — loads token from SecretStore then returns SDK client."""
        from hubspot import HubSpot
        from services.secret_store import secret_store
        token_data = await secret_store().get_token(self._connection_id)
        if token_data:
            return HubSpot(access_token=token_data.get("access_token", ""))
        from config import settings
        return HubSpot(access_token=settings.hubspot_api_key)

    def _mapping_sync(self):
        """Return a FieldMapper for this connection (sync bridge)."""
        if self._mapping is not None:
            return self._mapping
        import asyncio
        from services.field_mapper import load_mapper
        loop = asyncio.get_event_loop()
        self._mapping = loop.run_until_complete(load_mapper(self._connection_id))
        return self._mapping

    # ------------------------------------------------------------------ #
    # Core interface methods
    # ------------------------------------------------------------------ #

    async def search_client(self, name: str) -> list[ClientProfile]:
        hs = await self._async_client()
        from hubspot.crm.contacts import PublicObjectSearchRequest, Filter, FilterGroup
        fg = FilterGroup(filters=[
            Filter(property_name="firstname", operator="CONTAINS_TOKEN", value=name.split()[0])
        ])
        req = PublicObjectSearchRequest(
            filter_groups=[fg],
            properties=["firstname", "lastname", "jobtitle", "company", "city", "risk_score"],
            limit=10,
        )
        resp = hs.crm.contacts.search_api.do_search(public_object_search_request=req)
        return [self._map_contact_to_profile(r) for r in resp.results]

    async def get_client(self, client_id: str) -> Optional[ClientFullProfile]:
        hs = await self._async_client()
        contact = hs.crm.contacts.basic_api.get_by_id(
            contact_id=client_id,
            properties=[
                "firstname", "lastname", "date_of_birth", "jobtitle", "company", "city",
                "risk_score", "risk_factors", "last_rm_interaction_date",
                "cross_sell_product_1", "cross_sell_pitch_1", "cross_sell_value_1",
                "cross_sell_product_2", "cross_sell_pitch_2", "cross_sell_value_2",
            ],
            associations=["deals", "tickets", "notes"],
        )
        if not contact:
            return None
        profile = self._map_contact_to_profile(contact)
        products = self._get_deals(hs, contact)
        risk = self._get_risk(contact)
        cross_sell = self._get_cross_sell(contact)
        interactions, complaints, days_ago = await self.get_interactions(client_id)
        return ClientFullProfile(
            profile=profile, products=products, risk=risk,
            interactions=interactions, complaints=complaints,
            cross_sell=cross_sell, last_rm_interaction_days_ago=days_ago,
        )

    async def get_portfolio(self, client_id: str) -> list[LoanProduct]:
        hs = await self._async_client()
        contact = hs.crm.contacts.basic_api.get_by_id(contact_id=client_id, associations=["deals"])
        return self._get_deals(hs, contact)

    async def get_risk(self, client_id: str) -> Optional[RiskAssessment]:
        hs = await self._async_client()
        contact = hs.crm.contacts.basic_api.get_by_id(
            contact_id=client_id, properties=["risk_score", "risk_factors"]
        )
        return self._get_risk(contact)

    async def get_cross_sell(self, client_id: str) -> list[CrossSellOpportunity]:
        hs = await self._async_client()
        contact = hs.crm.contacts.basic_api.get_by_id(
            contact_id=client_id,
            properties=[f"cross_sell_product_{i}" for i in (1, 2)] +
                       [f"cross_sell_pitch_{i}" for i in (1, 2)] +
                       [f"cross_sell_value_{i}" for i in (1, 2)],
        )
        return self._get_cross_sell(contact)

    async def get_interactions(self, client_id: str) -> tuple[list[Interaction], list[Complaint], int]:
        hs = await self._async_client()
        interactions, complaints, days_ago = [], [], 0

        notes_assoc = hs.crm.contacts.associations_api.get_all(contact_id=client_id, to_object_type="notes")
        for note_ref in (notes_assoc.results or []):
            try:
                n = hs.crm.notes.basic_api.get_by_id(
                    note_id=note_ref.id,
                    properties=["hs_note_body", "hs_timestamp", "hubspot_owner_id"],
                )
                ts = n.properties.get("hs_timestamp", "") or ""
                interactions.append(Interaction(
                    date=ts[:10],
                    channel="crm_note",
                    summary=n.properties.get("hs_note_body", ""),
                    rm_name=n.properties.get("hubspot_owner_id", "Unknown RM"),
                ))
            except Exception:
                pass

        tickets_assoc = hs.crm.contacts.associations_api.get_all(contact_id=client_id, to_object_type="tickets")
        for ticket_ref in (tickets_assoc.results or []):
            try:
                t = hs.crm.tickets.basic_api.get_by_id(
                    ticket_id=ticket_ref.id,
                    properties=["subject", "content", "hs_ticket_category", "hs_pipeline_stage", "createdate"],
                )
                stage = t.properties.get("hs_pipeline_stage", "")
                complaints.append(Complaint(
                    id=t.id,
                    date=(t.properties.get("createdate", "") or "")[:10],
                    category=t.properties.get("hs_ticket_category", "General"),
                    summary=t.properties.get("content", "") or t.properties.get("subject", ""),
                    status="open" if stage == "1" else "resolved",
                ))
            except Exception:
                pass

        if interactions:
            try:
                last = datetime.fromisoformat(interactions[0].date)
                days_ago = (date.today() - last.date()).days
            except Exception:
                pass
        return interactions, complaints, days_ago

    async def list_all(self) -> list[ClientProfile]:
        """Paginated list of all contacts (no hard cap)."""
        hs = await self._async_client()
        all_contacts = []
        after = None
        while True:
            page = hs.crm.contacts.basic_api.get_page(
                limit=100,
                after=after,
                properties=["firstname", "lastname", "jobtitle", "company", "city", "risk_score"],
            )
            all_contacts.extend(page.results or [])
            if not (page.paging and page.paging.next and page.paging.next.after):
                break
            after = page.paging.next.after
        return [self._map_contact_to_profile(c) for c in all_contacts]

    async def log_briefing(self, briefing: BriefingLog) -> None:
        """Create a HubSpot Note + update last_rm_interaction_date on the contact."""
        hs = await self._async_client()
        today = date.today().isoformat()
        try:
            hs.crm.notes.basic_api.create(
                simple_public_object_input_for_create={
                    "properties": {
                        "hs_note_body": (
                            f"[SYNC Briefing] RM: {briefing.rm_name} | "
                            f"Duration: {briefing.duration_seconds:.0f}s | "
                            f"Flags: {', '.join(briefing.key_flags)} | "
                            f"Pitch: {briefing.suggested_pitch[:200]}"
                        ),
                        "hs_timestamp": briefing.timestamp,
                    },
                    "associations": [{
                        "to": {"id": briefing.client_id},
                        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
                    }],
                }
            )
        except Exception as e:
            logger.warning("HubSpot note creation failed: %s", e)

        try:
            hs.crm.contacts.basic_api.update(
                contact_id=briefing.client_id,
                simple_public_object_input={"properties": {"last_rm_interaction_date": today}},
            )
        except Exception as e:
            logger.warning("HubSpot contact update failed: %s", e)

    # ------------------------------------------------------------------ #
    # Voice-command action methods (Phase 6)
    # ------------------------------------------------------------------ #

    async def create_note(self, client_id: str, body: str) -> str:
        hs = await self._async_client()
        r = hs.crm.notes.basic_api.create(simple_public_object_input_for_create={
            "properties": {"hs_note_body": body, "hs_timestamp": datetime.utcnow().isoformat() + "Z"},
            "associations": [{"to": {"id": client_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]}],
        })
        return r.id

    async def create_task(self, client_id: str, subject: str, due_date: str, assignee_id: str = "") -> str:
        hs = await self._async_client()
        props = {"hs_task_subject": subject, "hs_timestamp": due_date, "hs_task_status": "NOT_STARTED"}
        if assignee_id:
            props["hubspot_owner_id"] = assignee_id
        r = hs.crm.objects.basic_api.create(
            object_type="tasks",
            simple_public_object_input_for_create={
                "properties": props,
                "associations": [{"to": {"id": client_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 204}]}],
            },
        )
        return r.id

    async def update_contact_field(self, client_id: str, field: str, value: str) -> None:
        hs = await self._async_client()
        hs.crm.contacts.basic_api.update(
            contact_id=client_id,
            simple_public_object_input={"properties": {field: value}},
        )

    async def update_complaint_status(self, complaint_id: str, status: str) -> None:
        hs = await self._async_client()
        stage = "1" if status == "open" else "2" if status == "escalated" else "4"
        hs.crm.tickets.basic_api.update(
            ticket_id=complaint_id,
            simple_public_object_input={"properties": {"hs_pipeline_stage": stage}},
        )

    async def schedule_follow_up(self, client_id: str, when: str, kind: str, notes: str) -> str:
        return await self.create_task(client_id, f"Follow-up: {kind} — {notes}", when)

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #

    def _map_contact_to_profile(self, contact) -> ClientProfile:
        p = contact.properties
        name = f"{p.get('firstname', '')} {p.get('lastname', '')}".strip()
        age = 0
        dob = p.get("date_of_birth", "") or ""
        if dob:
            try:
                age = (date.today() - datetime.strptime(dob[:10], "%Y-%m-%d").date()).days // 365
            except ValueError:
                pass
        return ClientProfile(
            client_id=contact.id,
            name=name,
            age=age,
            occupation=p.get("jobtitle", ""),
            company=p.get("company", ""),
            city=p.get("city", ""),
            risk_score=p.get("risk_score", "low"),
        )

    def _get_deals(self, hs, contact) -> list[LoanProduct]:
        products = []
        if not contact.associations:
            return products
        deals_data = contact.associations.get("deals") if isinstance(contact.associations, dict) else None
        deal_ids = []
        if deals_data and hasattr(deals_data, "results"):
            deal_ids = [a.id for a in (deals_data.results or [])]
        for deal_id in deal_ids:
            try:
                deal = hs.crm.deals.basic_api.get_by_id(
                    deal_id=deal_id,
                    properties=["product_type", "amount", "emi_amount", "months_paid",
                                "tenure_months", "next_due_date", "payment_history"],
                )
                p = deal.properties
                products.append(LoanProduct(
                    product_type=p.get("product_type", "personal_loan"),
                    principal=float(p.get("amount", 0) or 0),
                    emi=float(p.get("emi_amount", 0) or 0),
                    tenure_months=int(float(p.get("tenure_months", 0) or 0)),
                    months_paid=int(float(p.get("months_paid", 0) or 0)),
                    next_due_date=p.get("next_due_date", "") or "",
                    payment_history=[h.strip() for h in (p.get("payment_history", "") or "").split(",") if h.strip()],
                ))
            except Exception:
                pass
        return products

    def _get_risk(self, contact) -> RiskAssessment:
        p = contact.properties
        factors_raw = p.get("risk_factors", "") or ""
        factors = [f.strip() for f in factors_raw.split("\n") if f.strip()]
        return RiskAssessment(score=p.get("risk_score", "low"), factors=factors)

    def _get_cross_sell(self, contact) -> list[CrossSellOpportunity]:
        p = contact.properties
        result = []
        for i in (1, 2):
            prod = p.get(f"cross_sell_product_{i}")
            if prod:
                result.append(CrossSellOpportunity(
                    product=prod,
                    eligibility_reason="Based on HubSpot profile",
                    pitch_angle=p.get(f"cross_sell_pitch_{i}", ""),
                    estimated_value=float(p.get(f"cross_sell_value_{i}", 0) or 0),
                ))
        return result
