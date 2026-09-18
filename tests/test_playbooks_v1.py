"""Unit tests for Playbook Loader and Cue Matcher (v1)."""

import unittest
from src.playbooks.loader_v1 import PlaybookLoader, Playbook


class TestPlaybooks(unittest.TestCase):

    def setUp(self):
        self.loader = PlaybookLoader()

    def test_list_available_playbooks(self):
        pbs = self.loader.list_available()
        names = [p["name"] for p in pbs]
        self.assertIn("general_speech", names)
        self.assertIn("municipal_meetings", names)
        self.assertIn("interview_podcast", names)
        self.assertIn("corporate_meeting", names)

    def test_municipal_playbook_cues(self):
        pb = self.loader.load("municipal_meetings")
        self.assertEqual(pb.name, "municipal_meetings")

        # Test chair cue
        role = pb.detect_role("I now open this meeting with a roll call.")
        self.assertEqual(role, "Chair")

        # Test motion cue
        role_motion = pb.detect_role("So moved. Motion to approve.")
        self.assertEqual(role_motion, "Member Motion")

    def test_podcast_playbook_cues(self):
        pb = self.loader.load("interview_podcast")
        role_host = pb.detect_role("Welcome back to the show, my guest today is John.")
        self.assertEqual(role_host, "Host")

        role_guest = pb.detect_role("Thanks for having me, excited to be here.")
        self.assertEqual(role_guest, "Guest")

    def test_roster_matching(self):
        pb = self.loader.load("municipal_meetings")
        match = pb.match_roster("Mr. Evans, I am here as well.")
        self.assertIsNotNone(match)
        self.assertIn("Evans", match)


if __name__ == "__main__":
    unittest.main()
