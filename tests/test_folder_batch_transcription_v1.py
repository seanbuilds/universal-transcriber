"""Automated Tests for Local Folder Batch Transcription (v1).
<!-- Tests for folder inspection, placeholder staging, web API endpoints, and step-by-step batch transcription -->
"""

import io
import json
import shutil
import tempfile
import unittest
import wave
import struct
from pathlib import Path

from src.engine.playlist_v1 import (
    PlaylistManagerV1,
    STATUS_PENDING,
    STATUS_COMPLETED,
)
from app_v6 import app


def _create_mock_wav(path: Path, duration_sec: int = 1):
    """Generate a minimal valid uncompressed PCM wav file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        num_frames = 16000 * duration_sec
        data = struct.pack('<' + ('h' * num_frames), *([0] * num_frames))
        f.writeframes(data)


class TestFolderBatchTranscription(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="transcriber_folder_test_"))
        self.media_dir = self.tmp_dir / "Meeting_Recordings"
        self.media_dir.mkdir(parents=True)
        self.client = app.test_client()

        # Create 3 valid audio files in media_dir
        _create_mock_wav(self.media_dir / "01_intro.wav", duration_sec=1)
        _create_mock_wav(self.media_dir / "02_discussion.wav", duration_sec=2)
        _create_mock_wav(self.media_dir / "03_conclusion.wav", duration_sec=1)

        # Create a non-media file to verify filtering
        (self.media_dir / "notes.txt").write_text("Meeting notes", encoding="utf-8")

        self.staging_dir = self.tmp_dir / "Staging"
        self.staging_dir.mkdir(parents=True)
        self.mgr = PlaylistManagerV1(base_playlists_dir=self.staging_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_inspect_local_directory(self):
        """Verify inspect_local_directory filters media files and computes item count and metadata."""
        meta = self.mgr.inspect_local_directory(self.media_dir)
        self.assertTrue(meta["is_local_folder"])
        self.assertTrue(meta["is_playlist"])
        self.assertEqual(meta["item_count"], 3)
        self.assertEqual(len(meta["items"]), 3)
        self.assertEqual(meta["title"], "Meeting_Recordings")

        filenames = [it["filename"] for it in meta["items"]]
        self.assertEqual(filenames, ["01_intro.wav", "02_discussion.wav", "03_conclusion.wav"])

    def test_stage_local_folder_creates_placeholders_and_manifest(self):
        """Verify staging creates .pending placeholder files and manifest for all items."""
        meta = self.mgr.inspect_local_directory(self.media_dir)
        folder_dir, manifest_path = self.mgr.stage_playlist(meta, custom_folder_name="Test_Folder_Stage")

        self.assertTrue(folder_dir.exists())
        self.assertTrue(manifest_path.exists())

        # Check manifest content
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(data["item_count"], 3)

        # Check .pending placeholder files
        pending_files = list(folder_dir.glob("*.pending"))
        self.assertEqual(len(pending_files), 3)

    def test_api_folder_inspect_endpoint(self):
        """Verify POST /api/folder/inspect returns metadata for local folders."""
        resp = self.client.post("/api/folder/inspect", json={"folder_path": str(self.media_dir)})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["item_count"], 3)
        self.assertEqual(data["title"], "Meeting_Recordings")

        # Non-existent folder
        resp_404 = self.client.post("/api/folder/inspect", json={"folder_path": str(self.tmp_dir / "nonexistent")})
        self.assertEqual(resp_404.status_code, 404)

        # Missing parameter
        resp_400 = self.client.post("/api/folder/inspect", json={})
        self.assertEqual(resp_400.status_code, 400)

    def test_api_folder_start_endpoint(self):
        """Verify POST /api/folder/start accepts request and stages batch."""
        resp = self.client.post("/api/folder/start", json={
            "folder_path": str(self.media_dir),
            "custom_folder_name": "API_Folder_Start_Test"
        })
        self.assertEqual(resp.status_code, 202)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "accepted")
        self.assertEqual(data["item_count"], 3)
        self.assertIn("playlist_id", data)

    def test_api_folder_upload_endpoint(self):
        """Verify POST /api/folder/upload receives multiple files and stages batch collection."""
        wav_data_1 = io.BytesIO()
        with wave.open(wav_data_1, 'w') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(16000)
            f.writeframes(struct.pack('<' + ('h' * 16000), *([0] * 16000)))
        wav_data_1.seek(0)

        wav_data_2 = io.BytesIO()
        with wave.open(wav_data_2, 'w') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(16000)
            f.writeframes(struct.pack('<' + ('h' * 16000), *([0] * 16000)))
        wav_data_2.seek(0)

        data = {
            "folder_name": "Uploaded_Batch_Test",
            "playbook": "general_speech",
            "files[]": [
                (wav_data_1, "part1.wav"),
                (wav_data_2, "part2.wav"),
            ]
        }

        resp = self.client.post(
            "/api/folder/upload",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 202)
        res_json = resp.get_json()
        self.assertTrue(res_json["success"])
        self.assertEqual(res_json["item_count"], 2)


if __name__ == "__main__":
    unittest.main()
