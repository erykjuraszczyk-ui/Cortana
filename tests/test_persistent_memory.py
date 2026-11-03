import tempfile
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cortana_soul.persistent_memory import (
    HybridReranker, MemoryIndexSynchronizer, PersistentBM25Index,
)
from cortana_soul.semantic import SemanticSearchResult


@dataclass(frozen=True)
class Record:
    record_id: str
    document_id: str
    source: str
    text: str
    created_at: str
    category: str = "general"


class PersistentMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "memory.sqlite3")
        self.index = PersistentBM25Index(self.db)
        self.records = [
            Record("r1", "d1", "notes", "Qdrant vector database and embeddings",
                   "2026-10-30T12:00:00+00:00", "technical"),
            Record("r2", "d2", "journal", "BM25 lexical search and ranking",
                   "2026-10-20T12:00:00+00:00", "personal"),
            Record("r3", "d3", "notes", "Hybrid retrieval combines vector and lexical search",
                   "2026-10-25T12:00:00+00:00", "technical"),
        ]

    def tearDown(self):
        self.temp.cleanup()

    def test_persists_across_instances(self):
        self.index.upsert(self.records)
        reopened = PersistentBM25Index(self.db)
        results = reopened.search("Qdrant embeddings")
        self.assertEqual(results[0][0].record_id, "r1")

    def test_metadata_filters(self):
        self.index.upsert(self.records)
        results = self.index.search("search", source="notes", category="technical")
        self.assertEqual([record.record_id for record, _ in results], ["r3"])

    def test_document_deletion(self):
        self.index.upsert(self.records)
        self.assertEqual(self.index.remove_document("d1"), 1)
        self.assertNotIn("r1", self.index.record_ids())

    def test_rebuild_replaces_stale_records(self):
        self.index.upsert(self.records)
        self.assertEqual(self.index.rebuild(self.records[:1]), 1)
        self.assertEqual(self.index.record_ids(), ("r1",))

    def test_sync_health_reports_missing_and_stale(self):
        self.index.upsert(self.records[:2])
        sync = MemoryIndexSynchronizer(self.index)
        health = sync.check_consistency([self.records[0], self.records[2]])
        self.assertFalse(health.is_consistent)
        self.assertEqual(health.missing_ids, ("r3",))
        self.assertEqual(health.stale_ids, ("r2",))

    def test_sync_rebuild_restores_consistency(self):
        sync = MemoryIndexSynchronizer(self.index)
        sync.rebuild(self.records)
        self.assertTrue(sync.check_consistency(self.records).is_consistent)

    def test_version_increments_on_mutation(self):
        initial = self.index.version
        self.index.upsert(self.records[:1])
        self.assertGreater(self.index.version, initial)

    def test_rejects_in_memory_database(self):
        with self.assertRaises(ValueError):
            PersistentBM25Index(":memory:")

    def test_reranker_prefers_relevant_recent_record(self):
        results = [
            SemanticSearchResult(self.records[1], 0.95),
            SemanticSearchResult(self.records[0], 0.70),
        ]
        reranker = HybridReranker()
        ranked = reranker.rerank(
            "Qdrant vector embeddings",
            results,
            now=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(ranked[0].record.record_id, "r1")

    def test_reranker_validates_weights(self):
        with self.assertRaises(ValueError):
            HybridReranker(relevance_weight=0, recency_weight=0)


if __name__ == "__main__":
    unittest.main()
