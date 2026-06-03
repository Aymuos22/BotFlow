"""
Async database engine and session management.

Uses SQLAlchemy 2.0 async API.  The engine is configured once at module
import time; sessions are injected via the FastAPI ``get_db`` dependency.

Production target  : Supabase Postgres  (postgresql+asyncpg://)
Local / test target: SQLite in-memory   (sqlite+aiosqlite:///:memory:)
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _build_engine(database_url: str) -> AsyncEngine:
    """
    Build an async SQLAlchemy engine with sensible pool settings.

    SQLite does not support connection pools the same way Postgres does,
    so pool parameters are only applied for Postgres connections.
    """
    kwargs: dict = {"echo": settings.db_echo}

    if "sqlite" in database_url:
        # SQLite specific: disable thread check for async usage
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow
        kwargs["pool_recycle"] = settings.db_pool_recycle_seconds

    return create_async_engine(database_url, **kwargs)


engine: AsyncEngine = _build_engine(settings.database_url)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=True,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a transactional async DB session.

    Commits on clean exit, rolls back on any exception, and always
    closes the session when the request ends.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
