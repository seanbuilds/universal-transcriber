"""Persistent Speaker Diarization & Voice Profiling (v1)."""

import json
import math
from pathlib import Path
from typing import List, Dict, Any, Optional

from config_v1 import SPEAKERS_DB_PATH


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two numeric vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class SpeakerDatabase:
    """Manages persistent cross-session speaker voice profiles."""

    def __init__(self, db_path: Path = SPEAKERS_DB_PATH, similarity_threshold: float = 0.82):
        self.db_path = db_path
        self.similarity_threshold = similarity_threshold
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.db_path.exists():
            try:
                return json.loads(self.db_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"profiles": [], "aliases": {}}

    def save(self) -> None:
        """Persist speaker profiles to disk."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

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
                self.save()
                return True
        self.save()
        return True

    def match_or_register(self, embedding: List[float], session_id: str = "") -> str:
        """Match an embedding against known profiles, or create a new profile."""
        best_match = None
        highest_sim = -1.0

        for p in self.data.get("profiles", []):
            ref_emb = p.get("embedding", [])
            sim = cosine_similarity(embedding, ref_emb)
            if sim > highest_sim:
                highest_sim = sim
                best_match = p

        if best_match and highest_sim >= self.similarity_threshold:
            # Update rolling average embedding
            n = best_match.get("samples_count", 1)
            old_emb = best_match.get("embedding", [])
            new_emb = [(old * n + new) / (n + 1) for old, new in zip(old_emb, embedding)]
            best_match["embedding"] = new_emb
            best_match["samples_count"] = n + 1
            if session_id and session_id not in best_match.setdefault("seen_in", []):
                best_match["seen_in"].append(session_id)
            self.save()
            return best_match["id"]

        # Create new profile
        count = len(self.data.get("profiles", [])) + 1
        new_id = f"Speaker_{chr(64 + count) if count <= 26 else count}"
        new_profile = {
            "id": new_id,
            "name": new_id.replace("_", " "),
            "embedding": embedding,
            "samples_count": 1,
            "seen_in": [session_id] if session_id else []
        }
        self.data.setdefault("profiles", []).append(new_profile)
        self.save()
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
