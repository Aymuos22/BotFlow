"""
Deterministic and tenant-safe S3 key generation.

Key strategy:
    companies/{company_id}/documents/{document_id}/{sanitized_filename}

Rules:
  - company_id and document_id are UUIDs → no injection risk
  - filename is sanitized (lowercase, safe chars only)
  - never use raw user input directly in key paths
"""
import re
import uuid


def sanitize_filename(filename: str) -> str:
    """
    Convert an arbitrary filename to a safe S3-compatible string.

    - Lowercases the name
    - Replaces spaces with underscores
    - Removes any character that is not alphanumeric, hyphen, underscore, or dot

    Examples:
        ``"My Document (2024).pdf"`` → ``"my_document_2024.pdf"``
        ``"../../../etc/passwd"``    → ``"etcpasswd"``
    """
    name = filename.strip().lower()
    name = name.replace(" ", "_")
    name = re.sub(r"[^\w.\-]", "", name)  # keep word chars, dots, hyphens
    name = re.sub(r"\.{2,}", ".", name)   # collapse multiple dots
    name = name.strip("._-")             # strip leading/trailing punctuation
    return name or "file"


def build_document_s3_key(
    company_id: str | uuid.UUID,
    document_id: str | uuid.UUID,
    filename: str,
) -> str:
    """
    Build the canonical S3 key for a company document.

    Format:
        ``companies/{company_id}/documents/{document_id}/{safe_filename}``

    Args:
        company_id:  The owning company's UUID.
        document_id: The document's UUID.
        filename:    Original uploaded filename (will be sanitized).

    Returns:
        A slash-separated S3 object key string.

    Example:
        ``companies/abc-123/documents/def-456/my_report.pdf``
    """
    safe_name = sanitize_filename(filename)
    return f"companies/{company_id}/documents/{document_id}/{safe_name}"
