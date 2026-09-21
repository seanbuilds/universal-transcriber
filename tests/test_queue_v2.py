"""Persistent SQLite Job Queue Tests (v2)."""

import unittest
import tempfile
from pathlib import Path
from src.engine.queue_v2 import (
    JobQueue,
    STATUS_PENDING,
    STATUS_DOWNLOADING,
    STATUS_COMPLETED,
    STATUS_FAILED
)


class TestQueueV2(unittest.TestCase):

    def test_queue_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_queue.sqlite"
            queue = JobQueue(db_path=db_path)

            # Enqueue
            ok = queue.enqueue("job_001", "https://youtube.com/watch?v=123", title="Town Meeting")
            self.assertTrue(ok)

            # Verify pending
            job = queue.get_job("job_001")
            self.assertIsNotNone(job)
            self.assertEqual(job["status"], STATUS_PENDING)

            # Claim
            claimed = queue.get_next_pending_job()
            self.assertIsNotNone(claimed)
            self.assertEqual(claimed["job_id"], "job_001")
            self.assertEqual(claimed["status"], STATUS_DOWNLOADING)

            # Progress update
            queue.update_progress("job_001", status="transcribing", progress_pct=50, message="Halfway")
            updated = queue.get_job("job_001")
            self.assertEqual(updated["progress_pct"], 50)

            # Complete
            queue.mark_completed("job_001", {"files": {"md": "/tmp/out.md"}})
            completed = queue.get_job("job_001")
            self.assertEqual(completed["status"], STATUS_COMPLETED)
            self.assertEqual(completed["result"]["files"]["md"], "/tmp/out.md")

    def test_clear_all_jobs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_queue_clear.sqlite"
            queue = JobQueue(db_path=db_path)

            queue.enqueue("job_a", "https://youtube.com/watch?v=1", title="Job A")
            queue.enqueue("job_b", "https://youtube.com/watch?v=2", title="Job B")
            self.assertEqual(len(queue.list_jobs()), 2)

            cleared = queue.clear_all_jobs()
            self.assertEqual(cleared, 2)
            self.assertEqual(len(queue.list_jobs()), 0)


if __name__ == "__main__":
    unittest.main()

