"""
One-time setup: switch SK Group to Twilio WhatsApp provider.

Usage
-----
Set your Twilio WhatsApp number in the TWILIO_WHATSAPP_NUMBER variable
below, then run:

    python data/scripts/setup_skgroup_twilio.py

The script connects directly to the production database via DATABASE_URL
and updates the company_configs row for SK Group.

What it changes
---------------
- whatsapp_provider  → 'twilio'
- twilio_whatsapp_number → your Twilio number (e.g. whatsapp:+14155238886)

Stack note
----------
This project uses Twilio only for WhatsApp; credentials are stored per company
in ``company_configs`` (Account SID, Auth Token, sender number).
"""
import asyncio
import os
import uuid

import asyncpg

# ── Configure these ─────────────────────────────────────────────────────────

SKGROUP_ID = uuid.UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")

# Your Twilio WhatsApp sender number in whatsapp:+<E.164> format.
# Examples:
#   Sandbox:         whatsapp:+14155238886
#   Business number: whatsapp:+91XXXXXXXXXX
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "")

# ─────────────────────────────────────────────────────────────────────────────

raw = os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")


async def run() -> None:
    if not TWILIO_WHATSAPP_NUMBER:
        print(
            "ERROR: TWILIO_WHATSAPP_NUMBER is not set.\n"
            "Either set it as an environment variable or edit this script directly.\n"
            "Example: TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886 python data/scripts/setup_skgroup_twilio.py"
        )
        return

    if not raw:
        print("ERROR: DATABASE_URL environment variable is not set.")
        return

    number = TWILIO_WHATSAPP_NUMBER
    if not number.startswith("whatsapp:"):
        number = f"whatsapp:{number}"
    print(f"Connecting to database…")
    c = await asyncpg.connect(raw)

    # Check the migration has been applied
    col_exists = await c.fetchval(
        """
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name='company_configs' AND column_name='whatsapp_provider'
        """
    )
    if not col_exists:
        print(
            "ERROR: Column 'whatsapp_provider' not found in company_configs.\n"
            "Run the database migration first:\n\n"
            "    alembic upgrade head\n"
        )
        await c.close()
        return

    # Check SK Group exists
    row = await c.fetchrow(
        "SELECT company_id, whatsapp_provider, twilio_whatsapp_number "
        "FROM company_configs WHERE company_id = $1",
        SKGROUP_ID,
    )
    if not row:
        print(f"ERROR: No company_configs row found for SK Group (id={SKGROUP_ID}).")
        await c.close()
        return

    print(f"\nCurrent SK Group config:")
    print(f"  whatsapp_provider     : {row['whatsapp_provider']}")
    print(f"  twilio_whatsapp_number: {row['twilio_whatsapp_number']}")

    # Apply the Twilio switch
    await c.execute(
        "UPDATE company_configs "
        "SET whatsapp_provider = $2, twilio_whatsapp_number = $3 "
        "WHERE company_id = $1",
        SKGROUP_ID,
        "twilio",
        number,
    )
    print(f"\nUpdated SK Group:")
    print(f"  whatsapp_provider      → twilio")
    print(f"  twilio_whatsapp_number → {number}")

    # Verify
    updated = await c.fetchrow(
        "SELECT whatsapp_provider, twilio_whatsapp_number FROM company_configs WHERE company_id = $1",
        SKGROUP_ID,
    )
    print(f"\nVerified in database:")
    print(f"  whatsapp_provider     : {updated['whatsapp_provider']}")
    print(f"  twilio_whatsapp_number: {updated['twilio_whatsapp_number']}")

    await c.close()
    print("\nDone. SK Group is now configured to use Twilio.")
    print(
        "\nNext steps:"
        "\n  1. Ensure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER are set in .env"
        "\n  2. Restart the API server"
        "\n  3. Set Twilio webhook URL to: https://54.252.233.98.nip.io/api/v1/webhooks/twilio/messages"
        f"\n  4. Test by sending a WhatsApp message to {number}"
    )


asyncio.run(run())
