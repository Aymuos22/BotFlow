#!/usr/bin/env python3
"""
Load every supported file under ./data (or --data-dir) into Weaviate.

Paths under ``<data-dir>/scripts/`` are skipped (operational helpers, not RAG content).

Uses the same chunking and parsing helpers as the production indexer.
Chunks are tagged with your company_id so RAG and the WhatsApp/portal flows
can retrieve them.

Configuration (pick one way to choose the Weaviate collection + company_id):

  A) Database + tenant: set DATABASE_URL and LOCAL_INGEST_COMPANY_ID in .env
     (or pass --company-id). Collection name is read from company_config.

  B) Explicit: set LOCAL_WEAVIATE_COLLECTION and LOCAL_INGEST_COMPANY_ID
     (or pass --collection and --company-id).

Requires WEAVIATE_URL (and WEAVIATE_API_KEY if your instance uses one).

Usage (from repo root):

  python scripts/ingest_local_data.py
  python scripts/ingest_local_data.py --data-dir ./data --company-id <uuid>
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import mimetypes
import sys
from pathlib import Path
from typing import Optional, Tuple
from uuid import NAMESPACE_URL, UUID, uuid5

# Repo root on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.integrations.embeddings.client import get_embedding_client  # noqa: E402
from app.integrations.weaviate.client import WeaviateClient  # noqa: E402
from app.models.company_config import CompanyConfig  # noqa: E402
from app.utils.text_processing import chunk_text, parse_document  # noqa: E402

logger = logging.getLogger("ingest_local_data")

_READABLE_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".pdf",
    ".json",
}


def _mime_for_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    return {
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".pdf": "application/pdf",
        ".json": "application/json",
    }.get(path.suffix.lower(), "text/plain")


def _iter_files(data_dir: Path) -> list[Path]:
    if not data_dir.is_dir():
        return []
    data_root = data_dir.resolve()
    out: list[Path] = []
    for p in sorted(data_dir.rglob("*")):
        if not p.is_file():
            continue
        if p.name.startswith(".") or "__pycache__" in p.parts:
            continue
        try:
            rel = p.resolve().relative_to(data_root)
        except ValueError:
            continue
        # Operational helpers under data/scripts/ must not be indexed as RAG.
        if rel.parts and rel.parts[0] == "scripts":
            continue
        if p.suffix.lower() in _READABLE_SUFFIXES:
            out.append(p)
    return out


async def _resolve_collection_and_company(
    company_id_arg: Optional[str],
    collection_arg: Optional[str],
) -> Tuple[str, str]:
    """
    Returns (weaviate_collection_name, company_id_str).
    """
    cid_raw = company_id_arg or settings.local_ingest_company_id
    coll_raw = collection_arg or settings.local_weaviate_collection

    if coll_raw and cid_raw:
        return coll_raw.strip(), str(UUID(cid_raw.strip()))

    if cid_raw and not coll_raw:
        company_id = UUID(cid_raw.strip())
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(CompanyConfig).where(CompanyConfig.company_id == company_id)
            )
            row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(
                f"No company_config row for company_id={company_id}. "
                "Onboard the company first or set LOCAL_WEAVIATE_COLLECTION."
            )
        return row.weaviate_collection, str(company_id)

    raise ValueError(
        "Set LOCAL_INGEST_COMPANY_ID (and optionally LOCAL_WEAVIATE_COLLECTION) in .env, "
        "or pass --company-id / --collection. See the script docstring."
    )


async def _ingest_one(
    weaviate: WeaviateClient,
    collection: str,
    company_id: str,
    file_path: Path,
    data_root: Path,
    chunk_size: int,
    chunk_overlap: int,
) -> int:
    rel = file_path.resolve().relative_to(data_root.resolve())
    rel_posix = rel.as_posix()
    document_id = str(uuid5(NAMESPACE_URL, f"local-ingest:{rel_posix}"))
    mime = _mime_for_path(file_path)
    raw = file_path.read_bytes()
    text = parse_document(raw, mime)
    chunks = chunk_text(text, chunk_size, chunk_overlap)
    if not chunks:
        logger.warning("Skipping empty extract: %s", rel_posix)
        return 0

    await weaviate.delete_document_chunks(collection, document_id)
    vectors = None
    emb = get_embedding_client()
    if emb is not None:
        try:
            vectors = await emb.embed_documents(chunks)
            if len(vectors) != len(chunks) or any(not v for v in vectors):
                vectors = None
        except Exception as exc:
            logger.warning("Embedding skipped for %s: %s", rel_posix, exc)
            vectors = None
    n = await weaviate.upsert_document_chunks(
        collection_name=collection,
        document_id=document_id,
        company_id=company_id,
        file_name=file_path.name,
        s3_key=f"local://{rel_posix}",
        chunks=chunks,
        vectors=vectors,
    )
    logger.info("Ingested %s (%d chunks)", rel_posix, n)
    return n


async def _async_main(args: argparse.Namespace) -> int:
    try:
        try:
            collection, company_id = await _resolve_collection_and_company(
                args.company_id,
                args.collection,
            )
        except ValueError as exc:
            logger.error("%s", exc)
            return 1

        data_dir = Path(args.data_dir).resolve()
        files = _iter_files(data_dir)
        if not files:
            logger.warning("No ingestible files under %s", data_dir)
            return 0

        weaviate = WeaviateClient(
            url=settings.weaviate_url,
            api_key=settings.weaviate_api_key,
            timeout=settings.weaviate_timeout_seconds,
        )
        try:
            await weaviate.ensure_indexing_collection(collection)

            total_chunks = 0
            for fp in files:
                total_chunks += await _ingest_one(
                    weaviate,
                    collection,
                    company_id,
                    fp,
                    data_dir,
                    args.chunk_size,
                    args.chunk_overlap,
                )

            logger.info(
                "Done: %d files, %d chunks → collection %r",
                len(files),
                total_chunks,
                collection,
            )
            return 0
        finally:
            await weaviate.aclose()
    finally:
        # Close DB pool before the event loop stops (avoids Windows SSL noise
        # after asyncio.run() when Postgres was used for company_config lookup).
        await engine.dispose()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(description="Ingest ./data into Weaviate (local dev).")
    p.add_argument(
        "--data-dir",
        default=str(_ROOT / "data"),
        help="Directory of files to index (default: ./data)",
    )
    p.add_argument(
        "--company-id",
        default=None,
        help="Company UUID (overrides LOCAL_INGEST_COMPANY_ID)",
    )
    p.add_argument(
        "--collection",
        default=None,
        help="Weaviate class name (overrides DB / LOCAL_WEAVIATE_COLLECTION)",
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=settings.chunk_size,
        help=f"Chunk size (default from CHUNK_SIZE env, {settings.chunk_size})",
    )
    p.add_argument(
        "--chunk-overlap",
        type=int,
        default=settings.chunk_overlap,
        help=f"Overlap (default from CHUNK_OVERLAP env, {settings.chunk_overlap})",
    )
    args = p.parse_args()
    raise SystemExit(asyncio.run(_async_main(args)))


if __name__ == "__main__":
    main()
