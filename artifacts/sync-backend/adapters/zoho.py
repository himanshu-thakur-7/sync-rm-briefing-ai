"""Zoho CRM v2 adapter.

OAuth2 — uses Authlib tokens stored via SecretStore.
API base: https://www.zohoapis.in/crm/v2  (or api_domain from token response)

Modules used: Contacts, Deals, Cases (complaints), Tasks (interactions), Notes.

Custom fields required (see provisioning.py for full spec):
  Contacts: Risk_Score, Risk_Factors, Last_RM_Interaction_Date, Cross_Sell_Product_1/2, Cross_Sell_Pitch_1/2, Cross_Sell_Value_1/2
  Deals: Product_Type, EMI_Amount, Months_Paid, Tenure_Months, Next_Due_Date, Payment_History
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


def _is_rate_limited(exc: Exception) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


class ZohoCRMAdapter(CRMAdapter):
    """Zoho CRM v2 REST adapter."""

    def __init__(self, *, connection_id: str = "zoho_default", metadata: Optional[dict] = None) -> None:
        self._connection_id = connection_id
        self._meta = metadata or {}
        self._api_domain = self._meta.get("api_domain", "https://www.zohoapis.in")

    async def _headers(self) -> dict:
        from services.secret_store import secret_store
        token = await secret_store().get_token(self._connection_id)
        if not token:
            raise RuntimeError(f"No OAuth token for connection {self._connection_id}")
        return {"Authorization": f"Zoho-oauthtoken {token['access_token']}"}

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4), retry=retry_if_exception(_is_rate_limited))
    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        headers = await self._headers()
        async with httpx.AsyncClient(base_url=self._api_domain, timeout=20) as c:
            r = await c.get(f"/crm/v2/{path}", headers=headers, params=params or {})
            if r.status_code == 204:
                return {"data": []}
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, json: dict) -> dict:
        headers = await self._headers()
        async with httpx.AsyncClient(base_url=self._api_domain, timeout=20) as c:
            r = await c.post(f"/crm/v2/{path}", headers=headers, json=json)
            r.raise_for_status()
            return r.json()

    def _record_to_profile(self, rec: dict) -> ClientProfile:
        dob_str = rec.get("Date_of_Birth", "") or ""
        age = 0
        if dob_str:
            try:
                age = (date.today() - datetime.strptime(dob_str[:10], "%Y-%m-%d").date()).days // 365
            except ValueError:
                pass
        return ClientProfile(
            client_id=rec["id"],
            name=f"{rec.get('First_Name', '')} {rec.get('Last_Name', '')}".strip() or rec.get("Full_Name", ""),
            age=age,
            occupation=rec.get("Title", ""),
            company=rec.get("Account_Name", {}).get("name", "") if isinstance(rec.get("Account_Name"), dict) else rec.get("Account_Name", ""),
            city=rec.get("Mailing_City", ""),
            risk_score=rec.get("Risk_Score", "low"),
        )

    async def list_all(self) -> list[ClientProfile]:
        data = await self._get("Contacts", {"fields": "id,First_Name,Last_Name,Title,Account_Name,Mailing_City,Risk_Score", "per_page": 200})
        return [self._record_to_profile(r) for r in data.get("data", [])]

    async def search_client(self, name: str) -> list[ClientProfile]:
        try:
            data = await self._get("Contacts/search", {"criteria": f"(Full_Name:contains:{name})"})
            profiles = [self._record_to_profile(r) for r in data.get("data", [])]
        except Exception:
            all_clients = await self.list_all()
            profiles = [c for c in all_clients if fuzz.token_sort_ratio(name.lower(), c.name.lower()) >= 70]
        return profiles

    async def get_client(self, client_id: str) -> Optional[ClientFullProfile]:
        try:
            data = await self._get(f"Contacts/{client_id}")
        except Exception:
            return None
        recs = data.get("data", [])
        if not recs:
            return None
        rec = recs[0]
        profile = self._record_to_profile(rec)
        risk = RiskAssessment(
            score=rec.get("Risk_Score", "low"),
            factors=[f.strip() for f in (rec.get("Risk_Factors", "") or "").split("|") if f.strip()],
        )
        cross_sell = []
        for i in (1, 2):
            prod = rec.get(f"Cross_Sell_Product_{i}")
            if prod:
                cross_sell.append(CrossSellOpportunity(
                    product=prod,
                    eligibility_reason="Based on Zoho profile",
                    pitch_angle=rec.get(f"Cross_Sell_Pitch_{i}", ""),
                    estimated_value=float(rec.get(f"Cross_Sell_Value_{i}", 0) or 0),
                ))
        products = await self.get_portfolio(client_id)
        interactions, complaints, days_ago = await self.get_interactions(client_id)
        return ClientFullProfile(
            profile=profile, products=products, risk=risk,
            interactions=interactions, complaints=complaints,
            cross_sell=cross_sell, last_rm_interaction_days_ago=days_ago,
        )

    async def get_portfolio(self, client_id: str) -> list[LoanProduct]:
        try:
            data = await self._get("Deals", {"criteria": f"(Contact_Name.id:equals:{client_id})", "per_page": 50,
                                              "fields": "id,Product_Type,Amount,EMI_Amount,Months_Paid,Tenure_Months,Next_Due_Date,Payment_History"})
            return [
                LoanProduct(
                    product_type=r.get("Product_Type", "personal_loan"),
                    principal=float(r.get("Amount", 0) or 0),
                    emi=float(r.get("EMI_Amount", 0) or 0),
                    tenure_months=int(r.get("Tenure_Months", 0) or 0),
                    months_paid=int(r.get("Months_Paid", 0) or 0),
                    next_due_date=r.get("Next_Due_Date", ""),
                    payment_history=[h.strip() for h in (r.get("Payment_History", "") or "").split(",") if h.strip()],
                )
                for r in data.get("data", [])
            ]
        except Exception:
            return []

    async def get_risk(self, client_id: str) -> Optional[RiskAssessment]:
        try:
            data = await self._get(f"Contacts/{client_id}", {"fields": "Risk_Score,Risk_Factors"})
            rec = data.get("data", [{}])[0]
            return RiskAssessment(
                score=rec.get("Risk_Score", "low"),
                factors=[f.strip() for f in (rec.get("Risk_Factors", "") or "").split("|") if f.strip()],
            )
        except Exception:
            return None

    async def get_cross_sell(self, client_id: str) -> list[CrossSellOpportunity]:
        client = await self.get_client(client_id)
        return client.cross_sell if client else []

    async def get_interactions(self, client_id: str) -> tuple[list[Interaction], list[Complaint], int]:
        interactions, complaints, days_ago = [], [], 0
        try:
            tasks = await self._get("Tasks", {"criteria": f"(Who_Id.id:equals:{client_id})", "per_page": 20,
                                               "fields": "id,Subject,Description,Activity_Type,Due_Date,Owner"})
            for t in tasks.get("data", []):
                channel = {"Call": "phone", "Email": "email"}.get(t.get("Activity_Type", ""), "phone")
                dt = t.get("Due_Date", "")[:10]
                interactions.append(Interaction(date=dt, channel=channel, summary=t.get("Description", "") or t.get("Subject", ""),
                                                rm_name=(t.get("Owner") or {}).get("name", "Unknown RM") if isinstance(t.get("Owner"), dict) else "Unknown RM"))
            if interactions:
                try:
                    days_ago = (date.today() - datetime.strptime(interactions[0].date, "%Y-%m-%d").date()).days
                except ValueError:
                    pass
        except Exception as e:
            logger.warning("Zoho tasks fetch failed: %s", e)
        try:
            cases = await self._get("Cases", {"criteria": f"(Contact_Name.id:equals:{client_id})", "per_page": 20,
                                               "fields": "id,Subject,Description,Status,Case_Origin,Created_Time"})
            for c in cases.get("data", []):
                st = c.get("Status", "Open")
                complaints.append(Complaint(id=c["id"], date=c.get("Created_Time", "")[:10],
                                            category=c.get("Case_Origin", "General"), summary=c.get("Description", "") or c.get("Subject", ""),
                                            status="open" if st in ("Open", "New") else "escalated" if "Escal" in st else "resolved"))
        except Exception as e:
            logger.warning("Zoho cases fetch failed: %s", e)
        return interactions, complaints, days_ago

    async def log_briefing(self, briefing: BriefingLog) -> None:
        try:
            await self._post("Notes", {"data": [{"Note_Title": f"SYNC Briefing — {briefing.rm_name}",
                                                  "Note_Content": f"Duration: {briefing.duration_seconds:.0f}s | Flags: {', '.join(briefing.key_flags)} | Pitch: {briefing.suggested_pitch[:200]}",
                                                  "Parent_Id": {"id": briefing.client_id}, "$se_module": "Contacts"}]})
            await self._post(f"Contacts/{briefing.client_id}", {"data": [{"Last_RM_Interaction_Date": briefing.timestamp[:10]}]})
        except Exception as e:
            logger.error("Zoho log_briefing failed: %s", e)

    async def create_note(self, client_id: str, body: str) -> str:
        r = await self._post("Notes", {"data": [{"Note_Title": "SYNC Note", "Note_Content": body,
                                                  "Parent_Id": {"id": client_id}, "$se_module": "Contacts"}]})
        return str(r.get("data", [{}])[0].get("details", {}).get("id", ""))

    async def create_task(self, client_id: str, subject: str, due_date: str, assignee_id: str = "") -> str:
        r = await self._post("Tasks", {"data": [{"Subject": subject, "Due_Date": due_date,
                                                  "Who_Id": {"id": client_id, "type": "Contacts"}}]})
        return str(r.get("data", [{}])[0].get("details", {}).get("id", ""))

    async def update_contact_field(self, client_id: str, field: str, value: str) -> None:
        await self._post(f"Contacts/{client_id}", {"data": [{field: value}]})

    async def update_complaint_status(self, complaint_id: str, status: str) -> None:
        await self._post(f"Cases/{complaint_id}", {"data": [{"Status": status}]})

    async def schedule_follow_up(self, client_id: str, when: str, kind: str, notes: str) -> str:
        return await self.create_task(client_id, f"Follow-up: {kind} — {notes}", when)
