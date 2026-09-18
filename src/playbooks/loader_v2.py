"""Playbook Loader and Anchored Cue Matcher (v2).
<!-- v2 – Schema validation, word-boundary regex anchoring (\b), strict roster matching -->
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from config_v2 import PLAYBOOKS_DIR, DEFAULT_PLAYBOOK


class PlaybookValidationError(Exception):
    """Raised when a playbook fails schema validation."""
    pass


class Playbook:
    """Represents a validated domain playbook."""

    def __init__(self, data: Dict[str, Any], filepath: Optional[Path] = None):
        self._validate_schema(data)
        self.name: str = data["name"]
        self.version: str = data.get("version", "v1")
        self.description: str = data.get("description", "")
        self.default_role: str = data.get("default_role", "Speaker")
        self.roles: List[str] = data.get("roles", [self.default_role])
        self.cues: Dict[str, List[str]] = data.get("cues", {})
        self.default_roster: List[str] = data.get("default_roster", [])
        self.filepath: Optional[Path] = filepath

    @staticmethod
    def _validate_schema(data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise PlaybookValidationError("Playbook root must be a JSON object.")
        if "name" not in data or not isinstance(data["name"], str):
            raise PlaybookValidationError("Playbook missing required 'name' string field.")
        if "roles" in data and not isinstance(data["roles"], list):
            raise PlaybookValidationError("'roles' field must be a list of strings.")
        if "cues" in data and not isinstance(data["cues"], dict):
            raise PlaybookValidationError("'cues' field must be a dictionary of phrase lists.")

    def detect_role(self, text: str) -> Optional[str]:
        """Match conversational cues using strict word boundaries to eliminate polysemy false positives."""
        if not text:
            return None
        lower = text.lower()
        for role_key, phrases in self.cues.items():
            for phrase in phrases:
                # Finding R3-03: Word boundary anchoring
                pattern = r'\b' + re.escape(phrase.lower()) + r'\b'
                if re.search(pattern, lower):
                    return role_key.replace("_", " ").title()
        return None

    def match_roster(self, text: str) -> Optional[str]:
        """Check if any known roster member is matched using exact word boundaries."""
        if not text or not self.default_roster:
            return None
        lower = text.lower()
        for member in self.default_roster:
            # Check full name with word boundaries
            pattern_full = r'\b' + re.escape(member.lower()) + r'\b'
            if re.search(pattern_full, lower):
                return member
            # Check last name if distinct (> 3 chars)
            parts = member.split()
            if parts:
                last_name = parts[-1].lower()
                if len(last_name) > 3:
                    pattern_last = r'\b' + re.escape(last_name) + r'\b'
                    if re.search(pattern_last, lower):
                        return member
        return None


class PlaybookLoader:
    """Manages discovery, validation, and loading of domain playbooks."""

    def __init__(self, playbooks_dir: Path = PLAYBOOKS_DIR):
        self.playbooks_dir = playbooks_dir

    def list_available(self) -> List[Dict[str, str]]:
        """List all available validated playbooks."""
        results = []
        if not self.playbooks_dir.exists():
            return results
        for p in sorted(self.playbooks_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                pb = Playbook(data, filepath=p)
                results.append({
                    "name": pb.name,
                    "description": pb.description,
                    "default_role": pb.default_role,
                    "file": str(p),
                })
            except Exception:
                continue
        return results

    def load(self, name: Optional[str] = None) -> Playbook:
        """Load a playbook by name or return the validated default."""
        target_name = (name or DEFAULT_PLAYBOOK).strip().lower()
        candidates = [
            self.playbooks_dir / f"{target_name}_v2.json",
            self.playbooks_dir / f"{target_name}_v1.json",
            self.playbooks_dir / f"{target_name}.json",
        ]
        for c in candidates:
            if c.exists():
                try:
                    data = json.loads(c.read_text(encoding="utf-8"))
                    return Playbook(data, filepath=c)
                except Exception:
                    break

        default_file = self.playbooks_dir / f"{DEFAULT_PLAYBOOK}_v1.json"
        if default_file.exists():
            data = json.loads(default_file.read_text(encoding="utf-8"))
            return Playbook(data, filepath=default_file)

        return Playbook({
            "name": "default",
            "version": "v2",
            "description": "Fallback general playbook",
            "default_role": "Speaker",
            "roles": ["Speaker"],
            "cues": {}
        })
