from abc import ABC, abstractmethod
from models import (
    ClientProfile, ClientFullProfile, LoanProduct,
    RiskAssessment, Interaction, Complaint,
    CrossSellOpportunity, BriefingLog
)


class CRMAdapter(ABC):
    """Abstract base class for CRM integrations."""

    @abstractmethod
    async def search_client(self, name: str) -> list[ClientProfile]:
        """Fuzzy search clients by name."""
        pass

    @abstractmethod
    async def get_client(self, client_id: str) -> ClientFullProfile | None:
        """Get full client profile with all data."""
        pass

    @abstractmethod
    async def get_portfolio(self, client_id: str) -> list[LoanProduct]:
        pass

    @abstractmethod
    async def get_risk(self, client_id: str) -> RiskAssessment | None:
        pass

    @abstractmethod
    async def get_cross_sell(self, client_id: str) -> list[CrossSellOpportunity]:
        pass

    @abstractmethod
    async def get_interactions(self, client_id: str) -> tuple[list[Interaction], list[Complaint], int]:
        """Returns (interactions, complaints, last_rm_interaction_days_ago)."""
        pass

    @abstractmethod
    async def list_all(self) -> list[ClientProfile]:
        """List all clients."""
        pass

    @abstractmethod
    async def log_briefing(self, briefing: BriefingLog) -> None:
        """Log a completed briefing back to CRM."""
        pass
