"""Tests for 'General' Category Playbook and Field Wording (Mandatory vs Optional) (v1)."""

import unittest
import json
from pathlib import Path
from src.playbooks.loader_v3 import PlaybookLoaderV3
from config_v5 import DEFAULT_PLAYBOOK, PLAYBOOKS_DIR
import app_v6


class TestGeneralCategoryAndFieldWording(unittest.TestCase):

    def setUp(self):
        self.loader = PlaybookLoaderV3()
        self.app = app_v6.app.test_client()

    def test_default_playbook_is_general(self):
        """Verify that system default playbook is 'general'."""
        self.assertEqual(DEFAULT_PLAYBOOK, "general")
        self.assertEqual(app_v6.DEFAULT_PLAYBOOK, "general")

    def test_general_playbook_file_exists_and_validates(self):
        """Verify that general_v1.json exists and conforms strictly to JSON Schema v7."""
        gen_file = PLAYBOOKS_DIR / "general_v1.json"
        self.assertTrue(gen_file.exists(), "playbooks/general_v1.json must exist")
        data = json.loads(gen_file.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "general")
        valid, err = self.loader.validate_dict(data)
        self.assertTrue(valid, f"Schema validation error: {err}")

    def test_loader_loads_general_playbook(self):
        """Verify loader loads 'general' and returns default role 'Speaker'."""
        pb = self.loader.load("general")
        self.assertIsNotNone(pb)
        self.assertEqual(pb.name, "general")
        self.assertEqual(pb.default_role, "Speaker")
        self.assertIn("Speaker", pb.roles)

    def test_loader_list_available_includes_general(self):
        """Verify that 'general' is included in list of available playbooks."""
        pbs = self.loader.list_available()
        names = [p["name"] for p in pbs]
        self.assertIn("general", names)
        # Also ensure legacy general_speech remains available for backward compatibility
        self.assertIn("general_speech", names)

    def test_api_playbooks_endpoint_includes_general(self):
        """Verify that GET /api/playbooks returns 'general'."""
        resp = self.app.get("/api/playbooks")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        names = [p["name"] for p in data]
        self.assertIn("general", names)

    def test_index_html_contains_field_wording_and_general_default(self):
        """Verify frontend static/index.html has explicit Mandatory/Optional indicators and General default."""
        html_path = Path(__file__).resolve().parent.parent / "static" / "index.html"
        content = html_path.read_text(encoding="utf-8")

        # Mandatory indicators
        self.assertIn("badge-mandatory", content)
        self.assertIn("Option A: Local Media Ingestion", content)
        self.assertIn("Option B: Media URL or Local File Path", content)
        self.assertIn("Mandatory (Option A or B)", content)

        # Optional indicators
        self.assertIn("badge-optional", content)
        self.assertIn("Custom Name / Title", content)
        self.assertIn("Category / Domain Playbook", content)
        self.assertIn("Default: General", content)
        self.assertIn("Diarization Mode", content)
        self.assertIn("Default: AHC", content)

        # Default option selected
        self.assertIn('<option value="general" selected>🌐 General (Default)</option>', content)

        # loadPlaybooks sorts general to top
        self.assertIn('pb.name === "general"', content)
        self.assertIn('General (Default)', content)


if __name__ == "__main__":
    unittest.main()
