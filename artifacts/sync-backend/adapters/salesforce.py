"""
Salesforce CRM adapter.

Required Salesforce custom fields to create:
  Contact:
    - Risk_Score__c (Picklist: very_low, low, medium, watch, high)
    - Risk_Factors__c (Long Text Area)
    - Last_RM_Interaction_Date__c (Date)
  Opportunity (mapped to LoanProduct):
    - Product_Type__c (Picklist: home_loan, personal_loan, business_loan, car_loan, credit_card, fd)
    - EMI_Amount__c (Currency)
    - Months_Paid__c (Number)
    - Tenure_Months__c (Number)
    - Next_Due_Date__c (Date)
    - Payment_History__c (Long Text Area, comma-separated)
  Cross_Sell__c (Custom Object):
    - Contact__c (Lookup to Contact)
    - Product__c (Text)
    - Pitch_Angle__c (Long Text Area)
    - Estimated_Value__c (Currency)

Install: pip install simple-salesforce
"""
from adapters.base import CRMAdapter
from models import (
    ClientProfile, ClientFullProfile, LoanProduct,
    RiskAssessment, Interaction, Complaint,
    CrossSellOpportunity, BriefingLog
)
from config import settings


class SalesforceCRMAdapter(CRMAdapter):
    """Salesforce REST API adapter using simple-salesforce."""

    def __init__(self):
        try:
            from simple_salesforce import Salesforce
            self.sf = Salesforce(
                instance_url=settings.salesforce_instance_url,
                session_id=settings.salesforce_access_token,
            )
        except ImportError:
            raise RuntimeError("simple-salesforce not installed. Run: pip install simple-salesforce")

    async def search_client(self, name: str) -> list[ClientProfile]:
        sosl = f"FIND {{{name}}} IN NAME FIELDS RETURNING Contact(Id, FirstName, LastName, Title, Account.Name, MailingCity, Risk_Score__c)"
        result = self.sf.search(sosl)
        contacts = result.get("searchRecords", [])
        return [self._map_contact(c) for c in contacts]

    async def get_client(self, client_id: str) -> ClientFullProfile | None:
        soql = f"""
            SELECT Id, FirstName, LastName, Title, Account.Name, MailingCity,
                   Risk_Score__c, Risk_Factors__c, Last_RM_Interaction_Date__c
            FROM Contact WHERE Id = '{client_id}'
        """
        result = self.sf.query(soql)
        if not result["records"]:
            return None
        contact = result["records"][0]
        profile = self._map_contact(contact)
        products = await self.get_portfolio(client_id)
        risk = await self.get_risk(client_id)
        interactions, complaints, days_ago = await self.get_interactions(client_id)
        cross_sell = await self.get_cross_sell(client_id)
        return ClientFullProfile(
            profile=profile, products=products, risk=risk or RiskAssessment(score="low", factors=[]),
            interactions=interactions, complaints=complaints,
            cross_sell=cross_sell, last_rm_interaction_days_ago=days_ago
        )

    async def get_portfolio(self, client_id: str) -> list[LoanProduct]:
        soql = f"""
            SELECT Product_Type__c, Amount, EMI_Amount__c, Months_Paid__c,
                   Tenure_Months__c, Next_Due_Date__c, Payment_History__c
            FROM Opportunity WHERE ContactId = '{client_id}' AND StageName != 'Closed Lost'
        """
        result = self.sf.query(soql)
        return [self._map_opportunity(r) for r in result["records"]]

    async def get_risk(self, client_id: str) -> RiskAssessment | None:
        soql = f"SELECT Risk_Score__c, Risk_Factors__c FROM Contact WHERE Id = '{client_id}'"
        result = self.sf.query(soql)
        if not result["records"]:
            return None
        r = result["records"][0]
        factors_raw = r.get("Risk_Factors__c", "") or ""
        return RiskAssessment(
            score=r.get("Risk_Score__c", "low"),
            factors=[f.strip() for f in factors_raw.split("\n") if f.strip()],
        )

    async def get_cross_sell(self, client_id: str) -> list[CrossSellOpportunity]:
        soql = f"""
            SELECT Product__c, Eligibility_Reason__c, Pitch_Angle__c, Estimated_Value__c
            FROM Cross_Sell__c WHERE Contact__c = '{client_id}'
        """
        result = self.sf.query(soql)
        return [CrossSellOpportunity(
            product=r["Product__c"],
            eligibility_reason=r.get("Eligibility_Reason__c", ""),
            pitch_angle=r.get("Pitch_Angle__c", ""),
            estimated_value=float(r.get("Estimated_Value__c", 0)),
        ) for r in result["records"]]

    async def get_interactions(self, client_id: str) -> tuple[list[Interaction], list[Complaint], int]:
        from datetime import date, datetime
        tasks_soql = f"""
            SELECT ActivityDate, Type, Description, Owner.Name
            FROM Task WHERE WhoId = '{client_id}' ORDER BY ActivityDate DESC LIMIT 10
        """
        cases_soql = f"""
            SELECT CaseNumber, CreatedDate, Type, Description, Status
            FROM Case WHERE ContactId = '{client_id}' ORDER BY CreatedDate DESC
        """
        tasks = self.sf.query(tasks_soql)["records"]
        cases = self.sf.query(cases_soql)["records"]

        interactions = [Interaction(
            date=r.get("ActivityDate", ""),
            channel=r.get("Type", "phone").lower(),
            summary=r.get("Description", ""),
            rm_name=r.get("Owner", {}).get("Name", "Unknown RM"),
        ) for r in tasks]

        complaints = [Complaint(
            id=r["CaseNumber"],
            date=r.get("CreatedDate", "")[:10],
            category=r.get("Type", "General"),
            summary=r.get("Description", ""),
            status="open" if r.get("Status") in ("New", "Working") else "resolved",
        ) for r in cases]

        days_ago = 0
        if interactions:
            try:
                last_date = datetime.fromisoformat(interactions[0].date)
                days_ago = (date.today() - last_date.date()).days
            except Exception:
                pass
        return interactions, complaints, days_ago

    async def list_all(self) -> list[ClientProfile]:
        soql = "SELECT Id, FirstName, LastName, Title, Account.Name, MailingCity, Risk_Score__c FROM Contact LIMIT 200"
        result = self.sf.query(soql)
        return [self._map_contact(r) for r in result["records"]]

    async def log_briefing(self, briefing: BriefingLog) -> None:
        """Create a Salesforce Task to log the completed briefing."""
        self.sf.Task.create({
            "WhoId": briefing.client_id,
            "Subject": f"[SYNC] Briefing delivered to {briefing.rm_name}",
            "Description": (
                f"Duration: {briefing.duration_seconds}s\n"
                f"Flags: {', '.join(briefing.key_flags)}\n"
                f"Pitch: {briefing.suggested_pitch}"
            ),
            "Status": "Completed",
            "ActivityDate": briefing.timestamp[:10],
        })

    def _map_contact(self, r: dict) -> ClientProfile:
        name = f"{r.get('FirstName', '')} {r.get('LastName', '')}".strip()
        account = r.get("Account") or {}
        return ClientProfile(
            client_id=r["Id"],
            name=name,
            age=0,
            occupation=r.get("Title", ""),
            company=account.get("Name", ""),
            city=r.get("MailingCity", ""),
            risk_score=r.get("Risk_Score__c", "low"),
        )

    def _map_opportunity(self, r: dict) -> LoanProduct:
        history_raw = r.get("Payment_History__c", "") or ""
        return LoanProduct(
            product_type=r.get("Product_Type__c", "personal_loan"),
            principal=float(r.get("Amount", 0)),
            emi=float(r.get("EMI_Amount__c", 0)),
            tenure_months=int(r.get("Tenure_Months__c", 0)),
            months_paid=int(r.get("Months_Paid__c", 0)),
            next_due_date=r.get("Next_Due_Date__c", ""),
            payment_history=[h.strip() for h in history_raw.split(",") if h.strip()],
        )
