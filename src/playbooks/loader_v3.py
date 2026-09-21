"""Playbook Loader with JSON Schema v7 Validation (v3).
<!-- v3 – JSON Schema v7 draft validation, strict syntax checking, parliamentary presiding role detection -->
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

try:
    import jsonschema
    from jsonschema import Draft7Validator
except ImportError:
    jsonschema = None
    Draft7Validator = None

from config_v3 import PLAYBOOKS_DIR, DEFAULT_PLAYBOOK, PLAYBOOK_SCHEMA_PATH


class PlaybookValidationError(Exception):
    """Raised when a playbook fails schema validation."""
    pass


# Embedded fallback schema in case file is absent
EMBEDDED_SCHEMA_V7 = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Universal Transcriber Domain Playbook Schema",
    "type": "object",
    "required": ["name", "default_role", "roles", "cues"],
    "properties": {
        "$schema": {"type": "string"},
        "name": {"type": "string", "pattern": "^[a-zA-Z0-9_-]+$", "minLength": 1, "maxLength": 64},
        "version": {"type": "string"},
        "description": {"type": "string"},
        "default_role": {"type": "string", "minLength": 1},
        "roles": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "cues": {
            "type": "object",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        },
        "default_roster": {"type": "array", "items": {"type": "string"}},
        "chair_roles": {"type": "array", "items": {"type": "string"}},
        "affirmative_cues": {"type": "array", "items": {"type": "string"}},
        "negative_cues": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}


def load_playbook_schema() -> Dict[str, Any]:
    """Load schema from schema_v1.json or use embedded schema."""
    if PLAYBOOK_SCHEMA_PATH.exists():
        try:
            return json.loads(PLAYBOOK_SCHEMA_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return EMBEDDED_SCHEMA_V7


class PlaybookV3:
    """Represents a validated domain playbook with parliamentary roll-call metadata."""

    def __init__(self, data: Dict[str, Any], filepath: Optional[Path] = None):
        self._validate_schema(data)
        self.name: str = data["name"]
        self.version: str = data.get("version", "v1")
        self.description: str = data.get("description", "")
        self.default_role: str = data.get("default_role", "Speaker")
        self.roles: List[str] = data.get("roles", [self.default_role])
        self.cues: Dict[str, List[str]] = data.get("cues", {})
        self.default_roster: List[str] = data.get("default_roster", [])

        # Presiding and parliamentary vote heuristics
        self.chair_roles: List[str] = data.get("chair_roles", [
            "Chair", "Vice Chair", "President", "Moderator", "Mayor", "Meeting Leader"
        ])
        self.affirmative_cues: List[str] = data.get("affirmative_cues", [
            "aye", "yes", "present", "here", "in favor", "support", "approve"
        ])
        self.negative_cues: List[str] = data.get("negative_cues", [
            "no", "nay", "opposed", "abstain", "recuse"
        ])

        self.filepath: Optional[Path] = filepath

    @staticmethod
    def _validate_schema(data: Dict[str, Any]) -> None:
        """Validate data dictionary strictly against JSON Schema v7."""
        if not isinstance(data, dict):
            raise PlaybookValidationError("Playbook root must be a JSON object.")

        if Draft7Validator is not None:
            schema = load_playbook_schema()
            validator = Draft7Validator(schema)
            errors = list(validator.iter_errors(data))
            if errors:
                err_messages = [f"{e.json_path or 'root'}: {e.message}" for e in errors]
                raise PlaybookValidationError(f"Schema validation failed: {'; '.join(err_messages)}")
        else:
            # Fallback manual validation if jsonschema is unavailable
            if "name" not in data or not isinstance(data["name"], str) or not data["name"]:
                raise PlaybookValidationError("Playbook missing required 'name' string field.")
            if "default_role" not in data or not isinstance(data["default_role"], str):
                raise PlaybookValidationError("Playbook missing required 'default_role' string field.")
            if "roles" not in data or not isinstance(data["roles"], list) or not data["roles"]:
                raise PlaybookValidationError("'roles' field must be a non-empty list of strings.")
            if "cues" not in data or not isinstance(data["cues"], dict):
                raise PlaybookValidationError("'cues' field must be a dictionary of phrase lists.")

    def is_chair_role(self, role_name: Optional[str]) -> bool:
        """Determine if a role title has parliamentary presiding authority."""
        if not role_name:
            return False
        clean = role_name.strip().lower()
        return any(c.lower() in clean for c in self.chair_roles)

    def detect_role(self, text: str) -> Optional[str]:
        """Match conversational cues using strict word boundaries."""
        if not text:
            return None
        lower = text.lower()
        for role_key, phrases in self.cues.items():
            for phrase in phrases:
                pattern = r'\b' + re.escape(phrase.lower()) + r'\b'
                if re.search(pattern, lower):
                    return role_key.replace("_", " ").title()
        return None

    def match_roster(self, text: str) -> Optional[str]:
        """Check if any known roster member is mentioned using exact word boundaries."""
        if not text or not self.default_roster:
            return None
        lower = text.lower()
        for member in self.default_roster:
            # Match full name with word boundaries
            pattern_full = r'\b' + re.escape(member.lower()) + r'\b'
            if re.search(pattern_full, lower):
                return member
            # Match last name if distinct (> 3 characters)
            parts = member.split()
            if parts:
                last_name = parts[-1].lower()
                if len(last_name) > 3:
                    pattern_last = r'\b' + re.escape(last_name) + r'\b'
                    if re.search(pattern_last, lower):
                        return member
        return None


Playbook = PlaybookV3


class PlaybookLoaderV3:
    """Discovers, validates, and loads domain playbooks with JSON Schema v7."""

    def __init__(self, playbooks_dir: Path = PLAYBOOKS_DIR):
        self.playbooks_dir = playbooks_dir

    @staticmethod
    def validate_dict(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate a dictionary against the playbook schema without creating an instance."""
        try:
            PlaybookV3(data)
            return True, None
        except PlaybookValidationError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected validation error: {e}"

    def list_available(self) -> List[Dict[str, Any]]:
        """List all valid domain playbooks discovered in the playbooks directory."""
        results = []
        if not self.playbooks_dir.exists():
            return results

        # Group by base name to pick the latest version (e.g. municipal_meetings_v2 > v1)
        files_by_base: Dict[str, Path] = {}
        for p in sorted(self.playbooks_dir.glob("*.json")):
            if p.name.startswith("schema_"):
                continue
            base = re.sub(r'_v\d+$', '', p.stem)
            files_by_base[base] = p

        for base, p in sorted(files_by_base.items()):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                pb = PlaybookV3(data, filepath=p)
                results.append({
                    "name": pb.name,
                    "version": pb.version,
                    "description": pb.description,
                    "default_role": pb.default_role,
                    "roles": pb.roles,
                    "roster_count": len(pb.default_roster),
                    "file": str(p),
                })
            except Exception:
                continue
        return results

    def load(self, name: Optional[str] = None) -> PlaybookV3:
        """Load a playbook by name or return the default validated playbook."""
        target_name = (name or DEFAULT_PLAYBOOK).strip().lower()
        target_base = re.sub(r'_v\d+$', '', target_name)

        versioned_candidates = sorted(
            self.playbooks_dir.glob(f"{target_base}_v*.json"),
            key=lambda p: [int(x) if x.isdigit() else x for x in re.findall(r'\d+', p.stem)],
            reverse=True,
        )
        candidates = versioned_candidates + [
            self.playbooks_dir / f"{target_base}.json",
            self.playbooks_dir / f"{target_name}.json",
        ]
        if target_base in ("general", "general_speech"):
            alt = "general_speech" if target_base == "general" else "general"
            candidates.extend([
                self.playbooks_dir / f"{alt}_v1.json",
                self.playbooks_dir / f"{alt}.json",
            ])
        for c in candidates:
            if c.exists():
                try:
                    data = json.loads(c.read_text(encoding="utf-8"))
                    return PlaybookV3(data, filepath=c)
                except Exception:
                    continue

        default_file = self.playbooks_dir / f"{DEFAULT_PLAYBOOK}_v1.json"
        if default_file.exists():
            try:
                data = json.loads(default_file.read_text(encoding="utf-8"))
                return PlaybookV3(data, filepath=default_file)
            except Exception:
                pass

        return PlaybookV3({
            "name": "default",
            "version": "v3",
            "description": "Fallback domain-agnostic playbook",
            "default_role": "Speaker",
            "roles": ["Speaker"],
            "cues": {},
        })


PlaybookLoader = PlaybookLoaderV3
