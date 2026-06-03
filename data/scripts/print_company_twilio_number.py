import asyncio
import uuid

from app.core.database import AsyncSessionLocal
from app.repositories.company_config_repository import CompanyConfigRepository

CID = uuid.UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        cfg = await CompanyConfigRepository(db).get_by_company(CID)
        if not cfg:
            print("NO_CONFIG")
            return
        print("twilio_whatsapp_number=", cfg.twilio_whatsapp_number)


if __name__ == "__main__":
    asyncio.run(main())
