"""Async SQLite engine + session lifecycle."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from config import settings

logger = logging.getLogger(__name__)

_engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

async_session_maker = async_sessionmaker(
    _engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """Create tables if missing. Idempotent; safe to call on every boot."""
    # Import to register tables on the metadata before create_all runs.
    from db import models  # noqa: F401

    async with _engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("DB initialized at %s", settings.database_url)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Async session context manager. Commits on success; rolls back on error."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose() -> None:
    """Tear down the engine on app shutdown."""
    await _engine.dispose()
