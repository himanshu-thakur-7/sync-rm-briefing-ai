"""End-to-end API integration tests using the FastAPI test client."""
import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_health(app_client):
    r = await app_client.get("/api/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_clients(app_client):
    r = await app_client.get("/api/v1/clients")
    assert r.status_code == 200
    clients = r.json()
    assert len(clients) == 5
    names = [c["name"] for c in clients]
    assert "Rahul Mehta" in names


@pytest.mark.asyncio
async def test_get_client_full_profile(app_client):
    r = await app_client.get("/api/v1/clients/lsq_001")
    assert r.status_code == 200
    data = r.json()
    assert data["profile"]["name"] == "Rahul Mehta"
    assert data["risk"]["score"] == "low"
    assert len(data["products"]) >= 1
    assert len(data["cross_sell"]) >= 1


@pytest.mark.asyncio
async def test_search_client_fuzzy(app_client):
    r = await app_client.get("/api/v1/clients/search", params={"name": "vikram"})
    assert r.status_code == 200
    results = r.json()
    assert any("Vikram" in c["name"] for c in results)


@pytest.mark.asyncio
async def test_integrations_list(app_client, lsq_sandbox_id):
    r = await app_client.get("/api/v1/integrations")
    assert r.status_code == 200
    conns = r.json()
    ids = [c["id"] for c in conns]
    assert lsq_sandbox_id in ids


@pytest.mark.asyncio
async def test_integration_test_endpoint(app_client, lsq_sandbox_id):
    r = await app_client.post(f"/api/v1/integrations/{lsq_sandbox_id}/test")
    assert r.status_code == 200
    result = r.json()
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_oauth_providers(app_client):
    r = await app_client.get("/api/v1/oauth/providers")
    assert r.status_code == 200
    providers = {p["provider"] for p in r.json()}
    assert "hubspot" in providers
    assert "fake_leadsquared" in providers


@pytest.mark.asyncio
async def test_embed_spec(app_client, lsq_sandbox_id):
    r = await app_client.get(f"/api/v1/embeds/{lsq_sandbox_id}/contact/lsq_001")
    assert r.status_code == 200
    spec = r.json()
    assert "url" in spec
    assert spec["may_block_frame"] is False  # FakeLSQ is always embeddable


@pytest.mark.asyncio
async def test_sandbox_html_view(app_client):
    r = await app_client.get("/api/v1/embeds/sandbox/contact/lsq_001")
    assert r.status_code == 200
    assert "Rahul Mehta" in r.text
    assert "LeadSquared" in r.text


@pytest.mark.asyncio
async def test_voice_command_parse(app_client, lsq_sandbox_id):
    r = await app_client.post("/api/v1/voice/commands/parse", json={
        "transcript": "Add a note that she is interested in a home loan",
        "context": {
            "active_connection_id": lsq_sandbox_id,
            "active_client_id": "lsq_004",
            "active_client_name": "Sneha Reddy",
            "rm_name": "Test RM",
        },
    })
    assert r.status_code == 200
    cmd = r.json()
    assert cmd["tool"]
    assert "dry_run_preview" in cmd


@pytest.mark.asyncio
async def test_sync_now(app_client):
    r = await app_client.post("/api/v1/calls/sync-now", json={
        "client_id": "lsq_005",
        "rm_phone": "+919876543210",
        "rm_name": "Test RM",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["call_id"]
    assert data["status"] in ("initiated", "simulated")
