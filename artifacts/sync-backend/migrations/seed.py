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
