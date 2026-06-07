"""End-to-end Morning Brief router: schedule CRUD + mid-call /ask + /act."""
from __future__ import annotations

import asyncio
import os
import pytest


@pytest.mark.asyncio
async def test_schedule_crud_and_trigger_flow(app_client):
    """Create → list → trigger → wait → history shows counters."""
    # 1. Create
    r = await app_client.post("/api/v1/morning-brief/schedules", json={
        "rm_name": "Himanshu", "rm_phone": "+919876543210",
        "connection_id": "conn_lsq_sandbox",
        "hour_local": 7, "minute_local": 45, "weekday_mask": 31,
        "timezone": "Asia/Kolkata", "company_name": "Acme",
        "language_style": "hinglish", "enabled": True,
    })
    assert r.status_code == 200
    sched = r.json()
    sid = sched["id"]
    assert sched["enabled"] is True
    assert sched["next_call_at"]

    # 2. List
    r = await app_client.get("/api/v1/morning-brief/schedules")
    assert r.status_code == 200
    assert any(s["id"] == sid for s in r.json())

    # 3. Patch (disable)
    r = await app_client.patch(f"/api/v1/morning-brief/schedules/{sid}", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    # Re-enable for trigger test
    await app_client.patch(f"/api/v1/morning-brief/schedules/{sid}", json={"enabled": True})

    # 4. Trigger now
    r = await app_client.post(f"/api/v1/morning-brief/schedules/{sid}/trigger")
    assert r.status_code == 200
    call_id = r.json()["call_id"]
    assert call_id.startswith(("demo_brief_", "sim_brief_"))

    # 5. Wait for simulated 2-way conversation to finish (8 lines @ 1s)
    await asyncio.sleep(10)

    # 6. History should show 1 question + 1 action recorded
    r = await app_client.get(f"/api/v1/morning-brief/calls?schedule_id={sid}")
    assert r.status_code == 200
    rows = r.json()
    assert rows, "Expected at least one call history row"
    match = next((row for row in rows if row["call_id"] == call_id), None)
    assert match is not None, f"call_id {call_id} not in {[r['call_id'] for r in rows]}"
    assert match["questions_asked"] >= 1
    assert match["actions_executed"] >= 1


@pytest.mark.asyncio
async def test_mid_call_ask_endpoint(app_client):
    """The /ask endpoint returns a grounded answer for a known client."""
    # Create + trigger a schedule so the call_id exists
    r = await app_client.post("/api/v1/morning-brief/schedules", json={
        "rm_name": "Tester", "rm_phone": "+919999999999",
        "connection_id": "conn_lsq_sandbox",
        "hour_local": 8, "minute_local": 0, "weekday_mask": 31,
        "timezone": "Asia/Kolkata", "company_name": "Acme",
        "language_style": "english_only", "enabled": True,
    })
    sid = r.json()["id"]
    r = await app_client.post(f"/api/v1/morning-brief/schedules/{sid}/trigger")
    call_id = r.json()["call_id"]

    # Wait for the call row + agenda to land
    await asyncio.sleep(1)

    r = await app_client.post(f"/api/v1/morning-brief/{call_id}/ask", json={
        "question": "Tell me about Vikram",
        "client_hint": "Vikram",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["answer"]
    assert body["spoken"]


@pytest.mark.asyncio
async def test_mid_call_act_endpoint_executes_in_crm(app_client):
    """The /act endpoint parses an intent and executes against the active CRM."""
    r = await app_client.post("/api/v1/morning-brief/schedules", json={
        "rm_name": "Tester2", "rm_phone": "+919888888888",
        "connection_id": "conn_lsq_sandbox",
        "hour_local": 9, "minute_local": 30, "weekday_mask": 31,
        "timezone": "Asia/Kolkata", "company_name": "Acme",
        "language_style": "auto", "enabled": True,
    })
    sid = r.json()["id"]
    r = await app_client.post(f"/api/v1/morning-brief/schedules/{sid}/trigger")
    call_id = r.json()["call_id"]
    await asyncio.sleep(1)

    r = await app_client.post(f"/api/v1/morning-brief/{call_id}/act", json={
        "intent": "create_task",
        "details": "follow-up call with Vikram tomorrow at 10 AM",
        "client_hint": "Vikram",
    })
    assert r.status_code == 200
    body = r.json()
    assert "done" in body["confirmation"].lower() or "logged" in body["confirmation"].lower()
