"""Self-Healing Dialogue & Parliamentary Roll-Call FSM Engine (v3).
<!-- v3 – Parliamentary roll-call finite state machine eliminating chair-member inversion, acoustic-lexical fusion -->
"""

from __future__ import annotations

import re
from typing import List, Dict, Any, Optional, Set

from src.playbooks.loader_v3 import PlaybookV3, Playbook

# Bounds for paragraph coalescing
MAX_INTER_TURN_GAP_SECONDS = 3.0    # Gaps exceeding 3.0s (e.g. recesses or pauses) break paragraph
MAX_BLOCK_DURATION_SECONDS = 60.0   # Prevents monolithic text walls

# Legitimate English repetition doublets (preserve grammatical double words)
GRAMMATICAL_DOUBLETS = {"that", "had", "which"}

# Roll-Call FSM States
STATE_NORMAL = "NORMAL"
STATE_ROLL_CALL_ACTIVE = "ROLL_CALL_ACTIVE"
STATE_AWAITING_MEMBER_VOTE = "AWAITING_MEMBER_VOTE"


def clean_stutters(text: str) -> str:
    """Strip acoustic repeated words while preserving valid grammatical doublets."""
    if not text:
        return ""

    def replace_word(m):
        w = m.group(1)
        if w.lower() in GRAMMATICAL_DOUBLETS:
            return m.group(0)
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


class RollCallFSM:
    """Finite State Machine tracking parliamentary roll calls to prevent speaker inversion."""

    def __init__(self, playbook: PlaybookV3):
        self.playbook = playbook
        self.state = STATE_NORMAL
        self.chair_speaker = "Chair"
        self.pending_member: Optional[str] = None
        self.cluster_to_role: Dict[str, str] = {}

        # Roll call trigger patterns
        self.roll_call_start_patterns = [
            r'\broll\s+call\b',
            r'\bcall\s+the\s+roll\b',
            r'\btake\s+the\s+roll\b',
            r'\broll\s+call\s+vote\b',
            r'\broll\s+is\s+called\b',
        ]

        # Roll call termination patterns
        self.roll_call_end_patterns = [
            r'\bmotion\s+(?:carries|passes|is\s+adopted|fails|defeated)\b',
            r'\bpasses\s+(?:unanimously|unanimous)\b',
            r'\bvoting\s+is\s+(?:closed|concluded)\b',
            r'\bquorum\s+is\s+present\b',
            r'\ball\s+members\s+present\b',
            r'\bwe\s+have\s+a\s+quorum\b',
        ]

    def _is_roll_call_start(self, lower_text: str) -> bool:
        return any(re.search(pat, lower_text) for pat in self.roll_call_start_patterns)

    def _is_roll_call_end(self, lower_text: str) -> bool:
        return any(re.search(pat, lower_text) for pat in self.roll_call_end_patterns)

    def _is_vote_or_attendance_response(self, text: str) -> bool:
        lower = text.lower().strip(" .,?!")
        words = lower.split()
        if not words:
            return False

        # Pure response (e.g. "Aye", "Present", "Yes", "No", "Here", "Abstain")
        if any(lower == aff for aff in self.playbook.affirmative_cues):
            return True
        if any(lower == neg for neg in self.playbook.negative_cues):
            return True

        # Short response starting with affirmative or negative cue
        if words[0] in ("aye", "yes", "present", "here", "no", "nay", "abstain"):
            return True

        # Explicit voting phrasing (e.g. "I vote aye", "votes yes", "voting in favor")
        if re.search(r'\b(?:vote|votes|voting)\s+(?:aye|yes|no|nay|in\s+favor|present|abstain)\b', lower):
            return True

        # General regex check for vote response cues without arbitrary length limits
        has_affirmative = any(re.search(r'\b' + re.escape(c) + r'\b', lower) for c in self.playbook.affirmative_cues)
        has_negative = any(re.search(r'\b' + re.escape(c) + r'\b', lower) for c in self.playbook.negative_cues)
        if has_affirmative or has_negative:
            return True

        return False

    def process_turn(
        self,
        raw_text: str,
        current_speaker: str,
        cue_role: Optional[str],
        roster_match: Optional[str],
        acoustic_speaker: Optional[str] = None,
    ) -> str:
        """Evaluate dialogue turn through FSM and return the true speaker assignment."""
        lower = raw_text.lower()

        # Check for roll call start cue
        if self._is_roll_call_start(lower):
            self.state = STATE_ROLL_CALL_ACTIVE
            if self.playbook.is_chair_role(cue_role or current_speaker):
                self.chair_speaker = cue_role or current_speaker
            else:
                self.chair_speaker = "Chair"
            if acoustic_speaker and acoustic_speaker.startswith("Speaker_"):
                self.cluster_to_role[acoustic_speaker] = self.chair_speaker

        # Check for roll call termination cue
        if self.state in (STATE_ROLL_CALL_ACTIVE, STATE_AWAITING_MEMBER_VOTE) and self._is_roll_call_end(lower):
            self.state = STATE_NORMAL
            self.pending_member = None
            if acoustic_speaker and acoustic_speaker.startswith("Speaker_"):
                self.cluster_to_role[acoustic_speaker] = self.chair_speaker
            return self.chair_speaker

        # State 1: Awaiting response from called member
        if self.state == STATE_AWAITING_MEMBER_VOTE and self.pending_member:
            # If chair skipped and called a new member
            if roster_match and roster_match != self.pending_member:
                self.pending_member = roster_match
                if acoustic_speaker and acoustic_speaker.startswith("Speaker_"):
                    self.cluster_to_role[acoustic_speaker] = self.chair_speaker
                return self.chair_speaker

            # Check if this utterance is the response from the called member
            is_vote = self._is_vote_or_attendance_response(raw_text)
            is_addressing_chair = bool(re.search(r'\b(?:mr\.|madam|mister)?\s*(?:chair|chairman|chairwoman|president|moderator)\b', lower))

            if is_vote or is_addressing_chair or (acoustic_speaker and acoustic_speaker != self._get_chair_cluster()):
                attributed_member = self.pending_member
                if acoustic_speaker and acoustic_speaker.startswith("Speaker_"):
                    self.cluster_to_role[acoustic_speaker] = attributed_member
                if is_vote:
                    self.state = STATE_ROLL_CALL_ACTIVE
                    self.pending_member = None
                return attributed_member

        # State 2: Active roll call in progress
        if self.state in (STATE_ROLL_CALL_ACTIVE, STATE_AWAITING_MEMBER_VOTE):
            if roster_match:
                # Critical inversion fix: When in roll call and a roster name is spoken
                # as a query or invitation by the chair, the speaker is the CHAIR!
                self.pending_member = roster_match
                self.state = STATE_AWAITING_MEMBER_VOTE
                if acoustic_speaker and acoustic_speaker.startswith("Speaker_"):
                    self.cluster_to_role[acoustic_speaker] = self.chair_speaker
                return self.chair_speaker

            # If chair speaks other procedural text during roll call
            if cue_role and self.playbook.is_chair_role(cue_role):
                if acoustic_speaker and acoustic_speaker.startswith("Speaker_"):
                    self.cluster_to_role[acoustic_speaker] = cue_role
                return cue_role
            if self.chair_speaker:
                if acoustic_speaker and acoustic_speaker.startswith("Speaker_"):
                    self.cluster_to_role[acoustic_speaker] = self.chair_speaker
                return self.chair_speaker

        # State 3: NORMAL state
        if roster_match:
            if self._is_vote_or_attendance_response(raw_text):
                if acoustic_speaker and acoustic_speaker.startswith("Speaker_"):
                    self.cluster_to_role[acoustic_speaker] = roster_match
                return roster_match
            if self.playbook.is_chair_role(current_speaker) or (cue_role and self.playbook.is_chair_role(cue_role)):
                res = current_speaker or "Chair"
                if acoustic_speaker and acoustic_speaker.startswith("Speaker_"):
                    self.cluster_to_role[acoustic_speaker] = res
                return res

        if cue_role:
            if acoustic_speaker and acoustic_speaker.startswith("Speaker_"):
                self.cluster_to_role[acoustic_speaker] = cue_role
            return cue_role

        # Acoustic-lexical fusion: check if acoustic cluster was previously identified with a role
        if acoustic_speaker:
            if acoustic_speaker in self.cluster_to_role:
                return self.cluster_to_role[acoustic_speaker]
            # Preserve the acoustic cluster identity from neural diarization
            return acoustic_speaker

        return current_speaker

    def _get_chair_cluster(self) -> Optional[str]:
        for cluster, role in self.cluster_to_role.items():
            if self.playbook.is_chair_role(role) or role == self.chair_speaker:
                return cluster
        return None


class TurnCoalescerV3:
    """Applies domain playbooks, Roll-Call FSM, temporal gap bounds, and turn coalescing."""

    def __init__(self, playbook: PlaybookV3):
        self.playbook = playbook
        self.fsm = RollCallFSM(playbook=playbook)

    def heal_and_coalesce(
        self,
        segments: List[Dict[str, Any]],
        initial_speaker: Optional[str] = None,
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
            acoustic_spk = seg.get("speaker")

            # 1. Roster matching with word boundaries
            roster_match = self.playbook.match_roster(raw_text)

            # 2. Playbook anchored cue matching
            cue_role = self.playbook.detect_role(raw_text)

            # 3. Yield detection with strict name bounds
            yield_match = None
            if any(k in lower for k in ["turn the floor over to", "hand it over to", "turn over to", "recognize"]):
                m = re.search(
                    r'(?:turn the floor over to|hand it over to|turn over to|recognize)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})',
                    raw_text,
                )
                if m:
                    yield_match = m.group(1).strip()

            # 4. Determine assigned speaker via Roll-Call FSM
            if pending_yield:
                assigned_spk = pending_yield
                pending_yield = None
            else:
                assigned_spk = self.fsm.process_turn(
                    raw_text=raw_text,
                    current_speaker=current_speaker,
                    cue_role=cue_role,
                    roster_match=roster_match,
                    acoustic_speaker=acoustic_spk,
                )

            if yield_match:
                pending_yield = yield_match

            current_speaker = assigned_spk
            healed_segments.append({
                "ts": seg.get("ts", "00:00:00"),
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "speaker": assigned_spk,
                "text": raw_text,
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
                    "text": text,
                }
            else:
                is_same_speaker = (current_block["speaker"] == spk)
                time_gap = start_s - current_block["end"]
                total_duration = end_s - current_block["start"]

                if is_same_speaker and (0.0 <= time_gap <= MAX_INTER_TURN_GAP_SECONDS) and (total_duration <= MAX_BLOCK_DURATION_SECONDS):
                    clean_next = safe_deduplicate_overlap(current_block["text"], text)
                    if clean_next:
                        current_block["text"] += " " + clean_next
                    current_block["end"] = end_s
                else:
                    coalesced_blocks.append(current_block)
                    current_block = {
                        "ts": s["ts"],
                        "start": start_s,
                        "end": end_s,
                        "speaker": spk,
                        "text": text,
                    }

        if current_block:
            coalesced_blocks.append(current_block)

        return coalesced_blocks


TurnCoalescer = TurnCoalescerV3
