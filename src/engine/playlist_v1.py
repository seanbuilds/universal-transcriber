"""Playlist Ingestion, Manifest Staging, and Step-by-Step Lifecycle Coordinator (v1).
<!-- v1 – Dynamic YouTube playlist decomposition, placeholder staging, interactive warning/confirmation, and crash-resilient step-by-step transcription -->
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from config_v5 import TRANSCRIPTS_DIR, BASE_DIR

# Playlist parent storage directory
PLAYLISTS_BASE_DIR = TRANSCRIPTS_DIR / "Playlists"
PLAYLISTS_BASE_DIR.mkdir(parents=True, exist_ok=True)

STATUS_PENDING = "PENDING"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"


def sanitize_filename(name: str) -> str:
    """Sanitize string into safe filesystem path component."""
    clean = re.sub(r'[\\/*?:"<>|]', '_', name)
    clean = re.sub(r'\s+', '_', clean).strip('._- ')
    return clean or "Item"


def format_duration(seconds: int | float) -> str:
    """Format seconds into HH:MM:SS string."""
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


class PlaylistManagerV1:
    """Manages YouTube playlist decomposition, staging directories, placeholder files, and manifest tracking."""

    def __init__(self, base_playlists_dir: Optional[Path] = None):
        self.base_dir = Path(base_playlists_dir) if base_playlists_dir else PLAYLISTS_BASE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def inspect_source(self, source: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Inspect either a remote YouTube playlist or a local directory containing media files."""
        p = Path(source).expanduser()
        if p.exists() and p.is_dir():
            return self.inspect_local_directory(p, limit=limit)
        return self.inspect_playlist(source, limit=limit)

    def inspect_local_directory(
        self,
        dir_path: Path | str,
        recursive: bool = False,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Scan a local directory for all supported audio and video files and assemble batch metadata."""
        from src.engine.ingest_v4 import MediaIngestorV4

        p = Path(dir_path).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            raise FileNotFoundError(f"Local folder does not exist or is not a directory: {p}")

        files = MediaIngestorV4.scan_directory(p, recursive=recursive)
        if limit and limit > 0:
            files = files[:limit]

        items: List[Dict[str, Any]] = []
        total_duration = 0
        ffprobe = shutil.which("ffprobe")

        for idx, media_file in enumerate(files, 1):
            dur = 0
            if ffprobe:
                try:
                    probe_cmd = [
                        ffprobe, "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "json",
                        str(media_file),
                    ]
                    pres = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                    if pres.returncode == 0 and pres.stdout.strip():
                        info = json.loads(pres.stdout)
                        d_str = info.get("format", {}).get("duration")
                        if d_str:
                            dur = int(float(d_str))
                except Exception:
                    pass

            total_duration += dur
            clean_stem = sanitize_filename(media_file.stem)
            items.append({
                "index": idx,
                "id": f"file_{idx:03d}_{clean_stem}",
                "title": media_file.stem.replace("_", " ").title(),
                "url": str(media_file),
                "filename": media_file.name,
                "size_bytes": media_file.stat().st_size,
                "duration_seconds": dur,
                "duration_str": format_duration(dur),
                "upload_date": datetime.fromtimestamp(media_file.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d"),
                "status": STATUS_PENDING,
            })

        now_utc = datetime.now(timezone.utc)
        iso_date = now_utc.strftime("%Y%m%d")
        folder_title = p.name or "Local Folder Batch"

        return {
            "source_url": str(p),
            "title": folder_title,
            "is_playlist": True,
            "is_local_folder": True,
            "item_count": len(items),
            "total_duration_seconds": total_duration,
            "total_duration_str": format_duration(total_duration),
            "inspected_at": now_utc.isoformat(),
            "iso_date": iso_date,
            "items": items,
        }

    def inspect_playlist(self, source_url: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Query yt-dlp to inspect playlist structure and list all videos without downloading media."""
        yt_dlp = shutil.which("yt-dlp")
        if not yt_dlp:
            raise RuntimeError("yt-dlp executable not found in PATH.")

        cmd = [
            yt_dlp,
            "--dump-single-json",
            "--flat-playlist",
            "--socket-timeout", "30",
            "--retries", "5",
        ]
        if limit and limit > 0:
            cmd.extend(["--playlist-end", str(limit)])
        cmd.append(source_url)

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if res.returncode != 0 or not res.stdout.strip():
            # Fallback to line-delimited json dump
            fallback_cmd = [
                yt_dlp,
                "--dump-json",
                "--flat-playlist",
                "--socket-timeout", "30",
                "--retries", "5",
            ]
            if limit and limit > 0:
                fallback_cmd.extend(["--playlist-end", str(limit)])
            fallback_cmd.append(source_url)
            fallback_res = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=90)
            if fallback_res.returncode != 0 or not fallback_res.stdout.strip():
                err_msg = res.stderr.strip() or fallback_res.stderr.strip() or "Unknown error inspecting playlist"
                raise RuntimeError(f"Failed to inspect playlist: {err_msg}")

            lines = [l.strip() for l in fallback_res.stdout.splitlines() if l.strip()]
            entries = []
            playlist_title = "YouTube Playlist"
            for l in lines:
                try:
                    entries.append(json.loads(l))
                except Exception:
                    continue
        else:
            data = json.loads(res.stdout)
            entries = data.get("entries", [])
            playlist_title = data.get("title") or "YouTube Playlist"

        items: List[Dict[str, Any]] = []
        total_duration = 0

        for idx, entry in enumerate(entries, 1):
            if not entry:
                continue
            v_id = entry.get("id") or f"item_{idx:03d}"
            v_title = entry.get("title") or f"Video {idx}"
            v_url = entry.get("url") or (f"https://www.youtube.com/watch?v={v_id}" if v_id else source_url)
            v_dur = int(entry.get("duration", 0) or 0)
            v_date = entry.get("upload_date") or ""
            if len(v_date) == 8:
                v_date = f"{v_date[:4]}-{v_date[4:6]}-{v_date[6:]}"

            total_duration += v_dur
            items.append({
                "index": idx,
                "id": v_id,
                "title": v_title,
                "url": v_url,
                "duration_seconds": v_dur,
                "duration_str": format_duration(v_dur),
                "upload_date": v_date,
                "status": STATUS_PENDING,
            })

        now_utc = datetime.now(timezone.utc)
        iso_date = now_utc.strftime("%Y%m%d")

        return {
            "source_url": source_url,
            "title": playlist_title,
            "item_count": len(items),
            "total_duration_seconds": total_duration,
            "total_duration_str": format_duration(total_duration),
            "inspected_at": now_utc.isoformat(),
            "iso_date": iso_date,
            "items": items,
        }

    def stage_playlist(
        self,
        meta: Dict[str, Any],
        custom_folder_name: Optional[str] = None,
    ) -> Tuple[Path, Path]:
        """Create dedicated playlist collection directory, write manifest, INDEX.md, and create .pending placeholder files."""
        with self._lock:
            iso_date = meta.get("iso_date") or datetime.now(timezone.utc).strftime("%Y%m%d")
            clean_title = sanitize_filename(custom_folder_name or meta.get("title", "Playlist"))
            folder_name = f"{iso_date}_{clean_title}"
            playlist_dir = self.base_dir / folder_name
            playlist_dir.mkdir(parents=True, exist_ok=True)

            manifest_path = playlist_dir / "playlist_manifest.json"
            index_path = playlist_dir / "PLAYLIST_INDEX.md"

            # Create .pending placeholder files for each item
            for item in meta["items"]:
                idx = item["index"]
                clean_item_title = sanitize_filename(item["title"])
                placeholder_name = f"{idx:03d}_{iso_date}_{clean_item_title}.pending"
                item["placeholder_file"] = placeholder_name
                placeholder_path = playlist_dir / placeholder_name
                if not placeholder_path.exists():
                    placeholder_content = (
                        f"Universal Transcriber Placeholder\n"
                        f"Video Index: {idx} of {meta['item_count']}\n"
                        f"Title: {item['title']}\n"
                        f"URL: {item['url']}\n"
                        f"Status: PENDING\n"
                        f"Queued At: {datetime.now(timezone.utc).isoformat()}\n"
                    )
                    placeholder_path.write_text(placeholder_content, encoding="utf-8")

            # Write manifest JSON
            meta["playlist_dir"] = str(playlist_dir)
            meta["manifest_path"] = str(manifest_path)
            meta["index_path"] = str(index_path)
            meta["status"] = STATUS_IN_PROGRESS
            meta["completed_count"] = 0
            meta["failed_count"] = 0

            self._save_manifest_atomic(manifest_path, meta)
            self._render_index_markdown(index_path, meta)

            return playlist_dir, manifest_path

    def _save_manifest_atomic(self, manifest_path: Path, data: Dict[str, Any]) -> None:
        """Atomically persist manifest data to disk."""
        tmp_path = manifest_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(manifest_path)

    def load_manifest(self, manifest_path: Path) -> Dict[str, Any]:
        """Load playlist manifest from disk."""
        with self._lock:
            if not manifest_path.exists():
                raise FileNotFoundError(f"Manifest not found: {manifest_path}")
            return json.loads(manifest_path.read_text(encoding="utf-8"))

    def get_pending_items(self, manifest_path: Path) -> List[Dict[str, Any]]:
        """Return list of items that are still PENDING or FAILED."""
        manifest = self.load_manifest(manifest_path)
        return [
            item for item in manifest.get("items", [])
            if item.get("status") in (STATUS_PENDING, STATUS_FAILED)
        ]

    def update_item_status(
        self,
        manifest_path: Path,
        item_id: str,
        status: str,
        error_message: Optional[str] = None,
        output_dir: Optional[Path | str] = None,
        job_id: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Update single item's status, remove placeholder if completed, and update index."""
        with self._lock:
            manifest = self.load_manifest(manifest_path)
            playlist_dir = manifest_path.parent

            target_item = None
            for item in manifest.get("items", []):
                if item.get("id") == item_id:
                    target_item = item
                    break

            if not target_item:
                raise ValueError(f"Item {item_id} not found in manifest.")

            target_item["status"] = status
            target_item["updated_at"] = datetime.now(timezone.utc).isoformat()

            if job_id:
                target_item["job_id"] = job_id
            if duration_seconds:
                target_item["duration_seconds"] = int(duration_seconds)
                target_item["duration_str"] = format_duration(duration_seconds)

            if status == STATUS_COMPLETED:
                target_item["completed_at"] = datetime.now(timezone.utc).isoformat()
                if output_dir:
                    target_item["output_dir"] = str(output_dir)
                # Remove .pending placeholder
                placeholder = target_item.get("placeholder_file")
                if placeholder:
                    p_path = playlist_dir / placeholder
                    if p_path.exists():
                        p_path.unlink()
            elif status == STATUS_FAILED:
                target_item["error_message"] = error_message or "Unknown failure"
                target_item["failed_at"] = datetime.now(timezone.utc).isoformat()

            # Recount statistics
            items = manifest.get("items", [])
            completed = sum(1 for i in items if i.get("status") == STATUS_COMPLETED)
            failed = sum(1 for i in items if i.get("status") == STATUS_FAILED)
            pending = sum(1 for i in items if i.get("status") == STATUS_PENDING)

            manifest["completed_count"] = completed
            manifest["failed_count"] = failed
            manifest["pending_count"] = pending

            if pending == 0:
                manifest["status"] = STATUS_COMPLETED if failed == 0 else "COMPLETED_WITH_ERRORS"
                manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
            else:
                manifest["status"] = STATUS_IN_PROGRESS

            self._save_manifest_atomic(manifest_path, manifest)
            self._render_index_markdown(manifest_path.parent / "PLAYLIST_INDEX.md", manifest)
            return manifest

    def _render_index_markdown(self, index_path: Path, manifest: Dict[str, Any]) -> None:
        """Render a readable Markdown summary table of playlist transcription status."""
        title = manifest.get("title", "YouTube Playlist")
        total = manifest.get("item_count", 0)
        completed = manifest.get("completed_count", 0)
        failed = manifest.get("failed_count", 0)
        pending = total - (completed + failed)
        overall_status = manifest.get("status", "IN_PROGRESS")

        lines = [
            f"# 📺 Playlist Transcription: {title}",
            "",
            f"- **Source URL**: [{manifest.get('source_url', '')}]({manifest.get('source_url', '')})",
            f"- **Status**: `{overall_status}`",
            f"- **Total Items**: {total} videos ({manifest.get('total_duration_str', '00:00:00')})",
            f"- **Progress**: **{completed}** Completed | **{failed}** Failed | **{pending}** Pending",
            f"- **Last Updated**: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`",
            "",
            "---",
            "",
            "## Video Item Index",
            "",
            "| # | Video Title | Duration | Status | Outputs / Artifacts |",
            "| :-: | :--- | :-: | :-: | :--- |",
        ]

        for item in manifest.get("items", []):
            idx = item.get("index", 1)
            v_title = item.get("title", "Untitled")
            v_url = item.get("url", "#")
            dur = item.get("duration_str", "00:00:00")
            st = item.get("status", STATUS_PENDING)
            out_dir = item.get("output_dir", "")

            if st == STATUS_COMPLETED and out_dir:
                dir_name = Path(out_dir).name
                status_col = "✅ Completed"
                out_col = f"[`{dir_name}/`]({dir_name}/)"
            elif st == STATUS_FAILED:
                status_col = f"❌ Failed"
                err = item.get("error_message", "Error")
                out_col = f"`{err[:35]}...`" if len(err) > 35 else f"`{err}`"
            elif st == STATUS_IN_PROGRESS:
                status_col = "⏳ Processing..."
                out_col = "Transcribing now"
            else:
                placeholder = item.get("placeholder_file", "")
                status_col = "⏸️ Pending"
                out_col = f"`{placeholder}`"

            lines.append(f"| {idx} | [{v_title}]({v_url}) | {dur} | {status_col} | {out_col} |")

        lines.append("")
        lines.append("---")
        lines.append("*Generated automatically by Universal Transcriber v0.1-beta by @seanbuilds.*")
        lines.append("")

        index_path.write_text("\n".join(lines), encoding="utf-8")
