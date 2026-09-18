# tests/test_diarize_v3.py
"""Automated Test Suite for Diarization Engine v3 and VoiceEmbeddingExtractor."""

import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.engine.embeddings_v1 import VoiceEmbeddingExtractor
from src.engine.diarize_v3 import (
    cosine_similarity,
    unit_normalize,
    update_spherical_centroid,
    AgglomerativeClustering,
    SpeakerDatabaseV3,
)


class TestDiarizationV3(unittest.TestCase):

    def setUp(self):
        self.extractor = VoiceEmbeddingExtractor(embedding_dim=192)

    def test_unit_normalization_guarantee(self):
        """Verify VoiceEmbeddingExtractor outputs strict unit norm vectors."""
        # Synthesize 16kHz sine wave audio bytes (1 second = 16000 samples = 32000 bytes)
        samples = []
        for i in range(16000):
            val = int(16000 * math.sin(2 * math.pi * 440 * i / 16000))
            samples.extend(val.to_bytes(2, byteorder="little", signed=True))
        raw_bytes = bytes(samples)

        vec = self.extractor.extract_from_bytes(raw_bytes)
        self.assertIsNotNone(vec)
        self.assertEqual(len(vec), 192)

        norm = math.sqrt(sum(x * x for x in vec))
        self.assertAlmostEqual(norm, 1.0, places=6)

    def test_silence_rejection(self):
        """Verify digital silence bytes yield None instead of zero-vector."""
        silence_bytes = bytes(16000 * 2)  # All zeros
        vec = self.extractor.extract_from_bytes(silence_bytes)
        self.assertIsNone(vec)

    def test_ahc_clustering_separates_distinct_groups(self):
        """Verify AgglomerativeClustering groups similar vectors and separates distinct ones."""
        # Generate 2 clusters: Cluster A (around [1, 0, 0...]), Cluster B (around [0, 1, 0...])
        dim = 192
        cluster_a = []
        for _ in range(5):
            v = [0.0] * dim
            v[0] = 1.0 + 0.05 * math.sin(_)
            v[1] = 0.02 * _
            cluster_a.append(unit_normalize(v))

        cluster_b = []
        for _ in range(5):
            v = [0.0] * dim
            v[1] = 1.0 + 0.05 * math.cos(_)
            v[2] = 0.03 * _
            cluster_b.append(unit_normalize(v))

        # Interleave embeddings
        all_embeddings = []
        expected_labels = []
        for a, b in zip(cluster_a, cluster_b):
            all_embeddings.append(a)
            expected_labels.append("A")
            all_embeddings.append(b)
            expected_labels.append("B")

        ahc = AgglomerativeClustering(distance_threshold=0.30)
        labels = ahc.cluster(all_embeddings)

        self.assertEqual(len(labels), 10)
        # Verify that all A items share one label, and all B items share a different label
        label_a = labels[0]
        label_b = labels[1]
        self.assertNotEqual(label_a, label_b)

        for i, exp in enumerate(expected_labels):
            if exp == "A":
                self.assertEqual(labels[i], label_a)
            else:
                self.assertEqual(labels[i], label_b)

    def test_database_persistence_and_library_export(self):
        """Verify cross-session persistent storage and recovery."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "speakers_v3.json"
            db = SpeakerDatabaseV3(storage_path=db_path, similarity_threshold=0.75)

            v1 = unit_normalize([1.0] + [0.0] * 191)
            name1, sim1 = db.match_or_register(v1)
            self.assertEqual(name1, "Speaker_01")

            # Reload from disk
            db_reloaded = SpeakerDatabaseV3(storage_path=db_path, similarity_threshold=0.75)
            self.assertIn("Speaker_01", db_reloaded.profiles)
            self.assertEqual(len(db_reloaded.profiles), 1)

            # Match similar vector
            v1_similar = unit_normalize([0.98, 0.05] + [0.0] * 190)
            matched_name, match_sim = db_reloaded.match_or_register(v1_similar)
            self.assertEqual(matched_name, "Speaker_01")
            self.assertGreaterEqual(match_sim, 0.75)


if __name__ == "__main__":
    unittest.main()
