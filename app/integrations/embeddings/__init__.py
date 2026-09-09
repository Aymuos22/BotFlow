"""Embedding backends for RAG — VoyageAI (default) or OpenAI."""

from app.integrations.embeddings.client import (
    EmbeddingClientProtocol,
    OpenAIEmbeddingClient,
    VoyageEmbeddingClient,
    close_embedding_client,
    get_embedding_client,
)

__all__ = [
    "EmbeddingClientProtocol",
    "OpenAIEmbeddingClient",
    "VoyageEmbeddingClient",
    "close_embedding_client",
    "get_embedding_client",
]
