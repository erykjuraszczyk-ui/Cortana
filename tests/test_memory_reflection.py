import tempfile
import unittest
from pathlib import Path

from cortana_soul.affect import AffectState
from cortana_soul.context import ContextResolver
from cortana_soul.memory import EpisodicMemoryStore, MemoryEvent
from cortana_soul.memory_reflection import MemoryAwareReflectionEngine
from cortana_soul.reflection import ReflectionInput


class EpisodicMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = EpisodicMemoryStore(Path(self.temp.name) / "memory.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_consent_required(self):
        with self.assertRaises(PermissionError):
            self.store.record(MemoryEvent("completed"), consent=False)

    def test_record_and_aggregate_explicit_feedback(self):
        self.store.record(MemoryEvent("completed", "positive"), consent=True)
        self.store.record(MemoryEvent("completed", "positive"), consent=True)
        self.store.record(MemoryEvent("partial", "negative"), consent=True)
        summary = self.store.summarize()
        self.assertEqual(summary.event_count, 3)
        self.assertEqual(summary.feedback_count, 3)
        self.assertEqual(summary.positive_count, 2)
        self.assertEqual(summary.negative_count, 1)

    def test_filter_by_tone(self):
        self.store.record(MemoryEvent("completed", "positive", "concise"), consent=True)
        self.store.record(MemoryEvent("completed", "positive", "detailed"), consent=True)
        self.assertEqual(self.store.summarize(requested_tone="concise").event_count, 1)

    def test_clear_requires_confirmation(self):
        self.store.record(MemoryEvent("completed"), consent=True)
        with self.assertRaises(PermissionError):
            self.store.clear_all()
        self.assertEqual(self.store.clear_all(confirmed=True), 1)

    def test_invalid_event_rejected(self):
        with self.assertRaises(ValueError):
            MemoryEvent("completed", confidence=1.5)


class MemoryAwareReflectionTests(unittest.TestCase):
    def setUp(self):
        self.context = ContextResolver().resolve(task="Explain a concept")
        self.event = ReflectionInput(self.context, "completed", "none")
        self.affect = AffectState()

    def test_insufficient_memory_does_not_claim_pattern(self):
        from cortana_soul.memory import MemorySummary
        summary = MemorySummary(2, 2, 2, 0, 0, 2, 30)
        result = MemoryAwareReflectionEngine().reflect(self.event, self.affect, summary)
        self.assertEqual(result.memory_pattern, "insufficient_evidence")
        self.assertFalse(result.auto_applied)

    def test_repeated_positive_feedback_requests_permission(self):
        from cortana_soul.memory import MemorySummary
        summary = MemorySummary(4, 4, 4, 0, 0, 4, 30)
        result = MemoryAwareReflectionEngine().reflect(self.event, self.affect, summary)
        self.assertEqual(result.memory_pattern, "repeated_positive_feedback")
        self.assertIn("Ask the user", result.recommendation)
        self.assertTrue(result.requires_user_approval)
        self.assertFalse(result.auto_applied)

    def test_mixed_feedback_keeps_profile(self):
        from cortana_soul.memory import MemorySummary
        summary = MemorySummary(4, 4, 2, 1, 1, 3, 30)
        result = MemoryAwareReflectionEngine().reflect(self.event, self.affect, summary)
        self.assertEqual(result.memory_pattern, "mixed_or_no_stable_pattern")


if __name__ == "__main__":
    unittest.main()
