import asyncio, os, sys
sys.path.insert(0, "/app")
os.chdir("/app")
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    db_url = os.environ["DATABASE_URL"]
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.execute(text("""
            UPDATE company_configs
            SET whatsapp_provider = 'twilio',
                twilio_whatsapp_number = 'whatsapp:+14155238886'
            WHERE company_id = '33eaf707-06f1-4e30-93d8-d8da71afaa92'
        """))
        row = await conn.execute(text(
            "SELECT company_id, whatsapp_provider, twilio_whatsapp_number "
            "FROM company_configs WHERE company_id='33eaf707-06f1-4e30-93d8-d8da71afaa92'"
        ))
        print(row.fetchone())
    await engine.dispose()

asyncio.run(main())
