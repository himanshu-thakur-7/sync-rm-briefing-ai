"""Adapter contract tests.

Every CRM adapter must return a populated ClientFullProfile with:
  - profile.name (non-empty)
  - at least 1 product
  - a risk assessment with a valid score
  - at least 1 cross-sell opportunity

Parametrized over: MockCRMAdapter + FakeLeadSquaredCRMAdapter.
HubSpot/Salesforce/Zoho/Dynamics/Freshworks are tested via httpx MockTransport
stubs that simulate their API shapes.
"""
import pytest
import pytest_asyncio
from adapters.mock_crm import MockCRMAdapter
from adapters.fake_leadsquared import FakeLeadSquaredCRMAdapter


VALID_RISK_SCORES = {"very_low", "low", "medium", "watch", "high"}

ADAPTERS = [
    ("mock", MockCRMAdapter()),
    ("fake_leadsquared", FakeLeadSquaredCRMAdapter()),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("name,adapter", ADAPTERS, ids=[a[0] for a in ADAPTERS])
async def test_list_all_returns_five_clients(name, adapter):
    clients = await adapter.list_all()
    assert len(clients) == 5, f"{name}: expected 5 clients, got {len(clients)}"


@pytest.mark.asyncio
@pytest.mark.parametrize("name,adapter", ADAPTERS, ids=[a[0] for a in ADAPTERS])
async def test_search_client_fuzzy(name, adapter):
    results = await adapter.search_client("rahul")
    assert results, f"{name}: search for 'rahul' returned nothing"
    assert any("Rahul" in r.name for r in results), f"{name}: Rahul not in {[r.name for r in results]}"


@pytest.mark.asyncio
@pytest.mark.parametrize("name,adapter,client_id", [
    ("mock", MockCRMAdapter(), "client_001"),
    ("fake_leadsquared", FakeLeadSquaredCRMAdapter(), "lsq_001"),
], ids=["mock", "fake_leadsquared"])
async def test_get_client_full_profile(name, adapter, client_id):
    profile = await adapter.get_client(client_id)
    assert profile is not None, f"{name}: get_client returned None"
    assert profile.profile.name, f"{name}: profile.name is empty"
    assert len(profile.products) >= 1, f"{name}: no products"
    assert profile.risk.score in VALID_RISK_SCORES, f"{name}: invalid risk score {profile.risk.score}"
    assert len(profile.cross_sell) >= 1, f"{name}: no cross-sell opportunities"


@pytest.mark.asyncio
@pytest.mark.parametrize("name,adapter,client_id", [
    ("mock", MockCRMAdapter(), "client_005"),
    ("fake_leadsquared", FakeLeadSquaredCRMAdapter(), "lsq_005"),
], ids=["mock_vikram", "lsq_vikram"])
async def test_high_risk_client(name, adapter, client_id):
    """Vikram Desai is the high-risk client in both adapters."""
    profile = await adapter.get_client(client_id)
    assert profile is not None
    assert profile.risk.score == "high", f"{name}: expected high risk, got {profile.risk.score}"
    assert len(profile.risk.factors) >= 2, f"{name}: high-risk client should have multiple factors"


@pytest.mark.asyncio
@pytest.mark.parametrize("name,adapter,client_id", [
    ("mock", MockCRMAdapter(), "client_001"),
    ("fake_leadsquared", FakeLeadSquaredCRMAdapter(), "lsq_001"),
], ids=["mock_rahul", "lsq_rahul"])
async def test_complaint_present_for_rahul(name, adapter, client_id):
    """Rahul Mehta has one open complaint in both adapters."""
    _, complaints, _ = await adapter.get_interactions(client_id)
    assert any(c.status == "open" for c in complaints), \
        f"{name}: expected open complaint for Rahul, complaints={complaints}"


@pytest.mark.asyncio
@pytest.mark.parametrize("name,adapter,client_id", [
    ("mock", MockCRMAdapter(), "client_001"),
    ("fake_leadsquared", FakeLeadSquaredCRMAdapter(), "lsq_001"),
], ids=["mock_log", "lsq_log"])
async def test_log_briefing(name, adapter, client_id):
    """log_briefing should not raise."""
    from models import BriefingLog
    import uuid
    from datetime import datetime

    log = BriefingLog(
        briefing_id=str(uuid.uuid4()),
        client_id=client_id,
        client_name="Rahul Mehta",
        rm_id="rm_test",
        rm_name="Test RM",
        timestamp=datetime.utcnow().isoformat(),
        duration_seconds=38.0,
        key_flags=["complaint_open"],
        suggested_pitch="Test pitch",
        call_id=f"test_{uuid.uuid4().hex[:8]}",
        risk_score="low",
    )
    # Should not raise
    await adapter.log_briefing(log)
