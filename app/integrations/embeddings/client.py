"""
Text embeddings for Weaviate hybrid search.

Disabled unless ``RAG_EMBEDDINGS_ENABLED=true``. Supported providers:
``openai`` (requires ``EMBEDDING_API_KEY`` or ``OPENAI_API_KEY``) and
``fastembed`` (local ONNX model). When disabled, retrieval stays BM25-only and
existing collections without vectors continue to work.
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


class FastEmbedClient:
    """Local ONNX embeddings through Qdrant FastEmbed."""

    def __init__(
        self,
        model: str = "BAAI/bge-small-en-v1.5",
        *,
        batch_size: int = 64,
        cache_dir: str | None = None,
    ) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(
            model_name=model,
            batch_size=max(1, batch_size),
            cache_dir=cache_dir,
        )

    async def embed_query(self, text: str) -> List[float]:
        import asyncio

        vecs = await asyncio.to_thread(
            lambda: [_plain_vector(v) for v in self._model.query_embed([text])]
        )
        return vecs[0] if vecs else []

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        import asyncio

        if not texts:
            return []
        return await asyncio.to_thread(
            lambda: [_plain_vector(v) for v in self._model.passage_embed(texts)]
        )


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
        provider = (s.embedding_provider or "openai").strip().lower()
        if provider == "fastembed":
            _embedding_instance = FastEmbedClient(
                model=s.embedding_model or "BAAI/bge-small-en-v1.5",
                batch_size=s.embedding_batch_size,
                cache_dir=s.embedding_cache_dir,
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
