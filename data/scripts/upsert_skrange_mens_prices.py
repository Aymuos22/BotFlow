"""
Upsert skrange men's-health product pricing (MRP / COD / Prepaid).
Matches by name; creates new row when not found.

Usage (from repo root inside the API container):
    python data/scripts/upsert_skrange_mens_prices.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.integrations.weaviate.client import WeaviateClient  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402
from app.repositories.product_event_repository import ProductEventRepository  # noqa: E402
from app.repositories.product_repository import ProductRepository  # noqa: E402
from app.schemas.product import ProductCreate, ProductUpdate  # noqa: E402
from app.services.product_service import ProductService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("upsert_skrange_mens")

COMPANY_ID = UUID("55b3e336-62cf-45ab-95f6-0bb9432af326")  # skrange

PREPAID_OFFER = "10% off + free sexual oil worth ₹1299"

PRODUCTS = [
    {
        "name": "Liv Muztang",
        "sku": "SKR-LM-001",
        "category": "Men's Health",
        "mrp": 5999,
        "cod_price": 4999,
        "prepaid_price": 4499,
        "product_url": "https://skinrange.com/products/liv-muztang",
    },
    {
        "name": "Liv Muztang REX",
        "sku": "SKR-LMR-001",
        "category": "Men's Health",
        "mrp": 9374,
        "cod_price": 9374,
        "prepaid_price": 8436,
        "product_url": "https://skinrange.com/products/liv-muztang-rex",
    },
    {
        "name": "Liv Muztang Plus",
        "sku": "SKR-LMP-001",
        "category": "Men's Health",
        "mrp": 9375,
        "cod_price": 7499,
        "prepaid_price": 6749,
        "product_url": "https://skinrange.com/products/liv-muztang-plus",
    },
    {
        "name": "Herbo 65",
        "sku": "SKR-H65-001",
        "category": "Men's Health",
        "mrp": 4687,
        "cod_price": 4687,
        "prepaid_price": 4218,
        "product_url": "https://skinrange.com/products/herbo-365",
    },
    {
        "name": "Ultimate Hammer",
        "sku": "SKR-UH-001",
        "category": "Men's Health",
        "mrp": 1874,
        "cod_price": 1799,
        "prepaid_price": 1619,
        "product_url": "https://skinrange.com/products/ultimate-hammer",
    },
    {
        "name": "Kaama Gold",
        "sku": "SKR-KG-001",
        "category": "Men's Health",
        "mrp": 2999,
        "cod_price": 2499,
        "prepaid_price": 2249,
        "product_url": "https://skinrange.com/products/kaama-gold",
    },
    {
        "name": "Ayush for Men",
        "sku": "SKR-AFM-001",
        "category": "Men's Health",
        "mrp": 2900,
        "cod_price": 2900,
        "prepaid_price": 2610,
        "product_url": "https://skinrange.com/products/ayush-for-men",
    },
    {
        "name": "Extra Time Kit",
        "sku": "SKR-ETK-001",
        "category": "Men's Health",
        "mrp": 3749,
        "cod_price": 3599,
        "prepaid_price": 3239,
        "product_url": "https://skinrange.com/products/extra-time",
    },
    {
        "name": "Sandy RX",
        "sku": "SKR-SRX-001",
        "category": "Men's Health",
        "mrp": 14063,
        "cod_price": 14063,
        "prepaid_price": 12656,
        "product_url": "https://skinrange.com/products/sandy-rx",
    },
    {
        "name": "Jaam e Ishq",
        "sku": "SKR-JEI-001",
        "category": "Men's Health",
        "mrp": 7000,
        "cod_price": 5100,
        "prepaid_price": 4590,
        "product_url": "https://skinrange.com/products/jaam-e-ishq",
    },
    {
        "name": "Macamo The Latin Lava",
        "sku": "SKR-MAC-001",
        "category": "Men's Health",
        "mrp": 9999,
        "cod_price": 9999,
        "prepaid_price": 8999,
        "product_url": "https://skinrange.com/products/macamo",
    },
]

MENS_HEALTH_SYNONYMS = [
    "mardana takat kaise badhaye",
    "timing badhane ki dawa",
    "sex time kaise badhaye",
    "sex power badhane ki medicine",
    "stamina kaise badhaye",
    "weak erection treatment",
    "erection problem solution",
    "intercourse timing medicine",
    "mardana taqat",
    "sex timing capsule",
]


def _price_json(p: dict) -> dict:
    return {
        "currency": "INR",
        "mrp": p["mrp"],
        "cod_price": p["cod_price"],
        "prepaid_price": p["prepaid_price"],
        "prepaid_offer": PREPAID_OFFER,
    }


def _attributes_json(p: dict) -> dict:
    return {
        "brand": "Skinrange",
        "product_url": p["product_url"],
        "stock_status": "In Stock",
    }


def _synonyms(p: dict) -> list[str]:
    base = [p["name"], p["name"].lower()]
    base += MENS_HEALTH_SYNONYMS
    return list(dict.fromkeys(base))  # dedupe, preserve order


async def main() -> None:
    weaviate = WeaviateClient(
        url=settings.weaviate_url,
        api_key=settings.weaviate_api_key,
        timeout=settings.weaviate_timeout_seconds,
    )
    created = updated = failed = 0
    try:
        async with AsyncSessionLocal() as db:
            product_repo = ProductRepository(db)
            svc = ProductService(
                product_repo=product_repo,
                event_repo=ProductEventRepository(db),
                config_repo=CompanyConfigRepository(db),
                weaviate_client=weaviate,
            )

            for p in PRODUCTS:
                name = p["name"]
                sku = p["sku"]
                price = _price_json(p)
                attrs = _attributes_json(p)
                synonyms = _synonyms(p)

                # Try by SKU first, then by name
                existing = await product_repo.get_by_sku(COMPANY_ID, sku)
                if not existing:
                    # Fallback: name match
                    all_products = await product_repo.list_by_company(COMPANY_ID, is_active=None, limit=500)
                    existing = next(
                        (x for x in all_products if x.name.strip().casefold() == name.strip().casefold()),
                        None,
                    )

                try:
                    if existing:
                        await svc.update_product(
                            existing.id,
                            COMPANY_ID,
                            ProductUpdate(
                                name=name,
                                sku=sku,
                                category=p["category"],
                                price_json=price,
                                attributes_json=attrs,
                                synonyms=synonyms,
                                is_active=True,
                            ),
                        )
                        logger.info("UPDATE  %s — MRP %s / COD %s / Prepaid %s",
                                    name, p["mrp"], p["cod_price"], p["prepaid_price"])
                        updated += 1
                    else:
                        product = await svc.create_product(
                            COMPANY_ID,
                            ProductCreate(
                                name=name,
                                sku=sku,
                                category=p["category"],
                                price_json=price,
                                attributes_json=attrs,
                                synonyms=synonyms,
                                is_active=True,
                            ),
                        )
                        status = "indexed" if product.weaviate_indexed else "NOT indexed"
                        logger.info("CREATE  %s — [%s]", name, status)
                        created += 1
                except Exception as exc:
                    logger.error("ERROR   %s: %s", name, exc)
                    failed += 1

    finally:
        await weaviate.aclose()
        await engine.dispose()

    logger.info("\nDone — created=%d  updated=%d  failed=%d", created, updated, failed)


if __name__ == "__main__":
    asyncio.run(main())
