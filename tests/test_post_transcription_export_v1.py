"""Tests for Post-Transcription Local Folder & Multi-Format File Creation Guarantees (v1).
<!-- v1 – Automated verification that local folders and all 6 formats (.md, .txt, .srt, .vtt, .docx, .json) are created strictly after all steps succeed -->
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.engine.export_v4 import TranscriptExporterV4
from src.engine.pipeline_v6 import TranscriptionPipelineV6
from app_v6 import app


class TestPostTranscriptionExportV1(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.exporter = TranscriptExporterV4(base_output_dir=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_exporter_creates_all_six_formats_locally(self):
        """Exporter must create local folder and all 6 offered formats (.md, .txt, .srt, .vtt, .docx, .json)."""
        blocks = [
            {"speaker": "Chair", "ts": "00:00:01", "start": 1.0, "end": 4.0, "text": "Call to order."},
            {"speaker": "Member", "ts": "00:00:05", "start": 5.0, "end": 8.0, "text": "Second the motion."},
        ]
        metadata = {
            "title": "Town Board Hearing",
            "source": "https://www.youtube.com/watch?v=mock_hearing_1",
            "date": "2026-09-21",
            "duration_str": "00:00:08",
        }

        res = self.exporter.export(
            blocks=blocks,
            metadata=metadata,
            custom_dir=self.tmp_dir,
            custom_name="Town Board Hearing",
        )

        target_dir = Path(res["dir"])
        self.assertTrue(target_dir.exists())
        self.assertTrue(target_dir.is_dir())

        # Check all 6 files exist on disk
        for fmt in ["md", "txt", "srt", "vtt", "docx", "json"]:
            fpath = Path(res[fmt])
            self.assertTrue(fpath.exists(), f"Missing expected format: {fmt}")
            self.assertTrue(fpath.is_file())
            self.assertGreater(fpath.stat().st_size, 0, f"File {fmt} is empty")

        # Verify content includes meeting name and source URL
        md_content = Path(res["md"]).read_text(encoding="utf-8")
        self.assertIn("Town Board Hearing", md_content)
        self.assertIn("https://www.youtube.com/watch?v=mock_hearing_1", md_content)

        txt_content = Path(res["txt"]).read_text(encoding="utf-8")
        self.assertIn("Town Board Hearing", txt_content)
        self.assertIn("https://www.youtube.com/watch?v=mock_hearing_1", txt_content)

        json_content = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
        self.assertEqual(json_content["meeting_name"], "Town Board Hearing")
        self.assertEqual(json_content["source_url"], "https://www.youtube.com/watch?v=mock_hearing_1")

    def test_pipeline_failure_before_step_6_leaves_no_export_folder(self):
        """If an error occurs during ASR or earlier pipeline steps, no folder or transcript files are created on disk."""
        pipeline = TranscriptionPipelineV6(output_dir=self.tmp_dir)

        # Mock ingest to return valid wav, but mock ASR to raise an error
        mock_meta = {
            "source": "https://www.youtube.com/watch?v=test_fail",
            "title": "Unfinished Video",
            "date": "2026-09-21",
            "duration": 10.0,
            "duration_str": "00:00:10",
        }

        with patch.object(pipeline.ingestor, "extract_audio", return_value=(self.tmp_dir / "audio.wav", mock_meta)):
            with patch.object(pipeline.transcriber, "transcribe_streaming", side_effect=RuntimeError("Metal ASR memory allocation failure")):
                with self.assertRaises(RuntimeError):
                    pipeline.process(
                        source="https://www.youtube.com/watch?v=test_fail",
                        custom_name="Unfinished Video",
                    )

        # Confirm NO export folder was created on disk
        created_dirs = [d for d in self.tmp_dir.iterdir() if d.is_dir()]
        self.assertEqual(len(created_dirs), 0, f"Expected 0 export dirs, found: {created_dirs}")

    def test_api_open_folder_security_and_execution(self):
        """POST /api/open-folder rejects directory escape and runs /usr/bin/open for valid paths."""
        client = app.test_client()

        # 1. Missing parameter
        resp = client.post("/api/open-folder", json={})
        self.assertEqual(resp.status_code, 400)

        # 2. Directory escape (outside TRANSCRIPTS_DIR)
        resp = client.post("/api/open-folder", json={"path": "/etc/passwd"})
        self.assertEqual(resp.status_code, 403)

        # 3. Non-existent folder within transcripts root
        from config_v4 import TRANSCRIPTS_DIR
        resp = client.post("/api/open-folder", json={"path": str(TRANSCRIPTS_DIR / "non_existent_folder_xyz_123")})
        self.assertEqual(resp.status_code, 404)

        # 4. Valid directory with subprocess.run mocked
        test_valid_dir = TRANSCRIPTS_DIR / "test_valid_export_folder"
        test_valid_dir.mkdir(parents=True, exist_ok=True)
        try:
            with patch("app_v6.subprocess.run") as mock_run:
                resp = client.post("/api/open-folder", json={"path": str(test_valid_dir)})
                self.assertEqual(resp.status_code, 200)
                data = resp.get_json()
                self.assertTrue(data["success"])
                mock_run.assert_called_once()
        finally:
            if test_valid_dir.exists():
                test_valid_dir.rmdir()

    def test_playlist_step_by_step_export_creates_local_folder_and_six_files_only_after_steps_completed(self):
        """In a playlist, each completed item gets its own local folder with all 6 formats strictly after steps complete."""
        from src.engine.playlist_v1 import PlaylistManagerV1

        pipeline = TranscriptionPipelineV6(output_dir=self.tmp_dir / "out")
        playlist_base = self.tmp_dir / "Playlists"
        playlist_base.mkdir(parents=True, exist_ok=True)

        mock_playlist_meta = {
            "source_url": "https://www.youtube.com/playlist?list=PL_TEST_EXPORT",
            "title": "Town Board Series",
            "item_count": 2,
            "total_duration_seconds": 60,
            "total_duration_str": "00:01:00",
            "iso_date": "20260921",
            "items": [
                {
                    "index": 1,
                    "id": "vid_1",
                    "title": "Meeting Part 1",
                    "url": "https://www.youtube.com/watch?v=vid_1",
                    "duration_seconds": 30,
                    "duration_str": "00:00:30",
                    "upload_date": "",
                    "status": "PENDING",
                },
                {
                    "index": 2,
                    "id": "vid_2",
                    "title": "Meeting Part 2",
                    "url": "https://www.youtube.com/watch?v=vid_2",
                    "duration_seconds": 30,
                    "duration_str": "00:00:30",
                    "upload_date": "",
                    "status": "PENDING",
                }
            ]
        }

        # Mock process to succeed for item 1 and fail for item 2
        def mock_process(source, output_dir=None, custom_name=None, direct_dir=False, **kwargs):
            if "vid_2" in source:
                raise RuntimeError("Audio extraction timeout")

            target = Path(output_dir) if direct_dir and output_dir else Path(output_dir) / custom_name
            target.mkdir(parents=True, exist_ok=True)
            files = {}
            for fmt in ["md", "txt", "srt", "vtt", "docx", "json"]:
                f = target / f"{custom_name}.{fmt}"
                f.write_text(f"Content for {fmt}", encoding="utf-8")
                files[fmt] = str(f)

            return {
                "job_id": "job_item1",
                "title": custom_name,
                "iso_name": custom_name,
                "iso_output_dir": str(target),
                "export_dir": str(target),
                "duration": 30.0,
                "files": files,
            }

        with patch.object(PlaylistManagerV1, "inspect_playlist", return_value=mock_playlist_meta):
            with patch.object(pipeline, "process", side_effect=mock_process):
                res = pipeline.process_playlist(
                    source="https://www.youtube.com/playlist?list=PL_TEST_EXPORT",
                    output_dir=playlist_base,
                )

        playlist_dir = Path(res["playlist_dir"])
        self.assertTrue(playlist_dir.exists())

        # Item 1 succeeded: folder must exist with all 6 formats
        item1_folder = playlist_dir / "001_Meeting_Part_1"
        self.assertTrue(item1_folder.exists(), f"Item 1 folder missing: {item1_folder}")
        for fmt in ["md", "txt", "srt", "vtt", "docx", "json"]:
            self.assertTrue((item1_folder / f"Meeting Part 1.{fmt}").exists(), f"Missing {fmt} in {item1_folder}")

        # Item 1 placeholder file must be gone
        self.assertFalse((playlist_dir / "001_20260921_Meeting_Part_1.pending").exists())

        # Item 2 failed: its folder should NOT have been created on disk
        item2_folder = playlist_dir / "002_Meeting_Part_2"
        self.assertFalse(item2_folder.exists(), f"Item 2 folder should not exist: {item2_folder}")

        # Item 2 placeholder remains pending for resume
        self.assertTrue((playlist_dir / "002_20260921_Meeting_Part_2.pending").exists())


if __name__ == "__main__":
    unittest.main()

