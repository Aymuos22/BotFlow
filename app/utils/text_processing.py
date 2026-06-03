"""
Text parsing and chunking utilities for the document indexing pipeline.

Parsers
-------
``parse_document(content, mime_type)`` → plain text string

Supported MIME types:
  - text/plain          – direct UTF-8 decode
  - text/csv            – direct UTF-8 decode (treat as text)
  - application/pdf     – extract text via pypdf (best-effort)
  - anything else       – try UTF-8 decode, warn if it fails

Chunker
-------
``chunk_text(text, chunk_size, overlap)`` → list of text strings

Sliding-window character-level chunking with configurable overlap.
Tries to honour paragraph boundaries where possible.
"""
import io
import logging
from typing import List

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Parsers
# --------------------------------------------------------------------------- #


def parse_document(content: bytes, mime_type: str) -> str:
    """
    Extract plain text from raw file bytes.

    Args:
        content:   Raw bytes from S3.
        mime_type: MIME type string (e.g. ``"text/plain"``).

    Returns:
        Extracted text.  May be empty if extraction fails.
    """
    mime = (mime_type or "").lower().split(";")[0].strip()

    if mime in ("text/plain", "text/csv", "text/markdown"):
        return _decode_text(content)

    if mime == "application/pdf":
        return _parse_pdf(content)

    # Best-effort fallback for unknown types
    logger.warning("Unknown MIME type %r – attempting UTF-8 decode", mime)
    return _decode_text(content)


def _decode_text(content: bytes) -> str:
    """Decode bytes to string, replacing any undecodable bytes."""
    return content.decode("utf-8", errors="replace")


def _parse_pdf(content: bytes) -> str:
    """
    Extract text from a PDF using pypdf.

    Returns an empty string and logs a warning if pypdf is not installed
    or if extraction fails, so the pipeline can fall back gracefully.
    """
    try:
        from pypdf import PdfReader  # type: ignore[import]
    except ImportError:  # pragma: no cover
        logger.warning("pypdf not installed – PDF text extraction unavailable")
        return ""

    try:
        reader = PdfReader(io.BytesIO(content))
        pages: List[str] = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            pages.append(extracted)
        return "\n".join(pages)
    except Exception as exc:  # pragma: no cover
        logger.warning("PDF parse failed: %s", exc)
        return ""


# --------------------------------------------------------------------------- #
# Chunker
# --------------------------------------------------------------------------- #


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> List[str]:
    """
    Split *text* into overlapping fixed-size chunks.

    Strategy:
      1. Try to split on double-newline paragraph boundaries first.
      2. If a paragraph fits within ``chunk_size``, accumulate it.
      3. When accumulated text exceeds ``chunk_size``, emit a chunk
         and slide forward by ``(chunk_size - overlap)`` characters.

    Args:
        text:       Input plain text.
        chunk_size: Maximum characters per chunk (default 1000).
        overlap:    Characters to re-include from the previous chunk
                    to preserve context (default 100).

    Returns:
        List of non-empty text chunks.
    """
    if not text or not text.strip():
        return []

    # Normalise whitespace while preserving paragraph breaks
    text = text.strip()

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Try to break at a paragraph boundary within the last 20 % of the window
        if end < text_len:
            search_from = start + int(chunk_size * 0.8)
            boundary = text.rfind("\n\n", search_from, end)
            if boundary != -1:
                end = boundary + 2  # include the double-newline

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Advance start; ensure we always make forward progress
        advance = max(1, chunk_size - overlap)
        start = start + advance

    return chunks
