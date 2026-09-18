"""Diarization and Hypersphere Centroid Stability Tests (v2)."""

import unittest
import tempfile
from pathlib import Path
from src.engine.diarize_v2 import (
    SpeakerDatabase,
    cosine_similarity,
    normalize_vector,
    vector_norm,
    update_spherical_centroid
)


class TestDiarizationV2(unittest.TestCase):

    def test_unit_normalization(self):
        v = [3.0, 4.0, 0.0]
        normed = normalize_vector(v)
        self.assertAlmostEqual(vector_norm(normed), 1.0)
        self.assertAlmostEqual(normed[0], 0.6)
        self.assertAlmostEqual(normed[1], 0.8)

    def test_zero_vector_rejection(self):
        """Silence/zero vectors must not create phantom speakers (Finding R2-06)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_speakers.json"
            db = SpeakerDatabase(db_path=db_path)
            res = db.match_or_register([0.0] * 64)
            self.assertEqual(res, "Speaker")
            self.assertEqual(len(db.data.get("profiles", [])), 0)

    def test_hypersphere_centroid_stability_over_30_turns(self):
        """Simulate 30 consecutive updates; verify centroid remains on unit sphere and does not cannibalize distinct voices."""
        initial_anchor = normalize_vector([1.0, 0.2, 0.0])
        current_centroid = list(initial_anchor)

        for i in range(30):
            # Incoming sample with slight acoustic variation
            sample = normalize_vector([1.0, 0.2 + (i * 0.005), 0.05])
            current_centroid = update_spherical_centroid(
                current_centroid=current_centroid,
                new_sample=sample,
                alpha=0.85,
                anchor=initial_anchor,
                max_drift_cos=0.70
            )
            # Must remain unit norm
            self.assertAlmostEqual(vector_norm(current_centroid), 1.0, places=5)

        # Distinct speaker must NOT match
        distinct_speaker = normalize_vector([0.0, 1.0, 0.0])
        sim = cosine_similarity(current_centroid, distinct_speaker)
        self.assertLess(sim, 0.5)


if __name__ == "__main__":
    unittest.main()
