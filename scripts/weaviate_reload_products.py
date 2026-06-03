#!/usr/bin/env python3
"""
Drop the Weaviate collection for a company, recreate it fresh,
then reindex all active products from the database.

Does NOT touch PostgreSQL – product rows are kept as-is.

Usage:
    python scripts/weaviate_reload_products.py \
        --company-id 33eaf707-06f1-4e30-93d8-d8da71afaa92

Flags:
    --dry-run   Print what would happen without modifying Weaviate
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.integrations.weaviate.client import WeaviateClient
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.product_event_repository import ProductEventRepository
from app.repositories.product_repository import ProductRepository
from app.services.product_service import ProductService

logger = logging.getLogger("weaviate_reload_products")


async def run(company_id: UUID, dry_run: bool) -> None:
    weaviate = WeaviateClient(
        url=settings.weaviate_url,
        api_key=settings.weaviate_api_key,
        timeout=settings.weaviate_timeout_seconds,
    )

    try:
        async with AsyncSessionLocal() as db:
            config_repo = CompanyConfigRepository(db)
            product_repo = ProductRepository(db)
            event_repo = ProductEventRepository(db)

            # ── 1. Resolve collection name from company config ──────────── #
            config = await config_repo.get_by_company(company_id)
            if not config:
                logger.error("No CompanyConfig found for company %s", company_id)
                return

            collection = config.weaviate_collection
            logger.info("Collection name: %s", collection)

            # ── 2. Count products to be reindexed ───────────────────────── #
            products = await product_repo.list_by_company(
                company_id, is_active=True, limit=5000
            )
            logger.info(
                "Active products in DB: %d",
                len(products),
            )

            if dry_run:
                logger.info("[DRY RUN] Would delete + recreate collection %r", collection)
                logger.info("[DRY RUN] Would reindex %d products", len(products))
                for p in products:
                    logger.info("  %s  %s", p.sku or "(no sku)", p.name)
                return

            # ── 3. Drop existing collection ─────────────────────────────── #
            exists = await weaviate.collection_exists(collection)
            if exists:
                logger.info("Deleting collection %r …", collection)
                await weaviate.delete_collection(collection)
                logger.info("Collection deleted.")
            else:
                logger.info("Collection %r does not exist – will create fresh.", collection)

            # ── 4. Recreate collection ──────────────────────────────────── #
            logger.info("Creating collection %r …", collection)
            await weaviate.create_collection(collection)
            logger.info("Collection created.")

            # ── 5. Reindex all active products ──────────────────────────── #
            svc = ProductService(
                product_repo=product_repo,
                event_repo=event_repo,
                config_repo=config_repo,
                weaviate_client=weaviate,
            )

            ok = failed = 0
            for product in products:
                result = await svc.index_product(product)
                if result.success:
                    logger.info("  INDEXED  %s — %s", product.sku or "(no sku)", product.name)
                    ok += 1
                else:
                    logger.error(
                        "  FAILED   %s — %s : %s",
                        product.sku or "(no sku)",
                        product.name,
                        result.message,
                    )
                    failed += 1

            logger.info(
                "\nDone — indexed=%d  failed=%d  collection=%s",
                ok, failed, collection,
            )

    finally:
        await weaviate.aclose()
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    p = argparse.ArgumentParser(
        description="Wipe and reload Weaviate collection for a company"
    )
    p.add_argument("--company-id", required=True, help="Company UUID")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without touching Weaviate",
    )
    args = p.parse_args()
    asyncio.run(run(UUID(args.company_id), dry_run=args.dry_run))


if __name__ == "__main__":
    main()
