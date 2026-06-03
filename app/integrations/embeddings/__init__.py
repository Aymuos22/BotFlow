"""Embedding backends for RAG (optional OpenAI)."""

from app.integrations.embeddings.client import (
    EmbeddingClientProtocol,
    FastEmbedClient,
    OpenAIEmbeddingClient,
    close_embedding_client,
    get_embedding_client,
)

__all__ = [
    "EmbeddingClientProtocol",
    "FastEmbedClient",
    "OpenAIEmbeddingClient",
    "close_embedding_client",
    "get_embedding_client",
]
