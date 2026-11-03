# CORTANA SOUL CORE v1.8.0

**Release:** Autonomous Memory Integration & Durable Synchronization  
**Python:** 3.11+  
**Platforms:** Windows and Linux  
**Runtime dependencies:** Python standard library only

## Scope

v1.8.0 introduces an application-level integration service connecting the consent-controlled authoritative memory store to the persistent BM25 projection. It adds a durable SQLite outbox, retry processing, crash recovery, authoritative record enumeration for SQLite and Qdrant, and consistency-driven rebuilds.

## Architecture

```text
       EXPLICIT USER CONSENT
                |
      MemoryIntegrationService
                |
       AUTHORITATIVE STORE
         (SQLite / Qdrant)
                |
          list records
                |
       TransactionalOutbox
                |
          MemoryEventBus
                |
       PersistentBM25Index
                |
      MemoryConsistencyGuard
                |
       MemoryRecoveryEngine
                |
        Hybrid Retrieval
```

## Components

- `MemoryIntegrationService`: consent-gated facade for ingest and confirmed deletion. It writes to the authoritative store, records a durable sync event and dispatches pending work.
- `TransactionalOutbox`: file-backed SQLite queue with pending/processing/delivered/failed states, attempt counts and delayed retries.
- `MemoryEventBus`: idempotent upsert/delete projection dispatcher.
- `RetryManager`: bounded exponential backoff.
- `MemoryConsistencyGuard`: compares authoritative record IDs with the lexical index.
- `MemoryRecoveryEngine`: requeues abandoned processing events, checks consistency, rebuilds the index from the authoritative store when required, then dispatches due events.
- `list_document_records()`: added to SQLite and Qdrant stores for per-document synchronization and full recovery.

## Quick start — SQLite authoritative store

```python
from cortana_soul import (
    MemoryEventBus, MemoryIndexSynchronizer, MemoryIntegrationService,
    PersistentBM25Index, TransactionalOutbox,
)
from cortana_soul import SemanticMemoryStore, LocalSentenceTransformer

embedder = LocalSentenceTransformer(device="cpu")
store = SemanticMemoryStore("data/semantic.sqlite3", embedder)
index = PersistentBM25Index("data/lexical.sqlite3")
outbox = TransactionalOutbox("data/outbox.sqlite3")
sync = MemoryIndexSynchronizer(index)
bus = MemoryEventBus(outbox, sync)
memory = MemoryIntegrationService(store, outbox, bus)

document_id = memory.ingest(
    "Approved project knowledge",
    source="project-notes",
    consent=True,
)
matches = index.search("project knowledge", top_k=5)

# Deletion remains an explicit confirmed operation.
memory.delete_document(document_id, confirmed=True)
```

Use the same composition with `QdrantSemanticMemoryStore` as the authoritative store. Its `list_document_records()` method scrolls the collection for synchronization and recovery.

## Delivery and recovery semantics

1. The authoritative store remains the source of truth.
2. Ingestion requires `consent=True`; deletion requires `confirmed=True`.
3. After a successful source write, an outbox event is persisted and dispatched.
4. Failed projection work is retried with bounded exponential backoff; exhausted events are marked failed for operator review.
5. On process restart, abandoned `processing` events return to `pending`.
6. A recovery pass compares record IDs and rebuilds the BM25 projection if it detects missing or stale records.
7. Upsert and delete projection operations are safe to repeat.

### Important consistency boundary

The outbox and authoritative store are separate persistence systems. The implementation does **not** claim a distributed atomic transaction across SQLite and Qdrant. A process crash after the authoritative write but before outbox enqueue can leave a short-lived gap. Run `MemoryRecoveryEngine.recover(store.list_document_records())` at startup and periodically to repair it. A future SQLite-specific implementation may place the source mutation and outbox insert in the same database transaction.

## Operational guidance

- Keep the authoritative store, outbox and index on durable local storage.
- Call recovery at startup before serving retrieval traffic.
- Monitor pending and failed outbox counts via `outbox.stats()`.
- Investigate failed events before clearing the queue.
- Rebuild only from records returned by the consent-controlled authoritative store.
- Do not index credentials, secrets or payment information.
- No automatic chat transcript ingestion is introduced.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Tests cover consent, automatic projection updates, confirmed deletion, retry exhaustion, restart recovery and authoritative rebuild. CI requires no model downloads, network access or Qdrant server.

## Limitations

- The event worker is synchronous and invoked by the service; a background scheduler/worker process is a deployment concern.
- Cross-database atomicity is not provided. Reconciliation closes the crash gap eventually.
- Qdrant deletion does not expose an exact deleted-point count through the current adapter.
- The system is a deterministic software memory pipeline, not human-like memory or consciousness.
