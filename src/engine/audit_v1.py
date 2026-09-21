"""Comprehensive Persistent Transcription Audit Logger (v1).
<!-- v1 – Thread-safe SQLite audit trail, dual-write JSONL logging, and lifecycle tracking for used/unused transcriptions -->
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

from config_v4 import AUDIT_DB_PATH, AUDIT_LOG_JSONL_PATH, TRANSCRIPTS_DIR


class TranscriptionAuditLogger:
    """Persistent audit logging tracking every transcription attempt regardless of outcome or usage."""

    _instance_lock = threading.Lock()

    def __init__(
        self,
        db_path: Path = AUDIT_DB_PATH,
        jsonl_path: Path = AUDIT_LOG_JSONL_PATH,
    ):
        self.db_path = Path(db_path)
        self.jsonl_path = Path(jsonl_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transcription_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    custom_name TEXT,
                    playbook TEXT NOT NULL,
                    clustering_mode TEXT,
                    status TEXT NOT NULL,
                    audio_duration REAL DEFAULT 0.0,
                    total_segments INTEGER DEFAULT 0,
                    total_blocks INTEGER DEFAULT 0,
                    export_dir TEXT,
                    files_json TEXT,
                    error_message TEXT,
                    used_flag INTEGER DEFAULT 0,
                    used_at TEXT
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_job_id ON transcription_audit(job_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_status ON transcription_audit(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_used ON transcription_audit(used_flag);")
            conn.commit()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append_jsonl(self, event_type: str, data: Dict[str, Any]) -> None:
        """Append an immutable audit entry to the JSONL log file."""
        record = {
            "timestamp": self._now_iso(),
            "event_type": event_type,
            "data": data,
        }
        try:
            line = json.dumps(record, default=str) + "\n"
            with self._lock:
                with open(self.jsonl_path, "a", encoding="utf-8") as f:
                    f.write(line)
        except Exception:
            pass

    def log_job_started(
        self,
        job_id: str,
        source: str,
        playbook: str,
        clustering_mode: str = "ahc",
        custom_name: Optional[str] = None,
    ) -> None:
        """Record the initiation of a transcription job immediately upon submission."""
        now = self._now_iso()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO transcription_audit (
                        job_id, created_at, updated_at, source, custom_name,
                        playbook, clustering_mode, status, used_flag
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'SUBMITTED', 0)
                    ON CONFLICT(job_id) DO UPDATE SET
                        updated_at = excluded.updated_at,
                        source = excluded.source,
                        custom_name = excluded.custom_name,
                        playbook = excluded.playbook,
                        clustering_mode = excluded.clustering_mode,
                        status = 'SUBMITTED';
                """, (job_id, now, now, source, custom_name, playbook, clustering_mode))
                conn.commit()

        self._append_jsonl("JOB_STARTED", {
            "job_id": job_id,
            "source": source,
            "playbook": playbook,
            "clustering_mode": clustering_mode,
            "custom_name": custom_name,
        })

    def log_progress(
        self,
        job_id: str,
        stage: str,
        percent: int,
        audio_duration: Optional[float] = None,
        total_segments: Optional[int] = None,
    ) -> None:
        """Update job stage progress in the audit trail."""
        now = self._now_iso()
        with self._lock:
            with self._get_conn() as conn:
                updates = ["updated_at = ?", "status = 'PROCESSING'"]
                params: List[Any] = [now]
                if audio_duration is not None and audio_duration > 0:
                    updates.append("audio_duration = ?")
                    params.append(float(audio_duration))
                if total_segments is not None:
                    updates.append("total_segments = ?")
                    params.append(int(total_segments))
                params.append(job_id)

                sql = f"UPDATE transcription_audit SET {', '.join(updates)} WHERE job_id = ? AND status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')"
                conn.execute(sql, tuple(params))
                conn.commit()

        self._append_jsonl("JOB_PROGRESS", {
            "job_id": job_id,
            "stage": stage,
            "percent": percent,
            "audio_duration": audio_duration,
            "total_segments": total_segments,
        })

    def log_job_completed(
        self,
        job_id: str,
        audio_duration: float,
        total_segments: int,
        total_blocks: int,
        export_dir: str,
        files: Dict[str, str],
    ) -> None:
        """Record successful transcription completion and file export locations."""
        now = self._now_iso()
        files_json = json.dumps(files)
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE transcription_audit SET
                        updated_at = ?,
                        status = 'COMPLETED',
                        audio_duration = ?,
                        total_segments = ?,
                        total_blocks = ?,
                        export_dir = ?,
                        files_json = ?
                    WHERE job_id = ?;
                """, (now, float(audio_duration), int(total_segments), int(total_blocks), export_dir, files_json, job_id))
                conn.commit()

        self._append_jsonl("JOB_COMPLETED", {
            "job_id": job_id,
            "audio_duration": audio_duration,
            "total_segments": total_segments,
            "total_blocks": total_blocks,
            "export_dir": export_dir,
            "files": files,
        })

    def log_job_failed(self, job_id: str, error_message: str) -> None:
        """Record transcription failure with comprehensive error information."""
        now = self._now_iso()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE transcription_audit SET
                        updated_at = ?,
                        status = 'FAILED',
                        error_message = ?
                    WHERE job_id = ?;
                """, (now, str(error_message), job_id))
                conn.commit()

        self._append_jsonl("JOB_FAILED", {
            "job_id": job_id,
            "error_message": error_message,
        })

    def log_job_cancelled(self, job_id: str, reason: str = "User initiated clear / cancel") -> None:
        """Record job cancellation or user clearing."""
        now = self._now_iso()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE transcription_audit SET
                        updated_at = ?,
                        status = 'CANCELLED',
                        error_message = ?
                    WHERE job_id = ?;
                """, (now, reason, job_id))
                conn.commit()

        self._append_jsonl("JOB_CANCELLED", {
            "job_id": job_id,
            "reason": reason,
        })

    def mark_job_used(self, job_id: str, action: str = "viewed") -> bool:
        """Mark a completed transcription as used/consumed (e.g. downloaded, viewed)."""
        now = self._now_iso()
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("""
                    UPDATE transcription_audit SET
                        updated_at = ?,
                        used_flag = 1,
                        used_at = ?
                    WHERE job_id = ?;
                """, (now, now, job_id))
                conn.commit()
                affected = cur.rowcount > 0

        if affected:
            self._append_jsonl("JOB_MARKED_USED", {
                "job_id": job_id,
                "action": action,
            })
        return affected

    def get_audit_entry(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific audit log record by job ID."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM transcription_audit WHERE job_id = ?", (job_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get("files_json"):
                try:
                    data["files"] = json.loads(data["files_json"])
                except Exception:
                    data["files"] = {}
            return data

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Alias for get_audit_entry for consistent job retrieval across engines."""
        return self.get_audit_entry(job_id)

    def list_audit_entries(
        self,
        limit: int = 50,
        status: Optional[str] = None,
        used_only: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """List historical audit records with optional status or usage filtering."""
        query = "SELECT * FROM transcription_audit"
        conditions = []
        params: List[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status.upper())

        if used_only is True:
            conditions.append("used_flag = 1")
        elif used_only is False:
            conditions.append("used_flag = 0")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("files_json"):
                    try:
                        item["files"] = json.loads(item["files_json"])
                    except Exception:
                        item["files"] = {}
                results.append(item)
            return results

    def get_audit_summary(self) -> Dict[str, Any]:
        """Aggregate summary metrics across all logged transcriptions."""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM transcription_audit").fetchone()[0]
            completed = conn.execute("SELECT COUNT(*) FROM transcription_audit WHERE status = 'COMPLETED'").fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM transcription_audit WHERE status = 'FAILED'").fetchone()[0]
            cancelled = conn.execute("SELECT COUNT(*) FROM transcription_audit WHERE status = 'CANCELLED'").fetchone()[0]
            used = conn.execute("SELECT COUNT(*) FROM transcription_audit WHERE used_flag = 1").fetchone()[0]
            unused = conn.execute("SELECT COUNT(*) FROM transcription_audit WHERE used_flag = 0").fetchone()[0]

            return {
                "total_transcriptions_logged": total,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
                "used": used,
                "unused": unused,
            }

    def clear_audit_history(self, clear_jsonl: bool = True) -> int:
        """Clear all audit history records from the SQLite database and optionally archive/clear the JSONL ledger."""
        with self._lock:
            with self._get_conn() as conn:
                count = conn.execute("SELECT COUNT(*) FROM transcription_audit").fetchone()[0]
                conn.execute("DELETE FROM transcription_audit;")
                conn.commit()
            if clear_jsonl and self.jsonl_path.exists():
                try:
                    self.jsonl_path.write_text("", encoding="utf-8")
                except Exception:
                    pass
            return count
