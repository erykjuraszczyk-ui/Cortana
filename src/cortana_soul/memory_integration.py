"""Application-level memory integration, durable outbox and recovery.

The authoritative vector store and outbox are separate persistence systems.
This module therefore guarantees durable retry after enqueue, plus reconciliation
for the narrow crash window between an authoritative write and outbox enqueue.
It does not claim a distributed transaction across SQLite and Qdrant.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .persistent_memory import IndexHealth, MemoryIndexSynchronizer
from .semantic import SemanticMemoryRecord


@dataclass(frozen=True)
class MemoryEvent:
    event_id: str
    event_type: str
    document_id: str
    payload: tuple[dict, ...]
    attempts: int = 0


@dataclass(frozen=True)
class OutboxStats:
    pending: int
    failed: int
    delivered: int


class TransactionalOutbox:
    """Durable SQLite event queue with atomic enqueue and delivery bookkeeping."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        if self.database == ":memory:":
            raise ValueError("TransactionalOutbox requires a file-backed SQLite database")
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self):
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS memory_outbox (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    available_at REAL NOT NULL,
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    delivered_at REAL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS memory_outbox_due ON memory_outbox(status, available_at)")

    def enqueue(self, event_type: str, document_id: str, records=(), *, event_id: str | None = None) -> str:
        if event_type not in {"upsert", "delete"}:
            raise ValueError("event_type must be 'upsert' or 'delete'")
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("document_id must be a non-empty string")
        serialized = []
        for record in records:
            serialized.append({
                "record_id": record.record_id, "document_id": record.document_id,
                "source": record.source, "text": record.text, "created_at": record.created_at,
            })
        if event_type == "upsert" and not serialized:
            raise ValueError("upsert events require at least one record")
        identifier = event_id or str(uuid.uuid4())
        now = time.time()
        with self._connect() as db:
            db.execute("""
                INSERT OR IGNORE INTO memory_outbox
                (event_id, event_type, document_id, payload, available_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (identifier, event_type, document_id, json.dumps(serialized, ensure_ascii=False), now, now))
        return identifier

    def claim_due(self, *, limit: int = 50, now: float | None = None) -> tuple[MemoryEvent, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("limit must be from 1 to 500")
        current = time.time() if now is None else now
        with self._connect() as db:
            rows = db.execute("""
                SELECT * FROM memory_outbox
                WHERE status='pending' AND available_at<=?
                ORDER BY created_at, event_id LIMIT ?
            """, (current, limit)).fetchall()
            events = []
            for row in rows:
                db.execute("UPDATE memory_outbox SET status='processing' WHERE event_id=? AND status='pending'",
                           (row["event_id"],))
                records = tuple(json.loads(row["payload"]))
                events.append(MemoryEvent(row["event_id"], row["event_type"],
                                          row["document_id"], records, row["attempts"]))
            return tuple(events)

    def acknowledge(self, event_id: str) -> None:
        with self._connect() as db:
            db.execute("""
                UPDATE memory_outbox SET status='delivered', delivered_at=?, last_error=''
                WHERE event_id=? AND status='processing'
            """, (time.time(), event_id))

    def retry(self, event_id: str, error: str, *, delay_seconds: float, max_attempts: int) -> str:
        if delay_seconds < 0 or max_attempts < 1:
            raise ValueError("retry delay must be non-negative and max_attempts positive")
        with self._connect() as db:
            row = db.execute("SELECT attempts FROM memory_outbox WHERE event_id=?", (event_id,)).fetchone()
            if row is None:
                raise KeyError(event_id)
            attempts = int(row["attempts"]) + 1
            status = "failed" if attempts >= max_attempts else "pending"
            db.execute("""
                UPDATE memory_outbox SET attempts=?, status=?, available_at=?, last_error=?
                WHERE event_id=?
            """, (attempts, status, time.time() + delay_seconds, str(error)[:1000], event_id))
            return status

    def recover_processing(self) -> int:
        """Return abandoned processing events to pending after a process crash."""
        with self._connect() as db:
            cursor = db.execute("UPDATE memory_outbox SET status='pending' WHERE status='processing'")
            return int(cursor.rowcount)

    def stats(self) -> OutboxStats:
        with self._connect() as db:
            rows = db.execute("SELECT status, COUNT(*) AS count FROM memory_outbox GROUP BY status").fetchall()
        counts = {row["status"]: int(row["count"]) for row in rows}
        return OutboxStats(counts.get("pending", 0) + counts.get("processing", 0),
                           counts.get("failed", 0), counts.get("delivered", 0))


class RetryManager:
    def __init__(self, *, base_delay_seconds: float = 1.0, max_delay_seconds: float = 300.0,
                 max_attempts: int = 8) -> None:
        if base_delay_seconds < 0 or max_delay_seconds < base_delay_seconds or max_attempts < 1:
            raise ValueError("invalid retry policy")
        self.base_delay_seconds = float(base_delay_seconds)
        self.max_delay_seconds = float(max_delay_seconds)
        self.max_attempts = int(max_attempts)

    def delay_for(self, next_attempt: int) -> float:
        if next_attempt < 1:
            raise ValueError("next_attempt must be positive")
        return min(self.max_delay_seconds, self.base_delay_seconds * (2 ** (next_attempt - 1)))


class MemoryEventBus:
    """Dispatches durable outbox events to the derived lexical index."""

    def __init__(self, outbox: TransactionalOutbox, synchronizer: MemoryIndexSynchronizer,
                 retry: RetryManager | None = None) -> None:
        self.outbox = outbox
        self.synchronizer = synchronizer
        self.retry = retry or RetryManager()

    def dispatch(self, *, limit: int = 50) -> int:
        delivered = 0
        for event in self.outbox.claim_due(limit=limit):
            try:
                if event.event_type == "upsert":
                    records = tuple(SemanticMemoryRecord(**item) for item in event.payload)
                    self.synchronizer.sync_records(records)
                elif event.event_type == "delete":
                    self.synchronizer.remove_document(event.document_id)
                self.outbox.acknowledge(event.event_id)
                delivered += 1
            except Exception as exc:
                self.outbox.retry(
                    event.event_id, repr(exc),
                    delay_seconds=self.retry.delay_for(event.attempts + 1),
                    max_attempts=self.retry.max_attempts,
                )
        return delivered


class MemoryConsistencyGuard:
    def __init__(self, synchronizer: MemoryIndexSynchronizer) -> None:
        self.synchronizer = synchronizer

    def inspect(self, authoritative_records: Iterable[SemanticMemoryRecord]) -> IndexHealth:
        return self.synchronizer.check_consistency(authoritative_records)


class MemoryRecoveryEngine:
    def __init__(self, synchronizer: MemoryIndexSynchronizer, outbox: TransactionalOutbox,
                 event_bus: MemoryEventBus) -> None:
        self.synchronizer = synchronizer
        self.outbox = outbox
        self.event_bus = event_bus

    def recover(self, authoritative_records: Iterable[SemanticMemoryRecord]) -> IndexHealth:
        records = tuple(authoritative_records)
        self.outbox.recover_processing()
        health = self.synchronizer.check_consistency(records)
        if not health.is_consistent:
            self.synchronizer.rebuild(records)
        self.event_bus.dispatch()
        return self.synchronizer.check_consistency(records)


class MemoryIntegrationService:
    """Consent-gated facade that connects authoritative memory and BM25 projection.

    The wrapped store must provide ingest(), delete_document(), and
    list_document_records(). Outbox reconciliation repairs a crash between
    committing the source write and enqueueing its derived-index event.
    """

    def __init__(self, store, outbox: TransactionalOutbox, event_bus: MemoryEventBus) -> None:
        for method in ("ingest", "delete_document", "list_document_records"):
            if not callable(getattr(store, method, None)):
                raise TypeError(f"memory store must implement {method}()")
        self.store, self.outbox, self.event_bus = store, outbox, event_bus

    def ingest(self, text: str, *, source: str, consent: bool = False, **options) -> str:
        if consent is not True:
            raise PermissionError("memory integration requires explicit user consent")
        document_id = self.store.ingest(text, source=source, consent=True, **options)
        records = tuple(self.store.list_document_records(document_id))
        self.outbox.enqueue("upsert", document_id, records)
        self.event_bus.dispatch()
        return document_id

    def delete_document(self, document_id: str, *, confirmed: bool = False) -> int:
        if confirmed is not True:
            raise PermissionError("memory deletion requires explicit confirmation")
        removed = self.store.delete_document(document_id, confirmed=True)
        self.outbox.enqueue("delete", document_id)
        self.event_bus.dispatch()
        return removed
