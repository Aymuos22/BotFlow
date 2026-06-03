"""
One-time script: clear ALL chat + analytics data for SK Group.
Company ID: 33eaf707-06f1-4e30-93d8-d8da71afaa92

Tables cleared:
  retrieval_logs        — fallback / RAG analytics
  daily_company_metrics — aggregated daily stats
  conversations         — chat threads (cascades → messages, handoffs)
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


async def main(dry_run: bool = True):
    conn = await asyncpg.connect(PG_URL)
    try:
        convs   = await conn.fetchval("SELECT COUNT(*) FROM conversations        WHERE company_id=$1::uuid", COMPANY_ID)
        msgs    = await conn.fetchval("SELECT COUNT(*) FROM messages              WHERE company_id=$1::uuid", COMPANY_ID)
        hdoffs  = await conn.fetchval("SELECT COUNT(*) FROM handoffs              WHERE company_id=$1::uuid", COMPANY_ID)
        rlogs   = await conn.fetchval("SELECT COUNT(*) FROM retrieval_logs        WHERE company_id=$1::uuid", COMPANY_ID)
        metrics = await conn.fetchval("SELECT COUNT(*) FROM daily_company_metrics WHERE company_id=$1::uuid", COMPANY_ID)

        print(f"\n── SK Group data (company_id={COMPANY_ID}) ──")
        print(f"  conversations        : {convs}")
        print(f"  messages             : {msgs}   (cascade from conversations)")
        print(f"  handoffs             : {hdoffs}  (cascade from conversations)")
        print(f"  retrieval_logs       : {rlogs}   ← fallback chart source")
        print(f"  daily_company_metrics: {metrics}  ← analytics chart source")

        if dry_run:
            print("\n[DRY RUN] No changes made. Re-run with --execute to delete.\n")
            return

        # Order matters: retrieval_logs before conversations (FK)
        await conn.execute("DELETE FROM retrieval_logs        WHERE company_id=$1::uuid", COMPANY_ID)
        await conn.execute("DELETE FROM daily_company_metrics WHERE company_id=$1::uuid", COMPANY_ID)
        await conn.execute("DELETE FROM conversations         WHERE company_id=$1::uuid", COMPANY_ID)

        convs2   = await conn.fetchval("SELECT COUNT(*) FROM conversations        WHERE company_id=$1::uuid", COMPANY_ID)
        msgs2    = await conn.fetchval("SELECT COUNT(*) FROM messages              WHERE company_id=$1::uuid", COMPANY_ID)
        rlogs2   = await conn.fetchval("SELECT COUNT(*) FROM retrieval_logs        WHERE company_id=$1::uuid", COMPANY_ID)
        metrics2 = await conn.fetchval("SELECT COUNT(*) FROM daily_company_metrics WHERE company_id=$1::uuid", COMPANY_ID)

        print(f"\n✅ After cleanup:")
        print(f"  conversations        : {convs2}")
        print(f"  messages             : {msgs2}")
        print(f"  retrieval_logs       : {rlogs2}")
        print(f"  daily_company_metrics: {metrics2}")
        print("\nDone. SK Group is completely clean.\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    asyncio.run(main(dry_run=dry_run))
