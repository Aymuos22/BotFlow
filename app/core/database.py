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

    PgBouncer (transaction mode) note
    ----------------------------------
    Supabase exposes a PgBouncer transaction-pooler on port 6543.
    asyncpg's prepared-statement cache is incompatible with transaction
    pooling — it raises DuplicatePreparedStatementError when the server
    re-uses an underlying pooled connection that already has named prepared
    statements registered from a previous session.

    We unconditionally set statement_cache_size=0 for all asyncpg/Postgres
    connections.  This is safe for non-PgBouncer direct connections too: it
    simply disables asyncpg's client-side statement cache (minor perf cost,
    no correctness impact), and it avoids the fragile URL-pattern detection
    that can silently miss PgBouncer deployments with non-standard URLs.

    Standalone CLI scripts should additionally switch to the session pooler
    (port 5432) which fully supports the extended query protocol.
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
        # Always disable asyncpg prepared-statement cache for Postgres.
        # Required for PgBouncer transaction-mode (Supabase pooler);
        # harmless for direct connections.
        kwargs["connect_args"] = {"statement_cache_size": 0}

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
