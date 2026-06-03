"""
Patch Herbo 65 and Kaama Gold descriptions so description/buy queries resolve correctly.
Run from inside the API container:
    python data/scripts/patch_herbo65_kaamagold_desc.py
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
from app.schemas.product import ProductUpdate  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.services.product_service import ProductService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("patch_herbo_kaama")

COMPANY_ID = UUID("55b3e336-62cf-45ab-95f6-0bb9432af326")

PATCHES = [
    {
        "sku": "SKR-H65-001",
        "name": "Herbo 65",
        "description": (
            "Herbo 65 is a potent Ayurvedic men's health capsule formulated to address "
            "low energy, poor stamina, low testosterone levels, reduced libido, and weak "
            "muscle mass in men. It contains a blend of traditional Ayurvedic herbs that "
            "help restore hormonal balance, improve sexual performance, and combat stress. "
            "Ideal for men experiencing fatigue, hormonal imbalance, or performance issues. "
            "Take 1 capsule twice daily with water or milk for best results."
        ),
        "extra_synonyms": [
            "Herbo 65",
            "herbo 65",
            "herbo sixty five",
            "herbo365",
            "herbo 365",
            "herbo-65",
            "ayurvedic testosterone booster",
            "mens stamina capsule",
            "low testosterone medicine",
            "hormonal balance capsule for men",
            "herbal energy booster men",
        ],
        "used_for": (
            "Low energy in men, weak muscle mass, low testosterone, reduced sexual "
            "performance, stress and hormonal imbalance"
        ),
        "dosage": "1 capsule twice daily with water or milk",
    },
    {
        "sku": "SKR-KG-001",
        "name": "Kaama Gold",
        "description": (
            "Kaama Gold is a premium Ayurvedic capsule crafted to enhance male sexual "
            "health, boost libido and desire, improve erection quality, and increase "
            "overall stamina and confidence. Formulated with powerful Ayurvedic herbs "
            "known for their aphrodisiac and restorative properties. Suitable for men "
            "dealing with low libido, premature ejaculation (PE), erectile dysfunction "
            "(ED), or general sexual weakness. Kaama Gold is the ideal choice for men "
            "looking to naturally rejuvenate their sexual health and performance."
        ),
        "extra_synonyms": [
            "Kaama Gold",
            "kaama gold",
            "kama gold",
            "kaama gold capsule",
            "kama gold medicine",
            "kamagold",
            "libido booster capsule",
            "sex power capsule gold",
            "ayurvedic sex capsule",
            "premature ejaculation capsule",
            "erection strength capsule",
        ],
        "used_for": (
            "Low libido, premature ejaculation (PE), erectile dysfunction (ED), "
            "general sexual weakness, low stamina in men"
        ),
        "dosage": "1 capsule twice daily with water or milk",
    },
]


async def main() -> None:
    weaviate = WeaviateClient(
        url=settings.weaviate_url,
        api_key=settings.weaviate_api_key,
    )
    async with AsyncSessionLocal() as db:
        config_repo = CompanyConfigRepository(db)
        event_repo = ProductEventRepository(db)
        repo = ProductRepository(db)
        svc = ProductService(
            product_repo=repo,
            event_repo=event_repo,
            config_repo=config_repo,
            weaviate_client=weaviate,
        )

        for patch in PATCHES:
            sku = patch["sku"]
            products = await repo.list_by_company(COMPANY_ID, is_active=True, limit=500)
            target = next(
                (p for p in products if (p.sku or "").strip() == sku or (p.name or "").strip() == patch["name"]),
                None,
            )
            if target is None:
                logger.warning("Product not found: %s (%s)", patch["name"], sku)
                continue

            existing_synonyms = target.synonyms_json or []
            merged = list(dict.fromkeys(existing_synonyms + patch["extra_synonyms"]))

            existing_attrs = target.attributes_json or {}
            existing_attrs["used_for"] = patch["used_for"]
            existing_attrs["dosage"] = patch["dosage"]

            update = ProductUpdate(
                description=patch["description"],
                synonyms_json=merged,
                attributes_json=existing_attrs,
            )
            await svc.update_product(
                product_id=target.id,
                company_id=COMPANY_ID,
                payload=update,
            )
            logger.info("Patched: %s (%s)", patch["name"], sku)

    await engine.dispose()
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
