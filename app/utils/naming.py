"""
Deterministic and safe name generators for external integrations.

All generated names are derived solely from the company UUID so that:
  1. Names are idempotent – re-running onboarding for the same company
     always produces the same names.
  2. Names never expose the raw company ``name`` string, avoiding issues
     with special characters, spaces, or unicode.
  3. Names are validated against the constraints of each target system.

Weaviate collection name rules:
  - Must start with an uppercase letter
  - Alphanumeric only (no hyphens or underscores)
  - Max 200 characters

Channel key (company_channels.session_name) for Twilio:
  - Lowercase alphanumeric + hyphens; deterministic from company_id
"""
import re
import uuid


def generate_weaviate_collection_name(company_id: str | uuid.UUID) -> str:
    """
    Generate a safe, deterministic Weaviate collection name.

    Strategy: ``Co`` prefix + UUID hex (no hyphens), upper-cased.
    Example: ``Co550E8400E29B41D4A716446655440000`` (34 chars)

    Args:
        company_id: The company's UUID (str or uuid.UUID).

    Returns:
        A valid Weaviate collection name starting with a capital letter.
    """
    uid_hex = str(company_id).replace("-", "").upper()
    return f"Co{uid_hex}"


def generate_twilio_channel_key(company_id: str | uuid.UUID) -> str:
    """
    Deterministic channel identifier for ``company_channels.session_name`` (Twilio).

    Strategy: ``twilio-`` prefix + first 20 hex chars of UUID, lower-cased.
    """
    uid_hex = str(company_id).replace("-", "").lower()[:20]
    return f"twilio-{uid_hex}"


def rotate_twilio_channel_key(company_id: str | uuid.UUID, *, suffix: str) -> str:
    """New channel key when the primary WhatsApp number changes."""
    base = generate_twilio_channel_key(company_id)
    safe = re.sub(r"[^a-z0-9]", "", (suffix or "").lower())[:8]
    safe = safe or "r1"
    return f"{base}-{safe}"

def is_valid_weaviate_collection_name(name: str) -> bool:
    """
    Return True if ``name`` conforms to Weaviate collection naming rules.

    Rules:
      - Non-empty
      - Starts with a capital letter [A-Z]
      - Contains only alphanumeric characters [A-Za-z0-9]
      - Length between 2 and 200
    """
    if not name or len(name) < 2 or len(name) > 200:
        return False
    return bool(re.match(r'^[A-Z][A-Za-z0-9]+$', name))


def sanitize_to_slug(text: str) -> str:
    """
    Convert arbitrary text to a URL-safe lowercase slug.

    Useful for display purposes; NOT used for integration identifiers
    (use the UUID-based generators above for those).

    Example: ``"Acme Corp (India)"`` → ``"acme-corp-india"``
    """
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)        # remove non-word chars except spaces/hyphens
    slug = re.sub(r'[\s_]+', '-', slug)           # spaces/underscores → hyphens
    slug = re.sub(r'-{2,}', '-', slug)            # collapse multiple hyphens
    slug = slug.strip('-')
    return slug
