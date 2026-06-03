"""
One-time database table creation script.

Run this on a fresh Supabase/PostgreSQL database before starting the server:

    python scripts/create_tables.py

This will create all tables defined in app/models/.
For production, prefer Alembic migrations (Phase 4).
"""
import asyncio
import sys
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import engine
from app.models.base import Base

# Import all models to register them with SQLAlchemy metadata
import app.models  # noqa: F401


async def create_all_tables() -> None:
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Done. All tables created.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_all_tables())
