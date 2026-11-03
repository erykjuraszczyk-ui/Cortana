import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cortana_soul.core import load_profile
from cortana_soul.persistence import SoulProfileStore


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "config" / "soul-profile.json"


class SoulProfileStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "soul.sqlite3"
        self.profile = load_profile(PROFILE_PATH)
        self.store = SoulProfileStore(self.database)
        self.store.initialize(self.profile)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_profile_persists_and_reloads(self):
        revision, profile = self.store.get()
        self.assertEqual(revision, 1)
        self.assertEqual(profile.identity.display_name, "Cortana")

    def test_initialization_does_not_overwrite_existing_profile(self):
        self.assertEqual(self.store.initialize(self.profile), 1)
        self.assertEqual(self.store.get()[0], 1)

    def test_personality_update_requires_approval(self):
        with self.assertRaises(PermissionError):
            self.store.update_personality(
                {"humor": 0.50}, reason="User feedback", approved=False
            )

    def test_approved_small_personality_update_is_audited(self):
        revision = self.store.update_personality(
            {"humor": 0.50}, reason="User prefers slightly more humor",
            approved=True, expected_revision=1
        )
        self.assertEqual(revision, 2)
        current_revision, profile = self.store.get()
        self.assertEqual(current_revision, 2)
        self.assertEqual(profile.personality.humor, 0.50)
        event = self.store.history()[0]
        self.assertEqual(event["event_type"], "personality_updated")
        self.assertEqual(event["reason"], "User prefers slightly more humor")
        self.assertEqual(event["before"]["personality"]["humor"], 0.45)
        self.assertEqual(event["after"]["personality"]["humor"], 0.50)

    def test_identity_and_core_values_cannot_be_changed(self):
        with self.assertRaises(ValueError):
            self.store.update_personality(
                {"display_name": "Other"}, reason="rename",
                approved=True
            )

    def test_large_personality_step_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.update_personality(
                {"curiosity": 1.0}, reason="Large jump", approved=True
            )

    def test_stale_revision_is_rejected(self):
        self.store.update_personality(
            {"humor": 0.50}, reason="First change", approved=True,
            expected_revision=1
        )
        with self.assertRaises(RuntimeError):
            self.store.update_personality(
                {"humor": 0.55}, reason="Stale change", approved=True,
                expected_revision=1
            )

    def test_history_is_append_only(self):
        with sqlite3.connect(self.database) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM soul_change_log")
            db.rollback()


if __name__ == "__main__":
    unittest.main()
