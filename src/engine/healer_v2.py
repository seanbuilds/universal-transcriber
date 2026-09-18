"""Self-Healing Dialogue & Temporal-Bounded Turn Coalescing Engine (v2).
<!-- v2 – Temporal gap bounds (3s), block duration limits (60s), safe multi-word deduplication -->
"""

import re
from typing import List, Dict, Any, Optional

from src.playbooks.loader_v1 import Playbook

# Bounds for paragraph coalescing
MAX_INTER_TURN_GAP_SECONDS = 3.0    # Gaps exceeding 3.0s (e.g. recesses or pauses) break paragraph
MAX_BLOCK_DURATION_SECONDS = 60.0   # Prevents monolithic text walls

# Legitimate English repetition doublets (preserve grammatical double words)
GRAMMATICAL_DOUBLETS = {"that", "had", "which"}


def clean_stutters(text: str) -> str:
    """Strip acoustic repeated words while preserving valid grammatical doublets."""
    if not text:
        return ""

    def replace_word(m):
        w = m.group(1)
        if w.lower() in GRAMMATICAL_DOUBLETS:
            return m.group(0)  # keep both
        return w

    # Single-word stutter removal
    text = re.sub(r'\b([A-Za-z]+)\s+\1\b', replace_word, text, flags=re.IGNORECASE)
    # Multi-word phrase stutter removal (e.g. "summer meeting summer meeting")
    text = re.sub(r'\b([A-Za-z]+\s+[A-Za-z]+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
    return text.strip()


def safe_deduplicate_overlap(prev_text: str, next_text: str, min_k: int = 3, max_k: int = 15) -> str:
    """Remove overlapping words across Whisper sliding window boundaries requiring at least min_k words."""
    p_words = prev_text.split()
    n_words = next_text.split()
    if len(p_words) < min_k or len(n_words) < min_k:
        return next_text

    max_search = min(len(p_words), len(n_words), max_k)
    for k in range(max_search, min_k - 1, -1):
        suffix = " ".join(p_words[-k:]).lower().strip(".,?!\"'")
        prefix = " ".join(n_words[:k]).lower().strip(".,?!\"'")
        if suffix == prefix:
            return " ".join(n_words[k:]).strip()
    return next_text


class TurnCoalescer:
    """Applies domain playbook heuristics, temporal gap bounds, and turn coalescing."""

    def __init__(self, playbook: Playbook):
        self.playbook = playbook

    def heal_and_coalesce(
        self,
        segments: List[Dict[str, Any]],
        initial_speaker: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Process raw segments into cohesive, temporally bounded dialogue blocks."""
        if not segments:
            return []

        default_role = self.playbook.default_role or "Speaker"
        current_speaker = initial_speaker or default_role
        pending_yield: Optional[str] = None

        healed_segments = []

        for seg in segments:
            raw_text = clean_stutters(seg.get("text", ""))
            if not raw_text:
                continue

            lower = raw_text.lower()

            # 1. Roster matching (using word boundaries)
            roster_match = self.playbook.match_roster(raw_text)

            # 2. Playbook cue matching (anchored)
            cue_role = self.playbook.detect_role(raw_text)

            # 3. Yield detection with strict name bounds (Finding R2-11)
            yield_match = None
            if any(k in lower for k in ["turn the floor over to", "hand it over to", "turn over to"]):
                m = re.search(r'(?:turn the floor over to|hand it over to|turn over to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})', raw_text)
                if m:
                    yield_match = m.group(1).strip()

            # Assign speaker for this segment
            assigned_spk = current_speaker
            if pending_yield:
                assigned_spk = pending_yield
                pending_yield = None
            elif roster_match and any(w in lower for w in ["present", "here", "speaking", "aye"]):
                assigned_spk = roster_match
            elif cue_role:
                assigned_spk = cue_role

            if yield_match:
                pending_yield = yield_match

            current_speaker = assigned_spk
            healed_segments.append({
                "ts": seg.get("ts", "00:00:00"),
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "speaker": assigned_spk,
                "text": raw_text
            })

        # Coalesce consecutive segments spoken by the same speaker WITH TEMPORAL BOUNDS
        coalesced_blocks = []
        current_block = None

        for s in healed_segments:
            spk = s["speaker"]
            text = s["text"]
            start_s = s["start"]
            end_s = s["end"]

            if current_block is None:
                current_block = {
                    "ts": s["ts"],
                    "start": start_s,
                    "end": end_s,
                    "speaker": spk,
                    "text": text
                }
            else:
                # Check coalescing conditions (Finding R2-09)
                is_same_speaker = (current_block["speaker"] == spk)
                time_gap = start_s - current_block["end"]
                total_duration = end_s - current_block["start"]

                if is_same_speaker and (0.0 <= time_gap <= MAX_INTER_TURN_GAP_SECONDS) and (total_duration <= MAX_BLOCK_DURATION_SECONDS):
                    clean_next = safe_deduplicate_overlap(current_block["text"], text)
                    if clean_next:
                        current_block["text"] += " " + clean_next
                    current_block["end"] = end_s
                else:
                    # Flush finished block and begin new block
                    coalesced_blocks.append(current_block)
                    current_block = {
                        "ts": s["ts"],
                        "start": start_s,
                        "end": end_s,
                        "speaker": spk,
                        "text": text
                    }

        if current_block:
            coalesced_blocks.append(current_block)

        return coalesced_blocks
