"""Idempotent seed routines run on first boot."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlmodel import select

from db import get_session
from db.models import CRMConnection

logger = logging.getLogger(__name__)


async def seed_default_connections() -> None:
    """Seed the FakeLeadSquared sandbox (the default demo connection) and the
    Mock CRM (legacy fallback). Both are seeded only if no rows exist yet."""
    async with get_session() as session:
        existing = list((await session.exec(select(CRMConnection))).all())
        existing_ids = {row.id for row in existing}

        if "conn_lsq_sandbox" not in existing_ids:
            session.add(CRMConnection(
                id="conn_lsq_sandbox",
                provider="fake_leadsquared",
                label="LeadSquared (Sandbox)",
                status="active",
                auth_method="api_key",
                metadata_json={
                    "description": "In-process mock — exercises full LeadSquared adapter code path",
                    "region": "fake-lsq.sync.internal",
                },
                is_default=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
            logger.info("Seeded FakeLeadSquared sandbox connection (conn_lsq_sandbox).")

        if "conn_mock_default" not in existing_ids:
            session.add(CRMConnection(
                id="conn_mock_default",
                provider="mock",
                label="Mock CRM (Legacy)",
                status="active",
                auth_method="none",
                metadata_json={"description": "Pure in-memory 5-client dataset"},
                is_default=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
            logger.info("Seeded mock CRMConnection (conn_mock_default).")

        # If conn_mock_default was already the only default, flip it to lsq_sandbox.
        if "conn_lsq_sandbox" not in existing_ids:
            for row in existing:
                if row.is_default:
                    row.is_default = False
                    session.add(row)

    # ── R4: Pipedrive — seed a live connection if credentials are configured.
    # If CRM_ADAPTER=pipedrive we also promote it to is_default=True so the
    # dashboard's source switcher lands on Pipedrive out of the box.
    try:
        from config import settings
        pipedrive_configured = bool(settings.pipedrive_api_token and settings.pipedrive_company_domain)

        # SAFETY: if a Pipedrive row was persisted previously (e.g. dev sync.db
        # carried into prod) but the env no longer has credentials, demote it
        # back to non-default and re-promote the sandbox so every API call
        # doesn't 500 with 401-from-Pipedrive.
        if not pipedrive_configured:
            async with get_session() as session:
                stale = (await session.exec(
                    select(CRMConnection).where(CRMConnection.id == "conn_pipedrive_demo")
                )).first()
                if stale is not None and stale.is_default:
                    stale.is_default = False
                    session.add(stale)
                    sandbox = (await session.exec(
                        select(CRMConnection).where(CRMConnection.id == "conn_lsq_sandbox")
                    )).first()
                    if sandbox is not None:
                        sandbox.is_default = True
                        session.add(sandbox)
                    logger.warning(
                        "Pipedrive token missing in env — demoted conn_pipedrive_demo "
                        "and re-promoted conn_lsq_sandbox to default."
                    )

        if pipedrive_configured:
            async with get_session() as session:
                row = (await session.exec(
                    select(CRMConnection).where(CRMConnection.id == "conn_pipedrive_demo")
                )).first()
                wants_default = settings.crm_adapter == "pipedrive"
                if row is None:
                    session.add(CRMConnection(
                        id="conn_pipedrive_demo",
                        provider="pipedrive",
                        label=f"Pipedrive · {settings.pipedrive_company_domain}",
                        status="active",
                        auth_method="api_key",
                        metadata_json={
                            "company_domain": settings.pipedrive_company_domain,
                            "description": "Demo CRM — personal-token auth, fully populated",
                        },
                        is_default=wants_default,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    ))
                    logger.info("Seeded Pipedrive connection (conn_pipedrive_demo, default=%s).", wants_default)
                elif wants_default and not row.is_default:
                    row.is_default = True
                    session.add(row)
                    logger.info("Promoted conn_pipedrive_demo to default (CRM_ADAPTER=pipedrive).")
                # If Pipedrive is the default, unflag any other defaults
                if wants_default:
                    others = list((await session.exec(
                        select(CRMConnection).where(CRMConnection.id != "conn_pipedrive_demo")
                    )).all())
                    for o in others:
                        if o.is_default:
                            o.is_default = False
                            session.add(o)
    except Exception as e:
        logger.warning("Pipedrive seed skipped: %s", e)
