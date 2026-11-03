import json
import unittest
from pathlib import Path

from cortana_soul.core import SoulCore, load_profile, profile_from_dict


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "config" / "soul-profile.json"


class SoulCoreTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))

    def test_loads_default_profile(self):
        profile = load_profile(PROFILE_PATH)
        self.assertEqual(profile.identity.display_name, "Cortana")
        self.assertIn("honesty", profile.values)

    def test_personality_scores_are_bounded(self):
        self.data["personality"]["humor"] = 1.5
        with self.assertRaises(ValueError):
            profile_from_dict(self.data)

    def test_external_actions_require_approval(self):
        self.data["behavior"]["ask_before_external_actions"] = False
        with self.assertRaises(ValueError):
            profile_from_dict(self.data)

    def test_memory_requires_policy_check(self):
        self.data["behavior"]["memory_requires_policy_check"] = False
        with self.assertRaises(ValueError):
            profile_from_dict(self.data)

    def test_core_returns_identity_summary(self):
        core = SoulCore(load_profile(PROFILE_PATH))
        summary = core.describe()
        self.assertEqual(summary["agent_id"], "cortana")
        self.assertEqual(summary["language"], "pl-PL")


if __name__ == "__main__":
    unittest.main()
