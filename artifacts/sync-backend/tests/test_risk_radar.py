"""Risk Radar rule tests against the 5 FakeLeadSquared fixtures."""
import pytest
from adapters.fake_leadsquared import FakeLeadSquaredCRMAdapter
from services import risk_radar
from services import connection_registry


@pytest.fixture
def adapter(monkeypatch):
    a = FakeLeadSquaredCRMAdapter()

    # Point the registry at this adapter so risk_radar.scan can resolve it.
    async def _crm_for(connection_id):
        return a

    monkeypatch.setattr(connection_registry, "crm_for", _crm_for)
    return a


@pytest.mark.asyncio
async def test_scan_returns_plays(adapter):
    plays = await risk_radar.scan("conn_lsq_sandbox")
    assert plays, "Radar should detect at least one play"
    # One play per flagged client
    client_ids = [p.client_id for p in plays]
    assert len(client_ids) == len(set(client_ids)), "Plays must be deduped per client"


@pytest.mark.asyncio
async def test_vikram_is_critical_npa(adapter):
    plays = await risk_radar.scan("conn_lsq_sandbox")
    vik = next((p for p in plays if p.client_name == "Vikram Desai"), None)
    assert vik is not None, "Vikram should be flagged"
    assert vik.urgency == "CRITICAL"
    assert vik.trigger_type == "npa_risk"
    # Vikram also has an aging complaint + EMI due — captured as matched triggers
    assert "npa_risk" in vik.matched_triggers


@pytest.mark.asyncio
async def test_amit_aging_complaint(adapter):
    plays = await risk_radar.scan("conn_lsq_sandbox")
    amit = next((p for p in plays if p.client_name == "Amit Kulkarni"), None)
    assert amit is not None
    # Amit's escalated complaint is ~20 days old → HIGH aging_complaint
    assert "aging_complaint" in amit.matched_triggers


@pytest.mark.asyncio
async def test_plays_sorted_by_urgency(adapter):
    plays = await risk_radar.scan("conn_lsq_sandbox")
    rank = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
    ranks = [rank[p.urgency] for p in plays]
    assert ranks == sorted(ranks, reverse=True), "Plays must surface highest urgency first"


@pytest.mark.asyncio
async def test_rahul_complaint_too_recent_for_aging(adapter):
    """Rahul's complaint is only ~7 days old — should NOT trigger aging_complaint."""
    plays = await risk_radar.scan("conn_lsq_sandbox")
    rahul = next((p for p in plays if p.client_name == "Rahul Mehta"), None)
    if rahul:  # Rahul may still be flagged for proactive_crosssell (SIP/education)
        assert "aging_complaint" not in rahul.matched_triggers
