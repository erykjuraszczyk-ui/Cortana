"""Consent-based semantic memory with pluggable embedding providers.

The store persists only knowledge explicitly approved for long-term retention.
It does not ingest chat history automatically.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Sequence


class EmbeddingProvider(Protocol):
    """Adapter contract for a local or remote embedding model."""

    @property
    def dimension(self) -> int: ...

    def embed(self, text: str) -> Sequence[float]: ...


@dataclass(frozen=True)
class SemanticMemoryRecord:
    record_id: str
    document_id: str
    source: str
    text: str
    created_at: str


@dataclass(frozen=True)
class SemanticSearchResult:
    record: SemanticMemoryRecord
    score: float


@dataclass(frozen=True)
class ContextItem:
    source_id: str
    source: str
    text: str
    relevance: float


@dataclass(frozen=True)
class RetrievedContext:
    query: str
    items: tuple[ContextItem, ...]
    character_count: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_vector(vector: Sequence[float], dimension: int) -> tuple[float, ...]:
    if isinstance(vector, (str, bytes)) or len(vector) != dimension:
        raise ValueError(f"embedding must contain exactly {dimension} values")
    values = tuple(float(value) for value in vector)
    if any(not math.isfinite(value) for value in values):
        raise ValueError("embedding values must be finite")
    if not any(value != 0 for value in values):
        raise ValueError("embedding must not be a zero vector")
    return values


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def split_into_chunks(text: str, *, max_chars: int = 900, overlap: int = 120) -> tuple[str, ...]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 100:
        raise ValueError("max_chars must be an integer >= 100")
    if isinstance(overlap, bool) or not isinstance(overlap, int) or not 0 <= overlap < max_chars:
        raise ValueError("overlap must be between 0 and max_chars - 1")
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= max_chars:
        return (normalized,)
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + max_chars, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind(" ", start + max_chars // 2, end)
            if boundary > start:
                end = boundary
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return tuple(chunks)


class SemanticMemoryStore:
    """SQLite-backed vector store; all ingestion requires explicit consent."""

    def __init__(self, database: str | Path, embedder: EmbeddingProvider) -> None:
        self.database = str(database)
        self.embedder = embedder
        if isinstance(embedder.dimension, bool) or not isinstance(embedder.dimension, int) or embedder.dimension < 1:
            raise ValueError("embedding dimension must be a positive integer")
        if self.database != ":memory:":
            Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    record_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    text TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS semantic_memory_document ON semantic_memory(document_id)")

    def ingest(
        self, text: str, *, source: str, consent: bool = False,
        max_chars: int = 900, overlap: int = 120,
    ) -> str:
        if consent is not True:
            raise PermissionError("semantic memory ingestion requires explicit user consent")
        if not isinstance(source, str) or not source.strip() or len(source) > 200:
            raise ValueError("source must be a non-empty label of at most 200 characters")
        chunks = split_into_chunks(text, max_chars=max_chars, overlap=overlap)
        prepared = []
        for chunk in chunks:
            vector = _validate_vector(self.embedder.embed(chunk), self.embedder.dimension)
            prepared.append((str(uuid.uuid4()), chunk, json.dumps(vector), _utc_now()))
        document_id = str(uuid.uuid4())
        with self._connect() as db:
            db.executemany(
                """INSERT INTO semantic_memory
                   (record_id, document_id, source, text, embedding, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [(record_id, document_id, source.strip(), chunk, vector, created_at)
                 for record_id, chunk, vector, created_at in prepared],
            )
        return document_id

    def search(self, query: str, *, top_k: int = 5, min_score: float = -1.0) -> tuple[SemanticSearchResult, ...]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
            raise ValueError("top_k must be from 1 to 100")
        if isinstance(min_score, bool) or not isinstance(min_score, (int, float)) or not -1 <= min_score <= 1:
            raise ValueError("min_score must be between -1 and 1")
        query_vector = _validate_vector(self.embedder.embed(query), self.embedder.dimension)
        with self._connect() as db:
            rows = db.execute(
                "SELECT record_id, document_id, source, text, embedding, created_at FROM semantic_memory"
            ).fetchall()
        ranked: list[SemanticSearchResult] = []
        for row in rows:
            stored = _validate_vector(json.loads(row["embedding"]), self.embedder.dimension)
            score = _cosine(query_vector, stored)
            if score >= min_score:
                record = SemanticMemoryRecord(
                    record_id=row["record_id"], document_id=row["document_id"],
                    source=row["source"], text=row["text"], created_at=row["created_at"],
                )
                ranked.append(SemanticSearchResult(record, score))
        ranked.sort(key=lambda item: item.score, reverse=True)
        return tuple(ranked[:top_k])

    def list_document_records(self, document_id: str | None = None) -> tuple[SemanticMemoryRecord, ...]:
        """Return authoritative records for synchronization or full recovery."""
        query = ("SELECT record_id, document_id, source, text, created_at FROM semantic_memory"
                 + (" WHERE document_id = ?" if document_id is not None else "")
                 + " ORDER BY record_id")
        params = (document_id,) if document_id is not None else ()
        with self._connect() as db:
            rows = db.execute(query, params).fetchall()
        return tuple(SemanticMemoryRecord(
            record_id=row["record_id"], document_id=row["document_id"],
            source=row["source"], text=row["text"], created_at=row["created_at"],
        ) for row in rows)

    def delete_document(self, document_id: str, *, confirmed: bool = False) -> int:
        if confirmed is not True:
            raise PermissionError("deleting semantic memory requires explicit confirmation")
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("document_id must be a non-empty string")
        with self._connect() as db:
            cursor = db.execute("DELETE FROM semantic_memory WHERE document_id = ?", (document_id,))
            return int(cursor.rowcount)

    def clear_all(self, *, confirmed: bool = False) -> int:
        if confirmed is not True:
            raise PermissionError("clearing semantic memory requires explicit confirmation")
        with self._connect() as db:
            cursor = db.execute("DELETE FROM semantic_memory")
            return int(cursor.rowcount)


class LongTermContextAssembler:
    """Builds a bounded, source-attributed context from retrieved memories."""

    def __init__(self, *, max_characters: int = 4000) -> None:
        if isinstance(max_characters, bool) or not isinstance(max_characters, int) or max_characters < 100:
            raise ValueError("max_characters must be an integer >= 100")
        self.max_characters = max_characters

    def assemble(
        self, query: str, results: Sequence[SemanticSearchResult]
    ) -> RetrievedContext:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        items: list[ContextItem] = []
        seen: set[str] = set()
        used = 0
        for result in results:
            record = result.record
            if record.record_id in seen:
                continue
            prefix = f"[source:{record.source} | id:{record.record_id}] "
            available = self.max_characters - used - len(prefix)
            if available <= 0:
                break
            content = record.text[:available]
            if not content:
                continue
            items.append(ContextItem(record.record_id, record.source, content, result.score))
            used += len(prefix) + len(content)
            seen.add(record.record_id)
            if used >= self.max_characters:
                break
        return RetrievedContext(query=query, items=tuple(items), character_count=used)
