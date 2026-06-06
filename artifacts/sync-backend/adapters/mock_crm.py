"""
Mock CRM adapter — uses in-memory database from database.py.
This is the default adapter and requires no external API keys.
"""
from rapidfuzz import fuzz
from adapters.base import CRMAdapter
from models import (
    ClientProfile, ClientFullProfile, LoanProduct,
    RiskAssessment, Interaction, Complaint,
    CrossSellOpportunity, BriefingLog
)
import database


class MockCRMAdapter(CRMAdapter):
    """In-memory CRM adapter for demo purposes."""

    async def search_client(self, name: str) -> list[ClientProfile]:
        """Fuzzy match clients by name using rapidfuzz partial_ratio.

        Uses partial_ratio so first-name-only queries (e.g. "Rahul") score
        highly against full names ("Rahul Mehta"). Threshold 70 on partial.
        """
        results = []
        for client_id, full_profile in database.CLIENTS.items():
            score = fuzz.partial_ratio(name.lower(), full_profile.profile.name.lower())
            if score >= 70:
                results.append((score, full_profile.profile))
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results]

    async def get_client(self, client_id: str) -> ClientFullProfile | None:
        return database.CLIENTS.get(client_id)

    async def get_portfolio(self, client_id: str) -> list[LoanProduct]:
        client = database.CLIENTS.get(client_id)
        if not client:
            return []
        return client.products

    async def get_risk(self, client_id: str) -> RiskAssessment | None:
        client = database.CLIENTS.get(client_id)
        if not client:
            return None
        return client.risk

    async def get_cross_sell(self, client_id: str) -> list[CrossSellOpportunity]:
        client = database.CLIENTS.get(client_id)
        if not client:
            return []
        return client.cross_sell

    async def get_interactions(self, client_id: str) -> tuple[list[Interaction], list[Complaint], int]:
        client = database.CLIENTS.get(client_id)
        if not client:
            return [], [], 0
        return client.interactions, client.complaints, client.last_rm_interaction_days_ago

    async def list_all(self) -> list[ClientProfile]:
        return [c.profile for c in database.CLIENTS.values()]

    async def log_briefing(self, briefing: BriefingLog) -> None:
        database.BRIEFING_LOGS.append(briefing)
