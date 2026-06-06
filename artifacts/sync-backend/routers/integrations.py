"""Integrations router — manage CRM connections, sync, provisioning, field mappings.

Mounts at /api/v1/integrations. Used by the dashboard Integrations page.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import select

from db import get_session
from db.models import CRMConnection, FieldMapping
from services import connection_registry
from services.field_mapper import invalidate as invalidate_mapper
from services.provisioning import ProvisioningReport, detect, get_specs, provision

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


# ------------------------------------------------------------------ #
# Response models
# ------------------------------------------------------------------ #

class ConnectionSummary(BaseModel):
    id: str
    provider: str
    label: str
    status: str
    auth_method: str
    is_default: bool
    last_sync_at: Optional[str] = None
    last_error: Optional[str] = None
    provisioning_present: int = 0
    provisioning_missing: int = 0


class ConnectionDetail(ConnectionSummary):
    metadata: dict = {}
    provisioning_report: Optional[dict] = None


class ProvisionRequest(BaseModel):
    fields: list[str]


class FieldMappingItem(BaseModel):
    object_type: str
    canonical_name: str
    bank_field_name: str


class FieldMappingUpdate(BaseModel):
    mappings: list[FieldMappingItem]


class TestResult(BaseModel):
    ok: bool
    sample_client: Optional[str] = None
    error: Optional[str] = None


# ------------------------------------------------------------------ #
# List / detail
# ------------------------------------------------------------------ #

@router.get("", response_model=list[ConnectionSummary])
async def list_connections():
    conns = await connection_registry.list_connections()
    result = []
    for c in conns:
        specs = get_specs(c.provider)
        result.append(ConnectionSummary(
            id=c.id,
            provider=c.provider,
            label=c.label,
            status=c.status,
            auth_method=c.auth_method,
            is_default=c.is_default,
            last_sync_at=c.last_sync_at.isoformat() if c.last_sync_at else None,
            last_error=c.last_error,
            provisioning_present=len(specs),  # rough — actual check on /detail
            provisioning_missing=0,
        ))
    return result


@router.get("/{connection_id}", response_model=ConnectionDetail)
async def get_connection_detail(connection_id: str):
    conn = await connection_registry.get_connection(connection_id)
    if not conn:
        raise HTTPException(404, f"Connection {connection_id} not found")

    try:
        report = await detect(connection_id)
        report_dict = {
            "present": report.present,
            "missing": report.missing,
            "type_mismatch": report.type_mismatch,
            "checked_at": report.checked_at,
        }
        present_count = len(report.present)
        missing_count = len(report.missing)
    except Exception as e:
        logger.warning("Detect failed for %s: %s", connection_id, e)
        report_dict = None
        specs = get_specs(conn.provider)
        present_count = len(specs)
        missing_count = 0

    return ConnectionDetail(
        id=conn.id,
        provider=conn.provider,
        label=conn.label,
        status=conn.status,
        auth_method=conn.auth_method,
        is_default=conn.is_default,
        last_sync_at=conn.last_sync_at.isoformat() if conn.last_sync_at else None,
        last_error=conn.last_error,
        metadata=conn.metadata_json or {},
        provisioning_report=report_dict,
        provisioning_present=present_count,
        provisioning_missing=missing_count,
    )


# ------------------------------------------------------------------ #
# Sync / test
# ------------------------------------------------------------------ #

@router.post("/{connection_id}/sync-now")
async def sync_connection(connection_id: str):
    """Warm the adapter cache by calling list_all, update last_sync_at."""
    conn = await connection_registry.get_connection(connection_id)
    if not conn:
        raise HTTPException(404, f"Connection {connection_id} not found")

    try:
        adapter = await connection_registry.crm_for(connection_id)
        clients = await adapter.list_all()
        synced = len(clients)
    except Exception as e:
        async with get_session() as session:
            row = (await session.exec(select(CRMConnection).where(CRMConnection.id == connection_id))).first()
            if row:
                row.last_error = str(e)[:500]
                row.updated_at = datetime.now(timezone.utc)
                session.add(row)
        raise HTTPException(502, f"Sync failed: {e}")

    async with get_session() as session:
        row = (await session.exec(select(CRMConnection).where(CRMConnection.id == connection_id))).first()
        if row:
            row.last_sync_at = datetime.now(timezone.utc)
            row.last_error = None
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)

    # Broadcast to dashboard via WS
    from routers.webhooks import broadcast_event
    await broadcast_event({
        "type": "connection_synced",
        "data": {"connection_id": connection_id, "synced": synced},
    })

    return {"synced": synced, "connection_id": connection_id, "synced_at": datetime.now(timezone.utc).isoformat()}


@router.post("/{connection_id}/test", response_model=TestResult)
async def test_connection(connection_id: str):
    """Test the connection — list_all and return sample client name."""
    try:
        adapter = await connection_registry.crm_for(connection_id)
        clients = await adapter.list_all()
        sample = clients[0].name if clients else None
        return TestResult(ok=True, sample_client=sample)
    except Exception as e:
        return TestResult(ok=False, error=str(e))


# ------------------------------------------------------------------ #
# Set default connection
# ------------------------------------------------------------------ #

@router.post("/{connection_id}/set-default")
async def set_default(connection_id: str):
    async with get_session() as session:
        all_conns = list((await session.exec(select(CRMConnection))).all())
        for c in all_conns:
            c.is_default = (c.id == connection_id)
            session.add(c)
    return {"default": connection_id}


# ------------------------------------------------------------------ #
# Provisioning
# ------------------------------------------------------------------ #

@router.get("/{connection_id}/provision")
async def get_provisioning_status(connection_id: str):
    """Run detect() and return a fresh provisioning diff."""
    conn = await connection_registry.get_connection(connection_id)
    if not conn:
        raise HTTPException(404, f"Connection {connection_id} not found")
    try:
        report = await detect(connection_id)
    except Exception as e:
        raise HTTPException(502, f"Detect failed: {e}")
    specs = get_specs(conn.provider)
    return {
        "present": report.present,
        "missing": report.missing,
        "type_mismatch": report.type_mismatch,
        "checked_at": report.checked_at,
        "all_specs": [
            {"canonical": s.name, "crm_name": s.crm_name, "object": s.object_type, "required_for": s.required_for}
            for s in specs
        ],
    }


@router.post("/{connection_id}/provision")
async def provision_fields(connection_id: str, body: ProvisionRequest):
    """Create missing custom fields/properties in the bank's CRM."""
    conn = await connection_registry.get_connection(connection_id)
    if not conn:
        raise HTTPException(404, f"Connection {connection_id} not found")

    try:
        result = await provision(connection_id, body.fields)
    except Exception as e:
        raise HTTPException(502, f"Provision failed: {e}")

    if result.sf_package_zip:
        # Don't return the zip here — it's downloaded via a separate endpoint
        return {
            "provisioned": result.provisioned,
            "skipped": result.skipped,
            "errors": result.errors,
            "sf_package_available": True,
        }

    return {
        "provisioned": result.provisioned,
        "skipped": result.skipped,
        "errors": result.errors,
    }


@router.get("/{connection_id}/provision/sf-package.zip")
async def download_sf_package(connection_id: str):
    """Stream the Salesforce metadata package zip for manual deployment."""
    conn = await connection_registry.get_connection(connection_id)
    if not conn or conn.provider not in ("salesforce",):
        raise HTTPException(400, "Salesforce metadata packages only available for Salesforce connections")

    specs = get_specs(conn.provider)
    from services.provisioning import _provision_salesforce_package
    result = _provision_salesforce_package(specs)

    return StreamingResponse(
        iter([result.sf_package_zip]),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=sync-sf-package.zip"},
    )


# ------------------------------------------------------------------ #
# Field mappings
# ------------------------------------------------------------------ #

@router.get("/{connection_id}/field-mappings")
async def get_field_mappings(connection_id: str):
    """Return current canonical→bank field name overrides."""
    async with get_session() as session:
        rows = list(
            (await session.exec(select(FieldMapping).where(FieldMapping.connection_id == connection_id))).all()
        )
    return [
        {"object_type": r.object_type, "canonical_name": r.canonical_name, "bank_field_name": r.bank_field_name}
        for r in rows
    ]


@router.put("/{connection_id}/field-mappings")
async def update_field_mappings(connection_id: str, body: FieldMappingUpdate):
    """Upsert field-name overrides for the connection."""
    async with get_session() as session:
        # Delete existing
        existing = list(
            (await session.exec(select(FieldMapping).where(FieldMapping.connection_id == connection_id))).all()
        )
        for row in existing:
            await session.delete(row)
        # Re-insert
        for m in body.mappings:
            session.add(FieldMapping(
                connection_id=connection_id,
                object_type=m.object_type,
                canonical_name=m.canonical_name,
                bank_field_name=m.bank_field_name,
            ))
    # Invalidate the field mapper cache so next call picks up new mappings
    invalidate_mapper(connection_id)
    return {"updated": len(body.mappings)}
