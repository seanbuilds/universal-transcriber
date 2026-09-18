"""Automated Test Suite for Local Media Formats Support (.m4a, .mp3, .mp4, .mov, etc.) (v6).
<!-- v6 – First-class local media container tests: extraction, metadata probing, upload endpoint, directory scanning, and CLI local command -->
"""

import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.engine.ingest_v4 import (
    MediaIngestorV4,
    SUPPORTED_AUDIO_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    SUPPORTED_LOCAL_EXTENSIONS,
)
from src.engine.pipeline_v6 import TranscriptionPipelineV6
from src.engine.audit_v1 import TranscriptionAuditLogger
from app_v5 import app, UPLOADS_DIR
import cli_v6


class TestLocalMediaFormatsV6(unittest.TestCase):
    """Test suite verifying end-to-end multi-format local media processing."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp())
        cls.sample_files = {}

        # Synthesize 1-second media files using ffmpeg if available
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            formats = [
                ("test_audio.m4a", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "aac"]),
                ("test_audio.mp3", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "libmp3lame"]),
                ("test_audio.wav", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "pcm_s16le"]),
                ("test_video.mp4", ["-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
                                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"]),
                ("test_video.mov", ["-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
                                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                    "-c:v", "rawvideo", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le"]),
            ]
            for fname, args in formats:
                out_p = cls.temp_dir / fname
                cmd = [ffmpeg, "-y"] + args + [str(out_p)]
                res = subprocess.run(cmd, capture_output=True)
                if res.returncode == 0 and out_p.exists() and out_p.stat().st_size > 0:
                    cls.sample_files[fname] = out_p

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.client = app.test_client()
        self.ingestor = MediaIngestorV4(temp_dir=self.temp_dir / "ingest_work")

    def test_extension_classification_and_support(self):
        """Verify standard media containers are recognized by MediaIngestorV4."""
        for ext in (".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus"):
            self.assertIn(ext, SUPPORTED_AUDIO_EXTENSIONS)
            self.assertIn(ext, SUPPORTED_LOCAL_EXTENSIONS)

        for ext in (".mp4", ".mov", ".mkv", ".webm", ".avi"):
            self.assertIn(ext, SUPPORTED_VIDEO_EXTENSIONS)
            self.assertIn(ext, SUPPORTED_LOCAL_EXTENSIONS)

        if "test_audio.m4a" in self.sample_files:
            self.assertTrue(MediaIngestorV4.is_supported_local_media(self.sample_files["test_audio.m4a"]))
        if "test_video.mp4" in self.sample_files:
            self.assertTrue(MediaIngestorV4.is_supported_local_media(self.sample_files["test_video.mp4"]))

    def test_directory_scan_flat_and_recursive(self):
        """Verify scan_directory detects multi-format files flat and recursively."""
        scan_dir = self.temp_dir / "scan_test"
        sub_dir = scan_dir / "nested"
        sub_dir.mkdir(parents=True, exist_ok=True)

        (scan_dir / "clip1.m4a").write_bytes(b"dummy")
        (scan_dir / "clip2.MP4").write_bytes(b"dummy")
        (scan_dir / "notes.txt").write_bytes(b"text")
        (sub_dir / "clip3.mp3").write_bytes(b"dummy")

        flat_files = MediaIngestorV4.scan_directory(scan_dir, recursive=False)
        flat_names = [f.name for f in flat_files]
        self.assertIn("clip1.m4a", flat_names)
        self.assertIn("clip2.MP4", flat_names)
        self.assertNotIn("notes.txt", flat_names)
        self.assertNotIn("clip3.mp3", flat_names)

        rec_files = MediaIngestorV4.scan_directory(scan_dir, recursive=True)
        rec_names = [f.name for f in rec_files]
        self.assertIn("clip1.m4a", rec_names)
        self.assertIn("clip2.MP4", rec_names)
        self.assertIn("clip3.mp3", rec_names)
        self.assertNotIn("notes.txt", rec_names)

    def test_inspect_and_extract_m4a(self):
        """Verify M4A file metadata inspection and audio extraction."""
        if "test_audio.m4a" not in self.sample_files:
            self.skipTest("ffmpeg not available to synthesize M4A")

        p = self.sample_files["test_audio.m4a"]
        meta = self.ingestor.inspect_source(str(p))
        self.assertEqual(meta["format"], "m4a")
        self.assertEqual(meta["media_type"], "audio")
        self.assertGreater(meta["size_bytes"], 0)

        wav_p, ext_meta = self.ingestor.extract_audio(str(p), "job_test_m4a")
        self.assertTrue(wav_p.exists())
        self.assertGreater(wav_p.stat().st_size, 1000)

    def test_inspect_and_extract_mp4_video_bypassing(self):
        """Verify MP4 video container inspection and -vn video bypassing audio extraction."""
        if "test_video.mp4" not in self.sample_files:
            self.skipTest("ffmpeg not available to synthesize MP4")

        p = self.sample_files["test_video.mp4"]
        meta = self.ingestor.inspect_source(str(p))
        self.assertEqual(meta["format"], "mp4")
        self.assertEqual(meta["media_type"], "video")

        wav_p, ext_meta = self.ingestor.extract_audio(str(p), "job_test_mp4")
        self.assertTrue(wav_p.exists())
        self.assertGreater(wav_p.stat().st_size, 1000)

    def test_api_upload_endpoint_m4a_and_mp4(self):
        """Verify /api/upload accepts valid media containers and rejects unsupported formats."""
        # 1. Upload valid M4A
        data = {
            "file": (io.BytesIO(b"\x00" * 500), "sample_recording.m4a")
        }
        res = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["format"], "m4a")
        self.assertIn("uploads", payload["path"])

        # 2. Upload valid MP4
        data = {
            "file": (io.BytesIO(b"\x00" * 500), "stream_recording.mp4")
        }
        res = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["format"], "mp4")

        # 3. Reject unsupported executable file
        data = {
            "file": (io.BytesIO(b"binary"), "malicious_script.exe")
        }
        res = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Unsupported media format", res.get_json()["error"])

        # 4. Reject missing file part
        res = self.client.post("/api/upload", data={})
        self.assertEqual(res.status_code, 400)

    def test_pipeline_v6_with_local_m4a(self):
        """Verify TranscriptionPipelineV6 processes local file with audit and ISO export."""
        output_dir = self.temp_dir / "pipeline_test"
        pipeline = TranscriptionPipelineV6(output_dir=output_dir)

        dummy_audio = self.temp_dir / "voice.m4a"
        dummy_audio.write_bytes(b"\x00" * 1024)

        mock_segments = [
            {"start": 0.0, "end": 2.0, "ts": "00:00:00", "speaker": "Speaker_01", "text": "This is a local M4A test."},
        ]

        with patch.object(pipeline.ingestor, "extract_audio", return_value=(self.temp_dir / "voice.wav", {"title": "Voice", "duration": 2})):
            with patch.object(pipeline.transcriber, "transcribe_streaming", return_value=mock_segments):
                with patch.object(pipeline.speaker_db, "cluster_segments_offline", return_value=mock_segments):
                    res = pipeline.process(
                        source=str(dummy_audio),
                        custom_name="Local_Podcast_Episode",
                        playbook_name="gaming_videos"
                    )

        self.assertEqual(res["status"], "success")
        self.assertTrue(res["iso_name"].endswith("_Local_Podcast_Episode"))
        self.assertEqual(res["total_blocks"], 1)

    def test_cli_v6_local_command_parsing(self):
        """Verify cli_v6 argument parser parses local command arguments."""
        parser = cli_v6.argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        p_local = subparsers.add_parser("local")
        p_local.add_argument("target")
        p_local.add_argument("--recursive", "-r", action="store_true")
        p_local.add_argument("--title")

        args = parser.parse_args(["local", "/path/to/media.m4a", "--title", "GameMatch", "-r"])
        self.assertEqual(args.command, "local")
        self.assertEqual(args.target, "/path/to/media.m4a")
        self.assertEqual(args.title, "GameMatch")
        self.assertTrue(args.recursive)

    def test_catalog_stats_and_recent_items(self):
        """Verify MediaCatalog get_stats contains total_discovered and get_recent_items returns items."""
        from src.engine.catalog_v1 import MediaCatalog
        db_path = self.temp_dir / "catalog_test.sqlite"
        cat = MediaCatalog(db_path=db_path)
        stats = cat.get_stats()
        self.assertIn("total_discovered", stats)
        self.assertIn("completed", stats)
        self.assertIn("pending", stats)
        self.assertIn("failed", stats)
        self.assertEqual(stats["total"], 0)

        items = cat.get_recent_items(limit=10)
        self.assertEqual(items, [])

    def test_api_catalog_endpoint(self):
        """Verify /api/catalog returns 200 with valid stats and items."""
        res = self.client.get("/api/catalog")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertIn("stats", payload)
        self.assertIn("items", payload)
        self.assertIn("total_discovered", payload["stats"])
