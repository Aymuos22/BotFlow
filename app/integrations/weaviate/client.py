"""
Weaviate integration client.

Chunk objects use ``vectorizer=none``; optional dense vectors are supplied at
upsert when embeddings are enabled (``RAG_EMBEDDINGS_ENABLED`` + API key).

Retrieval uses BM25-only GraphQL when no query vector is provided, and
Weaviate ``hybrid`` (BM25 + vector) when a query embedding is available.

``get_weaviate_client`` returns a process-wide singleton; call
``close_weaviate_client()`` on application shutdown to release the HTTP pool.
"""
import json
import logging
import uuid as uuid_lib
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.integrations.weaviate.schemas import (
    WeaviateCreateClassRequest,
    WeaviatePropertySchema,
)

logger = logging.getLogger(__name__)

_CHUNK_INDEX_PROPERTIES: List[WeaviatePropertySchema] = [
    WeaviatePropertySchema(name="document_id", dataType=["text"]),
    WeaviatePropertySchema(name="company_id", dataType=["text"]),
    WeaviatePropertySchema(name="chunk_index", dataType=["int"]),
    WeaviatePropertySchema(name="chunk_text", dataType=["text"]),
    WeaviatePropertySchema(name="file_name", dataType=["text"]),
    WeaviatePropertySchema(name="s3_key", dataType=["text"]),
    # Phase 4 – products: null for document chunks, UUID string for product chunks
    WeaviatePropertySchema(name="product_id", dataType=["text"]),
]

_CHUNK_PROPERTIES = [
    "document_id",
    "company_id",
    "chunk_index",
    "chunk_text",
    "file_name",
    "s3_key",
    "product_id",
]


def json_escape(value: str) -> str:
    """Return a JSON-encoded string literal (with quotes) safe for GraphQL embedding."""
    return json.dumps(value)


def _format_gql_float_array(vec: List[float]) -> str:
    return "[" + ",".join(f"{float(v):.8g}" for v in vec) + "]"


_weaviate_instance: Optional["WeaviateClient"] = None


class WeaviateClient:
    """
    Async HTTP client for the Weaviate REST + GraphQL APIs.

    Reuses one ``httpx.AsyncClient`` per instance for connection pooling.
    """

    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._http: Optional[httpx.AsyncClient] = None

    async def _http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.timeout)
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _raise_for_status(self, response: httpx.Response, operation: str) -> None:
        if response.is_error:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise ExternalServiceError(
                service="Weaviate",
                message=f"{operation} failed (HTTP {response.status_code}): {detail}",
            )

    async def _post_graphql(self, graphql_query: str) -> Dict[str, Any]:
        client = await self._http_client()
        response = await client.post(
            f"{self.url}/v1/graphql",
            json={"query": graphql_query},
            headers=self._headers(),
        )
        self._raise_for_status(response, "graphql")
        return response.json()

    async def create_collection(self, collection_name: str) -> bool:
        payload = WeaviateCreateClassRequest(
            class_name=collection_name,
            properties=list(_CHUNK_INDEX_PROPERTIES),
        )
        client = await self._http_client()
        response = await client.post(
            f"{self.url}/v1/schema",
            json=payload.to_weaviate_dict(),
            headers=self._headers(),
        )
        self._raise_for_status(response, "create_collection")
        logger.info(
            "Weaviate collection created",
            extra={"collection": collection_name},
        )
        return True

    async def ensure_indexing_collection(self, collection_name: str) -> bool:
        if await self.collection_exists(collection_name):
            await self._ensure_product_id_property(collection_name)
            return True
        return await self.create_collection(collection_name)

    async def _ensure_product_id_property(self, collection_name: str) -> None:
        """
        Add the ``product_id`` property to an existing collection that was
        created before Phase 4.  Safe to call on collections that already
        have the property (Weaviate returns 422; we swallow it).
        """
        client = await self._http_client()
        payload = {"name": "product_id", "dataType": ["text"]}
        response = await client.post(
            f"{self.url}/v1/schema/{collection_name}/properties",
            json=payload,
            headers=self._headers(),
        )
        if response.status_code in (200, 201):
            logger.info(
                "Added product_id property to collection",
                extra={"collection": collection_name},
            )
        elif response.status_code == 422:
            pass  # property already exists – expected for most collections
        else:
            logger.warning(
                "Unexpected status adding product_id property",
                extra={
                    "collection": collection_name,
                    "status": response.status_code,
                },
            )

    async def collection_exists(self, collection_name: str) -> bool:
        client = await self._http_client()
        response = await client.get(
            f"{self.url}/v1/schema/{collection_name}",
            headers=self._headers(),
        )
        if response.status_code == 404:
            return False
        self._raise_for_status(response, "collection_exists")
        return True

    async def delete_collection(self, collection_name: str) -> bool:
        client = await self._http_client()
        response = await client.delete(
            f"{self.url}/v1/schema/{collection_name}",
            headers=self._headers(),
        )
        self._raise_for_status(response, "delete_collection")
        logger.info(
            "Weaviate collection deleted",
            extra={"collection": collection_name},
        )
        return True

    async def upsert_document_chunks(
        self,
        collection_name: str,
        document_id: str,
        company_id: str,
        file_name: str,
        s3_key: str,
        chunks: List[str],
        vectors: Optional[List[List[float]]] = None,
    ) -> int:
        """
        Batch-insert text chunks. Optional ``vectors`` must align 1:1 with ``chunks``.
        """
        if not chunks:
            return 0
        if vectors is not None and len(vectors) != len(chunks):
            logger.warning(
                "Embedding count mismatch; storing chunks without vectors",
                extra={
                    "collection": collection_name,
                    "chunks": len(chunks),
                    "vectors": len(vectors),
                },
            )
            vectors = None

        objects: List[Dict[str, Any]] = []
        for i, chunk_text in enumerate(chunks):
            obj_id = str(
                uuid_lib.uuid5(
                    uuid_lib.NAMESPACE_URL,
                    f"{document_id}-chunk-{i}",
                )
            )
            obj: Dict[str, Any] = {
                "class": collection_name,
                "id": obj_id,
                "properties": {
                    "document_id": str(document_id),
                    "company_id": str(company_id),
                    "chunk_index": i,
                    "chunk_text": chunk_text,
                    "file_name": file_name,
                    "s3_key": s3_key,
                },
            }
            if vectors is not None and vectors[i]:
                obj["vector"] = vectors[i]
            objects.append(obj)

        client = await self._http_client()
        response = await client.post(
            f"{self.url}/v1/batch/objects",
            json={"objects": objects},
            headers=self._headers(),
        )
        self._raise_for_status(response, "upsert_document_chunks")

        result_count = len(objects)
        logger.info(
            "Weaviate upserted chunks",
            extra={
                "collection": collection_name,
                "chunk_count": result_count,
                "with_vectors": vectors is not None,
            },
        )
        return result_count

    def _parse_search_objects(
        self, objects: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        hits: List[Dict[str, Any]] = []
        scores: List[float] = []
        for obj in objects:
            raw_score = obj.get("_additional", {}).get("score")
            sf: Optional[float] = None
            if raw_score is not None:
                try:
                    sf = float(raw_score)
                except (TypeError, ValueError):
                    sf = None
            if sf is not None:
                scores.append(sf)
            hits.append(
                {
                    "chunk_text": obj.get("chunk_text", "") or "",
                    "document_id": obj.get("document_id"),
                    "chunk_index": obj.get("chunk_index"),
                    "file_name": obj.get("file_name", "") or "",
                    "product_id": obj.get("product_id") or None,
                    "score": sf,
                }
            )
        top_score: Optional[float] = scores[0] if scores else None
        chunks = [h["chunk_text"] for h in hits]
        return {
            "hits": hits,
            "scores": scores,
            "chunks": chunks,
            "top_score": top_score,
        }

    def _bm25_graphql(self, collection_name: str, query: str, top_k: int) -> str:
        return (
            "{ Get { "
            f'{collection_name}('
            f'  bm25: {{ query: {json_escape(query)}, properties: ["chunk_text"] }},'
            f"  limit: {top_k}"
            ") { "
            "  chunk_text document_id chunk_index file_name product_id "
            "  _additional { score } "
            "} } }"
        )

    def _hybrid_graphql(
        self,
        collection_name: str,
        query: str,
        top_k: int,
        query_vector: List[float],
        alpha: float,
    ) -> str:
        alpha_c = min(1.0, max(0.0, float(alpha)))
        vec_lit = _format_gql_float_array(query_vector)
        return (
            "{ Get { "
            f'{collection_name}('
            f"  hybrid: {{ query: {json_escape(query)}, alpha: {alpha_c}, "
            f"  vector: {vec_lit} }},"
            f"  limit: {top_k}"
            ") { "
            "  chunk_text document_id chunk_index file_name product_id "
            "  _additional { score } "
            "} } }"
        )

    async def hybrid_search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        *,
        query_vector: Optional[List[float]] = None,
        hybrid_alpha: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Keyword search (BM25), or hybrid BM25 + vector when ``query_vector`` is set.

        Returns ``chunks``, ``hits`` (with metadata), ``scores``, ``top_score``, ``raw``,
        and ``search_mode`` (``bm25`` | ``hybrid``).
        """
        use_hybrid = bool(query_vector)
        raw: Dict[str, Any]
        mode = "bm25"

        if use_hybrid:
            try:
                gql = self._hybrid_graphql(
                    collection_name, query, top_k, query_vector, hybrid_alpha
                )
                raw = await self._post_graphql(gql)
                if raw.get("errors"):
                    logger.warning(
                        "Weaviate hybrid query failed; falling back to BM25: %s",
                        raw.get("errors"),
                    )
                    use_hybrid = False
                else:
                    mode = "hybrid"
            except ExternalServiceError as exc:
                logger.warning(
                    "Weaviate hybrid HTTP error; falling back to BM25: %s", exc
                )
                use_hybrid = False
                raw = {}

        if not use_hybrid:
            gql = self._bm25_graphql(collection_name, query, top_k)
            try:
                raw = await self._post_graphql(gql)
            except ExternalServiceError as exc:
                logger.warning(
                    "Weaviate BM25 search failed; returning empty search result: %s",
                    exc,
                )
                raw = {}
            mode = "bm25"

        objects = (
            raw.get("data", {}).get("Get", {}).get(collection_name, []) or []
        )
        parsed = self._parse_search_objects(objects)
        parsed["raw"] = raw
        parsed["search_mode"] = mode
        return parsed

    async def delete_document_chunks(
        self,
        collection_name: str,
        document_id: str,
    ) -> bool:
        payload = {
            "match": {
                "class": collection_name,
                "where": {
                    "path": ["document_id"],
                    "operator": "Equal",
                    "valueText": str(document_id),
                },
            }
        }
        client = await self._http_client()
        response = await client.request(
            "DELETE",
            f"{self.url}/v1/batch/objects",
            json=payload,
            headers=self._headers(),
        )
        self._raise_for_status(response, "delete_document_chunks")
        logger.info(
            "Weaviate deleted document chunks",
            extra={"collection": collection_name, "document_id": document_id},
        )
        return True


def get_weaviate_client() -> WeaviateClient:
    """
    FastAPI dependency: singleton Weaviate client (connection reuse).

    Override via ``app.dependency_overrides[get_weaviate_client]`` in tests.
    """
    global _weaviate_instance
    if _weaviate_instance is None:
        _weaviate_instance = WeaviateClient(
            url=settings.weaviate_url,
            api_key=settings.weaviate_api_key,
            timeout=settings.weaviate_timeout_seconds,
        )
    return _weaviate_instance


async def close_weaviate_client() -> None:
    global _weaviate_instance
    if _weaviate_instance is not None:
        await _weaviate_instance.aclose()
        _weaviate_instance = None
