"""Shared fixtures for the SYNC backend test suite."""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def app_client():
    """FastAPI test client with DB initialized and seeded."""
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_sync.db")

    from main import app
    from db import init_db
    from migrations.seed import seed_default_connections

    await init_db()
    await seed_default_connections()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(scope="session")
def lsq_sandbox_id():
    return "conn_lsq_sandbox"
