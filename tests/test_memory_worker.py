import tempfile
import threading
import time
import unittest
from pathlib import Path

from cortana_soul.memory_integration import MemoryEventBus, RetryManager, TransactionalOutbox
from cortana_soul.memory_worker import (
    DeadLetterQueue, MemoryLifecycleManager, MemoryMetrics, MemoryScheduler, MemoryWorker,
)
from cortana_soul.persistent_memory import MemoryIndexSynchronizer, PersistentBM25Index
from cortana_soul.semantic import SemanticMemoryRecord


class MemoryWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.outbox = TransactionalOutbox(root / "outbox.sqlite3")
        self.index = PersistentBM25Index(root / "index.sqlite3")
        self.sync = MemoryIndexSynchronizer(self.index)
        self.bus = MemoryEventBus(self.outbox, self.sync,
                                  RetryManager(base_delay_seconds=0, max_attempts=1))

    def tearDown(self):
        self.temp.cleanup()

    def enqueue(self, record_id="r1"):
        self.outbox.enqueue("upsert", "d1", [
            SemanticMemoryRecord(record_id, "d1", "notes", "worker queue processing", "now")
        ])

    def test_worker_dispatches_and_records_metrics(self):
        self.enqueue()
        metrics = MemoryMetrics()
        worker = MemoryWorker(self.bus, batch_size=10, metrics=metrics)
        self.assertEqual(worker.run_once(), 1)
        snapshot = metrics.snapshot()
        self.assertEqual(snapshot.cycles, 1)
        self.assertEqual(snapshot.delivered, 1)
        self.assertEqual(snapshot.pending, 0)
        self.assertEqual(self.index.record_ids(), ("r1",))

    def test_dead_letter_can_be_reviewed_and_requeued(self):
        class BrokenSync:
            def sync_records(self, records):
                raise RuntimeError("permanent test failure")
            def remove_document(self, document_id):
                raise RuntimeError("permanent test failure")

        broken_bus = MemoryEventBus(self.outbox, BrokenSync(),
                                    RetryManager(base_delay_seconds=0, max_attempts=1))
        self.enqueue()
        self.assertEqual(broken_bus.dispatch(), 0)
        queue = DeadLetterQueue(self.outbox)
        items = queue.list()
        self.assertEqual(len(items), 1)
        self.assertIn("permanent test failure", items[0]["last_error"])
        self.assertTrue(queue.requeue(items[0]["event_id"]))
        self.assertFalse(queue.requeue(items[0]["event_id"]))
        self.assertEqual(self.outbox.stats().pending, 1)

    def test_lifecycle_purges_only_old_delivered_events(self):
        self.enqueue()
        self.assertEqual(self.bus.dispatch(), 1)
        lifecycle = MemoryLifecycleManager(self.outbox)
        removed = lifecycle.purge_delivered(older_than_seconds=0, now=time.time() + 1)
        self.assertEqual(removed, 1)
        self.assertEqual(self.outbox.stats().delivered, 0)

    def test_scheduler_stops_cleanly(self):
        scheduler = MemoryScheduler(interval_seconds=0.01)
        calls = []
        thread = threading.Thread(target=scheduler.run_forever, args=(lambda: calls.append(1),))
        thread.start()
        time.sleep(0.04)
        scheduler.stop()
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertGreaterEqual(len(calls), 1)

    def test_worker_rejects_second_run_forever_start(self):
        worker = MemoryWorker(self.bus, idle_seconds=0.01)
        thread = threading.Thread(target=worker.run_forever)
        thread.start()
        deadline = time.time() + 1
        while not worker._started and time.time() < deadline:
            time.sleep(0.001)
        worker.stop()
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        with self.assertRaises(RuntimeError):
            worker.run_forever()


if __name__ == "__main__":
    unittest.main()
