"""Persistent Media Catalog and Idempotency Registry (v1).
<!-- v1 – SQLite catalog for channel/RSS deduplication, archival indexing, and idempotency -->
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator

from config_v3 import CATALOG_DB_PATH

STATUS_DISCOVERED = "discovered"
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


def compute_item_hash(url_or_id: str) -> str:
    """Compute deterministic SHA256 hex digest for unique identification."""
    clean = url_or_id.strip()
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]


class MediaCatalog:
    """Thread-safe SQLite catalog ensuring media items are not transcribed redundantly."""

    def __init__(self, db_path: Path = CATALOG_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS catalog_entries (
                    item_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    catalog_source TEXT,
                    title TEXT,
                    published_date TEXT,
                    duration_seconds INTEGER DEFAULT 0,
                    status TEXT CHECK(status IN ('discovered', 'pending', 'processing', 'completed', 'failed', 'skipped')),
                    transcript_dir TEXT,
                    error_message TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_catalog_url ON catalog_entries(url);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_catalog_status ON catalog_entries(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_catalog_source ON catalog_entries(catalog_source);")

    def register_item(
        self,
        item_id: str,
        url: str,
        title: str,
        catalog_source: str = "",
        published_date: str = "",
        duration_seconds: int = 0,
    ) -> bool:
        """Register newly discovered item. If already present, leaves existing status intact."""
        clean_id = item_id or compute_item_hash(url)
        with self._connection() as conn:
            cur = conn.execute("SELECT status FROM catalog_entries WHERE item_id = ? OR url = ?", (clean_id, url))
            row = cur.fetchone()
            if row:
                return False  # Already registered

            conn.execute("""
                INSERT INTO catalog_entries (item_id, url, catalog_source, title, published_date, duration_seconds, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (clean_id, url, catalog_source, title or "Untitled", published_date, duration_seconds, STATUS_DISCOVERED))
            return True

    def is_transcribed(self, item_id_or_url: str) -> bool:
        """Check if an item has already been successfully transcribed."""
        with self._connection() as conn:
            cur = conn.execute("""
                SELECT status FROM catalog_entries
                WHERE item_id = ? OR url = ?
            """, (item_id_or_url, item_id_or_url))
            row = cur.fetchone()
            if row and row["status"] == STATUS_COMPLETED:
                return True
        return False

    def mark_processing(self, item_id_or_url: str) -> None:
        """Update status to processing."""
        with self._connection() as conn:
            conn.execute("""
                UPDATE catalog_entries
                SET status = ?
                WHERE item_id = ? OR url = ?
            """, (STATUS_PROCESSING, item_id_or_url, item_id_or_url))

    def mark_completed(self, item_id_or_url: str, transcript_dir: str) -> None:
        """Mark item as completed with the directory path where transcripts reside."""
        with self._connection() as conn:
            conn.execute("""
                UPDATE catalog_entries
                SET status = ?, transcript_dir = ?, completed_at = CURRENT_TIMESTAMP
                WHERE item_id = ? OR url = ?
            """, (STATUS_COMPLETED, str(transcript_dir), item_id_or_url, item_id_or_url))

    def mark_failed(self, item_id_or_url: str, error_msg: str) -> None:
        """Mark item as failed."""
        with self._connection() as conn:
            conn.execute("""
                UPDATE catalog_entries
                SET status = ?, error_message = ?
                WHERE item_id = ? OR url = ?
            """, (STATUS_FAILED, str(error_msg), item_id_or_url, item_id_or_url))

    def list_entries(
        self,
        catalog_source: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List catalog entries with optional filters."""
        query = "SELECT * FROM catalog_entries WHERE 1=1"
        params: List[Any] = []
        if catalog_source:
            query += " AND catalog_source = ?"
            params.append(catalog_source)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY discovered_at DESC LIMIT ?"
        params.append(limit)

        with self._connection() as conn:
            cur = conn.execute(query, tuple(params))
            items = [dict(r) for r in cur.fetchall()]
            for it in items:
                if "source_url" not in it and "url" in it:
                    it["source_url"] = it["url"]
            return items

    def get_recent_items(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent catalog entries."""
        return self.list_entries(limit=limit)

    def get_stats(self) -> Dict[str, int]:
        """Return summary counts of items across all statuses."""
        with self._connection() as conn:
            cur = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM catalog_entries
                GROUP BY status
            """)
            counts = {r["status"]: r["count"] for r in cur.fetchall()}
            counts.setdefault("discovered", 0)
            counts.setdefault("pending", 0)
            counts.setdefault("processing", 0)
            counts.setdefault("completed", 0)
            counts.setdefault("failed", 0)
            counts.setdefault("skipped", 0)
            counts["total"] = sum(counts.values())
            counts["total_discovered"] = counts["total"]
            return counts
