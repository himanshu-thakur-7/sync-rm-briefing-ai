"""Salesforce CRM adapter — hardened for production.

Required custom fields (auto-defined in sf-package.zip from provisioning.py):
  Contact:
    - Risk_Score__c (Picklist: very_low, low, medium, watch, high)
    - Risk_Factors__c (Long Text Area)
    - Last_RM_Interaction_Date__c (Date)
  Opportunity (mapped to LoanProduct):
    - Product_Type__c (Picklist)
    - EMI_Amount__c (Currency), Months_Paid__c (Number), Tenure_Months__c (Number)
    - Next_Due_Date__c (Date), Payment_History__c (Long Text Area)
  Cross_Sell__c (Custom Object):
    - Contact__c (Lookup), Product__c, Pitch_Angle__c, Estimated_Value__c

Changes from v1:
  - SOQL injection patched: _escape_id() validates IDs before interpolation.
  - Constructor takes connection_id + loads token via SecretStore.
  - log_briefing writes Last_RM_Interaction_Date__c back to the Contact.
  - LIMIT 200 on list_all.
  - DOB → age via Contact.Birthdate.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Optional

from rapidfuzz import fuzz

from adapters.base import CRMAdapter
from models import (
    BriefingLog, ClientFullProfile, ClientProfile, Complaint,
    CrossSellOpportunity, Interaction, LoanProduct, RiskAssessment,
)

logger = logging.getLogger(__name__)

# Salesforce ID is exactly 15 or 18 alphanumeric chars.
_SFID_RE = re.compile(r"^[A-Za-z0-9]{15,18}$")


def _escape_id(client_id: str) -> str:
    """Whitelist Salesforce record IDs. Raises ValueError on any non-ID input."""
    if not _SFID_RE.match(client_id):
        raise ValueError(f"Invalid Salesforce ID: {client_id!r}")
    return client_id


class SalesforceCRMAdapter(CRMAdapter):
    """Salesforce REST API adapter using simple-salesforce."""

    def __init__(self, *, connection_id: str = "conn_salesforce", metadata: Optional[dict] = None) -> None:
        self._connection_id = connection_id
        self._meta = metadata or {}

    async def _sf(self):
        """Return an authenticated simple-salesforce Salesforce instance."""
        try:
            from simple_salesforce import Salesforce as SF
        except ImportError:
            raise RuntimeError("simple-salesforce not installed. Run: pip install simple-salesforce")

        from services.secret_store import secret_store
        token_data = await secret_store().get_token(self._connection_id)
        if token_data:
            access_token = token_data.get("access_token", "")
            instance_url = token_data.get("instance_url", "") or self._meta.get("instance_url", "")
        else:
            from config import settings
            access_token = settings.salesforce_access_token
            instance_url = settings.salesforce_instance_url

        return SF(instance_url=instance_url, session_id=access_token)

    # ------------------------------------------------------------------ #
    # Core interface
    # ------------------------------------------------------------------ #

    async def list_all(self) -> list[ClientProfile]:
        sf = await self._sf()
        result = sf.query("SELECT Id, FirstName, LastName, Title, Account.Name, MailingCity, Risk_Score__c FROM Contact LIMIT 200")
        return [self._contact_to_profile(r) for r in result.get("records", [])]

    async def search_client(self, name: str) -> list[ClientProfile]:
        sf = await self._sf()
        escaped = name.replace("'", "\\'")
        try:
            sosl = sf.search(f"FIND {{'{escaped}'}} IN NAME FIELDS RETURNING Contact(Id, FirstName, LastName, Title, Account.Name, MailingCity, Risk_Score__c)")
            records = sosl.get("searchRecords", [])
        except Exception:
            all_c = await self.list_all()
            return [c for c in all_c if fuzz.token_sort_ratio(name.lower(), c.name.lower()) >= 70]
        return [self._contact_to_profile(r) for r in records]

    async def get_client(self, client_id: str) -> Optional[ClientFullProfile]:
        sid = _escape_id(client_id)
        sf = await self._sf()
        try:
            result = sf.query(
                f"SELECT Id, FirstName, LastName, Title, Birthdate, Account.Name, MailingCity, "
                f"Risk_Score__c, Risk_Factors__c, Last_RM_Interaction_Date__c "
                f"FROM Contact WHERE Id = '{sid}' LIMIT 1"
            )
        except Exception:
            return None
        records = result.get("records", [])
        if not records:
            return None
        rec = records[0]
        profile = self._contact_to_profile(rec)
        risk = self._contact_to_risk(rec)
        products = await self.get_portfolio(client_id)
        cross_sell = await self.get_cross_sell(client_id)
        interactions, complaints, days_ago = await self.get_interactions(client_id)
        return ClientFullProfile(profile=profile, products=products, risk=risk,
                                  interactions=interactions, complaints=complaints,
                                  cross_sell=cross_sell, last_rm_interaction_days_ago=days_ago)

    async def get_portfolio(self, client_id: str) -> list[LoanProduct]:
        sid = _escape_id(client_id)
        sf = await self._sf()
        try:
            result = sf.query(
                f"SELECT Product_Type__c, Amount, EMI_Amount__c, Months_Paid__c, "
                f"Tenure_Months__c, Next_Due_Date__c, Payment_History__c "
                f"FROM Opportunity WHERE ContactId = '{sid}' AND StageName != 'Closed Lost' LIMIT 20"
            )
        except Exception:
            return []
        return [self._opp_to_loan(r) for r in result.get("records", [])]

    async def get_risk(self, client_id: str) -> Optional[RiskAssessment]:
        sid = _escape_id(client_id)
        sf = await self._sf()
        try:
            result = sf.query(f"SELECT Risk_Score__c, Risk_Factors__c FROM Contact WHERE Id = '{sid}' LIMIT 1")
        except Exception:
            return None
        recs = result.get("records", [])
        if not recs:
            return None
        return self._contact_to_risk(recs[0])

    async def get_cross_sell(self, client_id: str) -> list[CrossSellOpportunity]:
        sid = _escape_id(client_id)
        sf = await self._sf()
        try:
            result = sf.query(f"SELECT Product__c, Pitch_Angle__c, Estimated_Value__c FROM Cross_Sell__c WHERE Contact__c = '{sid}' LIMIT 5")
        except Exception:
            return []
        out = []
        for r in result.get("records", []):
            out.append(CrossSellOpportunity(
                product=r.get("Product__c", ""),
                eligibility_reason="Based on Salesforce profile",
                pitch_angle=r.get("Pitch_Angle__c", ""),
                estimated_value=float(r.get("Estimated_Value__c", 0) or 0),
            ))
        return out

    async def get_interactions(self, client_id: str) -> tuple[list[Interaction], list[Complaint], int]:
        sid = _escape_id(client_id)
        sf = await self._sf()
        interactions, complaints, days_ago = [], [], 0
        try:
            tasks = sf.query(f"SELECT ActivityDate, Type, Description, Owner.Name FROM Task WHERE WhoId = '{sid}' ORDER BY ActivityDate DESC LIMIT 20")
            for t in tasks.get("records", []):
                channel = {"Call": "phone", "Email": "email"}.get(t.get("Type", ""), "phone")
                interactions.append(Interaction(
                    date=(t.get("ActivityDate", "") or "")[:10],
                    channel=channel,
                    summary=t.get("Description", "") or "",
                    rm_name=(t.get("Owner") or {}).get("Name", "Unknown RM") if isinstance(t.get("Owner"), dict) else "Unknown RM",
                ))
            if interactions:
                try:
                    days_ago = (date.today() - datetime.strptime(interactions[0].date, "%Y-%m-%d").date()).days
                except ValueError:
                    pass
        except Exception as e:
            logger.warning("SF tasks failed: %s", e)

        try:
            cases = sf.query(f"SELECT CaseNumber, CreatedDate, Type, Description, Status FROM Case WHERE ContactId = '{sid}' LIMIT 20")
            for c in cases.get("records", []):
                st = c.get("Status", "New")
                complaints.append(Complaint(
                    id=c.get("CaseNumber", c.get("Id", "")),
                    date=(c.get("CreatedDate", "") or "")[:10],
                    category=c.get("Type", "General"),
                    summary=c.get("Description", "") or "",
                    status="open" if st in ("New", "Working") else "escalated" if st == "Escalated" else "resolved",
                ))
        except Exception as e:
            logger.warning("SF cases failed: %s", e)

        return interactions, complaints, days_ago

    async def log_briefing(self, briefing: BriefingLog) -> None:
        sid = _escape_id(briefing.client_id)
        sf = await self._sf()
        today = date.today().isoformat()
        try:
            sf.Task.create({
                "WhoId": sid,
                "Subject": f"[SYNC Briefing] {briefing.rm_name}",
                "Description": f"Duration: {briefing.duration_seconds:.0f}s | Flags: {', '.join(briefing.key_flags)} | Pitch: {briefing.suggested_pitch[:200]}",
                "Status": "Completed",
                "ActivityDate": today,
            })
        except Exception as e:
            logger.warning("SF Task creation failed: %s", e)
        try:
            sf.Contact.update(sid, {"Last_RM_Interaction_Date__c": today})
        except Exception as e:
            logger.warning("SF contact update failed: %s", e)

    # ------------------------------------------------------------------ #
    # Voice-command action methods (Phase 6)
    # ------------------------------------------------------------------ #

    async def create_note(self, client_id: str, body: str) -> str:
        sid = _escape_id(client_id)
        sf = await self._sf()
        r = sf.Task.create({"WhoId": sid, "Subject": "SYNC Note", "Description": body, "Status": "Completed", "ActivityDate": date.today().isoformat()})
        return str(r.get("id", ""))

    async def create_task(self, client_id: str, subject: str, due_date: str, assignee_id: str = "") -> str:
        sid = _escape_id(client_id)
        sf = await self._sf()
        payload = {"WhoId": sid, "Subject": subject, "Status": "Not Started", "ActivityDate": due_date}
        if assignee_id:
            payload["OwnerId"] = assignee_id
        r = sf.Task.create(payload)
        return str(r.get("id", ""))

    async def update_contact_field(self, client_id: str, field: str, value: str) -> None:
        sid = _escape_id(client_id)
        sf = await self._sf()
        sf.Contact.update(sid, {field: value})

    async def update_complaint_status(self, complaint_id: str, status: str) -> None:
        sf = await self._sf()
        sf_status = {"open": "New", "escalated": "Escalated", "resolved": "Closed"}.get(status, "New")
        sf.Case.update(complaint_id, {"Status": sf_status})

    async def schedule_follow_up(self, client_id: str, when: str, kind: str, notes: str) -> str:
        return await self.create_task(client_id, f"Follow-up: {kind} — {notes}", when)

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #

    def _contact_to_profile(self, rec: dict) -> ClientProfile:
        dob_str = rec.get("Birthdate", "") or ""
        age = 0
        if dob_str:
            try:
                age = (date.today() - datetime.strptime(dob_str[:10], "%Y-%m-%d").date()).days // 365
            except ValueError:
                pass
        account = rec.get("Account", {}) or {}
        company = account.get("Name", "") if isinstance(account, dict) else ""
        return ClientProfile(
            client_id=rec["Id"],
            name=f"{rec.get('FirstName', '')} {rec.get('LastName', '')}".strip(),
            age=age,
            occupation=rec.get("Title", ""),
            company=company,
            city=rec.get("MailingCity", ""),
            risk_score=rec.get("Risk_Score__c", "low"),
        )

    def _contact_to_risk(self, rec: dict) -> RiskAssessment:
        factors_raw = rec.get("Risk_Factors__c", "") or ""
        factors = [f.strip() for f in factors_raw.split("\n") if f.strip()]
        return RiskAssessment(score=rec.get("Risk_Score__c", "low"), factors=factors)

    def _opp_to_loan(self, rec: dict) -> LoanProduct:
        history_raw = rec.get("Payment_History__c", "") or ""
        history = [h.strip() for h in history_raw.split(",") if h.strip()]
        return LoanProduct(
            product_type=rec.get("Product_Type__c", "personal_loan"),
            principal=float(rec.get("Amount", 0) or 0),
            emi=float(rec.get("EMI_Amount__c", 0) or 0),
            tenure_months=int(float(rec.get("Tenure_Months__c", 0) or 0)),
            months_paid=int(float(rec.get("Months_Paid__c", 0) or 0)),
            next_due_date=(rec.get("Next_Due_Date__c", "") or "")[:10],
            payment_history=history,
        )
