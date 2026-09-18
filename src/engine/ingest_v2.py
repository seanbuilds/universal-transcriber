"""Audio/Video Ingestion & Conversion Engine (v2).
<!-- v2 – Hardened timeouts, network retries, playlist indexing, device node security checks -->
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

from config_v2 import SAMPLE_RATE, CHANNELS, AUDIO_FORMAT, TEMP_DIR, MAX_DOWNLOAD_TIMEOUT_SECONDS


class IngestionError(Exception):
    """Raised when audio extraction or conversion fails."""
    pass


class MediaIngestor:
    """Extracts and standardizes audio from YouTube or local media files."""

    def __init__(self, temp_dir: Path = TEMP_DIR):
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def is_remote_url(source: str) -> bool:
        """Check if source is a web or YouTube URL."""
        return source.startswith("http://") or source.startswith("https://")

    def inspect_source(self, source: str) -> Dict[str, Any]:
        """Extract metadata from local file or YouTube source with full playlist support."""
        meta = {
            "title": "Untitled Recording",
            "source": source,
            "date": "",
            "duration": 0,
            "duration_str": "Unknown",
            "is_playlist": False,
            "items": []
        }

        if self.is_remote_url(source):
            cmd = [
                "yt-dlp",
                "--dump-json",
                "--flat-playlist",
                "--socket-timeout", "30",
                "--retries", "5",
                source
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if res.returncode == 0:
                    lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
                    if len(lines) > 1:
                        meta["is_playlist"] = True
                        for l in lines:
                            try:
                                item = json.loads(l)
                                v_id = item.get("id") or ""
                                meta["items"].append({
                                    "id": v_id,
                                    "title": item.get("title", "Untitled"),
                                    "url": item.get("url") or (f"https://www.youtube.com/watch?v={v_id}" if v_id else source)
                                })
                            except Exception:
                                continue
                        meta["title"] = f"Playlist ({len(meta['items'])} items)"
                    elif len(lines) == 1:
                        item = json.loads(lines[0])
                        meta["title"] = item.get("title", "Untitled")
                        meta["date"] = item.get("upload_date", "")
                        if meta["date"] and len(meta["date"]) == 8:
                            meta["date"] = f"{meta['date'][:4]}-{meta['date'][4:6]}-{meta['date'][6:]}"
                        dur = item.get("duration", 0) or 0
                        meta["duration"] = int(dur)
                        d_s = meta["duration"]
                        meta["duration_str"] = f"{d_s // 3600:02d}:{(d_s % 3600) // 60:02d}:{d_s % 60:02d}"
            except Exception:
                meta["title"] = "Web Recording"
        else:
            p = Path(source).resolve()
            # Security: validate regular file, reject device nodes (/dev/zero, /dev/urandom)
            if not p.exists():
                raise IngestionError(f"Local file does not exist: {p}")
            if not p.is_file():
                raise IngestionError(f"Target is not a regular media file (device nodes, pipes, and directories rejected): {p}")

            meta["title"] = p.stem.replace("_", " ").title()
            ffprobe = shutil.which("ffprobe")
            if ffprobe:
                try:
                    probe_cmd = [
                        ffprobe, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(p)
                    ]
                    pres = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                    if pres.returncode == 0 and pres.stdout.strip():
                        d_float = float(pres.stdout.strip())
                        meta["duration"] = int(d_float)
                        d_s = meta["duration"]
                        meta["duration_str"] = f"{d_s // 3600:02d}:{(d_s % 3600) // 60:02d}:{d_s % 60:02d}"
                except Exception:
                    pass

        return meta

    def extract_audio(self, source: str, job_id: str) -> Tuple[Path, Dict[str, Any]]:
        """Extract audio to 16kHz mono WAV in a dedicated job subfolder with robust error handling."""
        job_dir = self.temp_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        wav_target = job_dir / "audio_16k.wav"

        meta = self.inspect_source(source)

        if self.is_remote_url(source):
            raw_audio = job_dir / "downloaded_stream.m4a"
            dl_cmd = [
                "yt-dlp",
                "-f", "ba/b",
                "-x",
                "--no-playlist",
                "--retries", "5",
                "--socket-timeout", "30",
                "--extractor-retries", "3",
                "-o", str(raw_audio),
                source
            ]
            try:
                subprocess.run(
                    dl_cmd,
                    check=True,
                    capture_output=True,
                    timeout=MAX_DOWNLOAD_TIMEOUT_SECONDS
                )
            except subprocess.TimeoutExpired:
                self.cleanup_job(job_id)
                raise IngestionError(f"yt-dlp download timed out after {MAX_DOWNLOAD_TIMEOUT_SECONDS}s.")
            except subprocess.CalledProcessError as e:
                self.cleanup_job(job_id)
                err_msg = e.stderr.decode(errors="replace") if e.stderr else str(e)
                raise IngestionError(f"yt-dlp download failed: {err_msg}")

            if not raw_audio.exists() or raw_audio.stat().st_size == 0:
                self.cleanup_job(job_id)
                raise IngestionError("Downloaded audio file is missing or 0 bytes.")

            convert_cmd = [
                "ffmpeg", "-y",
                "-i", str(raw_audio),
                "-ar", str(SAMPLE_RATE),
                "-ac", str(CHANNELS),
                "-c:a", AUDIO_FORMAT,
                str(wav_target)
            ]
            try:
                subprocess.run(convert_cmd, check=True, capture_output=True, timeout=300)
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.decode(errors="replace") if e.stderr else str(e)
                raise IngestionError(f"ffmpeg conversion failed: {err_msg}")
            finally:
                if raw_audio.exists():
                    raw_audio.unlink()
        else:
            local_src = Path(source).resolve()
            if not local_src.is_file():
                raise IngestionError(f"Invalid local source: {local_src}")

            convert_cmd = [
                "ffmpeg", "-y",
                "-i", str(local_src),
                "-ar", str(SAMPLE_RATE),
                "-ac", str(CHANNELS),
                "-c:a", AUDIO_FORMAT,
                str(wav_target)
            ]
            try:
                subprocess.run(convert_cmd, check=True, capture_output=True, timeout=300)
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.decode(errors="replace") if e.stderr else str(e)
                raise IngestionError(f"ffmpeg conversion failed: {err_msg}")

        if not wav_target.exists() or wav_target.stat().st_size == 0:
            raise IngestionError(f"Generated WAV file is missing or empty: {wav_target}")

        return wav_target, meta

    def cleanup_job(self, job_id: str) -> None:
        """Remove temporary directory and all partial files for a specific job."""
        job_dir = self.temp_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
