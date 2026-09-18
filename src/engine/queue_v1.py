"""Persistent SQLite Job Queue with WAL mode (v1).
<!-- v1 – Persistent crash-resilient queue for batch processing and daemon autonomy -->
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from config_v2 import QUEUE_DB_PATH

STATUS_PENDING = "pending"
STATUS_DOWNLOADING = "downloading"
STATUS_TRANSCRIBING = "transcribing"
STATUS_DIARIZING = "diarizing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


class JobQueue:
    """Thread-safe, crash-resilient SQLite progress and batch queue."""

    def __init__(self, db_path: Path = QUEUE_DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    title TEXT,
                    playbook TEXT DEFAULT 'general_speech',
                    status TEXT CHECK(status IN ('pending', 'downloading', 'transcribing', 'diarizing', 'completed', 'failed')),
                    progress_pct INTEGER DEFAULT 0,
                    stage_message TEXT DEFAULT 'Queued',
                    error_message TEXT,
                    result_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")

    def enqueue(self, job_id: str, source_url: str, title: str = "", playbook: str = "general_speech") -> bool:
        """Enqueue a new transcription job."""
        with self._get_connection() as conn:
            try:
                conn.execute("""
                    INSERT INTO jobs (job_id, source_url, title, playbook, status, progress_pct, stage_message)
                    VALUES (?, ?, ?, ?, ?, 0, 'Queued')
                    ON CONFLICT(job_id) DO UPDATE SET
                        source_url=excluded.source_url,
                        playbook=excluded.playbook,
                        updated_at=CURRENT_TIMESTAMP
                """, (job_id, source_url, title or source_url, playbook, STATUS_PENDING))
                return True
            except Exception:
                return False

    def update_progress(self, job_id: str, status: str, progress_pct: int, message: str = "") -> None:
        """Update job stage, percentage, and status."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE jobs
                SET status = ?, progress_pct = ?, stage_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
            """, (status, progress_pct, message, job_id))

    def mark_completed(self, job_id: str, result_data: Dict[str, Any]) -> None:
        """Record successful completion and serialize result paths."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE jobs
                SET status = ?, progress_pct = 100, stage_message = 'Completed',
                    result_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
            """, (STATUS_COMPLETED, json.dumps(result_data), job_id))

    def mark_failed(self, job_id: str, error_message: str) -> None:
        """Record job failure."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE jobs
                SET status = ?, stage_message = 'Failed', error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
            """, (STATUS_FAILED, str(error_message), job_id))

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve status and metadata for a single job."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("result_json"):
                try:
                    res["result"] = json.loads(res["result_json"])
                except Exception:
                    res["result"] = None
            return res

    def get_next_pending_job(self) -> Optional[Dict[str, Any]]:
        """Atomically claim the next pending job."""
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT * FROM jobs
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
            """)
            row = cur.fetchone()
            if not row:
                return None
            job_dict = dict(row)
            conn.execute("""
                UPDATE jobs
                SET status = ?, stage_message = 'Claimed by worker', updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
            """, (STATUS_DOWNLOADING, job_dict["job_id"]))
            job_dict["status"] = STATUS_DOWNLOADING
            job_dict["stage_message"] = "Claimed by worker"
            return job_dict

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent jobs."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
