"""
Text embeddings for Weaviate hybrid search.

Disabled unless ``RAG_EMBEDDINGS_ENABLED=true``. Supported providers:
``voyage`` (VoyageAI – recommended, requires ``VOYAGE_API_KEY``) and
``openai`` (requires ``EMBEDDING_API_KEY`` or ``OPENAI_API_KEY``).
When disabled, retrieval stays BM25-only and existing collections without
vectors continue to work.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


def _plain_vector(vec: object) -> List[float]:
    return [float(x) for x in vec]  # type: ignore[union-attr]


@runtime_checkable
class EmbeddingClientProtocol(Protocol):
    async def embed_query(self, text: str) -> List[float]:
        ...

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        ...


class OpenAIEmbeddingClient:
    """Async OpenAI embeddings with simple batching."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        *,
        batch_size: int = 64,
        timeout: float = 60.0,
    ) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._model = model
        self._batch_size = max(1, batch_size)

    async def embed_query(self, text: str) -> List[float]:
        vecs = await self.embed_documents([text])
        return vecs[0] if vecs else []

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        out: List[List[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            resp = await self._client.embeddings.create(
                model=self._model,
                input=batch,
            )
            # Preserve input order
            data = sorted(resp.data, key=lambda d: d.index)
            for row in data:
                if row.embedding:
                    out.append(list(row.embedding))
                else:
                    out.append([])
        return out


class VoyageEmbeddingClient:
    """VoyageAI cloud embeddings (async)."""

    def __init__(
        self,
        api_key: str,
        model: str = "voyage-3",
        *,
        batch_size: int = 128,
    ) -> None:
        import voyageai

        self._client = voyageai.AsyncClient(api_key=api_key)
        self._model = model
        self._batch_size = max(1, batch_size)

    async def embed_query(self, text: str) -> List[float]:
        import voyageai

        result = await self._client.embed([text], model=self._model, input_type="query")
        vecs: List[List[float]] = result.embeddings
        return vecs[0] if vecs else []

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        out: List[List[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            result = await self._client.embed(
                batch, model=self._model, input_type="document"
            )
            out.extend(result.embeddings)
        return out


_embedding_instance: Optional[EmbeddingClientProtocol] = None


def get_embedding_client() -> Optional[EmbeddingClientProtocol]:
    """
    Singleton embedding client when RAG embeddings are enabled and a key exists.
    """
    global _embedding_instance
    from app.core.config import get_settings

    s = get_settings()
    if not s.rag_embeddings_enabled:
        return None
    if _embedding_instance is None:
        provider = (s.embedding_provider or "voyage").strip().lower()
        if provider == "voyage":
            key = (s.voyage_api_key or s.embedding_api_key or "").strip()
            if not key:
                logger.warning(
                    "RAG_EMBEDDINGS_ENABLED with voyage provider but no "
                    "VOYAGE_API_KEY / EMBEDDING_API_KEY; skipping embeddings."
                )
                return None
            _embedding_instance = VoyageEmbeddingClient(
                api_key=key,
                model=s.embedding_model or "voyage-3",
                batch_size=s.embedding_batch_size,
            )
        elif provider == "openai":
            key = (s.embedding_api_key or s.openai_api_key or "").strip()
            if not key:
                logger.warning(
                    "RAG_EMBEDDINGS_ENABLED with openai provider but no "
                    "EMBEDDING_API_KEY / OPENAI_API_KEY; skipping embeddings."
                )
                return None
            _embedding_instance = OpenAIEmbeddingClient(
                api_key=key,
                model=s.embedding_model,
                batch_size=s.embedding_batch_size,
            )
        else:
            logger.warning("Unknown embedding provider %r; skipping embeddings.", provider)
            return None
    return _embedding_instance


async def close_embedding_client() -> None:
    global _embedding_instance
    if isinstance(_embedding_instance, OpenAIEmbeddingClient):
        await _embedding_instance._client.close()
    _embedding_instance = None
