"""
HubSpot CRM adapter.

Required HubSpot custom properties to create:
  Contact:
    - risk_score (enumeration: very_low, low, medium, watch, high)
    - risk_factors (multi_line_text)
    - last_rm_interaction_date (date)
    - cross_sell_product_1, cross_sell_pitch_1, cross_sell_value_1
    - cross_sell_product_2, cross_sell_pitch_2, cross_sell_value_2
  Deal:
    - product_type (enumeration: home_loan, personal_loan, business_loan, car_loan, credit_card, fd)
    - emi_amount (number)
    - months_paid (number)
    - tenure_months (number)
    - next_due_date (date)
    - payment_history (multi_line_text, comma-separated)

Install: pip install hubspot-api-client
"""
from adapters.base import CRMAdapter
from models import (
    ClientProfile, ClientFullProfile, LoanProduct,
    RiskAssessment, Interaction, Complaint,
    CrossSellOpportunity, BriefingLog
)
from config import settings


class HubSpotCRMAdapter(CRMAdapter):
    """HubSpot CRM adapter using HubSpot Python SDK."""

    def __init__(self):
        try:
            from hubspot import HubSpot
            self.client = HubSpot(access_token=settings.hubspot_api_key)
        except ImportError:
            raise RuntimeError("hubspot-api-client not installed. Run: pip install hubspot-api-client")

    async def search_client(self, name: str) -> list[ClientProfile]:
        from hubspot.crm.contacts import PublicObjectSearchRequest, Filter, FilterGroup
        filter_group = FilterGroup(filters=[
            Filter(property_name="firstname", operator="CONTAINS_TOKEN", value=name.split()[0])
        ])
        request = PublicObjectSearchRequest(
            filter_groups=[filter_group],
            properties=["firstname", "lastname", "jobtitle", "company", "city", "risk_score"],
            limit=10
        )
        response = self.client.crm.contacts.search_api.do_search(public_object_search_request=request)
        return [self._map_contact_to_profile(r) for r in response.results]

    async def get_client(self, client_id: str) -> ClientFullProfile | None:
        props = [
            "firstname", "lastname", "date_of_birth", "jobtitle", "company", "city",
            "risk_score", "risk_factors", "last_rm_interaction_date"
        ]
        contact = self.client.crm.contacts.basic_api.get_by_id(
            contact_id=client_id, properties=props,
            associations=["deals", "tickets", "notes"]
        )
        if not contact:
            return None
        profile = self._map_contact_to_profile(contact)
        deals = self._get_deals(contact)
        risk = self._get_risk(contact)
        interactions, complaints, days_ago = await self.get_interactions(client_id)
        cross_sell = await self.get_cross_sell(client_id)
        return ClientFullProfile(
            profile=profile, products=deals, risk=risk,
            interactions=interactions, complaints=complaints,
            cross_sell=cross_sell, last_rm_interaction_days_ago=days_ago
        )

    async def get_portfolio(self, client_id: str) -> list[LoanProduct]:
        contact = self.client.crm.contacts.basic_api.get_by_id(
            contact_id=client_id, associations=["deals"]
        )
        return self._get_deals(contact)

    async def get_risk(self, client_id: str) -> RiskAssessment | None:
        contact = self.client.crm.contacts.basic_api.get_by_id(
            contact_id=client_id,
            properties=["risk_score", "risk_factors"]
        )
        return self._get_risk(contact)

    async def get_cross_sell(self, client_id: str) -> list[CrossSellOpportunity]:
        contact = self.client.crm.contacts.basic_api.get_by_id(
            contact_id=client_id,
            properties=[
                "cross_sell_product_1", "cross_sell_pitch_1", "cross_sell_value_1",
                "cross_sell_product_2", "cross_sell_pitch_2", "cross_sell_value_2",
            ]
        )
        p = contact.properties
        results = []
        if p.get("cross_sell_product_1"):
            results.append(CrossSellOpportunity(
                product=p["cross_sell_product_1"],
                eligibility_reason="Based on CRM profile",
                pitch_angle=p.get("cross_sell_pitch_1", ""),
                estimated_value=float(p.get("cross_sell_value_1", 0)),
            ))
        if p.get("cross_sell_product_2"):
            results.append(CrossSellOpportunity(
                product=p["cross_sell_product_2"],
                eligibility_reason="Based on CRM profile",
                pitch_angle=p.get("cross_sell_pitch_2", ""),
                estimated_value=float(p.get("cross_sell_value_2", 0)),
            ))
        return results

    async def get_interactions(self, client_id: str) -> tuple[list[Interaction], list[Complaint], int]:
        from datetime import date, datetime
        notes = self.client.crm.contacts.associations_api.get_all(
            contact_id=client_id, to_object_type="notes"
        )
        tickets = self.client.crm.contacts.associations_api.get_all(
            contact_id=client_id, to_object_type="tickets"
        )
        interactions = []
        for note in (notes.results or []):
            n = self.client.crm.notes.basic_api.get_by_id(
                note_id=note.id, properties=["hs_note_body", "hs_timestamp", "hubspot_owner_id"]
            )
            interactions.append(Interaction(
                date=n.properties.get("hs_timestamp", "")[:10],
                channel="crm_note",
                summary=n.properties.get("hs_note_body", ""),
                rm_name=n.properties.get("hubspot_owner_id", "Unknown RM"),
            ))
        complaints = []
        for ticket in (tickets.results or []):
            t = self.client.crm.tickets.basic_api.get_by_id(
                ticket_id=ticket.id,
                properties=["subject", "content", "hs_ticket_category", "hs_pipeline_stage", "createdate"]
            )
            complaints.append(Complaint(
                id=t.id,
                date=t.properties.get("createdate", "")[:10],
                category=t.properties.get("hs_ticket_category", "General"),
                summary=t.properties.get("content", ""),
                status="open" if t.properties.get("hs_pipeline_stage") == "1" else "resolved",
            ))
        days_ago = 0
        if interactions:
            try:
                last_date = datetime.fromisoformat(interactions[0].date)
                days_ago = (date.today() - last_date.date()).days
            except Exception:
                pass
        return interactions, complaints, days_ago

    async def list_all(self) -> list[ClientProfile]:
        response = self.client.crm.contacts.basic_api.get_page(
            limit=100,
            properties=["firstname", "lastname", "jobtitle", "company", "city", "risk_score"]
        )
        return [self._map_contact_to_profile(r) for r in response.results]

    async def log_briefing(self, briefing: BriefingLog) -> None:
        """Create a HubSpot note on the contact to log the briefing."""
        self.client.crm.notes.basic_api.create(
            simple_public_object_input_for_create={
                "properties": {
                    "hs_note_body": (
                        f"[SYNC Briefing] RM: {briefing.rm_name} | "
                        f"Duration: {briefing.duration_seconds}s | "
                        f"Flags: {', '.join(briefing.key_flags)} | "
                        f"Pitch: {briefing.suggested_pitch}"
                    ),
                    "hs_timestamp": briefing.timestamp,
                },
                "associations": [{
                    "to": {"id": briefing.client_id},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]
                }]
            }
        )

    def _map_contact_to_profile(self, contact) -> ClientProfile:
        p = contact.properties
        name = f"{p.get('firstname', '')} {p.get('lastname', '')}".strip()
        return ClientProfile(
            client_id=contact.id,
            name=name,
            age=0,  # Calculate from date_of_birth if available
            occupation=p.get("jobtitle", ""),
            company=p.get("company", ""),
            city=p.get("city", ""),
            risk_score=p.get("risk_score", "low"),
        )

    def _get_deals(self, contact) -> list[LoanProduct]:
        products = []
        if not contact.associations:
            return products
        deal_ids = [a.id for a in (contact.associations.get("deals", {}).results or [])]
        for deal_id in deal_ids:
            deal = self.client.crm.deals.basic_api.get_by_id(
                deal_id=deal_id,
                properties=["product_type", "amount", "emi_amount", "months_paid",
                            "tenure_months", "next_due_date", "payment_history"]
            )
            p = deal.properties
            products.append(LoanProduct(
                product_type=p.get("product_type", "personal_loan"),
                principal=float(p.get("amount", 0)),
                emi=float(p.get("emi_amount", 0)),
                tenure_months=int(p.get("tenure_months", 0)),
                months_paid=int(p.get("months_paid", 0)),
                next_due_date=p.get("next_due_date", ""),
                payment_history=(p.get("payment_history", "") or "").split(","),
            ))
        return products

    def _get_risk(self, contact) -> RiskAssessment:
        p = contact.properties
        factors_raw = p.get("risk_factors", "") or ""
        factors = [f.strip() for f in factors_raw.split("\n") if f.strip()]
        return RiskAssessment(
            score=p.get("risk_score", "low"),
            factors=factors,
        )
