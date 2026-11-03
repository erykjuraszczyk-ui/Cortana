import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from cortana_soul.memory_integration import (
    MemoryEventBus, MemoryIntegrationService, MemoryRecoveryEngine,
    RetryManager, TransactionalOutbox,
)
from cortana_soul.persistent_memory import (
    MemoryIndexSynchronizer, PersistentBM25Index,
)
from cortana_soul.semantic import SemanticMemoryRecord


@dataclass(frozen=True)
class Record:
    record_id: str
    document_id: str
    source: str
    text: str
    created_at: str


class FakeStore:
    def __init__(self):
        self.records = {}

    def ingest(self, text, *, source, consent=False, **options):
        if consent is not True:
            raise PermissionError
        document_id = "doc-1"
        record = SemanticMemoryRecord("rec-1", document_id, source, text,
                                      "2026-11-03T12:00:00+00:00")
        self.records[record.record_id] = record
        return document_id

    def list_document_records(self, document_id=None):
        return tuple(record for record in self.records.values()
                     if document_id is None or record.document_id == document_id)

    def delete_document(self, document_id, *, confirmed=False):
        if confirmed is not True:
            raise PermissionError
        ids = [key for key, value in self.records.items()
               if value.document_id == document_id]
        for key in ids:
            del self.records[key]
        return len(ids)


class MemoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.index = PersistentBM25Index(root / "index.sqlite3")
        self.sync = MemoryIndexSynchronizer(self.index)
        self.outbox = TransactionalOutbox(root / "outbox.sqlite3")
        self.bus = MemoryEventBus(self.outbox, self.sync,
                                  RetryManager(base_delay_seconds=0, max_attempts=3))
        self.store = FakeStore()
        self.service = MemoryIntegrationService(self.store, self.outbox, self.bus)

    def tearDown(self):
        self.temp.cleanup()

    def test_ingest_requires_consent(self):
        with self.assertRaises(PermissionError):
            self.service.ingest("approved memory text", source="notes")
        self.assertEqual(self.index.record_ids(), ())

    def test_ingest_syncs_lexical_index(self):
        document_id = self.service.ingest(
            "Qdrant vector memory integration", source="notes", consent=True
        )
        self.assertEqual(document_id, "doc-1")
        results = self.index.search("Qdrant integration")
        self.assertEqual(results[0][0].record_id, "rec-1")
        self.assertEqual(self.outbox.stats().pending, 0)
        self.assertEqual(self.outbox.stats().delivered, 1)

    def test_delete_requires_confirmation_and_removes_index(self):
        self.service.ingest("Qdrant vector memory", source="notes", consent=True)
        with self.assertRaises(PermissionError):
            self.service.delete_document("doc-1")
        self.service.delete_document("doc-1", confirmed=True)
        self.assertEqual(self.index.record_ids(), ())

    def test_failed_dispatch_is_retried(self):
        class BrokenSync:
            def sync_records(self, records):
                raise RuntimeError("temporary index failure")
            def remove_document(self, document_id):
                raise RuntimeError("temporary index failure")

        broken = MemoryEventBus(self.outbox, BrokenSync(),
                                RetryManager(base_delay_seconds=0, max_attempts=2))
        event_id = self.outbox.enqueue(
            "upsert", "d1",
            [SemanticMemoryRecord("r1", "d1", "notes", "retry this", "now")]
        )
        self.assertEqual(broken.dispatch(), 0)
        self.assertEqual(self.outbox.stats().pending, 1)
        self.assertEqual(broken.dispatch(), 0)
        self.assertEqual(self.outbox.stats().failed, 1)

    def test_recovery_rebuilds_index_from_authoritative_store(self):
        self.store.ingest("Qdrant authoritative record", source="notes", consent=True)
        recovery = MemoryRecoveryEngine(self.sync, self.outbox, self.bus)
        health = recovery.recover(self.store.list_document_records())
        self.assertTrue(health.is_consistent)
        self.assertEqual(self.index.search("Qdrant")[0][0].record_id, "rec-1")

    def test_processing_events_are_recovered_after_restart(self):
        self.outbox.enqueue(
            "upsert", "d1",
            [SemanticMemoryRecord("r1", "d1", "notes", "retry this", "now")]
        )
        claimed = self.outbox.claim_due()
        self.assertEqual(len(claimed), 1)
        self.assertEqual(self.outbox.recover_processing(), 1)
        self.assertEqual(self.bus.dispatch(), 1)


if __name__ == "__main__":
    unittest.main()
