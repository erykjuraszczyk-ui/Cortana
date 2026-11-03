"""Optional local Qdrant vector-store adapter.

Requires qdrant-client only when instantiated. A collection is dedicated to a
single embedding dimension/model family; model changes require re-embedding.
"""
from __future__ import annotations

import uuid

from .semantic import (
    EmbeddingProvider, SemanticMemoryRecord, SemanticSearchResult,
    _utc_now, _validate_vector, split_into_chunks,
)


class QdrantSemanticMemoryStore:
    def __init__(
        self, client, embedder: EmbeddingProvider, *,
        collection_name: str = "cortana_semantic_memory",
    ) -> None:
        if not isinstance(collection_name, str) or not collection_name.strip():
            raise ValueError("collection_name must be a non-empty string")
        if (isinstance(embedder.dimension, bool)
                or not isinstance(embedder.dimension, int) or embedder.dimension < 1):
            raise ValueError("embedding dimension must be a positive integer")
        try:
            from qdrant_client import models
        except ImportError as exc:
            raise RuntimeError("Qdrant storage requires the optional 'qdrant-client' package") from exc
        self.client = client
        self.embedder = embedder
        self.collection_name = collection_name.strip()
        self._models = models
        collections = {item.name for item in client.get_collections().collections}
        if self.collection_name not in collections:
            client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=embedder.dimension, distance=models.Distance.COSINE
                ),
            )
        else:
            info = client.get_collection(self.collection_name)
            vectors = info.config.params.vectors
            size = getattr(vectors, "size", None)
            if size is None or size != embedder.dimension:
                raise ValueError(
                    "existing Qdrant collection dimension does not match the embedding model"
                )

    @classmethod
    def local(
        cls, path: str, embedder: EmbeddingProvider, *,
        collection_name: str = "cortana_semantic_memory",
    ) -> "QdrantSemanticMemoryStore":
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise RuntimeError("Qdrant storage requires the optional 'qdrant-client' package") from exc
        return cls(QdrantClient(path=path), embedder, collection_name=collection_name)

    def ingest(
        self, text: str, *, source: str, consent: bool = False,
        max_chars: int = 900, overlap: int = 120,
    ) -> str:
        if consent is not True:
            raise PermissionError("semantic memory ingestion requires explicit user consent")
        if not isinstance(source, str) or not source.strip() or len(source) > 200:
            raise ValueError("source must be a non-empty label of at most 200 characters")
        document_id = str(uuid.uuid4())
        points = []
        for chunk in split_into_chunks(text, max_chars=max_chars, overlap=overlap):
            vector = _validate_vector(self.embedder.embed(chunk), self.embedder.dimension)
            points.append(self._models.PointStruct(
                id=str(uuid.uuid4()), vector=list(vector),
                payload={
                    "document_id": document_id, "source": source.strip(),
                    "text": chunk, "created_at": _utc_now(),
                    "embedding_model": getattr(self.embedder, "model_name", "custom"),
                },
            ))
        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        return document_id

    def search(
        self, query: str, *, top_k: int = 5, min_score: float = -1.0,
    ) -> tuple[SemanticSearchResult, ...]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
            raise ValueError("top_k must be from 1 to 100")
        if (isinstance(min_score, bool) or not isinstance(min_score, (int, float))
                or not -1 <= min_score <= 1):
            raise ValueError("min_score must be between -1 and 1")
        vector = list(_validate_vector(self.embedder.embed(query), self.embedder.dimension))
        response = self.client.query_points(
            collection_name=self.collection_name, query=vector, limit=top_k,
            with_payload=True,
        )
        results = []
        for point in response.points:
            score = float(point.score)
            if score < min_score:
                continue
            payload = point.payload or {}
            record = SemanticMemoryRecord(
                record_id=str(point.id),
                document_id=str(payload.get("document_id", "")),
                source=str(payload.get("source", "unknown")),
                text=str(payload.get("text", "")),
                created_at=str(payload.get("created_at", "")),
            )
            results.append(SemanticSearchResult(record, score))
        return tuple(results)

    def list_document_records(self, document_id: str | None = None):
        """Scroll all authoritative payload records for index rebuild/reconciliation."""
        records = []
        offset = None
        query_filter = None
        if document_id is not None:
            if not isinstance(document_id, str) or not document_id.strip():
                raise ValueError("document_id must be a non-empty string")
            query_filter = self._models.Filter(must=[
                self._models.FieldCondition(
                    key="document_id", match=self._models.MatchValue(value=document_id)
                )
            ])
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                records.append(SemanticMemoryRecord(
                    record_id=str(point.id),
                    document_id=str(payload.get("document_id", "")),
                    source=str(payload.get("source", "unknown")),
                    text=str(payload.get("text", "")),
                    created_at=str(payload.get("created_at", "")),
                ))
            if offset is None:
                break
        return tuple(records)

    def delete_document(self, document_id: str, *, confirmed: bool = False) -> int:
        if confirmed is not True:
            raise PermissionError("deleting semantic memory requires explicit confirmation")
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("document_id must be a non-empty string")
        selector = self._models.FilterSelector(filter=self._models.Filter(must=[
            self._models.FieldCondition(
                key="document_id", match=self._models.MatchValue(value=document_id)
            )
        ]))
        self.client.delete(
            collection_name=self.collection_name, points_selector=selector, wait=True
        )
        # Qdrant's delete API does not provide an exact affected-point count.
        return 0

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()
