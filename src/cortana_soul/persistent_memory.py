"""Persistent BM25 indexing, synchronization and reranking for SOUL CORE v1.7.0.

This module stores only records supplied by the consent-controlled memory layer.
The vector store remains the source of truth; this SQLite index is rebuildable.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from .retrieval import tokenize
from .semantic import SemanticMemoryRecord, SemanticSearchResult


@dataclass(frozen=True)
class IndexHealth:
    indexed_records: int
    expected_records: int
    missing_ids: tuple[str, ...]
    stale_ids: tuple[str, ...]
    index_version: int

    @property
    def is_consistent(self) -> bool:
        return not self.missing_ids and not self.stale_ids


class PersistentBM25Index:
    """SQLite-persisted BM25 index with metadata filtering and atomic rebuilds."""

    def __init__(self, database: str | Path, *, k1: float = 1.5, b: float = 0.75) -> None:
        if isinstance(k1, bool) or not isinstance(k1, (int, float)) or not math.isfinite(k1) or k1 <= 0:
            raise ValueError("k1 must be positive and finite")
        if isinstance(b, bool) or not isinstance(b, (int, float)) or not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1")
        self.database = str(database)
        if self.database == ":memory:":
            raise ValueError("PersistentBM25Index requires a file-backed SQLite database")
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self.k1, self.b = float(k1), float(b)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS soul_bm25_documents (
                    record_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    category TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    tokens TEXT NOT NULL,
                    token_count INTEGER NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS soul_bm25_document ON soul_bm25_documents(document_id)")
            db.execute("CREATE INDEX IF NOT EXISTS soul_bm25_source ON soul_bm25_documents(source)")
            db.execute("CREATE INDEX IF NOT EXISTS soul_bm25_category ON soul_bm25_documents(category)")
            db.execute("""
                CREATE TABLE IF NOT EXISTS soul_bm25_meta (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )
            """)
            db.execute("INSERT OR IGNORE INTO soul_bm25_meta(key, value) VALUES ('version', 0)")

    @property
    def version(self) -> int:
        with self._connect() as db:
            row = db.execute("SELECT value FROM soul_bm25_meta WHERE key='version'").fetchone()
            return int(row["value"])

    def _bump_version(self, db: sqlite3.Connection) -> None:
        db.execute("UPDATE soul_bm25_meta SET value=value+1 WHERE key='version'")

    @staticmethod
    def _prepare(record: SemanticMemoryRecord) -> tuple:
        record_id = getattr(record, "record_id", None)
        document_id = getattr(record, "document_id", None)
        source = getattr(record, "source", None)
        text = getattr(record, "text", None)
        created_at = getattr(record, "created_at", "")
        category = getattr(record, "category", "general")
        if not all(isinstance(value, str) and value.strip() for value in (record_id, document_id, source, text)):
            raise ValueError("records must expose non-empty record_id, document_id, source and text")
        if not isinstance(created_at, str) or not isinstance(category, str):
            raise ValueError("created_at and category must be strings")
        terms = tokenize(text)
        return (record_id, document_id, source, category, text, created_at,
                json.dumps(terms, ensure_ascii=False), len(terms))

    def upsert(self, records: Iterable[SemanticMemoryRecord]) -> int:
        prepared = [self._prepare(record) for record in records]
        if not prepared:
            return 0
        with self._connect() as db:
            db.executemany("""
                INSERT INTO soul_bm25_documents
                (record_id, document_id, source, category, text, created_at, tokens, token_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_id) DO UPDATE SET
                    document_id=excluded.document_id, source=excluded.source,
                    category=excluded.category, text=excluded.text,
                    created_at=excluded.created_at, tokens=excluded.tokens,
                    token_count=excluded.token_count
            """, prepared)
            self._bump_version(db)
        return len(prepared)

    def rebuild(self, records: Iterable[SemanticMemoryRecord]) -> int:
        prepared = [self._prepare(record) for record in records]
        with self._connect() as db:
            db.execute("DELETE FROM soul_bm25_documents")
            db.executemany("""
                INSERT INTO soul_bm25_documents
                (record_id, document_id, source, category, text, created_at, tokens, token_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, prepared)
            self._bump_version(db)
        return len(prepared)

    def remove_document(self, document_id: str) -> int:
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("document_id must be a non-empty string")
        with self._connect() as db:
            cursor = db.execute("DELETE FROM soul_bm25_documents WHERE document_id=?", (document_id,))
            removed = int(cursor.rowcount)
            if removed:
                self._bump_version(db)
            return removed

    def remove_record(self, record_id: str) -> bool:
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("record_id must be a non-empty string")
        with self._connect() as db:
            cursor = db.execute("DELETE FROM soul_bm25_documents WHERE record_id=?", (record_id,))
            if cursor.rowcount:
                self._bump_version(db)
                return True
            return False

    def record_ids(self) -> tuple[str, ...]:
        with self._connect() as db:
            rows = db.execute("SELECT record_id FROM soul_bm25_documents ORDER BY record_id").fetchall()
        return tuple(row["record_id"] for row in rows)

    def search(
        self, query: str, *, top_k: int = 10, source: str | None = None,
        category: str | None = None, created_after: str | None = None,
        created_before: str | None = None,
    ):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
            raise ValueError("top_k must be from 1 to 100")
        for name, value in (("source", source), ("category", category),
                            ("created_after", created_after), ("created_before", created_before)):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string when supplied")
        clauses, params = [], []
        for column, value in (("source", source), ("category", category)):
            if value is not None:
                clauses.append(f"{column}=?")
                params.append(value)
        if created_after is not None:
            clauses.append("created_at>=?")
            params.append(created_after)
        if created_before is not None:
            clauses.append("created_at<=?")
            params.append(created_before)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as db:
            rows = db.execute("SELECT * FROM soul_bm25_documents" + where, params).fetchall()
        query_terms = set(tokenize(query))
        if not query_terms or not rows:
            return ()
        docs = [(row, tuple(json.loads(row["tokens"]))) for row in rows]
        count = len(docs)
        average_length = sum(len(tokens) for _, tokens in docs) / count or 1.0
        document_frequency = Counter()
        for _, tokens in docs:
            document_frequency.update(set(tokens))
        ranked = []
        for row, tokens in docs:
            frequencies = Counter(tokens)
            length = len(tokens)
            score = 0.0
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                df = document_frequency[term]
                idf = math.log(1 + (count - df + 0.5) / (df + 0.5))
                denominator = frequency + self.k1 * (1 - self.b + self.b * length / average_length)
                score += idf * frequency * (self.k1 + 1) / denominator
            if score > 0:
                record = SemanticMemoryRecord(
                    record_id=row["record_id"], document_id=row["document_id"],
                    source=row["source"], text=row["text"], created_at=row["created_at"],
                )
                ranked.append((record, score))
        ranked.sort(key=lambda item: (-item[1], item[0].record_id))
        return tuple(ranked[:top_k])


class MemoryIndexSynchronizer:
    """Explicit sync boundary between the authoritative store and BM25 index.

    Call sync_records after successful ingestion, remove_document after a
    confirmed source deletion, and rebuild at startup or after a failed sync.
    """

    def __init__(self, index: PersistentBM25Index) -> None:
        self.index = index

    def sync_records(self, records: Iterable[SemanticMemoryRecord]) -> int:
        return self.index.upsert(records)

    def remove_document(self, document_id: str) -> int:
        return self.index.remove_document(document_id)

    def rebuild(self, authoritative_records: Iterable[SemanticMemoryRecord]) -> int:
        return self.index.rebuild(authoritative_records)

    def check_consistency(self, authoritative_records: Iterable[SemanticMemoryRecord]) -> IndexHealth:
        expected = {record.record_id for record in authoritative_records}
        indexed = set(self.index.record_ids())
        return IndexHealth(
            indexed_records=len(indexed), expected_records=len(expected),
            missing_ids=tuple(sorted(expected - indexed)),
            stale_ids=tuple(sorted(indexed - expected)),
            index_version=self.index.version,
        )


class HybridReranker:
    """Deterministic second-stage reranker using lexical overlap and recency."""

    def __init__(self, *, relevance_weight: float = 0.85, recency_weight: float = 0.15) -> None:
        values = (relevance_weight, recency_weight)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
               for v in values) or sum(values) <= 0:
            raise ValueError("reranking weights must be finite, non-negative, and not both zero")
        total = float(sum(values))
        self.relevance_weight = float(relevance_weight) / total
        self.recency_weight = float(recency_weight) / total

    def rerank(
        self, query: str, results: Sequence[SemanticSearchResult], *, top_k: int = 5,
        now: datetime | None = None,
    ) -> tuple[SemanticSearchResult, ...]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
            raise ValueError("top_k must be from 1 to 100")
        reference = now or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        query_terms = set(tokenize(query))
        ranked = []
        for result in results:
            record = result.record
            record_terms = set(tokenize(record.text))
            overlap = len(query_terms & record_terms) / len(query_terms) if query_terms else 0.0
            recency = 0.0
            try:
                created = datetime.fromisoformat(record.created_at.replace("Z", "+00:00"))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age_days = max(0.0, (reference - created).total_seconds() / 86400)
                recency = math.exp(-age_days / 30.0)
            except (TypeError, ValueError):
                pass
            semantic = max(0.0, min(1.0, (float(result.score) + 1.0) / 2.0))
            score = self.relevance_weight * (0.7 * semantic + 0.3 * overlap) + self.recency_weight * recency
            ranked.append(SemanticSearchResult(record, score))
        ranked.sort(key=lambda item: (-item.score, item.record.record_id))
        return tuple(ranked[:top_k])
