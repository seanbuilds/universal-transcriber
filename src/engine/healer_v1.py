"""Self-Healing Dialogue & Turn Coalescing Engine (v1)."""

import re
from typing import List, Dict, Any, Optional

from src.playbooks.loader_v1 import Playbook


def clean_stutters(text: str) -> str:
    """Strip repeated words and consecutive duplicate phrases."""
    if not text:
        return ""
    # Remove immediate single word repetitions (e.g. "the the" -> "the")
    text = re.sub(r'\b([A-Za-z]+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
    # Remove immediate two-word phrase repetitions (e.g. "summer meeting summer meeting")
    text = re.sub(r'\b([A-Za-z]+\s+[A-Za-z]+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
    return text.strip()


def deduplicate_overlap(prev_text: str, next_text: str) -> str:
    """Remove overlapping words across Whisper sliding window boundaries."""
    p_words = prev_text.split()
    n_words = next_text.split()
    if not p_words or not n_words:
        return next_text

    max_k = min(len(p_words), len(n_words), 6)
    for k in range(max_k, 0, -1):
        suffix = " ".join(p_words[-k:]).lower().strip(".,?!\"'")
        prefix = " ".join(n_words[:k]).lower().strip(".,?!\"'")
        if suffix == prefix:
            return " ".join(n_words[k:]).strip()
    return next_text


class TurnCoalescer:
    """Applies domain playbook heuristics and coalesces broken segments into cohesive blocks."""

    def __init__(self, playbook: Playbook):
        self.playbook = playbook

    def heal_and_coalesce(
        self,
        segments: List[Dict[str, Any]],
        initial_speaker: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Process raw segments, applying playbook cues and turn coalescing."""
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

            # 1. Roster matching (if playbook has roster)
            roster_match = self.playbook.match_roster(raw_text)

            # 2. Playbook cue matching
            cue_role = self.playbook.detect_role(raw_text)

            # 3. Yield detection ("turn the floor over to X", "hand over to X")
            yield_match = None
            if "turn the floor over to" in lower or "hand it over to" in lower or "turn over to" in lower:
                m = re.search(r'(?:turn the floor over to|hand it over to|turn over to)\s+([A-Za-z\.\s]+)', lower)
                if m:
                    yield_match = m.group(1).title().strip(" ,.")

            # Assign speaker for this segment
            assigned_spk = current_speaker
            if pending_yield:
                assigned_spk = pending_yield
                pending_yield = None
            elif roster_match and ("present" in lower or "here" in lower or "speaking" in lower or "aye" in lower):
                assigned_spk = roster_match
            elif cue_role:
                assigned_spk = cue_role

            if yield_match:
                pending_yield = yield_match

            current_speaker = assigned_spk
            healed_segments.append({
                "ts": seg.get("ts", "00:00:00"),
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "speaker": assigned_spk,
                "text": raw_text
            })

        # Coalesce consecutive segments spoken by the same speaker
        coalesced_blocks = []
        current_block = None

        for s in healed_segments:
            spk = s["speaker"]
            text = s["text"]

            if current_block is None:
                current_block = {
                    "ts": s["ts"],
                    "start": s["start"],
                    "end": s["end"],
                    "speaker": spk,
                    "text": text
                }
            elif current_block["speaker"] == spk:
                # Merge into current paragraph with boundary overlap cleanup
                clean_next = deduplicate_overlap(current_block["text"], text)
                if clean_next:
                    current_block["text"] += " " + clean_next
                current_block["end"] = s["end"]
            else:
                coalesced_blocks.append(current_block)
                current_block = {
                    "ts": s["ts"],
                    "start": s["start"],
                    "end": s["end"],
                    "speaker": spk,
                    "text": text
                }

        if current_block:
            coalesced_blocks.append(current_block)

        return coalesced_blocks
