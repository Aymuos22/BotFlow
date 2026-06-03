"""
Alembic environment configuration.

Configured for async SQLAlchemy (asyncpg / Supabase Postgres).
The DATABASE_URL is loaded from application settings so it always
matches the runtime environment without duplication.
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# ------------------------------------------------------------------ #
# Make app importable from migrations/
# ------------------------------------------------------------------ #
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.models import Base  # registers all ORM models

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection needed)."""
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine (required for asyncpg)."""
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda sync_conn: context.configure(
                connection=sync_conn,
                target_metadata=target_metadata,
                compare_type=True,
            )
        )
        async with connection.begin():
            await connection.run_sync(
                lambda sync_conn: context.run_migrations()
            )
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (connected) migration execution."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
