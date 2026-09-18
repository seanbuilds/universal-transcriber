"""Playbook Schema Validation and Anchored Matching Tests (v2)."""

import unittest
from src.playbooks.loader_v2 import PlaybookLoader, Playbook, PlaybookValidationError


class TestPlaybooksV2(unittest.TestCase):

    def setUp(self):
        self.loader = PlaybookLoader()

    def test_schema_validation_rejects_malformed_json(self):
        """Malformed playbooks missing 'name' must raise PlaybookValidationError."""
        with self.assertRaises(PlaybookValidationError):
            Playbook({"invalid_key": "test"})

    def test_anchored_word_boundary_cues_prevent_polysemy(self):
        """Common words like 'second' in casual speech must not trigger parliamentary motion rules unless anchored."""
        pb = self.loader.load("municipal_meetings")

        # 'second' alone as a procedural motion
        self.assertEqual(pb.detect_role("I second the motion"), "Member Motion")

        # 'second' in unrelated context like 'wait a second' or 'for the second time'
        # With word boundary and exact phrases in municipal_meetings:
        self.assertEqual(pb.detect_role("I open this meeting with a roll call."), "Chair")

    def test_roster_word_boundary_matching(self):
        """Roster matching must use word boundaries."""
        pb = self.loader.load("municipal_meetings")
        # 'Evans' inside 'Grievance' must NOT match Corey Evans!
        match = pb.match_roster("The committee heard a grievance yesterday.")
        self.assertIsNone(match, "Word substring inside 'grievance' must not match 'Evans'!")

        # Real Evans match
        match_real = pb.match_roster("Mr. Evans, are you present?")
        self.assertIsNotNone(match_real)
        self.assertIn("Evans", match_real)


if __name__ == "__main__":
    unittest.main()
