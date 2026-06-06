"""Microsoft Dynamics 365 CRM adapter.

Uses OData v9.1 REST API with Azure AD OAuth2 tokens (stored via SecretStore).
Instance URL: {settings.dynamics_instance_url}/api/data/v9.1/

Entities used: contacts, opportunities, incidents (cases), annotations (notes), tasks.

Custom fields required (prefixed sync_):
  contact: sync_riskscore, sync_riskfactors, sync_lastrminteractiondate,
           sync_crosssellproduct1, sync_crosssellpitch1, sync_crosssellvalue1,
           sync_crosssellproduct2, sync_crosssellpitch2, sync_crosssellvalue2
  opportunity: sync_producttype, sync_emiamount, sync_monthspaid,
               sync_tenuremonths, sync_nextduedate, sync_paymenthistory
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
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 503)


class DynamicsCRMAdapter(CRMAdapter):
    """Microsoft Dynamics 365 OData v9 adapter."""

    def __init__(self, *, connection_id: str = "dynamics_default", metadata: Optional[dict] = None) -> None:
        self._connection_id = connection_id
        from config import settings
        self._instance_url = (metadata or {}).get("instance_url") or settings.dynamics_instance_url
        self._base = f"{self._instance_url.rstrip('/')}/api/data/v9.1"

    async def _headers(self) -> dict:
        from services.secret_store import secret_store
        token = await secret_store().get_token(self._connection_id)
        if not token:
            raise RuntimeError(f"No OAuth token for connection {self._connection_id}")
        return {
            "Authorization": f"Bearer {token['access_token']}",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

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
            return r.json() if r.text else {}

    async def _patch(self, path: str, json: dict) -> None:
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.patch(f"{self._base}/{path}", headers=headers, json=json)
            r.raise_for_status()

    def _contact_to_profile(self, c: dict) -> ClientProfile:
        dob_str = c.get("birthdate", "") or ""
        age = 0
        if dob_str:
            try:
                age = (date.today() - datetime.strptime(dob_str[:10], "%Y-%m-%d").date()).days // 365
            except ValueError:
                pass
        return ClientProfile(
            client_id=c["contactid"],
            name=c.get("fullname", ""),
            age=age,
            occupation=c.get("jobtitle", ""),
            company=c.get("_parentcustomerid_value@OData.Community.Display.V1.FormattedValue", "") or c.get("companyname", ""),
            city=c.get("address1_city", ""),
            risk_score=c.get("sync_riskscore", "low"),
        )

    async def list_all(self) -> list[ClientProfile]:
        data = await self._get("contacts", {
            "$select": "contactid,fullname,jobtitle,companyname,address1_city,sync_riskscore",
            "$top": 200,
        })
        return [self._contact_to_profile(c) for c in data.get("value", [])]

    async def search_client(self, name: str) -> list[ClientProfile]:
        try:
            data = await self._get("contacts", {
                "$filter": f"contains(fullname,'{name}')",
                "$select": "contactid,fullname,jobtitle,companyname,address1_city,sync_riskscore",
                "$top": 10,
            })
            return [self._contact_to_profile(c) for c in data.get("value", [])]
        except Exception:
            all_c = await self.list_all()
            return [c for c in all_c if fuzz.token_sort_ratio(name.lower(), c.name.lower()) >= 70]

    async def get_client(self, client_id: str) -> Optional[ClientFullProfile]:
        try:
            data = await self._get(f"contacts({client_id})", {
                "$select": "contactid,fullname,jobtitle,companyname,address1_city,sync_riskscore,sync_riskfactors,birthdate,sync_crosssellproduct1,sync_crosssellpitch1,sync_crosssellvalue1,sync_crosssellproduct2,sync_crosssellpitch2,sync_crosssellvalue2",
            })
        except Exception:
            return None
        profile = self._contact_to_profile(data)
        risk = RiskAssessment(
            score=data.get("sync_riskscore", "low"),
            factors=[f.strip() for f in (data.get("sync_riskfactors", "") or "").split("|") if f.strip()],
        )
        cross_sell = []
        for i in (1, 2):
            prod = data.get(f"sync_crosssellproduct{i}")
            if prod:
                cross_sell.append(CrossSellOpportunity(
                    product=prod,
                    eligibility_reason="Based on Dynamics profile",
                    pitch_angle=data.get(f"sync_crosssellpitch{i}", ""),
                    estimated_value=float(data.get(f"sync_crosssellvalue{i}", 0) or 0),
                ))
        products = await self.get_portfolio(client_id)
        interactions, complaints, days_ago = await self.get_interactions(client_id)
        return ClientFullProfile(profile=profile, products=products, risk=risk,
                                  interactions=interactions, complaints=complaints,
                                  cross_sell=cross_sell, last_rm_interaction_days_ago=days_ago)

    async def get_portfolio(self, client_id: str) -> list[LoanProduct]:
        try:
            data = await self._get("opportunities", {
                "$filter": f"_parentcontactid_value eq {client_id}",
                "$select": "sync_producttype,estimatedvalue,sync_emiamount,sync_monthspaid,sync_tenuremonths,sync_nextduedate,sync_paymenthistory",
                "$top": 20,
            })
            return [
                LoanProduct(
                    product_type=o.get("sync_producttype", "personal_loan"),
                    principal=float(o.get("estimatedvalue", 0) or 0),
                    emi=float(o.get("sync_emiamount", 0) or 0),
                    tenure_months=int(o.get("sync_tenuremonths", 0) or 0),
                    months_paid=int(o.get("sync_monthspaid", 0) or 0),
                    next_due_date=(o.get("sync_nextduedate", "") or "")[:10],
                    payment_history=[h.strip() for h in (o.get("sync_paymenthistory", "") or "").split(",") if h.strip()],
                )
                for o in data.get("value", [])
            ]
        except Exception:
            return []

    async def get_risk(self, client_id: str) -> Optional[RiskAssessment]:
        try:
            data = await self._get(f"contacts({client_id})", {"$select": "sync_riskscore,sync_riskfactors"})
            return RiskAssessment(
                score=data.get("sync_riskscore", "low"),
                factors=[f.strip() for f in (data.get("sync_riskfactors", "") or "").split("|") if f.strip()],
            )
        except Exception:
            return None

    async def get_cross_sell(self, client_id: str) -> list[CrossSellOpportunity]:
        client = await self.get_client(client_id)
        return client.cross_sell if client else []

    async def get_interactions(self, client_id: str) -> tuple[list[Interaction], list[Complaint], int]:
        interactions, complaints, days_ago = [], [], 0
        try:
            tasks = await self._get("tasks", {
                "$filter": f"_regardingobjectid_value eq {client_id}",
                "$select": "subject,description,scheduledend,_ownerid_value",
                "$top": 20,
            })
            for t in tasks.get("value", []):
                dt = (t.get("scheduledend", "") or "")[:10]
                interactions.append(Interaction(date=dt, channel="phone", summary=t.get("description", "") or t.get("subject", ""), rm_name="RM"))
            if interactions:
                try:
                    days_ago = (date.today() - datetime.strptime(interactions[0].date, "%Y-%m-%d").date()).days
                except ValueError:
                    pass
        except Exception as e:
            logger.warning("Dynamics tasks failed: %s", e)
        try:
            incidents = await self._get("incidents", {
                "$filter": f"_customerid_value eq {client_id}",
                "$select": "incidentid,title,description,statecode,createdon",
                "$top": 20,
            })
            for inc in incidents.get("value", []):
                state = inc.get("statecode", 0)
                complaints.append(Complaint(id=inc["incidentid"], date=(inc.get("createdon", "") or "")[:10],
                                            category="Incident", summary=inc.get("description", "") or inc.get("title", ""),
                                            status="open" if state == 0 else "resolved"))
        except Exception as e:
            logger.warning("Dynamics incidents failed: %s", e)
        return interactions, complaints, days_ago

    async def log_briefing(self, briefing: BriefingLog) -> None:
        try:
            await self._post("annotations", {
                "subject": f"SYNC Briefing — {briefing.rm_name}",
                "notetext": f"Duration: {briefing.duration_seconds:.0f}s | Flags: {', '.join(briefing.key_flags)} | Pitch: {briefing.suggested_pitch[:200]}",
                "objectid_contact@odata.bind": f"/contacts({briefing.client_id})",
            })
            await self._patch(f"contacts({briefing.client_id})", {"sync_lastrminteractiondate": briefing.timestamp[:10]})
        except Exception as e:
            logger.error("Dynamics log_briefing failed: %s", e)

    async def create_note(self, client_id: str, body: str) -> str:
        r = await self._post("annotations", {"subject": "SYNC Note", "notetext": body,
                                              "objectid_contact@odata.bind": f"/contacts({client_id})"})
        return r.get("annotationid", "")

    async def create_task(self, client_id: str, subject: str, due_date: str, assignee_id: str = "") -> str:
        r = await self._post("tasks", {"subject": subject, "scheduledend": due_date,
                                        "regardingobjectid_contact@odata.bind": f"/contacts({client_id})"})
        return r.get("activityid", "")

    async def update_contact_field(self, client_id: str, field: str, value: str) -> None:
        await self._patch(f"contacts({client_id})", {field: value})

    async def update_complaint_status(self, complaint_id: str, status: str) -> None:
        state = 0 if status == "open" else 1
        await self._patch(f"incidents({complaint_id})", {"statecode": state})

    async def schedule_follow_up(self, client_id: str, when: str, kind: str, notes: str) -> str:
        return await self.create_task(client_id, f"Follow-up: {kind} — {notes}", when)
