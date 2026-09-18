"""Unit tests for Self-Healing and Dialogue Coalescing (v1)."""

import unittest
from src.engine.healer_v1 import clean_stutters, deduplicate_overlap, TurnCoalescer
from src.playbooks.loader_v1 import Playbook


class TestHealer(unittest.TestCase):

    def test_clean_stutters(self):
        # Single word repetition
        self.assertEqual(clean_stutters("we we will move forward"), "we will move forward")
        # Multi-word phrase repetition
        self.assertEqual(clean_stutters("summer meeting summer meeting is early"), "summer meeting is early")

    def test_deduplicate_overlap(self):
        prev_text = "Apologies to everybody for this summer meeting."
        next_text = "summer meeting. I know it is a little earlier."
        result = deduplicate_overlap(prev_text, next_text)
        self.assertEqual(result, "I know it is a little earlier.")

    def test_turn_coalescing(self):
        pb = Playbook({
            "name": "test",
            "default_role": "Speaker",
            "roles": ["Speaker"],
            "cues": {}
        })
        coalescer = TurnCoalescer(playbook=pb)

        raw_segments = [
            {"ts": "00:00:01", "start": 1.0, "end": 4.0, "text": "Hello and welcome to the session."},
            {"ts": "00:00:05", "start": 5.0, "end": 8.0, "text": "Today we have a very important topic to cover."},
            {"ts": "00:00:09", "start": 9.0, "end": 12.0, "text": "Let us get right into the details."}
        ]

        coalesced = coalescer.heal_and_coalesce(raw_segments)
        self.assertEqual(len(coalesced), 1)
        self.assertEqual(coalesced[0]["ts"], "00:00:01")
        self.assertIn("Hello and welcome", coalesced[0]["text"])
        self.assertIn("details.", coalesced[0]["text"])


if __name__ == "__main__":
    unittest.main()
