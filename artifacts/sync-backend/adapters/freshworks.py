"""Freshworks CRM (Freshsales) adapter.

Uses API-key auth (no OAuth — Freshsales uses static keys passed as
`Authorization: Token token={api_key}` header).

API base: https://{subdomain}.myfreshworks.com/crm/sales/api/v2/

Resources: contacts, deals, notes, tasks.

Custom fields (cf_*) required:
  contacts: cf_risk_score, cf_risk_factors, cf_last_rm_interaction, cf_cross_sell_product_1/2, cf_cross_sell_pitch_1/2, cf_cross_sell_value_1/2
  deals: cf_product_type, cf_emi_amount, cf_months_paid, cf_tenure_months, cf_next_due_date, cf_payment_history
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import httpx
from rapidfuzz import fuzz
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from adapters.base import CRMAdapter
from models import (
    BriefingLog, ClientFullProfile, ClientProfile, Complaint,
    CrossSellOpportunity, Interaction, LoanProduct, RiskAssessment,
)

logger = logging.getLogger(__name__)


def _is_throttled(exc: Exception) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


class FreshworksCRMAdapter(CRMAdapter):
    """Freshsales REST API adapter."""

    def __init__(self, *, connection_id: str = "freshworks_default", metadata: Optional[dict] = None) -> None:
        self._connection_id = connection_id
        from config import settings
        meta = metadata or {}
        subdomain = meta.get("subdomain") or settings.freshworks_subdomain
        self._base = f"https://{subdomain}.myfreshworks.com/crm/sales/api/v2"

    async def _headers(self) -> dict:
        from services.secret_store import secret_store
        token = await secret_store().get_token(self._connection_id)
        api_key = (token or {}).get("api_key", "")
        if not api_key:
            from config import settings
            api_key = settings.freshworks_api_key
        return {"Authorization": f"Token token={api_key}", "Content-Type": "application/json"}

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5), retry=retry_if_exception(_is_throttled))
    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{self._base}/{path}", headers=headers, params=params or {})
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, json: dict) -> dict:
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{self._base}/{path}", headers=headers, json=json)
            r.raise_for_status()
            return r.json()

    def _contact_to_profile(self, c: dict) -> ClientProfile:
        cf = c.get("custom_field", {}) or {}
        dob_str = cf.get("cf_date_of_birth", "") or ""
        age = 0
        if dob_str:
            try:
                age = (date.today() - datetime.strptime(dob_str[:10], "%Y-%m-%d").date()).days // 365
            except ValueError:
                pass
        return ClientProfile(
            client_id=str(c["id"]),
            name=c.get("display_name", ""),
            age=age,
            occupation=c.get("job_title", ""),
            company=c.get("company", {}).get("name", "") if isinstance(c.get("company"), dict) else "",
            city=c.get("city", ""),
            risk_score=cf.get("cf_risk_score", "low"),
        )

    async def list_all(self) -> list[ClientProfile]:
        data = await self._get("contacts/view/all", {"per_page": 200})
        return [self._contact_to_profile(c) for c in data.get("contacts", [])]

    async def search_client(self, name: str) -> list[ClientProfile]:
        try:
            data = await self._get("contacts/search", {"q": name, "per_page": 10})
            return [self._contact_to_profile(c) for c in data.get("contacts", [])]
        except Exception:
            all_c = await self.list_all()
            return [c for c in all_c if fuzz.token_sort_ratio(name.lower(), c.name.lower()) >= 70]

    async def get_client(self, client_id: str) -> Optional[ClientFullProfile]:
        try:
            data = await self._get(f"contacts/{client_id}")
        except Exception:
            return None
        contact = data.get("contact", data)
        cf = contact.get("custom_field", {}) or {}
        profile = self._contact_to_profile(contact)
        risk = RiskAssessment(
            score=cf.get("cf_risk_score", "low"),
            factors=[f.strip() for f in (cf.get("cf_risk_factors", "") or "").split("|") if f.strip()],
        )
        cross_sell = []
        for i in (1, 2):
            prod = cf.get(f"cf_cross_sell_product_{i}")
            if prod:
                cross_sell.append(CrossSellOpportunity(
                    product=prod, eligibility_reason="Based on Freshworks profile",
                    pitch_angle=cf.get(f"cf_cross_sell_pitch_{i}", ""),
                    estimated_value=float(cf.get(f"cf_cross_sell_value_{i}", 0) or 0),
                ))
        products = await self.get_portfolio(client_id)
        interactions, complaints, days_ago = await self.get_interactions(client_id)
        return ClientFullProfile(profile=profile, products=products, risk=risk,
                                  interactions=interactions, complaints=complaints,
                                  cross_sell=cross_sell, last_rm_interaction_days_ago=days_ago)

    async def get_portfolio(self, client_id: str) -> list[LoanProduct]:
        try:
            data = await self._get(f"contacts/{client_id}/deals")
            products = []
            for d in data.get("deals", []):
                cf = d.get("custom_field", {}) or {}
                products.append(LoanProduct(
                    product_type=cf.get("cf_product_type", "personal_loan"),
                    principal=float(d.get("amount", 0) or 0),
                    emi=float(cf.get("cf_emi_amount", 0) or 0),
                    tenure_months=int(cf.get("cf_tenure_months", 0) or 0),
                    months_paid=int(cf.get("cf_months_paid", 0) or 0),
                    next_due_date=(cf.get("cf_next_due_date", "") or "")[:10],
                    payment_history=[h.strip() for h in (cf.get("cf_payment_history", "") or "").split(",") if h.strip()],
                ))
            return products
        except Exception:
            return []

    async def get_risk(self, client_id: str) -> Optional[RiskAssessment]:
        client = await self.get_client(client_id)
        return client.risk if client else None

    async def get_cross_sell(self, client_id: str) -> list[CrossSellOpportunity]:
        client = await self.get_client(client_id)
        return client.cross_sell if client else []

    async def get_interactions(self, client_id: str) -> tuple[list[Interaction], list[Complaint], int]:
        interactions, complaints, days_ago = [], [], 0
        try:
            data = await self._get(f"contacts/{client_id}/activities")
            for act in data.get("activities", []):
                dt = (act.get("created_at", "") or "")[:10]
                interactions.append(Interaction(date=dt, channel="phone", summary=act.get("notes", "") or act.get("title", ""), rm_name="RM"))
            if interactions:
                try:
                    days_ago = (date.today() - datetime.strptime(interactions[0].date, "%Y-%m-%d").date()).days
                except ValueError:
                    pass
        except Exception as e:
            logger.warning("Freshworks activities failed: %s", e)
        return interactions, complaints, days_ago

    async def log_briefing(self, briefing: BriefingLog) -> None:
        try:
            await self._post(f"contacts/{briefing.client_id}/notes", {
                "note": {"description": f"[SYNC Briefing] RM: {briefing.rm_name} | Duration: {briefing.duration_seconds:.0f}s | Flags: {', '.join(briefing.key_flags)} | Pitch: {briefing.suggested_pitch[:200]}"}
            })
        except Exception as e:
            logger.error("Freshworks log_briefing failed: %s", e)

    async def create_note(self, client_id: str, body: str) -> str:
        r = await self._post(f"contacts/{client_id}/notes", {"note": {"description": body}})
        return str(r.get("note", {}).get("id", ""))

    async def create_task(self, client_id: str, subject: str, due_date: str, assignee_id: str = "") -> str:
        r = await self._post("tasks", {"task": {"title": subject, "due_date": due_date, "targetable_id": client_id, "targetable_type": "Contact"}})
        return str(r.get("task", {}).get("id", ""))

    async def update_contact_field(self, client_id: str, field: str, value: str) -> None:
        await self._post(f"contacts/{client_id}", {"contact": {"custom_field": {field: value}}})

    async def update_complaint_status(self, complaint_id: str, status: str) -> None:
        logger.warning("Freshworks complaint status update not directly supported via standard API")

    async def schedule_follow_up(self, client_id: str, when: str, kind: str, notes: str) -> str:
        return await self.create_task(client_id, f"Follow-up: {kind} — {notes}", when)
