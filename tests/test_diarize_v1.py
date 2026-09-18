"""Unit tests for Persistent Speaker Diarization (v1)."""

import unittest
import tempfile
from pathlib import Path
from src.engine.diarize_v1 import SpeakerDatabase, cosine_similarity


class TestDiarization(unittest.TestCase):

    def test_cosine_similarity(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v1, v2), 1.0)

        v3 = [0.0, 1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v1, v3), 0.0)

    def test_speaker_database_matching_and_renaming(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_speakers.json"
            db = SpeakerDatabase(db_path=db_path, similarity_threshold=0.85)

            # Register first speaker
            emb_a = [0.9, 0.1, 0.0]
            spk_id = db.match_or_register(emb_a, session_id="meeting_1")
            self.assertEqual(spk_id, "Speaker_A")

            # Match similar voice
            emb_a_similar = [0.89, 0.11, 0.0]
            matched_id = db.match_or_register(emb_a_similar, session_id="meeting_2")
            self.assertEqual(matched_id, "Speaker_A")

            # Rename speaker
            db.rename_speaker("Speaker_A", "Alice Smith")
            self.assertEqual(db.get_display_name("Speaker_A"), "Alice Smith")


if __name__ == "__main__":
    unittest.main()
