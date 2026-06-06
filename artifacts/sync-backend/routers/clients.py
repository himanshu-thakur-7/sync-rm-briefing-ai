from fastapi import APIRouter, HTTPException, Query
from models import ClientProfile, ClientFullProfile, LoanProduct, RiskAssessment, CrossSellOpportunity, ClientInteractions
from services.crm_factory import crm_async as crm

router = APIRouter(prefix="/v1/clients", tags=["clients"])


@router.get("", response_model=list[ClientProfile])
async def list_clients():
    """List all clients for dashboard dropdown."""
    return await (await crm()).list_all()


@router.get("/search", response_model=list[ClientProfile])
async def search_clients(name: str = Query(..., description="Client name to search")):
    """Fuzzy search clients by name."""
    return await (await crm()).search_client(name)


@router.get("/{client_id}", response_model=ClientFullProfile)
async def get_client(client_id: str):
    """Get full client profile."""
    client = await (await crm()).get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
    return client


@router.get("/{client_id}/portfolio", response_model=list[LoanProduct])
async def get_client_portfolio(client_id: str):
    """Get client's loan products."""
    return await (await crm()).get_portfolio(client_id)


@router.get("/{client_id}/risk", response_model=RiskAssessment)
async def get_client_risk(client_id: str):
    """Get client risk assessment."""
    risk = await (await crm()).get_risk(client_id)
    if not risk:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
    return risk


@router.get("/{client_id}/cross-sell", response_model=list[CrossSellOpportunity])
async def get_client_cross_sell(client_id: str):
    """Get cross-sell opportunities for client."""
    return await (await crm()).get_cross_sell(client_id)


@router.get("/{client_id}/interactions", response_model=ClientInteractions)
async def get_client_interactions(client_id: str):
    """Get client interactions and complaints."""
    interactions, complaints, days_ago = await (await crm()).get_interactions(client_id)
    return ClientInteractions(
        interactions=interactions,
        complaints=complaints,
        last_rm_interaction_days_ago=days_ago,
    )
