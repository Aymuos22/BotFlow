"""
Convert all WebP product images to JPEG (Meta WhatsApp Cloud API doesn't support WebP).
Updates the DB image_url to point to the new .jpeg files.
Run from repo root: python scripts/_convert_images_to_jpeg.py
"""
import asyncio, os, sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

COMPANY_ID = "33eaf707-06f1-4e30-93d8-d8da71afaa92"
STATIC_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "product-images" / COMPANY_ID

async def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        from dotenv import load_dotenv
        load_dotenv()
        db_url = os.environ["DATABASE_URL"]

    converted: list[tuple[str, str]] = []

    for img_path in STATIC_DIR.iterdir():
        if img_path.suffix.lower() in (".webp",):
            jpeg_path = img_path.with_suffix(".jpeg")
            print(f"Converting: {img_path.name} -> {jpeg_path.name}")
            with Image.open(img_path) as img:
                rgb = img.convert("RGB")
                rgb.save(jpeg_path, "JPEG", quality=90)
            converted.append((img_path.name, jpeg_path.name))

    if not converted:
        print("No WebP files found.")
        return

    engine = create_async_engine(db_url)
    async with AsyncSession(engine) as db:
        result = await db.execute(
            text("SELECT id, name, attributes_json FROM products WHERE company_id=:cid"),
            {"cid": COMPANY_ID},
        )
        rows = result.fetchall()
        updates = 0
        for row in rows:
            attrs = dict(row.attributes_json or {})
            url = attrs.get("image_url", "")
            if not url:
                continue
            for (old_name, new_name) in converted:
                old_encoded = old_name.replace(" ", "%20")
                new_encoded = new_name.replace(" ", "%20")
                if old_encoded in url:
                    new_url = url.replace(old_encoded, new_encoded)
                    attrs["image_url"] = new_url
                    await db.execute(
                        text("UPDATE products SET attributes_json=cast(:attrs as jsonb) WHERE id=:id"),
                        {"attrs": json.dumps(attrs), "id": row.id},
                    )
                    print(f"  Updated DB: {row.name}")
                    print(f"    old: {url}")
                    print(f"    new: {new_url}")
                    updates += 1
        await db.commit()
        print(f"\nConverted {len(converted)} images, updated {updates} DB records.")

asyncio.run(main())
