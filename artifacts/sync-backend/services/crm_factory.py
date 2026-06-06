"""Legacy CRM-adapter accessor.

Kept for back-compat with routers that import `crm()` directly. The real
multi-connection resolution now lives in `services.connection_registry`.
The `crm()` shim returns whatever adapter the registry resolves as default
at call time.
"""
import asyncio
import logging
from typing import Optional

from adapters.base import CRMAdapter

logger = logging.getLogger(__name__)

# Module-level cache so synchronous callers don't pay the lookup twice.
_cached: Optional[CRMAdapter] = None


def crm() -> CRMAdapter:
    """Return the default CRM adapter.

    Synchronous bridge over the async registry: routers that want the active
    adapter without a connection_id (the legacy path) get the registry's
    default. New code should prefer `await connection_registry.crm_for(id)`.
    """
    from services import connection_registry

    global _cached
    if _cached is not None:
        return _cached

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # Called from an async context — schedule a task and wait.
        # The legacy callers in routers/* are sync wrappers around await crm().*
        # so we expose an awaitable accessor below. The lazy import keeps the
        # adapter classes out of import-time costs.
        raise RuntimeError(
            "crm() called from running event loop — use `await crm_async()` "
            "or `await connection_registry.default_adapter()` instead."
        )

    _cached = asyncio.run(connection_registry.default_adapter())
    return _cached


async def crm_async() -> CRMAdapter:
    """Async accessor for the default adapter."""
    from services import connection_registry

    return await connection_registry.default_adapter()


def invalidate() -> None:
    global _cached
    _cached = None
    from services import connection_registry

    connection_registry.invalidate()
