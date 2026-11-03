import unittest

from cortana_soul.affect import AffectEngine, AffectState
from cortana_soul.context import ContextResolver
from cortana_soul.reflection import ReflectionEngine, ReflectionInput


class AffectEngineTests(unittest.TestCase):
    def test_smoothing_updates_state(self):
        engine = AffectEngine(smoothing=0.5)
        state = engine.update({"valence": 1.0, "uncertainty": 0.0})
        self.assertEqual(state.valence, 0.5)
        self.assertEqual(state.uncertainty, 0.25)
        self.assertTrue(state.updated_at)

    def test_unknown_dimension_rejected(self):
        with self.assertRaises(ValueError):
            AffectEngine().update({"anger": 0.9})

    def test_out_of_range_signal_rejected(self):
        with self.assertRaises(ValueError):
            AffectEngine().update({"arousal": 2.0})

    def test_boolean_is_not_numeric_signal(self):
        with self.assertRaises(ValueError):
            AffectEngine().update({"confidence": True})

    def test_invalid_initial_state_rejected(self):
        with self.assertRaises(ValueError):
            AffectState(valence=2.0)


class ContextResolverTests(unittest.TestCase):
    def test_resolves_explicit_context(self):
        frame = ContextResolver().resolve(
            task="Summarize a report", urgency="high",
            requested_tone="concise", requires_confirmation=True
        )
        self.assertEqual(frame.urgency, "high")
        self.assertTrue(frame.requires_confirmation)

    def test_invalid_context_rejected(self):
        with self.assertRaises(ValueError):
            ContextResolver().resolve(task="task", urgency="critical")


class ReflectionEngineTests(unittest.TestCase):
    def setUp(self):
        self.context = ContextResolver().resolve(task="Explain a concept")
        self.affect = AffectState()

    def test_negative_feedback_requests_clarification_not_adaptation(self):
        event = ReflectionInput(self.context, "completed", "negative")
        result = ReflectionEngine().reflect(event, self.affect)
        self.assertIsNone(result.suggested_style_field)
        self.assertTrue(result.requires_user_approval)
        self.assertFalse(result.auto_applied)

    def test_positive_single_event_does_not_change_profile(self):
        event = ReflectionInput(self.context, "completed", "positive")
        result = ReflectionEngine().reflect(event, self.affect)
        self.assertIn("do not infer", result.recommendation)
        self.assertIsNone(result.suggested_style_field)

    def test_incomplete_task_prioritizes_clarification(self):
        event = ReflectionInput(self.context, "partial", unresolved_questions=1)
        result = ReflectionEngine().reflect(event, self.affect)
        self.assertIn("Clarify", result.recommendation)

    def test_low_confidence_requests_verification(self):
        event = ReflectionInput(self.context, "unknown", confidence=0.2)
        result = ReflectionEngine().reflect(event, self.affect)
        self.assertIn("Verify", result.recommendation)


if __name__ == "__main__":
    unittest.main()
