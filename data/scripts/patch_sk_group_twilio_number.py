"""One-off: set SK Group company Twilio WhatsApp sender (DB update). Run inside API container."""
import asyncio
import uuid

from app.core.database import AsyncSessionLocal
from app.repositories.company_config_repository import CompanyConfigRepository

COMPANY_ID = uuid.UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")
NEW_SENDER = "whatsapp:+15559331743"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        repo = CompanyConfigRepository(db)
        cfg = await repo.get_by_company(COMPANY_ID)
        if not cfg:
            raise SystemExit("CompanyConfig not found")
        before = cfg.twilio_whatsapp_number
        cfg.twilio_whatsapp_number = NEW_SENDER
        await db.commit()
        print(f"OK: twilio_whatsapp_number {before!r} -> {cfg.twilio_whatsapp_number!r}")


if __name__ == "__main__":
    asyncio.run(main())
