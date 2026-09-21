"""Tests for Danger Zone History Clearing and Disk Preservation (v1).
<!-- Verifies database & queue reset while strictly guaranteeing disk files and folders remain intact. -->
"""

import tempfile
import shutil
from pathlib import Path
import unittest

from src.engine.audit_v1 import TranscriptionAuditLogger
from src.engine.queue_v2 import JobQueue
from app_v6 import app, audit_logger, job_queue


class TestDangerZoneClear(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.disk_transcript_dir = self.tmp_dir / "Transcripts" / "20260921_Town_Meeting"
        self.disk_transcript_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_file = self.disk_transcript_dir / "20260921_Town_Meeting.md"
        self.transcript_file.write_text("# Meeting Transcript\nSpeaker 1: Hello", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_audit_and_queue_clear_preserves_disk_files(self):
        """Verify clear_audit_history and clear_all_jobs reset state without touching files on disk."""
        db_path = self.tmp_dir / "audit.sqlite"
        jsonl_path = self.tmp_dir / "audit.jsonl"
        q_db = self.tmp_dir / "queue.sqlite"

        audit = TranscriptionAuditLogger(db_path=db_path, jsonl_path=jsonl_path)
        q = JobQueue(db_path=q_db)

        # Populate audit and queue
        audit.log_job_started("job_01", "https://example.com/1", "town_hall", custom_name="Town Meeting")
        audit.log_job_completed(
            "job_01",
            audio_duration=120.0,
            total_segments=10,
            total_blocks=5,
            export_dir=str(self.disk_transcript_dir),
            files={"md": str(self.transcript_file)}
        )
        q.enqueue("job_01", "https://example.com/1", title="Town Meeting")

        self.assertEqual(audit.get_audit_summary()["total_transcriptions_logged"], 1)
        self.assertEqual(len(q.list_jobs()), 1)

        # Clear audit and queue
        cleared_audit = audit.clear_audit_history(clear_jsonl=True)
        cleared_q = q.clear_all_jobs()

        self.assertEqual(cleared_audit, 1)
        self.assertEqual(cleared_q, 1)
        self.assertEqual(audit.get_audit_summary()["total_transcriptions_logged"], 0)
        self.assertEqual(len(audit.list_audit_entries()), 0)
        self.assertEqual(len(q.list_jobs()), 0)

        # CRITICAL USER REQUIREMENT: Physical disk folders and transcript files MUST NOT be deleted
        self.assertTrue(self.disk_transcript_dir.exists(), "Transcript folder must remain on disk")
        self.assertTrue(self.transcript_file.exists(), "Transcript export file must remain on disk")
        self.assertIn("Speaker 1: Hello", self.transcript_file.read_text(encoding="utf-8"))

    def test_api_clear_audit_endpoint(self):
        """Verify POST /api/audit/clear clears records, reports success, and maintains file safety."""
        client = app.test_client()

        # Insert a job into the global audit and queue
        audit_logger.log_job_started("job_api_test", "https://example.com/api", "general_speech", custom_name="API Test")
        job_queue.enqueue("job_api_test", "https://example.com/api", title="API Test")

        # Call clear endpoint
        resp = client.post("/api/audit/clear")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertTrue(data["success"])
        self.assertTrue(data["disk_files_preserved"])
        self.assertIn("Cleared", data["message"])

        # Check subsequent GET /api/audit
        resp_audit = client.get("/api/audit")
        self.assertEqual(resp_audit.status_code, 200)
        audit_res = resp_audit.get_json()
        self.assertEqual(audit_res["summary"]["total_transcriptions_logged"], 0)
        self.assertEqual(len(audit_res["entries"]), 0)


if __name__ == "__main__":
    unittest.main()
