# CORTANA SOUL CORE v1.7.0

**Release:** Persistent Hybrid Memory, Index Synchronization & Retrieval Optimization  
**Python:** 3.11+  
**Platforms:** Windows and Linux  
**Core dependencies:** Python standard library only

## Scope

v1.7.0 adds a durable SQLite-backed BM25 index, explicit synchronization/rebuild tooling, metadata-filtered lexical retrieval, consistency diagnostics, and a deterministic second-stage reranker. SQLite or Qdrant remains the authoritative vector-memory backend; the lexical index is a derived, rebuildable projection.

## Architecture

```text
          APPROVED MEMORY
          (SQLite / Qdrant)
                  |
       list approved records
                  |
       MemoryIndexSynchronizer
           /           \
       UPSERT          REBUILD
           \           /
         PersistentBM25Index
                  |
       Metadata-filtered BM25
                  |
       HybridRetriever (v1.6)
                  |
         HybridReranker
                  |
      Bounded context assembler
                  |
           CORTANA CORE
```

## Components

- `PersistentBM25Index`: persists documents, token streams, metadata and an index version in SQLite. Reopens safely after process restart.
- `MemoryIndexSynchronizer`: synchronizes supplied authoritative records, removes a deleted document from the lexical projection, performs full rebuilds and reports missing/stale IDs.
- `IndexHealth`: exposes indexed/expected counts, missing IDs, stale IDs, index version and a consistency flag.
- `HybridReranker`: second-stage deterministic ranking using semantic score, query-term overlap and a configurable 30-day recency decay.
- Existing `BM25Index` and `HybridRetriever` remain available for lightweight in-memory workflows.

## Quick start

```python
from cortana_soul import (
    HybridReranker,
    MemoryIndexSynchronizer,
    PersistentBM25Index,
)

# Use a durable file, not :memory:.
index = PersistentBM25Index("data/cortana-memory.sqlite3")
sync = MemoryIndexSynchronizer(index)

# records must be read from the consent-controlled authoritative store.
sync.sync_records(approved_records)

# After restart, reopen the same database file; the index persists.
matches = index.search(
    "Qdrant vector memory",
    top_k=10,
    source="project-notes",
    category="technical",
)

health = sync.check_consistency(approved_records)
if not health.is_consistent:
    sync.rebuild(approved_records)

# Rerank a candidate set returned by HybridRetriever.
reranked = HybridReranker().rerank(
    "Qdrant vector memory",
    hybrid_results,
    top_k=5,
)
```

## Synchronization contract

1. The vector store is authoritative; the BM25 index is a derived projection.
2. After a successful consented ingest, pass the newly stored records to `sync_records`.
3. After a confirmed document deletion, call the authoritative store's deletion method and then `remove_document(document_id)`.
4. On startup, after a crash, or when a consistency check reports drift, enumerate approved records from the authoritative store and call `rebuild(records)`.
5. Treat a failed lexical-index update as recoverable: do not roll back a successfully committed authoritative memory write; mark/retry synchronization and rebuild from the source of truth.

The synchronization API is intentionally explicit. It does not silently ingest chat transcripts, poll external databases, or claim cross-database atomicity. A future application service can invoke it as a post-commit hook for both SQLite and Qdrant adapters.

## Retrieval optimization

- BM25 tokenization reuses the v1.6.0 Unicode-aware tokenizer.
- Metadata filters: exact `source`, exact `category`, inclusive ISO-8601 `created_after` and `created_before`.
- Index version increments after successful mutations and can be observed by monitoring.
- Reranking is deterministic for equal inputs and uses record ID as the final tie-breaker.
- Ranking values are not probabilities and should not be interpreted as confidence.

## Privacy and security

- The index stores only records explicitly supplied by the consent-controlled memory layer.
- No automatic conversation ingestion is introduced.
- Deletion from the authoritative store and the derived index must both be confirmed by the application workflow.
- The index duplicates approved text locally; protect its database file with OS permissions and disk encryption.
- Do not index credentials, secrets, payment data or other sensitive information.
- Keep the authoritative store and index on trusted local storage unless the user has explicitly configured an approved remote deployment.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Tests cover persistence across instances, metadata filtering, document deletion, rebuild, consistency diagnostics, versioning, reranking and validation. No model download, network access or Qdrant service is required.

## Limitations

- Synchronization is a post-commit application contract, not a distributed transaction across SQLite/Qdrant and the BM25 projection.
- The application must enumerate all approved source records to perform a full rebuild or exact consistency check.
- Metadata filters on this lexical index are exact-match filters.
- Recency decay is a ranking heuristic, not a semantic truth signal.
- The memory system is software infrastructure; it does not imply human-like memory or consciousness.
