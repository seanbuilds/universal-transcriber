"""Self-Healing and Temporal Gap Boundary Tests (v2)."""

import unittest
from src.engine.healer_v2 import clean_stutters, safe_deduplicate_overlap, TurnCoalescer
from src.playbooks.loader_v2 import Playbook


class TestHealerV2(unittest.TestCase):

    def test_grammatical_doublet_preservation(self):
        """Preserve valid English grammar doublets like 'that that' and 'had had'."""
        text = "I know that that decision was difficult."
        self.assertEqual(clean_stutters(text), "I know that that decision was difficult.")

        stutter_text = "we we should move forward"
        self.assertEqual(clean_stutters(stutter_text), "we should move forward")

    def test_safe_multi_word_deduplication(self):
        """Require min_k words to deduplicate; do not strip valid single words."""
        prev_text = "We will now conclude the committee meeting."
        # Overlapping 3 words: "the committee meeting"
        next_text = "the committee meeting is now adjourned."
        result = safe_deduplicate_overlap(prev_text, next_text, min_k=3)
        self.assertEqual(result, "is now adjourned.")

    def test_temporal_gap_breaks_paragraph(self):
        """A silence gap > 3.0s (e.g. 15-minute recess) MUST split into separate blocks even for same speaker."""
        pb = Playbook({
            "name": "test",
            "default_role": "Speaker",
            "roles": ["Speaker"],
            "cues": {}
        })
        coalescer = TurnCoalescer(playbook=pb)

        segments = [
            {"ts": "00:01:00", "start": 60.0, "end": 75.0, "text": "We will take a 15-minute recess now."},
            # 15 minute gap (900 seconds later)
            {"ts": "00:16:15", "start": 975.0, "end": 990.0, "text": "Welcome back, the recess is concluded."}
        ]

        blocks = coalescer.heal_and_coalesce(segments)
        self.assertEqual(len(blocks), 2, "15-minute recess must NOT be collapsed into a single block!")
        self.assertEqual(blocks[0]["ts"], "00:01:00")
        self.assertEqual(blocks[1]["ts"], "00:16:15")


if __name__ == "__main__":
    unittest.main()
