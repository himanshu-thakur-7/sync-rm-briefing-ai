"""Per-connection CRM adapter resolution.

Replaces the singleton in `crm_factory.py` for new code paths. Old callers
that still use `crm_factory.crm()` keep working — that function now delegates
to `default_adapter()` here.

Multiple CRM connections can be registered simultaneously (HubSpot + Salesforce
+ Mock). `crm_for(connection_id)` returns the right adapter for each one,
caching instances so we don't re-instantiate HTTP clients on every call.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlmodel import select

from adapters.base import CRMAdapter
from db import get_session
from db.models import CRMConnection

logger = logging.getLogger(__name__)


# Adapter class cache, keyed by provider string.
_CLASS_CACHE: dict[str, type[CRMAdapter]] = {}
# Instantiated adapter cache, keyed by connection_id.
_INSTANCE_CACHE: dict[str, CRMAdapter] = {}


def _load_adapter_class(provider: str) -> type[CRMAdapter]:
    """Lazy import — keeps unused CRM SDKs from being imported at startup."""
    if provider in _CLASS_CACHE:
        return _CLASS_CACHE[provider]

    if provider == "mock":
        from adapters.mock_crm import MockCRMAdapter as cls
    elif provider == "hubspot":
        from adapters.hubspot import HubSpotCRMAdapter as cls
    elif provider == "salesforce":
        from adapters.salesforce import SalesforceCRMAdapter as cls
    elif provider == "zoho":
        from adapters.zoho import ZohoCRMAdapter as cls
    elif provider == "dynamics":
        from adapters.dynamics import DynamicsCRMAdapter as cls
    elif provider == "freshworks":
        from adapters.freshworks import FreshworksCRMAdapter as cls
    elif provider == "leadsquared":
        from adapters.leadsquared import LeadSquaredCRMAdapter as cls
    elif provider == "fake_leadsquared":
        from adapters.fake_leadsquared import FakeLeadSquaredCRMAdapter as cls
    else:
        raise ValueError(f"Unknown CRM provider: {provider}")

    _CLASS_CACHE[provider] = cls
    return cls


async def get_connection(connection_id: str) -> Optional[CRMConnection]:
    async with get_session() as session:
        return (
            await session.exec(
                select(CRMConnection).where(CRMConnection.id == connection_id)
            )
        ).first()


async def list_connections() -> list[CRMConnection]:
    async with get_session() as session:
        return list(
            (await session.exec(select(CRMConnection).order_by(CRMConnection.created_at))).all()
        )


async def default_connection_id() -> str:
    """Return the connection_id for the currently active default connection.

    Priority:
      1. CRMConnection row with is_default=True
      2. First active connection
      3. Falls back to legacy `settings.crm_adapter` value (e.g. "mock")
    """
    async with get_session() as session:
        row = (
            await session.exec(
                select(CRMConnection).where(CRMConnection.is_default == True).limit(1)  # noqa: E712
            )
        ).first()
        if row is not None:
            return row.id
        row = (
            await session.exec(
                select(CRMConnection).where(CRMConnection.status == "active").limit(1)
            )
        ).first()
        if row is not None:
            return row.id
    # Last resort: synthetic legacy id so old code that doesn't know about
    # the registry still routes through the configured adapter.
    from config import settings

    return f"legacy_{settings.crm_adapter}"


async def crm_for(connection_id: str) -> CRMAdapter:
    """Return the adapter instance bound to a given connection_id."""
    if connection_id in _INSTANCE_CACHE:
        return _INSTANCE_CACHE[connection_id]

    # Legacy fallback path — synthesise an adapter from settings.
    if connection_id.startswith("legacy_"):
        provider = connection_id[len("legacy_") :]
        cls = _load_adapter_class(provider)
        adapter = await _instantiate(cls, connection_id=connection_id, provider=provider, metadata={})
        _INSTANCE_CACHE[connection_id] = adapter
        return adapter

    conn = await get_connection(connection_id)
    if conn is None:
        raise KeyError(f"No CRMConnection row for id={connection_id!r}")
    cls = _load_adapter_class(conn.provider)
    adapter = await _instantiate(
        cls, connection_id=conn.id, provider=conn.provider, metadata=conn.metadata_json or {}
    )
    _INSTANCE_CACHE[connection_id] = adapter
    return adapter


async def _instantiate(
    cls: type[CRMAdapter], *, connection_id: str, provider: str, metadata: dict
) -> CRMAdapter:
    """Construct an adapter. Adapters that accept connection_id are passed it;
    legacy adapters with a no-arg constructor still work."""
    try:
        return cls(connection_id=connection_id, metadata=metadata)  # type: ignore[call-arg]
    except TypeError:
        return cls()  # type: ignore[call-arg]


async def default_adapter() -> CRMAdapter:
    return await crm_for(await default_connection_id())


def invalidate(connection_id: Optional[str] = None) -> None:
    if connection_id is None:
        _INSTANCE_CACHE.clear()
    else:
        _INSTANCE_CACHE.pop(connection_id, None)
