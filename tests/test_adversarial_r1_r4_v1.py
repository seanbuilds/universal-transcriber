"""Empirical Adversarial Test Suite for R1 and R4 Findings (v1).

Adversarially challenges and empirically tests:
1. Finding R4-01: Path traversal vulnerability in app_v1.py (/api/file)
2. Finding R4-02: Wildcard CORS configuration in app_v1.py
3. Finding R1-07: --no-playlist behavior and playlist truncation in ingest_v1.py
4. Finding R1-01: Unhandled subprocess.TimeoutExpired in ingest_v1.py
5. Finding R1-02: Uncaught ffmpeg conversion exceptions in remote download path
6. Finding R1-09: Hardcoded 1200s timeout in transcribe_v1.py
7. Finding R4-06: Missing batch subcommand in cli_v1.py
8. Finding R4-04: Synchronous blocking HTTP API in app_v1.py
9. Finding R1-16: Total absence of persistent SQLite queue
10. Finding R1-17: Unsanitized date string path traversal in export_v1.py
"""

import inspect
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app_v1 import app
from src.engine.ingest_v1 import MediaIngestor, IngestionError
from src.engine.transcribe_v1 import WhisperTranscriber, TranscriptionError
from src.engine.export_v1 import TranscriptExporter
try:
    import cli_v1
except ImportError:
    import archive.cli_v1 as cli_v1


class TestAdversarialSecurityR4(unittest.TestCase):
    """Adversarial stress-testing of Security & Concurrency findings (R4)."""

    def setUp(self):
        self.client = app.test_client()

    def test_r4_01_api_file_arbitrary_file_read_passwd(self):
        """Verify /api/file serves sensitive host files outside TRANSCRIPTS_DIR."""
        res = self.client.get("/api/file?path=/etc/passwd")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(b"root:" in res.data or b"nobody:" in res.data or b"User Database" in res.data)

    def test_r4_01_api_file_relative_path_traversal(self):
        """Verify /api/file resolves directory traversal sequences to arbitrary local files."""
        res = self.client.get("/api/file?path=static/../pyproject_v1.toml")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"[build-system]", res.data)

    def test_r4_02_wildcard_cors_headers(self):
        """Verify CORS allows arbitrary origins on API endpoints."""
        res = self.client.get("/api/playbooks", headers={"Origin": "https://malicious-site.example"})
        self.assertEqual(res.status_code, 200)
        cors_header = res.headers.get("Access-Control-Allow-Origin")
        # Flask-CORS with CORS(app) allows either '*' or reflects requesting origin
        self.assertIn(cors_header, ["*", "https://malicious-site.example"])

    def test_r4_02_preflight_options_cors(self):
        """Verify OPTIONS preflight request grants cross-origin access."""
        res = self.client.options("/api/file", headers={
            "Origin": "https://attacker.site",
            "Access-Control-Request-Method": "GET"
        })
        cors_header = res.headers.get("Access-Control-Allow-Origin")
        self.assertIn(cors_header, ["*", "https://attacker.site"])

    def test_r4_06_missing_batch_subcommand_in_cli(self):
        """Verify that cli_v1.py advertises 'batch' in docstring but fails with invalid choice."""
        self.assertIn("batch <Playlist-or-Folder>", cli_v1.__doc__)
        # Invoke CLI with 'batch'
        with self.assertRaises(SystemExit) as ctx:
            with patch("sys.argv", ["cli_v1.py", "batch", "dummy_source"]):
                cli_v1.main()
        # argparse exits with code 2 on invalid choice
        self.assertEqual(ctx.exception.code, 2)

    def test_r4_04_synchronous_blocking_architecture(self):
        """Verify app_v1.py:transcribe executes pipeline.process synchronously in request handler."""
        # Inspect source code of transcribe() function
        lines, _ = inspect.getsourcelines(app.view_functions["transcribe"])
        source_code = "".join(lines)
        self.assertIn("result = pipeline.process(", source_code)
        # Verify no background thread, Celery, or async queue is invoked
        self.assertNotIn("threading.Thread", source_code)
        self.assertNotIn("submit", source_code)
        self.assertNotIn("queue", source_code.lower())


class TestAdversarialResilienceR1(unittest.TestCase):
    """Adversarial stress-testing of Pipeline Resilience findings (R1)."""

    def test_r1_07_no_playlist_flag_collision_and_truncation(self):
        """Verify extract_audio enforces --no-playlist and single static output filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ingestor = MediaIngestor(temp_dir=Path(tmpdir))
            job_id = "test_job_playlist"
            job_dir = Path(tmpdir) / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            raw_audio = job_dir / "downloaded_stream.m4a"

            captured_cmds = []
            def fake_run(cmd, *args, **kwargs):
                captured_cmds.append(cmd)
                # Simulate yt-dlp creating raw_audio
                raw_audio.write_bytes(b"dummy audio data")
                # When ffmpeg is called, simulate wav creation
                if "ffmpeg" in cmd:
                    wav_target = Path(cmd[-1])
                    wav_target.write_bytes(b"RIFF" + b"\x00" * 40)
                return MagicMock(returncode=0)

            with patch.object(ingestor, "inspect_source", return_value={"is_playlist": True, "title": "Playlist (240 items)"}):
                with patch("subprocess.run", side_effect=fake_run):
                    ingestor.extract_audio("https://www.youtube.com/playlist?list=PLmwI4alP7o5sR5DMzTiFNEE4ELEb3L_ec", job_id)

            yt_cmd = captured_cmds[0]
            # Assert --no-playlist was passed
            self.assertIn("--no-playlist", yt_cmd)
            # Assert static filename was passed to -o without template expansion
            self.assertIn("-o", yt_cmd)
            out_idx = yt_cmd.index("-o") + 1
            self.assertTrue(yt_cmd[out_idx].endswith("downloaded_stream.m4a"))
            self.assertNotIn("%(", yt_cmd[out_idx])

    def test_r1_01_unhandled_timeout_expired_in_ingest(self):
        """Verify subprocess.TimeoutExpired escapes yt-dlp try-except block."""
        ingestor = MediaIngestor()
        with patch.object(ingestor, "inspect_source", return_value={"is_playlist": False}):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["yt-dlp"], timeout=300)):
                with self.assertRaises(subprocess.TimeoutExpired):
                    # Should raise TimeoutExpired directly because only CalledProcessError is caught
                    ingestor.extract_audio("https://example.com/video", "test_timeout_job")

    def test_r1_02_remote_ffmpeg_conversion_no_exception_handler(self):
        """Verify remote ffmpeg transcode lacks exception handler, letting raw CalledProcessError escape."""
        ingestor = MediaIngestor()
        with patch.object(ingestor, "inspect_source", return_value={"is_playlist": False}):
            def fake_run(cmd, *args, **kwargs):
                if "yt-dlp" in cmd:
                    # Create raw_audio so it proceeds to ffmpeg
                    raw_audio = Path(cmd[cmd.index("-o") + 1])
                    raw_audio.write_bytes(b"dummy")
                    return MagicMock(returncode=0)
                elif "ffmpeg" in cmd:
                    raise subprocess.CalledProcessError(returncode=1, cmd=cmd, stderr=b"corrupt stream")

            with patch("subprocess.run", side_effect=fake_run):
                # Must raise CalledProcessError directly, violating IngestionError interface
                with self.assertRaises(subprocess.CalledProcessError):
                    ingestor.extract_audio("https://example.com/video", "test_ffmpeg_err_job")

    def test_r1_09_hardcoded_1200s_timeout_transcribe(self):
        """Verify transcribe_v1.py hardcodes 1200s timeout and raises on expiry."""
        transcriber = WhisperTranscriber()
        transcriber.model_path = Path("/tmp/dummy_model.bin")

        recorded_timeout = None
        def fake_run(cmd, *args, **kwargs):
            nonlocal recorded_timeout
            recorded_timeout = kwargs.get("timeout")
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=recorded_timeout)

        with patch("shutil.which", return_value="/usr/local/bin/whisper-cli"):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("subprocess.run", side_effect=fake_run):
                    with self.assertRaises(TranscriptionError) as ctx:
                        transcriber._run_whisper_cli("/usr/local/bin/whisper-cli", Path("/tmp/fake.wav"), Path("/tmp"))
                    self.assertEqual(recorded_timeout, 1200)
                    self.assertIn("whisper-cli timed out", str(ctx.exception))

    def test_r1_16_absence_of_sqlite_queue(self):
        """Verify repository v1 prototype baseline completely lacked SQLite queue schema."""
        repo_root = Path(__file__).resolve().parent.parent
        # The original prototype engine modules before remediation
        prototype_modules = [
            "ingest_v1.py",
            "transcribe_v1.py",
            "diarize_v1.py",
            "healer_v1.py",
            "export_v1.py",
            "pipeline_v1.py",
        ]
        
        sqlite_mentions = []
        for mod_name in prototype_modules:
            py_file = repo_root / "src" / "engine" / mod_name
            if py_file.exists():
                content = py_file.read_text(encoding="utf-8")
                if "sqlite3" in content or "sqlite" in content:
                    sqlite_mentions.append(py_file.name)
        
        # Confirms Finding R1-16: 0 SQLite queue modules in original v1 engine prototype
        self.assertEqual(sqlite_mentions, [])

    def test_r1_17_export_date_path_traversal_crash(self):
        """Verify unsanitized date string with slashes causes FileNotFoundError or path escape."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            exporter = TranscriptExporter(base_output_dir=base_dir)
            
            blocks = [{"speaker": "Speaker", "start": 0.0, "end": 2.0, "ts": "00:00:00", "text": "Test"}]
            # Date with slashes simulating date format like 2026/09/11
            metadata = {
                "title": "Meeting",
                "date": "2026/09/11",
                "duration_str": "00:02"
            }
            # Crashes with FileNotFoundError because subpath 2026/09/11_Meeting/2026/09 does not exist
            with self.assertRaises(FileNotFoundError):
                exporter.export(blocks=blocks, metadata=metadata)



if __name__ == "__main__":
    unittest.main()
