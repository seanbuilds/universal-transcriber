"""Persistent Speaker Diarization & Spherical Voice Profiling (v2).
<!-- v2 – Unit-sphere vector normalization, drift-bounded EMA, zero-vector rejection -->
"""

import json
import math
from pathlib import Path
from typing import List, Dict, Any, Optional

from config_v2 import SPEAKERS_DB_PATH


def vector_norm(v: List[float]) -> float:
    """Calculate Euclidean norm of a vector."""
    return math.sqrt(sum(x * x for x in v))


def normalize_vector(v: List[float]) -> List[float]:
    """Normalize vector to unit length (L2 norm = 1.0)."""
    n = vector_norm(v)
    if n == 0.0 or math.isnan(n):
        return [0.0] * len(v)
    return [x / n for x in v]


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two numeric vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = vector_norm(v1)
    norm2 = vector_norm(v2)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm1 * norm2)))


def update_spherical_centroid(
    current_centroid: List[float],
    new_sample: List[float],
    alpha: float = 0.85,
    anchor: Optional[List[float]] = None,
    max_drift_cos: float = 0.70
) -> List[float]:
    """Update speaker embedding centroid using spherical EMA normalization."""
    c_norm = normalize_vector(current_centroid)
    s_norm = normalize_vector(new_sample)

    if vector_norm(s_norm) == 0.0:
        return c_norm

    # Exponential moving average on unit sphere
    updated = [alpha * c + (1.0 - alpha) * s for c, s in zip(c_norm, s_norm)]
    projected = normalize_vector(updated)

    # Drift clamp against initial registration anchor
    if anchor is not None:
        drift_sim = cosine_similarity(projected, anchor)
        if drift_sim < max_drift_cos:
            return c_norm

    return projected


class SpeakerDatabase:
    """Manages persistent, drift-bounded cross-session speaker voice profiles."""

    def __init__(self, db_path: Path = SPEAKERS_DB_PATH, similarity_threshold: float = 0.82):
        self.db_path = db_path
        self.similarity_threshold = similarity_threshold
        self.data = self._load()
        self._dirty = False

    def _load(self) -> Dict[str, Any]:
        if self.db_path.exists():
            try:
                return json.loads(self.db_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"profiles": [], "aliases": {}}

    def save(self, force: bool = False) -> None:
        """Persist speaker profiles to disk atomically."""
        if not self._dirty and not force:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.db_path.with_suffix(".tmp")
        temp_file.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        temp_file.replace(self.db_path)
        self._dirty = False

    def list_speakers(self) -> List[Dict[str, Any]]:
        """Return list of all recognized speaker profiles."""
        profiles = []
        aliases = self.data.get("aliases", {})
        for p in self.data.get("profiles", []):
            spk_id = p.get("id")
            name = aliases.get(spk_id, p.get("name", spk_id))
            profiles.append({
                "id": spk_id,
                "name": name,
                "sessions_count": len(p.get("seen_in", [])),
                "samples_count": p.get("samples_count", 1)
            })
        return profiles

    def rename_speaker(self, speaker_id: str, new_name: str) -> bool:
        """Assign or update a human name for a speaker profile."""
        aliases = self.data.setdefault("aliases", {})
        aliases[speaker_id] = new_name.strip()
        for p in self.data.get("profiles", []):
            if p.get("id") == speaker_id:
                p["name"] = new_name.strip()
                self._dirty = True
                self.save(force=True)
                return True
        self._dirty = True
        self.save(force=True)
        return True

    def match_or_register(self, embedding: List[float], session_id: str = "") -> str:
        """Match an embedding against known profiles, rejecting zero-vectors and preventing centroid drift."""
        # Reject silence/zero vectors (Finding R2-06)
        if not embedding or vector_norm(embedding) < 1e-5:
            return "Speaker"

        norm_embedding = normalize_vector(embedding)

        best_match = None
        highest_sim = -1.0

        for p in self.data.get("profiles", []):
            ref_emb = p.get("embedding", [])
            sim = cosine_similarity(norm_embedding, ref_emb)
            if sim > highest_sim:
                highest_sim = sim
                best_match = p

        if best_match and highest_sim >= self.similarity_threshold:
            # Update rolling centroid on unit sphere with anchor clamping
            anchor = p.get("anchor_embedding") or p.get("embedding")
            updated_centroid = update_spherical_centroid(
                current_centroid=best_match["embedding"],
                new_sample=norm_embedding,
                alpha=0.85,
                anchor=anchor,
                max_drift_cos=0.68
            )
            best_match["embedding"] = updated_centroid
            best_match["samples_count"] = best_match.get("samples_count", 1) + 1
            if session_id and session_id not in best_match.setdefault("seen_in", []):
                best_match["seen_in"].append(session_id)
            self._dirty = True
            return best_match["id"]

        # Register new speaker with sequential naming (Finding R2-08)
        count = len(self.data.get("profiles", [])) + 1
        new_id = f"Speaker_{count:02d}"
        new_profile = {
            "id": new_id,
            "name": f"Speaker {count:02d}",
            "embedding": norm_embedding,
            "anchor_embedding": norm_embedding,  # Fixed anchor for drift control
            "samples_count": 1,
            "seen_in": [session_id] if session_id else []
        }
        self.data.setdefault("profiles", []).append(new_profile)
        self._dirty = True
        return new_id

    def get_display_name(self, speaker_id: str) -> str:
        """Get the human display name for a speaker ID."""
        aliases = self.data.get("aliases", {})
        if speaker_id in aliases:
            return aliases[speaker_id]
        for p in self.data.get("profiles", []):
            if p.get("id") == speaker_id:
                return p.get("name", speaker_id)
        return speaker_id
