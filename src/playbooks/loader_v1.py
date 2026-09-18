"""Playbook Loader and Cue Matcher (v1)."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from config_v1 import PLAYBOOKS_DIR, DEFAULT_PLAYBOOK


class Playbook:
    """Represents a loaded domain playbook."""

    def __init__(self, data: Dict[str, Any], filepath: Optional[Path] = None):
        self.name: str = data.get("name", "custom")
        self.version: str = data.get("version", "v1")
        self.description: str = data.get("description", "")
        self.default_role: str = data.get("default_role", "Speaker")
        self.roles: List[str] = data.get("roles", [self.default_role])
        self.cues: Dict[str, List[str]] = data.get("cues", {})
        self.default_roster: List[str] = data.get("default_roster", [])
        self.filepath: Optional[Path] = filepath

    def detect_role(self, text: str) -> Optional[str]:
        """Match conversational cues against text to infer speaker role."""
        if not text:
            return None
        lower = text.lower()
        for role, phrases in self.cues.items():
            for p in phrases:
                if p in lower:
                    return role.replace("_", " ").title()
        return None

    def match_roster(self, text: str) -> Optional[str]:
        """Check if any known roster member is mentioned or identified."""
        if not text or not self.default_roster:
            return None
        lower = text.lower()
        for member in self.default_roster:
            # Check full name or last name
            parts = member.split()
            last_name = parts[-1].lower() if parts else ""
            if member.lower() in lower:
                return member
            if len(last_name) > 3 and f" {last_name}" in lower:
                return member
        return None


class PlaybookLoader:
    """Manages discovery and loading of domain playbooks."""

    def __init__(self, playbooks_dir: Path = PLAYBOOKS_DIR):
        self.playbooks_dir = playbooks_dir

    def list_available(self) -> List[Dict[str, str]]:
        """List all available playbooks."""
        results = []
        if not self.playbooks_dir.exists():
            return results
        for p in sorted(self.playbooks_dir.glob("*_v1.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                results.append({
                    "name": data.get("name", p.stem.replace("_v1", "")),
                    "description": data.get("description", ""),
                    "default_role": data.get("default_role", "Speaker"),
                    "file": str(p),
                })
            except Exception:
                continue
        return results

    def load(self, name: Optional[str] = None) -> Playbook:
        """Load a playbook by name or return the default."""
        target_name = (name or DEFAULT_PLAYBOOK).strip().lower()
        # Look for <name>_v1.json or <name>.json
        candidates = [
            self.playbooks_dir / f"{target_name}_v1.json",
            self.playbooks_dir / f"{target_name}.json",
        ]
        for c in candidates:
            if c.exists():
                try:
                    data = json.loads(c.read_text(encoding="utf-8"))
                    return Playbook(data, filepath=c)
                except Exception as e:
                    break

        # Fallback to default
        default_file = self.playbooks_dir / f"{DEFAULT_PLAYBOOK}_v1.json"
        if default_file.exists():
            data = json.loads(default_file.read_text(encoding="utf-8"))
            return Playbook(data, filepath=default_file)

        # Minimal fallback
        return Playbook({
            "name": "default",
            "version": "v1",
            "description": "Fallback general playbook",
            "default_role": "Speaker",
            "roles": ["Speaker"],
            "cues": {}
        })
