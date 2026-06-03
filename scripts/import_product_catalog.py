#!/usr/bin/env python3
"""
Bulk-import a product catalog JSON file into the DB and auto-index
each product into Weaviate so the RAG pipeline can search them.

JSON format expected:
    {
      "products": [
        {
          "product_id": "SKR-001",   <- used as sku
          "category": "...",
          "name": "...",
          "description": "..."
        },
        ...
      ]
    }

Usage:
    python scripts/import_product_catalog.py \
        --file data/skinrange_catalog.json \
        --company-id 33eaf707-06f1-4e30-93d8-d8da71afaa92

Options:
    --skip-existing   Skip products whose SKU already exists (default: update them)
    --dry-run         Print what would be done without writing anything
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from uuid import UUID

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.integrations.weaviate.client import WeaviateClient  # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402
from app.repositories.product_event_repository import ProductEventRepository  # noqa: E402
from app.repositories.product_repository import ProductRepository  # noqa: E402
from app.schemas.product import ProductCreate, ProductUpdate  # noqa: E402
from app.services.product_service import ProductService  # noqa: E402

logger = logging.getLogger("import_product_catalog")

SKINRANGE_SYNONYMS_BY_SKU: dict[str, list[str]] = {
    "SKR-001": [
        "sharab chorne ki dawa",
        "sharab ki adat kaise chhode",
        "alcohol chorne ka ayurvedic ilaj",
        "daru chodne ki medicine",
        "nasha mukti dawa",
        "cigarette chorne ki dawa",
        "gutkha chodne ka ilaj",
        "smoking chodne ka tarika",
        "tambaku chorne ki medicine",
        "drinking habit kaise band kare",
        "sharab ki talab kaise kam kare",
        "nasha chhudane wali dawa",
        "daru chodne ka upay",
        "Mere husband bhut peete hai",
    ],
    "SKR-004": [
        "sugar ki dawa kaunsi best hai",
        "diabetes ka ayurvedic ilaj kya hai",
        "blood sugar kaise control kare",
        "sugar kam karne ki medicine",
        "diabetes ki herbal dawa",
        "sugar patient ko kaunsi dawa leni chahiye",
        "diabetes ko jad se kaise khatam kare",
        "bina insulin sugar kaise control kare",
        "high sugar ka desi ilaj",
        "diabetes ke liye best ayurvedic medicine",
    ],
    "SKR-006": [
        "hair fall rokne ka oil kaunsa best hai",
        "baal ugane ka ayurvedic oil",
        "ganjapan ka oil",
        "hair growth oil kaunsa use kare",
        "baal jhadne ki ayurvedic dawa",
        "adivasi hair oil original",
        "hair regrowth oil ayurvedic",
        "safed baal ka ayurvedic oil",
        "dandruff hatane ka herbal oil",
        "baal lambe ghane kaise kare",
        "hair fall control oil",
        "ayurvedic tel for hair growth",
        "weak hair roots ka ilaj",
        "scalp infection ka ayurvedic oil",
        "baal patle hone ka ilaj",
        "hair thickness kaise badhaye",
        "natural hair growth treatment",
        "baal tootne se kaise roke",
        "men hair fall solution",
        "women hair fall treatment",
        "damaged hair repair oil",
        "chemical free hair oil",
        "stress se hair fall ka ilaj",
        "ayurvedic hair care oil",
        "hair regrowth ka desi ilaj",
        "jhadte baalon ka solution",
    ],
    "SKR-008": [
        "body weakness ki ayurvedic dawa",
        "immunity badhane ki best medicine",
        "thakan dur karne ka ayurvedic dawa",
        "energy booster ayurvedic medicine",
        "sharir ki kamzori ka ilaj",
        "body me taqat kaise badhaye",
        "weakness ke liye dawa",
        "immunity booster capsule",
        "natural energy booster medicine",
    ],
    "SKR-012": [
        "PCOS ki dawa",
        "periods regular karne ki dawa",
        "hormonal imbalance ka treatment",
        "white discharge ki ayurvedic medicine",
        "irregular periods ka desi ilaj",
        "fertility badhane ki medicine",
        "PCOD ki herbal medicine",
    ],
    "SKR-019": [
        "pet saaf karne ki dawa kaunsi hai",
        "kabz ka ayurvedic dawa",
        "gas aur acidity ki medicine",
        "pet ki safai kaise kare",
        "bloating aur gas ka ilaj",
        "acidity turant kaise thik kare",
        "digestion improve karne ki dawa",
        "constipation ki herbal medicine",
        "gut health ke liye best ayurvedic dawa",
    ],
    "SKR-022": [
        "mardana takat kaise badhaye",
        "timing badhane ki dawa",
        "sex time kaise badhaye",
        "ling size kaise badhaye",
        "sex power badhane ki medicine",
        "stamina kaise badhaye",
        "sperm count kaise badhaye",
        "weak erection",
        "shaadi ke baad kamzori",
        "penis erection medicine",
        "weak erection treatment",
        "erection problem solution",
        "sex karte waqt dhilapan",
        "discharge jaldi ho jata hai",
        "intercourse timing medicine",
        "sex timing oil",
        "sex timing capsule",
        "mardana taqat oil",
        "penis enlargement oil",
        "size badhane ka ayurvedic tarika",
        "sperm quality improve kaise kare",
    ],
    "SKR-024": [
        "mardana takat kaise badhaye",
        "timing badhane ki dawa",
        "sex time kaise badhaye",
        "sex power badhane ki medicine",
        "stamina kaise badhaye",
        "sperm count kaise badhaye",
        "weak erection",
        "shaadi ke baad kamzori",
        "penis erection medicine",
        "weak erection treatment",
        "erection problem solution",
        "sex karte waqt dhilapan",
        "discharge jaldi ho jata hai",
        "intercourse timing medicine",
        "sex timing capsule",
        "mardana taqat oil",
        "sperm quality improve kaise kare",
    ],
    "SKR-027": [
        "mardana takat kaise badhaye",
        "timing badhane ki dawa",
        "sex time kaise badhaye",
        "sex power badhane ki medicine",
        "stamina kaise badhaye",
        "weak erection treatment",
        "erection problem solution",
        "sex karte waqt dhilapan",
        "intercourse timing medicine",
        "sex timing capsule",
        "mardana taqat oil",
    ],
    "SKR-031": [
        "fatty liver medicine",
        "liver detox kaise kare",
        "sharab se kharab liver ka ilaj",
        "liver weakness ki medicine",
        "liver ke liye best ayurvedic dawa",
        "liver swelling ka ayurvedic ilaj",
    ],
    "SKR-032": [
        "pet saaf karne ki dawa kaunsi hai",
        "kabz ka ayurvedic dawa",
        "gas aur acidity ki medicine",
        "pet ki safai kaise kare",
        "bloating aur gas ka ilaj",
        "acidity turant kaise thik kare",
        "digestion improve karne ki dawa",
        "constipation ki herbal medicine",
        "gut health ke liye best ayurvedic dawa",
    ],
    "SKR-035": [
        "mardana takat kaise badhaye",
        "timing badhane ki dawa",
        "sex time kaise badhaye",
        "sex power badhane ki medicine",
        "stamina kaise badhaye",
        "sperm count kaise badhaye",
        "weak erection",
        "shaadi ke baad kamzori",
        "penis erection medicine",
        "weak erection treatment",
        "erection problem solution",
        "sex karte waqt dhilapan",
        "discharge jaldi ho jata hai",
        "intercourse timing medicine",
        "sex timing capsule",
        "mardana taqat oil",
        "sperm quality improve kaise kare",
    ],
    "SKR-029": [
        "safed daag ka ayurvedic ilaj kya hai",
        "vitiligo ki best ayurvedic dawa",
        "safed daag kaise thik kare",
        "vitiligo ke liye herbal medicine",
        "safed daag failne se kaise roke",
        "vitiligo treatment without side effects",
        "leucoderma ki ayurvedic dawa",
        "white patches ka ayurvedic ilaj",
        "vitiligo ke liye best medicine",
        "safed daag ki herbal dawa",
        "body par white spots ka ilaj",
        "vitiligo me kaunsi dawa leni chahiye",
        "safed daag ki medicine online",
        "purane safed daag ka ilaj",
        "vitiligo ke liye natural treatment",
    ],
}


def _dedupe_text(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = " ".join(str(value or "").strip().split())
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _product_synonyms(raw: dict) -> list[str]:
    sku = str(raw.get("product_id") or "")
    values: list[str] = []
    values.extend(SKINRANGE_SYNONYMS_BY_SKU.get(sku, []))
    values.extend(str(item) for item in raw.get("synonyms", []) or [])
    values.extend(str(item) for item in raw.get("used_for", []) or [])
    if raw.get("slug"):
        values.append(str(raw["slug"]).replace("-", " "))
    if raw.get("name"):
        values.append(str(raw["name"]))
    return _dedupe_text(values)


def _price_json(raw: dict) -> dict | None:
    pricing = raw.get("pricing")
    if not isinstance(pricing, dict):
        return None
    price: dict = {
        "currency": "INR",
        "text": pricing.get("master_reference") or pricing.get("raw"),
    }
    if pricing.get("raw"):
        price["raw"] = pricing["raw"]
    amounts = pricing.get("extracted_amounts_inr")
    if amounts:
        price["extracted_amounts_inr"] = amounts
        first_amount = amounts[0].get("amount_inr") if isinstance(amounts[0], dict) else None
        if first_amount is not None:
            price["amount"] = first_amount
    return {k: v for k, v in price.items() if v is not None}


def _attributes_json(raw: dict, *, brand: str, global_offers: list[dict]) -> dict:
    keys = [
        "slug",
        "form_variant",
        "stock_status",
        "product_link",
        "used_for",
        "key_ingredients",
        "benefits",
        "dosage_schedule",
        "expected_timeline",
        "recommended_duration",
        "safety_notes",
        "available_packs",
        "variants",
        "source_file",
    ]
    attrs = {key: raw.get(key) for key in keys if raw.get(key) not in (None, "", [], {})}
    if brand:
        attrs["brand"] = brand
    if raw.get("product_link"):
        attrs["product_url"] = raw["product_link"]
    if global_offers:
        attrs["global_offers"] = global_offers
    return attrs


def _is_active_from_stock(raw: dict) -> bool:
    stock = str(raw.get("stock_status") or "").casefold()
    if "out of stock" in stock:
        return False
    return True


async def run(
    catalog_path: Path,
    company_id: UUID,
    skip_existing: bool,
    dry_run: bool,
) -> None:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    products_raw = data.get("products", [])
    brand = data.get("brand", "")
    global_offers = data.get("global_offers", []) or []
    logger.info(
        "Catalog: %s  brand=%r  products=%d  company=%s",
        catalog_path.name,
        brand,
        len(products_raw),
        company_id,
    )

    if dry_run:
        logger.info("[DRY RUN] Would import %d products.", len(products_raw))
        for p in products_raw:
            logger.info("  %s — %s (%s)", p.get("product_id"), p.get("name"), p.get("category"))
        return

    weaviate = WeaviateClient(
        url=settings.weaviate_url,
        api_key=settings.weaviate_api_key,
        timeout=settings.weaviate_timeout_seconds,
    )

    created = updated = skipped = failed = 0

    try:
        async with AsyncSessionLocal() as db:
            svc = ProductService(
                product_repo=ProductRepository(db),
                event_repo=ProductEventRepository(db),
                config_repo=CompanyConfigRepository(db),
                weaviate_client=weaviate,
            )

            for raw in products_raw:
                sku = raw.get("product_id") or None
                name = (raw.get("name") or "").strip()
                category = (raw.get("category") or "").strip() or None
                description = (raw.get("description") or "").strip() or None
                price_json = _price_json(raw)
                attributes_json = _attributes_json(
                    raw,
                    brand=brand,
                    global_offers=global_offers,
                )
                synonyms = _product_synonyms(raw)
                is_active = _is_active_from_stock(raw)

                if not name:
                    logger.warning("Skipping entry with no name: %s", raw)
                    skipped += 1
                    continue

                existing = None
                if sku:
                    existing = await svc._products.get_by_sku(company_id, sku)

                if existing:
                    if skip_existing:
                        logger.info("  SKIP  %s — %s", sku, name)
                        skipped += 1
                        continue
                    # Update
                    try:
                        await svc.update_product(
                            existing.id,
                            company_id,
                            ProductUpdate(
                                name=name,
                                sku=sku,
                                category=category,
                                description=description,
                                price_json=price_json,
                                attributes_json=attributes_json,
                                synonyms=synonyms,
                                is_active=is_active,
                            ),
                        )
                        logger.info("  UPDATE %s — %s  (indexed=%s)", sku, name,
                                    existing.weaviate_indexed)
                        updated += 1
                    except Exception as exc:
                        logger.error("  ERROR updating %s: %s", sku, exc)
                        failed += 1
                else:
                    # Create (auto-indexes into Weaviate)
                    try:
                        product = await svc.create_product(
                            company_id,
                            ProductCreate(
                                name=name,
                                sku=sku,
                                category=category,
                                description=description,
                                price_json=price_json,
                                attributes_json=attributes_json,
                                synonyms=synonyms,
                                is_active=is_active,
                            ),
                        )
                        status = "indexed" if product.weaviate_indexed else "NOT indexed (reindex later)"
                        logger.info("  CREATE %s — %s  [%s]", sku, name, status)
                        created += 1
                    except Exception as exc:
                        logger.error("  ERROR creating %s (%s): %s", sku, name, exc)
                        failed += 1

    finally:
        await weaviate.aclose()
        await engine.dispose()

    logger.info(
        "\nDone — created=%d  updated=%d  skipped=%d  failed=%d",
        created, updated, skipped, failed,
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s  %(message)s",
    )
    p = argparse.ArgumentParser(description="Bulk-import product catalog JSON → DB + Weaviate")
    p.add_argument("--file", required=True, help="Path to catalog JSON file")
    p.add_argument("--company-id", required=True, help="Target company UUID")
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip products whose SKU already exists (default: update them)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan without writing anything",
    )
    args = p.parse_args()
    asyncio.run(
        run(
            catalog_path=Path(args.file),
            company_id=UUID(args.company_id),
            skip_existing=args.skip_existing,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
