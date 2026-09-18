"""Audio/Video Ingestion & Catalog Discovery Engine (v4).
<!-- v4 – Comprehensive local media container support (.m4a, .mp3, .mp4, .mov, .mkv, .wav, .flac, .aac), ffprobe tag inspection, and video-bypassing extraction -->
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List, Set

from config_v3 import (
    SAMPLE_RATE,
    CHANNELS,
    AUDIO_FORMAT,
    TEMP_DIR,
    MAX_DOWNLOAD_TIMEOUT_SECONDS,
)
from src.engine.catalog_v1 import MediaCatalog, compute_item_hash


class IngestionError(Exception):
    """Raised when audio extraction, catalog discovery, or conversion fails."""
    pass


# Supported audio and video media containers
SUPPORTED_AUDIO_EXTENSIONS: Set[str] = {
    ".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus", ".aiff", ".aif", ".wma", ".alac"
}

SUPPORTED_VIDEO_EXTENSIONS: Set[str] = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv", ".wmv", ".m4v"
}

SUPPORTED_LOCAL_EXTENSIONS: Set[str] = SUPPORTED_AUDIO_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS


class MediaIngestorV4:
    """Extracts, standardizes, and catalogs audio from YouTube, RSS feeds, or local media."""

    def __init__(self, temp_dir: Path = TEMP_DIR, catalog: Optional[MediaCatalog] = None):
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = catalog or MediaCatalog()

    @staticmethod
    def is_remote_url(source: str) -> bool:
        """Check if source is a web or YouTube URL."""
        return source.startswith("http://") or source.startswith("https://")

    @classmethod
    def is_supported_local_media(cls, path_or_str: Path | str) -> bool:
        """Check if a local file path points to a supported audio/video container."""
        p = Path(path_or_str)
        return p.is_file() and p.suffix.lower() in SUPPORTED_LOCAL_EXTENSIONS

    @classmethod
    def scan_directory(cls, dir_path: Path | str, recursive: bool = False) -> List[Path]:
        """Scan a local directory for all supported audio and video files case-insensitively."""
        root = Path(dir_path).resolve()
        if not root.is_dir():
            return []

        matched: List[Path] = []
        iterator = root.rglob("*") if recursive else root.glob("*")
        for item in iterator:
            if item.is_file() and item.suffix.lower() in SUPPORTED_LOCAL_EXTENSIONS:
                matched.append(item)
        return sorted(matched, key=lambda x: x.name.lower())

    def inspect_source(self, source: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Extract metadata from local file, YouTube video, playlist, or RSS feed."""
        meta = {
            "title": "Untitled Recording",
            "source": source,
            "date": "",
            "duration": 0,
            "duration_str": "00:00:00",
            "is_playlist": False,
            "items": [],
            "format": "unknown",
            "media_type": "unknown",
            "size_bytes": 0,
        }

        if self.is_remote_url(source):
            meta["media_type"] = "remote_stream"
            # Check if this might be an RSS/Atom feed
            if any(source.lower().endswith(ext) for ext in [".xml", ".rss", ".atom", "feed"]):
                try:
                    items = self.parse_rss_feed(source)
                    if items:
                        meta["is_playlist"] = True
                        meta["items"] = items
                        meta["title"] = f"Podcast Feed ({len(items)} episodes)"
                        return meta
                except Exception:
                    pass

            # Inspect YouTube video or playlist via yt-dlp
            yt_dlp = shutil.which("yt-dlp")
            if not yt_dlp:
                meta["title"] = "Web Media Stream"
                return meta

            try:
                cmd = [
                    yt_dlp,
                    "--dump-single-json",
                    "--flat-playlist",
                    "--socket-timeout", "30",
                    "--retries", "5",
                ]
                if limit and limit > 0:
                    cmd.extend(["--playlist-end", str(limit)])
                cmd.append(source)

                res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if res.returncode == 0 and res.stdout.strip():
                    data = json.loads(res.stdout)
                    if "entries" in data and data["entries"]:
                        meta["is_playlist"] = True
                        meta["title"] = data.get("title", "Playlist")
                        for e in data["entries"]:
                            if not e:
                                continue
                            v_id = e.get("id") or ""
                            meta["items"].append({
                                "id": v_id,
                                "title": e.get("title", "Untitled"),
                                "url": e.get("url") or (f"https://www.youtube.com/watch?v={v_id}" if v_id else source),
                                "date": e.get("upload_date", ""),
                                "duration": int(e.get("duration", 0) or 0),
                            })
                    else:
                        meta["title"] = data.get("title", "Untitled Video")
                        meta["date"] = data.get("upload_date", "")
                        if meta["date"] and len(meta["date"]) == 8:
                            meta["date"] = f"{meta['date'][:4]}-{meta['date'][4:6]}-{meta['date'][6:]}"
                        dur = data.get("duration", 0) or 0
                        meta["duration"] = int(dur)
                        d_s = meta["duration"]
                        meta["duration_str"] = f"{d_s // 3600:02d}:{(d_s % 3600) // 60:02d}:{d_s % 60:02d}"
                else:
                    # Fallback to line-delimited json
                    fallback_cmd = [
                        yt_dlp,
                        "--dump-json",
                        "--flat-playlist",
                        "--socket-timeout", "30",
                        "--retries", "5",
                    ]
                    if limit and limit > 0:
                        fallback_cmd.extend(["--playlist-end", str(limit)])
                    fallback_cmd.append(source)
                    res = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=60)

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
                                        "url": item.get("url") or (f"https://www.youtube.com/watch?v={v_id}" if v_id else source),
                                        "date": item.get("upload_date", ""),
                                        "duration": int(item.get("duration", 0) or 0),
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
            if not p.exists():
                raise IngestionError(f"Local file does not exist: {p}")
            if not p.is_file():
                raise IngestionError(f"Target is not a regular media file (device nodes, pipes, and directories rejected): {p}")

            ext = p.suffix.lower()
            meta["format"] = ext.lstrip(".")
            meta["media_type"] = "video" if ext in SUPPORTED_VIDEO_EXTENSIONS else "audio"
            meta["size_bytes"] = p.stat().st_size
            meta["title"] = p.stem.replace("_", " ").title()

            ffprobe = shutil.which("ffprobe")
            if ffprobe:
                try:
                    probe_cmd = [
                        ffprobe, "-v", "error",
                        "-show_entries", "format=duration:format_tags=title,artist,album:stream=codec_type,sample_rate,channels",
                        "-of", "json",
                        str(p),
                    ]
                    pres = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                    if pres.returncode == 0 and pres.stdout.strip():
                        info = json.loads(pres.stdout)
                        fmt_info = info.get("format", {})
                        d_str = fmt_info.get("duration")
                        if d_str:
                            meta["duration"] = int(float(d_str))
                            d_s = meta["duration"]
                            meta["duration_str"] = f"{d_s // 3600:02d}:{(d_s % 3600) // 60:02d}:{d_s % 60:02d}"

                        # Use embedded tag title if clean and meaningful
                        tags = fmt_info.get("tags", {})
                        tag_title = tags.get("title") or tags.get("TITLE")
                        if tag_title and len(tag_title.strip()) > 1:
                            meta["title"] = tag_title.strip()
                except Exception:
                    pass

        return meta

    def _fallback_regex_parse_feed(self, xml_text: str) -> List[Dict[str, Any]]:
        """Fallback regex-based feed parsing for malformed XML."""
        items: List[Dict[str, Any]] = []
        item_blocks = re.findall(r'<item[\s>](.*?)</item>', xml_text, flags=re.DOTALL | re.IGNORECASE)
        for block in item_blocks:
            t_m = re.search(r'<title>(.*?)</title>', block, flags=re.DOTALL | re.IGNORECASE)
            title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', t_m.group(1)).strip() if t_m else "Untitled Episode"
            g_m = re.search(r'<guid.*?>(.*?)</guid>', block, flags=re.DOTALL | re.IGNORECASE)
            guid = g_m.group(1).strip() if g_m else ""
            enc_m = re.search(r'<enclosure[^>]+url=["\']([^"\']+)["\']', block, flags=re.IGNORECASE)
            url = enc_m.group(1).strip() if enc_m else ""
            if not url:
                l_m = re.search(r'<link>(.*?)</link>', block, flags=re.DOTALL | re.IGNORECASE)
                url = l_m.group(1).strip() if l_m else ""
            if url:
                items.append({
                    "id": guid or compute_item_hash(url),
                    "title": title,
                    "url": url,
                    "date": "",
                    "duration": 0,
                })
        return items

    def parse_rss_feed(self, feed_url_or_xml: str) -> List[Dict[str, Any]]:
        """Parse podcast RSS or Atom XML feed and extract media enclosures."""
        xml_content = ""
        stripped = feed_url_or_xml.strip()
        if self.is_remote_url(stripped):
            req = urllib.request.Request(
                stripped,
                headers={"User-Agent": "Universal-Transcriber/4.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                xml_content = resp.read().decode("utf-8", errors="replace")
        elif not stripped.startswith("<") and Path(stripped).exists():
            xml_content = Path(stripped).read_text(encoding="utf-8", errors="replace")
        else:
            xml_content = stripped

        # Clean illegal XML control characters and unescaped ampersands
        clean_xml = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', xml_content)
        clean_xml = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', clean_xml)

        try:
            root = ET.fromstring(clean_xml)
        except ET.ParseError:
            return self._fallback_regex_parse_feed(clean_xml)

        items: List[Dict[str, Any]] = []

        # RSS 2.0 handling
        for item in root.findall(".//item"):
            title_elem = item.find("title")
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else "Untitled Episode"

            guid_elem = item.find("guid")
            guid = guid_elem.text.strip() if guid_elem is not None and guid_elem.text else ""

            pub_elem = item.find("pubDate")
            pub_date = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""

            enclosure = item.find("enclosure")
            media_url = ""
            if enclosure is not None and "url" in enclosure.attrib:
                media_url = enclosure.attrib["url"]
            else:
                link_elem = item.find("link")
                if link_elem is not None and link_elem.text:
                    media_url = link_elem.text.strip()

            if media_url:
                item_id = guid or compute_item_hash(media_url)
                items.append({
                    "id": item_id,
                    "title": title,
                    "url": media_url,
                    "date": pub_date,
                    "duration": 0,
                })

        # Atom feed handling if no RSS items found
        if not items:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns) or root.findall(".//entry"):
                title_elem = entry.find("atom:title", ns) if entry.find("atom:title", ns) is not None else entry.find("title")
                title = title_elem.text.strip() if title_elem is not None and title_elem.text else "Untitled Entry"

                id_elem = entry.find("atom:id", ns) if entry.find("atom:id", ns) is not None else entry.find("id")
                entry_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""

                media_url = ""
                for link in entry.findall("atom:link", ns) or entry.findall("link"):
                    if link.attrib.get("rel") == "enclosure" or link.attrib.get("type", "").startswith("audio/"):
                        media_url = link.attrib.get("href", "")
                        break
                if not media_url:
                    first_link = entry.find("atom:link", ns)
                    if first_link is not None and "href" in first_link.attrib:
                        media_url = first_link.attrib["href"]

                if media_url:
                    items.append({
                        "id": entry_id or compute_item_hash(media_url),
                        "title": title,
                        "url": media_url,
                        "date": "",
                        "duration": 0,
                    })

        return items

    def extract_audio(self, source: str, job_id: str) -> Tuple[Path, Dict[str, Any]]:
        """Extract audio to 16kHz mono WAV in dedicated job subfolder."""
        job_dir = self.temp_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        wav_target = job_dir / "audio_16k.wav"

        meta = self.inspect_source(source)

        if self.is_remote_url(source):
            raw_output_template = job_dir / "stream_raw.%(ext)s"
            strategies = [
                # Strategy 1: Standard extraction
                [
                    "yt-dlp",
                    "-f", "ba/b",
                    "-x",
                    "--no-playlist",
                    "--retries", "5",
                    "--socket-timeout", "30",
                    "--extractor-retries", "3",
                    "-o", str(raw_output_template),
                    source,
                ],
                # Strategy 2: Android/Web player client fallback
                [
                    "yt-dlp",
                    "--extractor-args", "youtube:player_client=android,web",
                    "-f", "ba/b",
                    "-x",
                    "--no-playlist",
                    "--retries", "5",
                    "--socket-timeout", "30",
                    "--extractor-retries", "3",
                    "-o", str(raw_output_template),
                    source,
                ],
                # Strategy 3: iOS/Web client fallback
                [
                    "yt-dlp",
                    "--extractor-args", "youtube:player_client=ios,web",
                    "-f", "ba/b",
                    "-x",
                    "--no-playlist",
                    "--retries", "5",
                    "--socket-timeout", "30",
                    "--extractor-retries", "3",
                    "-o", str(raw_output_template),
                    source,
                ],
            ]

            cookie_path = Path.home() / ".config" / "yt-dlp" / "cookies.txt"
            if cookie_path.exists():
                for s in strategies:
                    s.extend(["--cookies", str(cookie_path)])

            download_success = False
            last_err = ""

            for cmd in strategies:
                try:
                    subprocess.run(
                        cmd,
                        check=True,
                        capture_output=True,
                        timeout=MAX_DOWNLOAD_TIMEOUT_SECONDS,
                    )
                    download_success = True
                    break
                except subprocess.TimeoutExpired:
                    last_err = f"yt-dlp download timed out after {MAX_DOWNLOAD_TIMEOUT_SECONDS}s."
                except subprocess.CalledProcessError as e:
                    last_err = e.stderr.decode(errors="replace") if e.stderr else str(e)
                    continue

            candidates = list(job_dir.glob("stream_raw.*")) + list(job_dir.glob("downloaded_stream.*"))
            valid_candidates = [f for f in candidates if f.is_file() and f.stat().st_size > 0]

            if not download_success and not valid_candidates:
                self.cleanup_job(job_id)
                raise IngestionError(f"yt-dlp download failed: {last_err.strip()}")

            if not valid_candidates:
                self.cleanup_job(job_id)
                raise IngestionError("Downloaded audio file is missing or 0 bytes.")

            raw_audio = valid_candidates[0]

            convert_cmd = [
                "ffmpeg", "-y",
                "-i", str(raw_audio),
                "-vn",
                "-ar", str(SAMPLE_RATE),
                "-ac", str(CHANNELS),
                "-c:a", AUDIO_FORMAT,
                str(wav_target),
            ]
            try:
                subprocess.run(convert_cmd, check=True, capture_output=True, timeout=300)
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.decode(errors="replace") if e.stderr else str(e)
                raise IngestionError(f"ffmpeg conversion failed: {err_msg}")
            finally:
                for f in candidates:
                    try:
                        if f.exists():
                            f.unlink()
                    except OSError:
                        pass
        else:
            local_src = Path(source).resolve()
            if not local_src.is_file():
                raise IngestionError(f"Invalid local source: {local_src}")

            # Optimize extraction: bypass video decoding (-vn), map primary audio stream
            convert_cmd = [
                "ffmpeg", "-y",
                "-i", str(local_src),
                "-vn",
                "-map", "0:a:0?",
                "-ar", str(SAMPLE_RATE),
                "-ac", str(CHANNELS),
                "-c:a", AUDIO_FORMAT,
                str(wav_target),
            ]
            try:
                subprocess.run(convert_cmd, check=True, capture_output=True, timeout=300)
            except subprocess.CalledProcessError:
                # Fallback to default audio mapping if stream specifier 0:a:0? is unsupported
                fallback_cmd = [
                    "ffmpeg", "-y",
                    "-i", str(local_src),
                    "-vn",
                    "-ar", str(SAMPLE_RATE),
                    "-ac", str(CHANNELS),
                    "-c:a", AUDIO_FORMAT,
                    str(wav_target),
                ]
                try:
                    subprocess.run(fallback_cmd, check=True, capture_output=True, timeout=300)
                except subprocess.CalledProcessError as e:
                    err_msg = e.stderr.decode(errors="replace") if e.stderr else str(e)
                    raise IngestionError(f"ffmpeg conversion failed for {local_src.name}: {err_msg}")

        if not wav_target.exists() or wav_target.stat().st_size == 0:
            raise IngestionError(f"Generated WAV file is missing or empty: {wav_target}")

        return wav_target, meta

    def cleanup_job(self, job_id: str) -> None:
        """Remove temporary job working directory."""
        job_dir = self.temp_dir / job_id
        if job_dir.exists():
            try:
                shutil.rmtree(job_dir, ignore_errors=True)
            except OSError:
                pass
