"""Tests for Universal Transcriber Official 0.1-Beta Product Release.
<!-- v1 – Verify canonical entrypoints, version contracts, executable scripts, and schema compliance -->
"""

import json
import os
import subprocess
import unittest
from pathlib import Path

from app import app
import config
from src.playbooks.loader_v3 import PlaybookLoaderV3
from src.engine.ingest_v4 import SUPPORTED_LOCAL_EXTENSIONS


class TestRelease01Beta(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        self.base_dir = Path(__file__).parent.parent.resolve()

    def test_canonical_config_metadata(self):
        """Verify canonical config.py exposes 0.1-beta version and Sean Tyler attribution."""
        self.assertEqual(config.VERSION, "0.1.0-beta")
        self.assertEqual(config.APP_NAME, "Universal Transcriber")
        self.assertEqual(config.AUTHOR, "seanbuilds")
        self.assertEqual(config.AUTHOR_EMAIL, "ohheysean@gmail.com")

    def test_canonical_app_api_info_endpoint(self):
        """Verify canonical app.py /api/info returns version 0.1.0-beta."""
        res = self.client.get("/api/info")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("name"), "Universal Transcriber")
        self.assertEqual(data.get("version"), "0.1.0-beta")
        self.assertEqual(data.get("author"), "seanbuilds")
        self.assertTrue(data.get("metal_acceleration"))
        self.assertIn(".m4a", data.get("supported_containers", []))
        self.assertIn(".mp4", data.get("supported_containers", []))

    def test_canonical_cli_version_flag(self):
        """Verify python3 cli.py --version output."""
        res = subprocess.run(
            ["/opt/homebrew/opt/python@3.14/bin/python3", "cli.py", "--version"],
            cwd=str(self.base_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("Universal Transcriber v0.1.0-beta (@seanbuilds)", res.stdout)

    def test_executable_scripts_permissions(self):
        """Verify turnkey scripts are executable."""
        scripts = ["install.sh", "install_v1.sh", "start_app.sh", "start_app_v2.sh", "cli.py", "app.py"]
        for s in scripts:
            p = self.base_dir / s
            self.assertTrue(p.exists(), f"Script {s} must exist")
            self.assertTrue(os.access(p, os.X_OK), f"Script {s} must be executable")

    def test_all_playbooks_validate_against_schema(self):
        """Verify all playbooks strictly conform to JSON Schema v7."""
        loader = PlaybookLoaderV3()
        pbs = loader.list_available()
        self.assertGreaterEqual(len(pbs), 6)
        expected_names = {"general_speech", "municipal_meetings", "interview_podcast", "corporate_meeting", "academic_lecture", "gaming_videos"}
        found_names = {p["name"] for p in pbs}
        self.assertTrue(expected_names.issubset(found_names))

    def test_supported_media_extensions(self):
        """Verify first-class audio and video container formats."""
        required = {".m4a", ".mp3", ".mp4", ".mov", ".mkv", ".wav", ".flac", ".aac"}
        self.assertTrue(required.issubset(SUPPORTED_LOCAL_EXTENSIONS))


if __name__ == "__main__":
    unittest.main()
