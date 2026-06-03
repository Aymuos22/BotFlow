import asyncio, os, sys
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres.iakbglkslkndohkxwest:MindoraXai%40220203@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres")
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

COMPANY_ID = "33eaf707-06f1-4e30-93d8-d8da71afaa92"

async def check():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with AsyncSession(engine) as db:
        result = await db.execute(text(
            "SELECT name, attributes_json FROM products "
            "WHERE company_id=:cid AND name ILIKE :q"
        ), {"cid": COMPANY_ID, "q": "%ayush%"})
        rows = result.fetchall()
        for row in rows:
            attrs = row.attributes_json or {}
            print(f"Product : {row.name}")
            print(f"image_url: {attrs.get('image_url', 'NOT SET')}")
            print()

asyncio.run(check())
