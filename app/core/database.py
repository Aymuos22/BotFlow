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


def _coerce_to_session_pooler(url: str) -> str:
    """
    Supabase exposes two PgBouncer endpoints:

      • Transaction pooler  — port 6543  (pool_mode=transaction)
        asyncpg creates *named* prepared statements (``__asyncpg_stmt_N__``)
        that get stranded on the backend connection when the SQLAlchemy pool
        returns the connection mid-session.  On the next checkout PgBouncer
        may hand back a backend that still has ``__asyncpg_stmt_1__``
        registered → DuplicatePreparedStatementError.
        Setting statement_cache_size=0 is NOT sufficient: asyncpg still
        creates named statements; it just stops caching the objects.

      • Session pooler      — port 5432  (pool_mode=session)
        Each PgBouncer "session" maps to one persistent backend connection
        for its entire lifetime, so prepared statements never collide across
        different asyncpg instances.

    Automatically rewrite port 6543 → 5432 so the app always connects via
    the session pooler.  No-op for direct connections and any other port.
    """
    return url.replace(":6543/", ":5432/")


def _build_engine(database_url: str) -> AsyncEngine:
    """Build an async SQLAlchemy engine with sensible pool settings."""
    kwargs: dict = {"echo": settings.db_echo}

    if "sqlite" in database_url:
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow
        kwargs["pool_recycle"] = settings.db_pool_recycle_seconds
        # Belt-and-suspenders: disable asyncpg's own statement cache too.
        kwargs["connect_args"] = {"statement_cache_size": 0}

    return create_async_engine(database_url, **kwargs)


# Rewrite the URL before building the engine.  When DATABASE_URL points at
# Supabase's transaction pooler (port 6543) this switches it to the session
# pooler (port 5432) which fully supports asyncpg's prepared statements.
_db_url = _coerce_to_session_pooler(settings.database_url)

engine: AsyncEngine = _build_engine(_db_url)

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
