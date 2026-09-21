"""Tests for YouTube Playlist Breakdown, Staging Manifests, Placeholders, and Step-by-Step Processing (v1).
<!-- v1 – Automated verification of playlist inspection, placeholder generation, resume logic, and error isolation -->
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.engine.playlist_v1 import (
    PlaylistManagerV1,
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_FAILED,
    format_duration,
    sanitize_filename,
)
from src.engine.pipeline_v6 import TranscriptionPipelineV6
from app_v6 import app


class TestPlaylistStagingV1(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.mgr = PlaylistManagerV1(base_playlists_dir=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_sanitize_filename_and_duration_formatter(self):
        """Sanitizer strips illegal characters and duration formatter returns standard HH:MM:SS."""
        self.assertEqual(sanitize_filename("2026/09/21: Planning? Board *Hearing*"), "2026_09_21__Planning__Board__Hearing")
        self.assertEqual(format_duration(3665), "01:01:05")
        self.assertEqual(format_duration(45), "00:00:45")

    def test_inspect_playlist_mock(self):
        """yt-dlp flat-playlist json output is correctly decomposed into video items."""
        mock_dump = {
            "title": "Town Council Series 2026",
            "entries": [
                {
                    "id": "vid_001",
                    "title": "Meeting 1 - Budget Review",
                    "duration": 3600,
                    "upload_date": "20260901",
                    "url": "https://www.youtube.com/watch?v=vid_001"
                },
                {
                    "id": "vid_002",
                    "title": "Meeting 2 - Public Hearing",
                    "duration": 1800,
                    "upload_date": "20260908",
                    "url": "https://www.youtube.com/watch?v=vid_002"
                }
            ]
        }

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(mock_dump)

        with patch("shutil.which", return_value="/usr/local/bin/yt-dlp"):
            with patch("subprocess.run", return_value=mock_proc):
                meta = self.mgr.inspect_playlist("https://www.youtube.com/playlist?list=PL123")

        self.assertEqual(meta["title"], "Town Council Series 2026")
        self.assertEqual(meta["item_count"], 2)
        self.assertEqual(meta["total_duration_seconds"], 5400)
        self.assertEqual(meta["total_duration_str"], "01:30:00")
        self.assertEqual(len(meta["items"]), 2)
        self.assertEqual(meta["items"][0]["title"], "Meeting 1 - Budget Review")
        self.assertEqual(meta["items"][1]["id"], "vid_002")

    def test_stage_playlist_creates_manifest_index_and_placeholders(self):
        """Staging creates dedicated folder, playlist_manifest.json, PLAYLIST_INDEX.md, and .pending placeholder files."""
        meta = {
            "source_url": "https://www.youtube.com/playlist?list=PL999",
            "title": "Planning Board Hearings",
            "item_count": 2,
            "total_duration_seconds": 2400,
            "total_duration_str": "00:40:00",
            "iso_date": "20260921",
            "items": [
                {
                    "index": 1,
                    "id": "vid_a",
                    "title": "Hearing Part 1",
                    "url": "https://www.youtube.com/watch?v=vid_a",
                    "duration_seconds": 1200,
                    "duration_str": "00:20:00",
                    "upload_date": "2026-09-20",
                    "status": STATUS_PENDING,
                },
                {
                    "index": 2,
                    "id": "vid_b",
                    "title": "Hearing Part 2",
                    "url": "https://www.youtube.com/watch?v=vid_b",
                    "duration_seconds": 1200,
                    "duration_str": "00:20:00",
                    "upload_date": "2026-09-21",
                    "status": STATUS_PENDING,
                }
            ]
        }

        playlist_dir, manifest_path = self.mgr.stage_playlist(meta)

        self.assertTrue(playlist_dir.exists())
        self.assertTrue(manifest_path.exists())
        index_path = playlist_dir / "PLAYLIST_INDEX.md"
        self.assertTrue(index_path.exists())

        # Check placeholder files
        placeholders = list(playlist_dir.glob("*.pending"))
        self.assertEqual(len(placeholders), 2)
        self.assertTrue(any("Hearing_Part_1.pending" in p.name for p in placeholders))
        self.assertTrue(any("Hearing_Part_2.pending" in p.name for p in placeholders))

        # Check manifest contents
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], STATUS_IN_PROGRESS)
        self.assertEqual(manifest["completed_count"], 0)
        self.assertEqual(manifest["failed_count"], 0)

        # Check markdown contents
        md_text = index_path.read_text(encoding="utf-8")
        self.assertIn("Planning Board Hearings", md_text)
        self.assertIn("Hearing Part 1", md_text)
        self.assertIn("Hearing Part 2", md_text)
        self.assertIn("Pending", md_text)

    def test_update_item_status_removes_placeholder_on_completion(self):
        """When an item is completed, its .pending placeholder is deleted and manifest counters increment."""
        meta = {
            "source_url": "https://www.youtube.com/playlist?list=PLTEST",
            "title": "Test Playlist",
            "item_count": 1,
            "total_duration_seconds": 600,
            "total_duration_str": "00:10:00",
            "iso_date": "20260921",
            "items": [
                {
                    "index": 1,
                    "id": "vid_test",
                    "title": "Solo Video",
                    "url": "https://www.youtube.com/watch?v=vid_test",
                    "duration_seconds": 600,
                    "duration_str": "00:10:00",
                    "upload_date": "2026-09-21",
                    "status": STATUS_PENDING,
                }
            ]
        }

        playlist_dir, manifest_path = self.mgr.stage_playlist(meta)
        placeholder = playlist_dir / meta["items"][0]["placeholder_file"]
        self.assertTrue(placeholder.exists())

        # Complete item
        output_mock_dir = playlist_dir / "001_20260921_Solo_Video"
        output_mock_dir.mkdir(parents=True, exist_ok=True)

        updated_manifest = self.mgr.update_item_status(
            manifest_path=manifest_path,
            item_id="vid_test",
            status=STATUS_COMPLETED,
            output_dir=output_mock_dir,
            job_id="job_mock123",
            duration_seconds=600,
        )

        # Placeholder must be deleted upon completion
        self.assertFalse(placeholder.exists())
        self.assertEqual(updated_manifest["completed_count"], 1)
        self.assertEqual(updated_manifest["pending_count"], 0)
        self.assertEqual(updated_manifest["status"], STATUS_COMPLETED)

        # Index markdown must reflect completion
        index_md = (playlist_dir / "PLAYLIST_INDEX.md").read_text(encoding="utf-8")
        self.assertIn("Completed", index_md)
        self.assertIn("001_20260921_Solo_Video", index_md)

    def test_resume_playlist_returns_only_uncompleted_items(self):
        """get_pending_items returns only pending or failed items, skipping completed ones."""
        meta = {
            "source_url": "https://www.youtube.com/playlist?list=PLRESUME",
            "title": "Resume Test",
            "item_count": 3,
            "total_duration_seconds": 900,
            "total_duration_str": "00:15:00",
            "iso_date": "20260921",
            "items": [
                {"index": 1, "id": "v1", "title": "V1", "url": "url1", "duration_seconds": 300, "duration_str": "00:05:00", "upload_date": "", "status": STATUS_PENDING},
                {"index": 2, "id": "v2", "title": "V2", "url": "url2", "duration_seconds": 300, "duration_str": "00:05:00", "upload_date": "", "status": STATUS_PENDING},
                {"index": 3, "id": "v3", "title": "V3", "url": "url3", "duration_seconds": 300, "duration_str": "00:05:00", "upload_date": "", "status": STATUS_PENDING},
            ]
        }

        playlist_dir, manifest_path = self.mgr.stage_playlist(meta)

        # Mark item 1 completed and item 2 failed
        self.mgr.update_item_status(manifest_path, "v1", STATUS_COMPLETED, output_dir=playlist_dir / "out1")
        self.mgr.update_item_status(manifest_path, "v2", STATUS_FAILED, error_message="Download 403")

        pending = self.mgr.get_pending_items(manifest_path)
        pending_ids = [p["id"] for p in pending]

        self.assertNotIn("v1", pending_ids)
        self.assertIn("v2", pending_ids)  # Failed item should be retried
        self.assertIn("v3", pending_ids)  # Pending item should be processed
        self.assertEqual(len(pending), 2)

    def test_pipeline_process_playlist_isolated_error_tolerance(self):
        """If one video fails in a playlist, the pipeline records failure and continues processing remaining videos."""
        pipeline = TranscriptionPipelineV6(output_dir=self.tmp_dir / "out")

        mock_meta = {
            "source_url": "https://www.youtube.com/playlist?list=PLISO",
            "title": "Error Isolation Test",
            "item_count": 3,
            "total_duration_seconds": 90,
            "total_duration_str": "00:01:30",
            "iso_date": "20260921",
            "items": [
                {"index": 1, "id": "pass1", "title": "Pass 1", "url": "url1", "duration_seconds": 30, "duration_str": "00:00:30", "upload_date": "", "status": STATUS_PENDING},
                {"index": 2, "id": "fail2", "title": "Fail 2", "url": "url2", "duration_seconds": 30, "duration_str": "00:00:30", "upload_date": "", "status": STATUS_PENDING},
                {"index": 3, "id": "pass3", "title": "Pass 3", "url": "url3", "duration_seconds": 30, "duration_str": "00:00:30", "upload_date": "", "status": STATUS_PENDING},
            ]
        }

        def mock_process(source, **kwargs):
            if "url2" in source:
                raise RuntimeError("Private video: HTTP 403 Forbidden")
            return {
                "job_id": f"job_{source}",
                "iso_output_dir": str(self.tmp_dir / f"exported_{source[-4:]}"),
                "duration": 30.0,
            }

        with patch.object(PlaylistManagerV1, "inspect_playlist", return_value=mock_meta):
            with patch.object(pipeline, "process", side_effect=mock_process):
                res = pipeline.process_playlist(
                    source="https://www.youtube.com/playlist?list=PLISO",
                    output_dir=self.tmp_dir / "Playlists",
                )

        manifest = res["manifest"]
        self.assertEqual(manifest["completed_count"], 2)
        self.assertEqual(manifest["failed_count"], 1)
        self.assertEqual(manifest["status"], "COMPLETED_WITH_ERRORS")
        self.assertEqual(len(res["results"]), 2)

        items = manifest["items"]
        self.assertEqual(items[0]["status"], STATUS_COMPLETED)
        self.assertEqual(items[1]["status"], STATUS_FAILED)
        self.assertIn("Private video", items[1]["error_message"])
        self.assertEqual(items[2]["status"], STATUS_COMPLETED)

    def test_web_api_playlist_inspect_endpoint(self):
        """POST /api/playlist/inspect returns parsed playlist structure and target directory."""
        client = app.test_client()
        mock_meta = {
            "source_url": "https://www.youtube.com/playlist?list=PLAPI",
            "title": "API Test Playlist",
            "item_count": 2,
            "total_duration_seconds": 600,
            "total_duration_str": "00:10:00",
            "iso_date": "20260921",
            "items": [
                {"index": 1, "id": "a", "title": "A", "url": "http://a", "duration_seconds": 300, "duration_str": "00:05:00"},
                {"index": 2, "id": "b", "title": "B", "url": "http://b", "duration_seconds": 300, "duration_str": "00:05:00"},
            ]
        }

        with patch.object(PlaylistManagerV1, "inspect_playlist", return_value=mock_meta):
            resp = client.post("/api/playlist/inspect", json={"url": "https://www.youtube.com/playlist?list=PLAPI"})

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["item_count"], 2)
        self.assertIn("API_Test_Playlist", data["target_dir"])
        self.assertEqual(len(data["items"]), 2)


if __name__ == "__main__":
    unittest.main()
