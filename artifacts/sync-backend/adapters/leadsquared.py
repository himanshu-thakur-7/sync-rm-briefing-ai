"""
LeadSquared CRM adapter.

LeadSquared is the dominant CRM/LMS for Indian banks, NBFCs, and
insurance companies. Authentication uses a static Access Key + Secret Key
pair (no OAuth — LeadSquared uses HMAC-based API auth).

API base: https://{region}.leadsquared.com/v2/  (region: api-in21, api-us11, etc.)

Custom fields required on Lead entity:
  - mx_Risk_Score (String: very_low | low | medium | watch | high)
  - mx_Risk_Factors (String, pipe-separated)
  - mx_Last_RM_Interaction_Days (Number)
  - mx_Cross_Sell_Product_1 (String)
  - mx_Cross_Sell_Pitch_1 (String)
  - mx_Cross_Sell_Value_1 (Number)
  - mx_Cross_Sell_Product_2 (String) — optional
  - mx_Cross_Sell_Pitch_2 (String) — optional
  - mx_Cross_Sell_Value_2 (Number) — optional
  - mx_DOB (Date)

Activity type map (defaults — override via FieldMapper):
  5 = Phone, 3 = Branch, 6 = Email, 9 = App

Opportunity (Loan) entity:
  Custom entity "Loan" or use the built-in Opportunity module with custom fields:
  ProductType, Principal, EMIAmount, TenureMonths, MonthsPaid, NextDueDate, PaymentHistory

Complaint / Ticket entity:
  Custom entity "Complaint" or Service Cloud tickets:
  Category, Description, Status (open | escalated | resolved), CreatedDate

Writeback:
  log_briefing → POST /v2/LeadManagement.svc/AddActivity with ActivityType=101 (SYNC Briefing custom type)
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import httpx
from rapidfuzz import fuzz

from adapters.base import CRMAdapter
from models import (
    BriefingLog, ClientFullProfile, ClientProfile, Complaint,
    CrossSellOpportunity, Interaction, LoanProduct, RiskAssessment,
)

logger = logging.getLogger(__name__)

_ACTIVITY_CHANNEL_MAP = {
    5: "phone",
    3: "branch",
    6: "email",
    9: "app",
}


class LeadSquaredCRMAdapter(CRMAdapter):
    """LeadSquared REST API adapter using httpx."""

    def __init__(
        self,
        *,
        connection_id: str = "lsq_default",
        metadata: Optional[dict] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        from config import settings

        meta = metadata or {}
        self._access_key = meta.get("access_key") or settings.leadsquared_access_key
        self._secret_key = meta.get("secret_key") or settings.leadsquared_secret_key
        region = meta.get("region") or settings.leadsquared_region
        self._base_url = f"https://{region}.leadsquared.com/v2"
        self._connection_id = connection_id
        self._http = http_client  # override for FakeLeadSquared

    def _client(self) -> httpx.AsyncClient:
        """Return a fresh client per call. Subclasses (FakeLeadSquared) may
        inject a factory callable instead of a pre-built client instance."""
        if callable(self._http):
            return self._http()
        if self._http is not None:
            return self._http  # pre-built client (legacy path)
        return httpx.AsyncClient(
            base_url=self._base_url,
            params={"accessKey": self._access_key, "secretKey": self._secret_key},
            timeout=20,
        )

    async def _get(self, path: str, params: Optional[dict] = None) -> dict | list:
        async with self._client() as c:
            r = await c.get(path, params=params or {})
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, json: dict) -> dict:
        async with self._client() as c:
            r = await c.post(path, json=json)
            r.raise_for_status()
            return r.json()

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #

    def _lead_to_profile(self, lead: dict) -> ClientProfile:
        fields = {f["SchemaName"]: f["Value"] for f in lead.get("Fields", [])}
        dob_str = fields.get("mx_DOB", "")
        age = 0
        if dob_str:
            try:
                age = (date.today() - datetime.strptime(dob_str[:10], "%Y-%m-%d").date()).days // 365
            except ValueError:
                pass
        first = lead.get("FirstName", "")
        last = lead.get("LastName", "")
        return ClientProfile(
            client_id=lead["ProspectID"],
            name=f"{first} {last}".strip(),
            age=age,
            occupation=lead.get("JobTitle", ""),
            company=lead.get("Company", ""),
            city=lead.get("City", ""),
            risk_score=fields.get("mx_Risk_Score", "low"),
        )

    def _lead_to_risk(self, lead: dict) -> RiskAssessment:
        fields = {f["SchemaName"]: f["Value"] for f in lead.get("Fields", [])}
        factors_raw = fields.get("mx_Risk_Factors", "")
        factors = [f.strip() for f in factors_raw.split("|") if f.strip()]
        return RiskAssessment(score=fields.get("mx_Risk_Score", "low"), factors=factors)

    def _lead_to_cross_sell(self, lead: dict) -> list[CrossSellOpportunity]:
        fields = {f["SchemaName"]: f["Value"] for f in lead.get("Fields", [])}
        result = []
        if fields.get("mx_Cross_Sell_Product_1"):
            result.append(CrossSellOpportunity(
                product=fields["mx_Cross_Sell_Product_1"],
                eligibility_reason="Based on CRM profile",
                pitch_angle=fields.get("mx_Cross_Sell_Pitch_1", ""),
                estimated_value=float(fields.get("mx_Cross_Sell_Value_1", 0) or 0),
            ))
        if fields.get("mx_Cross_Sell_Product_2"):
            result.append(CrossSellOpportunity(
                product=fields["mx_Cross_Sell_Product_2"],
                eligibility_reason="Based on CRM profile",
                pitch_angle=fields.get("mx_Cross_Sell_Pitch_2", ""),
                estimated_value=float(fields.get("mx_Cross_Sell_Value_2", 0) or 0),
            ))
        return result

    def _opp_to_loan(self, opp: dict) -> LoanProduct:
        raw_history = opp.get("PaymentHistory", "")
        history = [h.strip() for h in raw_history.split(",") if h.strip()] if raw_history else []
        return LoanProduct(
            product_type=opp.get("ProductType", "personal_loan"),
            principal=float(opp.get("Principal", 0)),
            emi=float(opp.get("EMIAmount", 0)),
            tenure_months=int(opp.get("TenureMonths", 0)),
            months_paid=int(opp.get("MonthsPaid", 0)),
            next_due_date=opp.get("NextDueDate", ""),
            payment_history=history,
        )

    def _activity_to_interaction(self, act: dict) -> Interaction:
        channel = _ACTIVITY_CHANNEL_MAP.get(act.get("ActivityType", 5), "phone")
        raw_date = act.get("ActivityDate", "")
        try:
            parsed = datetime.strptime(raw_date[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            parsed = raw_date
        return Interaction(
            date=parsed,
            channel=channel,
            summary=act.get("Note", ""),
            rm_name=act.get("OwnerName", "Unknown RM"),
        )

    def _ticket_to_complaint(self, ticket: dict) -> Complaint:
        raw_date = ticket.get("CreatedDate", "")
        try:
            parsed = datetime.strptime(raw_date[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            parsed = raw_date
        return Complaint(
            id=ticket.get("TicketId", ""),
            date=parsed,
            category=ticket.get("Category", "General"),
            summary=ticket.get("Description", ""),
            status=ticket.get("Status", "open"),
        )

    # ------------------------------------------------------------------ #
    # CRMAdapter interface
    # ------------------------------------------------------------------ #

    async def list_all(self) -> list[ClientProfile]:
        data = await self._get(
            "/LeadManagement.svc/Leads.GetAll",
            {"pageIndex": 1, "pageSize": 200},
        )
        leads = data if isinstance(data, list) else data.get("List", [])
        return [self._lead_to_profile(l) for l in leads]

    async def search_client(self, name: str) -> list[ClientProfile]:
        """Fuzzy search using partial_ratio — handles first-name-only queries."""
        all_clients = await self.list_all()
        results = []
        for cp in all_clients:
            score = fuzz.partial_ratio(name.lower(), cp.name.lower())
            if score >= 70:
                results.append((score, cp))
        results.sort(reverse=True, key=lambda x: x[0])
        return [r[1] for r in results]

    async def get_client(self, client_id: str) -> Optional[ClientFullProfile]:
        try:
            data = await self._get(
                "/LeadManagement.svc/Lead.GetById",
                {"id": client_id},
            )
        except httpx.HTTPStatusError:
            return None
        lead = data if isinstance(data, dict) else (data[0] if data else None)
        if not lead:
            return None

        profile = self._lead_to_profile(lead)
        risk = self._lead_to_risk(lead)
        cross_sell = self._lead_to_cross_sell(lead)
        products = await self.get_portfolio(client_id)
        interactions, complaints, days_ago = await self.get_interactions(client_id)

        return ClientFullProfile(
            profile=profile,
            products=products,
            risk=risk,
            interactions=interactions,
            complaints=complaints,
            cross_sell=cross_sell,
            last_rm_interaction_days_ago=days_ago,
        )

    async def get_portfolio(self, client_id: str) -> list[LoanProduct]:
        try:
            data = await self._get(
                "/ProspectActivity.svc/GetOpportunitiesByLeadId",
                {"leadId": client_id},
            )
        except Exception:
            return []
        opps = data if isinstance(data, list) else data.get("List", [])
        return [self._opp_to_loan(o) for o in opps]

    async def get_risk(self, client_id: str) -> Optional[RiskAssessment]:
        try:
            data = await self._get(
                "/LeadManagement.svc/Lead.GetById",
                {"id": client_id},
            )
        except Exception:
            return None
        lead = data if isinstance(data, dict) else (data[0] if data else None)
        return self._lead_to_risk(lead) if lead else None

    async def get_cross_sell(self, client_id: str) -> list[CrossSellOpportunity]:
        try:
            data = await self._get(
                "/LeadManagement.svc/Lead.GetById",
                {"id": client_id},
            )
        except Exception:
            return []
        lead = data if isinstance(data, dict) else (data[0] if data else None)
        return self._lead_to_cross_sell(lead) if lead else []

    async def get_interactions(self, client_id: str) -> tuple[list[Interaction], list[Complaint], int]:
        interactions, complaints, days_ago = [], [], 0
        try:
            acts = await self._get(
                "/ProspectActivity.svc/GetActivitiesByLeadId",
                {"leadId": client_id, "pageIndex": 1, "pageSize": 50},
            )
            act_list = acts if isinstance(acts, list) else acts.get("List", [])
            interactions = [self._activity_to_interaction(a) for a in act_list if a.get("ActivityType") != 101]
            if interactions:
                try:
                    last = datetime.strptime(interactions[0].date[:10], "%Y-%m-%d").date()
                    days_ago = (date.today() - last).days
                except ValueError:
                    pass
        except Exception as e:
            logger.warning("LSQ activities fetch failed for %s: %s", client_id, e)

        try:
            tix = await self._get(
                "/CustomObject.svc/GetObjectById",
                {"objectSchemaName": "mx_Complaints", "leadId": client_id},
            )
            tix_list = tix if isinstance(tix, list) else tix.get("List", [])
            complaints = [self._ticket_to_complaint(t) for t in tix_list]
        except Exception as e:
            logger.warning("LSQ complaints fetch failed for %s: %s", client_id, e)

        return interactions, complaints, days_ago

    async def log_briefing(self, briefing: BriefingLog) -> None:
        """Create a SYNC Briefing activity (ActivityType=101) on the lead."""
        note = (
            f"[SYNC Briefing] RM: {briefing.rm_name} | "
            f"Duration: {briefing.duration_seconds:.0f}s | "
            f"Flags: {', '.join(briefing.key_flags)} | "
            f"Pitch: {briefing.suggested_pitch[:200]}"
        )
        try:
            await self._post(
                "/ProspectActivity.svc/Create",
                {
                    "RelatedProspectId": briefing.client_id,
                    "ActivityEvent": 101,
                    "ActivityNote": note,
                    "ActivityDateTime": briefing.timestamp,
                },
            )
        except Exception as e:
            logger.error("LSQ log_briefing failed for %s: %s", briefing.client_id, e)

    # ------------------------------------------------------------------ #
    # Voice-command action methods (Phase 6)
    # ------------------------------------------------------------------ #

    async def create_note(self, client_id: str, body: str) -> str:
        resp = await self._post(
            "/ProspectActivity.svc/Create",
            {"RelatedProspectId": client_id, "ActivityEvent": 5, "ActivityNote": body},
        )
        return str(resp.get("Message", {}).get("Id", ""))

    async def create_task(self, client_id: str, subject: str, due_date: str, assignee_id: str = "") -> str:
        resp = await self._post(
            "/ProspectActivity.svc/Create",
            {
                "RelatedProspectId": client_id,
                "ActivityEvent": 102,
                "ActivityNote": subject,
                "ActivityDateTime": due_date,
            },
        )
        return str(resp.get("Message", {}).get("Id", ""))

    async def update_contact_field(self, client_id: str, field: str, value: str) -> None:
        await self._post(
            "/LeadManagement.svc/Lead.Update",
            {"LeadId": client_id, "Fields": [{"SchemaName": field, "Value": value}]},
        )

    async def update_complaint_status(self, complaint_id: str, status: str) -> None:
        await self._post(
            "/CustomObject.svc/UpdateObject",
            {"ObjectSchemaName": "mx_Complaints", "ObjectId": complaint_id, "Fields": [{"SchemaName": "Status", "Value": status}]},
        )

    async def schedule_follow_up(self, client_id: str, when: str, kind: str, notes: str) -> str:
        return await self.create_task(client_id, f"Follow-up: {kind} — {notes}", when)
