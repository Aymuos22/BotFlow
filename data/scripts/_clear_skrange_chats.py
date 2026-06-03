"""
One-time script: clear ONLY user chat data for SK Range (Skin Range).
Company ID: 33eaf707-06f1-4e30-93d8-d8da71afaa92

Tables cleared (user chat data only):
  conversations  — chat threads (cascades → messages, handoffs)

Tables NOT touched:
  retrieval_logs        — fallback / RAG analytics  ← preserved
  daily_company_metrics — aggregated daily stats     ← preserved
  portal_users          — agent/portal accounts      ← preserved
  products              — product catalogue          ← preserved

Usage:
  # dry-run (safe, prints counts only):
  python data/scripts/_clear_skrange_chats.py

  # actually delete:
  python data/scripts/_clear_skrange_chats.py --execute
"""
import asyncio
import os
import sys

import asyncpg

COMPANY_ID = "33eaf707-06f1-4e30-93d8-d8da71afaa92"

RAW_URL = os.environ["DATABASE_URL"]
PG_URL = (
    RAW_URL.replace("postgresql+asyncpg://", "postgresql://")
           .replace("postgres+asyncpg://", "postgresql://")
)


async def main(dry_run: bool = True) -> None:
    conn = await asyncpg.connect(PG_URL)
    try:
        convs  = await conn.fetchval("SELECT COUNT(*) FROM conversations WHERE company_id=$1::uuid", COMPANY_ID)
        msgs   = await conn.fetchval("SELECT COUNT(*) FROM messages      WHERE company_id=$1::uuid", COMPANY_ID)
        hdoffs = await conn.fetchval("SELECT COUNT(*) FROM handoffs      WHERE company_id=$1::uuid", COMPANY_ID)

        print(f"\n-- SK Range chat data (company_id={COMPANY_ID}) --")
        print(f"  conversations : {convs}")
        print(f"  messages      : {msgs}   (cascade-deleted with conversations)")
        print(f"  handoffs      : {hdoffs}  (cascade-deleted with conversations)")

        if dry_run:
            print("\n[DRY RUN] No changes made. Re-run with --execute to delete.\n")
            return

        # Single DELETE on conversations — FK cascades wipe messages + handoffs.
        await conn.execute(
            "DELETE FROM conversations WHERE company_id=$1::uuid",
            COMPANY_ID,
        )

        convs2  = await conn.fetchval("SELECT COUNT(*) FROM conversations WHERE company_id=$1::uuid", COMPANY_ID)
        msgs2   = await conn.fetchval("SELECT COUNT(*) FROM messages      WHERE company_id=$1::uuid", COMPANY_ID)
        hdoffs2 = await conn.fetchval("SELECT COUNT(*) FROM handoffs      WHERE company_id=$1::uuid", COMPANY_ID)

        print(f"\nAfter cleanup:")
        print(f"  conversations : {convs2}")
        print(f"  messages      : {msgs2}")
        print(f"  handoffs      : {hdoffs2}")
        print("\nDone. SK Range chat data is clean (analytics preserved).\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    asyncio.run(main(dry_run=dry_run))
