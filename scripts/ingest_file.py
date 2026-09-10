#!/usr/bin/env python3
"""
Ingest a single file into Weaviate for a specific company.

Usage:
    python scripts/ingest_file.py --file path/to/file.pdf --company-id <uuid>

Example:
    python scripts/ingest_file.py \
        --file "C:/Users/lenovo/Downloads/resume_soumya_darshan_sukla.pdf" \
        --company-id b271173d-3270-49ae-a8b4-979c80d1b431
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import mimetypes
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Load .env then swap transaction pooler → session pooler for CLI scripts.
import os as _os
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass
_db_url = _os.environ.get("DATABASE_URL", "")
if ":6543/" in _db_url:
    _os.environ["DATABASE_URL"] = _db_url.replace(":6543/", ":5432/")

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.integrations.embeddings.client import get_embedding_client  # noqa: E402
from app.integrations.weaviate.client import WeaviateClient  # noqa: E402
from app.models.company_config import CompanyConfig  # noqa: E402
from app.utils.text_processing import chunk_text, parse_document  # noqa: E402

logger = logging.getLogger("ingest_file")


def _mime_for_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    return {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".pdf": "application/pdf",
        ".json": "application/json",
    }.get(path.suffix.lower(), "text/plain")


async def _resolve_collection(company_id: UUID) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CompanyConfig).where(CompanyConfig.company_id == company_id)
        )
        row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(
            f"No company_config row found for company_id={company_id}. "
            "Onboard the company first."
        )
    return row.weaviate_collection


async def _ingest(file_path: Path, company_id: UUID, chunk_size: int, chunk_overlap: int) -> int:
    collection = await _resolve_collection(company_id)
    logger.info("Weaviate collection: %s", collection)

    mime = _mime_for_path(file_path)
    raw = file_path.read_bytes()
    logger.info("Parsing %s (%s, %.1f KB) ...", file_path.name, mime, len(raw) / 1024)

    text = parse_document(raw, mime)
    if not text or not text.strip():
        logger.error("No text extracted from %s", file_path.name)
        return 1

    chunks = chunk_text(text, chunk_size, chunk_overlap)
    logger.info("Split into %d chunks (size=%d, overlap=%d)", len(chunks), chunk_size, chunk_overlap)

    document_id = str(uuid5(NAMESPACE_URL, f"local-ingest:{file_path.name}"))

    weaviate = WeaviateClient(
        url=settings.weaviate_url,
        api_key=settings.weaviate_api_key,
        timeout=settings.weaviate_timeout_seconds,
    )

    try:
        await weaviate.ensure_indexing_collection(collection)
        await weaviate.delete_document_chunks(collection, document_id)
        logger.info("Deleted any existing chunks for document_id=%s", document_id)

        vectors = None
        emb = get_embedding_client()
        if emb is not None:
            logger.info("Computing embeddings via %s ...", settings.embedding_provider)
            try:
                vectors = await emb.embed_documents(chunks)
                if len(vectors) != len(chunks) or any(not v for v in vectors):
                    logger.warning("Embedding result mismatch; storing without vectors.")
                    vectors = None
                else:
                    logger.info("Embeddings computed for %d chunks.", len(vectors))
            except Exception as exc:
                logger.warning("Embedding failed (%s); storing without vectors.", exc)
                vectors = None
        else:
            logger.info("Embeddings disabled (RAG_EMBEDDINGS_ENABLED=false); using Weaviate vectorizer.")

        n = await weaviate.upsert_document_chunks(
            collection_name=collection,
            document_id=document_id,
            company_id=str(company_id),
            file_name=file_path.name,
            s3_key=f"local://{file_path.name}",
            chunks=chunks,
            vectors=vectors,
        )
        logger.info("✅  Ingested %d chunks from '%s' → collection '%s'", n, file_path.name, collection)
        return 0
    finally:
        await weaviate.aclose()


async def _async_main(args: argparse.Namespace) -> int:
    try:
        file_path = Path(args.file).expanduser().resolve()
        if not file_path.exists():
            logger.error("File not found: %s", file_path)
            return 1

        company_id = UUID(args.company_id.strip())
        return await _ingest(
            file_path=file_path,
            company_id=company_id,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
    finally:
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Ingest a single file into Weaviate.")
    p.add_argument("--file", required=True, help="Path to the file to ingest (PDF, TXT, MD, CSV, JSON)")
    p.add_argument("--company-id", required=True, help="Company UUID (e.g. b271173d-...)")
    p.add_argument("--chunk-size", type=int, default=settings.chunk_size)
    p.add_argument("--chunk-overlap", type=int, default=settings.chunk_overlap)
    args = p.parse_args()
    raise SystemExit(asyncio.run(_async_main(args)))


if __name__ == "__main__":
    main()
