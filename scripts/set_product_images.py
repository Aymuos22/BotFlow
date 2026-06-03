#!/usr/bin/env python3
"""
set_product_images.py — Populate attributes_json.image_url for products
that have a matching image file in app/static/product-images/<company_id>/.

The URL written to the DB is:
    {PUBLIC_BASE_URL}/static/product-images/{company_id}/{filename}

WhatsApp will fetch the image from that URL when the bot recommends a product.

Usage (from repo root):
    python scripts/set_product_images.py
    python scripts/set_product_images.py --company-id 33eaf707-06f1-4e30-93d8-d8da71afaa92
    python scripts/set_product_images.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from uuid import UUID

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select, update                          # noqa: E402
from app.core.config import get_settings                      # noqa: E402
from app.core.database import AsyncSessionLocal, engine       # noqa: E402
from app.models.product import Product                        # noqa: E402

SKRANGE = UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")


def _slug(text: str) -> str:
    """Lower-case, collapse whitespace/punctuation to a single space."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _match_score(product_name: str, filename_stem: str) -> int:
    """
    Returns how many words from the filename appear in the product name.
    Higher = better match.
    """
    p_words = set(_slug(product_name).split())
    f_words = set(_slug(filename_stem).split())
    # Ignore very common filler tokens
    ignore = {"1", "2", "3", "kit", "the"}
    p_words -= ignore
    f_words -= ignore
    return len(p_words & f_words)


async def run(company_id: UUID, dry_run: bool) -> None:
    s = get_settings()
    base_url = s.public_base_url.rstrip("/")

    images_dir = _ROOT / "app" / "static" / "product-images" / str(company_id)
    if not images_dir.exists():
        print(f"[ERROR] Images directory not found: {images_dir}")
        sys.exit(1)

    image_files = list(images_dir.iterdir())
    if not image_files:
        print(f"[WARN] No image files found in {images_dir}")
        return

    print(f"Found {len(image_files)} image file(s) in {images_dir}")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Product).where(Product.company_id == company_id)
        )
        products: list[Product] = result.scalars().all()

    print(f"Found {len(products)} products for company {company_id}")

    updated: list[tuple[str, str, str]] = []   # (product_name, filename, url)
    unmatched_files: list[str] = []

    for img_file in sorted(image_files):
        stem = img_file.stem          # e.g. "ayush for men"
        best_prod: Product | None = None
        best_score = 0

        for prod in products:
            score = _match_score(prod.name or "", stem)
            if score > best_score:
                best_score = score
                best_prod = prod

        if best_score == 0 or best_prod is None:
            unmatched_files.append(img_file.name)
            print(f"  [SKIP] {img_file.name!r} — no matching product found")
            continue

        # Build the public image URL (URL-encode spaces as %20)
        encoded_name = img_file.name.replace(" ", "%20")
        image_url = (
            f"{base_url}/static/product-images/{company_id}/{encoded_name}"
        )
        print(
            f"  [MATCH] {img_file.name!r} -> {best_prod.name!r} "
            f"(score={best_score})"
        )
        print(f"          URL: {image_url}")
        updated.append((best_prod.name, img_file.name, image_url))

        if not dry_run:
            async with AsyncSessionLocal() as db:
                existing_attrs: dict = best_prod.attributes_json or {}
                new_attrs = {**existing_attrs, "image_url": image_url}
                await db.execute(
                    update(Product)
                    .where(Product.id == best_prod.id)
                    .values(attributes_json=new_attrs)
                )
                await db.commit()

    print()
    print(f"{'[DRY RUN] Would update' if dry_run else 'Updated'} {len(updated)} product(s):")
    for name, fname, url in updated:
        print(f"  • {name}")
        print(f"    image: {fname}")
        print(f"    url:   {url}")

    if unmatched_files:
        print(f"\nUnmatched image files ({len(unmatched_files)}):")
        for f in unmatched_files:
            print(f"  ✗ {f}")

    await engine.dispose()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--company-id", default=str(SKRANGE))
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches without writing to the database.",
    )
    args = p.parse_args()
    asyncio.run(run(UUID(args.company_id), args.dry_run))


if __name__ == "__main__":
    main()
