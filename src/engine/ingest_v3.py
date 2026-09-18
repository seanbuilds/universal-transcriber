"""Audio/Video Ingestion & Catalog Discovery Engine (v3).
<!-- v3 – YouTube channel indexing, RSS/Atom podcast parsing, SQLite catalog idempotency -->
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
from typing import Dict, Any, Tuple, Optional, List

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


class MediaIngestorV3:
    """Extracts, standardizes, and catalogs audio from YouTube, RSS feeds, or local media."""

    def __init__(self, temp_dir: Path = TEMP_DIR, catalog: Optional[MediaCatalog] = None):
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = catalog or MediaCatalog()

    @staticmethod
    def is_remote_url(source: str) -> bool:
        """Check if source is a web or YouTube URL."""
        return source.startswith("http://") or source.startswith("https://")

    def inspect_source(self, source: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Extract metadata from single file, YouTube video, or playlist."""
        meta = {
            "title": "Untitled Recording",
            "source": source,
            "date": "",
            "duration": 0,
            "duration_str": "Unknown",
            "is_playlist": False,
            "items": [],
        }

        if self.is_remote_url(source):
            # Check if this might be an RSS/Atom feed
            if any(source.lower().endswith(ext) for ext in [".xml", ".rss", ".atom", "feed"]):
                try:
                    rss_items = self.parse_rss_feed(source)
                    if rss_items:
                        if limit and limit > 0:
                            rss_items = rss_items[:limit]
                        meta["is_playlist"] = True
                        meta["items"] = rss_items
                        meta["title"] = f"RSS Feed ({len(rss_items)} items)"
                        return meta
                except Exception:
                    pass

            cmd = [
                "yt-dlp",
                "--dump-json",
                "--flat-playlist",
                "--socket-timeout", "30",
                "--retries", "5",
            ]
            if limit and limit > 0:
                cmd.extend(["--playlist-end", str(limit)])
            cmd.append(source)

            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if res.returncode != 0:
                    # Retry with android,web client fallback on 403 or throttling
                    fallback_cmd = [
                        "yt-dlp",
                        "--extractor-args", "youtube:player_client=android,web",
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

            meta["title"] = p.stem.replace("_", " ").title()
            ffprobe = shutil.which("ffprobe")
            if ffprobe:
                try:
                    probe_cmd = [
                        ffprobe, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(p),
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
                headers={"User-Agent": "Universal-Transcriber/3.0"}
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

            # Check enclosure
            enclosure = item.find("enclosure")
            media_url = ""
            if enclosure is not None and "url" in enclosure.attrib:
                media_url = enclosure.attrib["url"]
            else:
                # Fallback to link
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
                    rel = link.attrib.get("rel", "")
                    href = link.attrib.get("href", "")
                    if rel in ("enclosure", "alternate") and href:
                        media_url = href
                        break

                if media_url:
                    item_id = entry_id or compute_item_hash(media_url)
                    items.append({
                        "id": item_id,
                        "title": title,
                        "url": media_url,
                        "date": "",
                        "duration": 0,
                    })

        return items

    def discover_catalog(
        self,
        source: str,
        catalog_source_name: str = "",
        force: bool = False,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Discover items from YouTube channel/playlist or RSS feed, indexing in SQLite catalog.

        Returns only un-transcribed items unless force=True.
        """
        source_name = catalog_source_name or source
        discovered_items: List[Dict[str, Any]] = []

        if self.is_remote_url(source):
            if any(source.lower().endswith(ext) for ext in [".xml", ".rss", ".atom", "feed"]):
                raw_items = self.parse_rss_feed(source)
                if limit and limit > 0:
                    raw_items = raw_items[:limit]
            else:
                meta = self.inspect_source(source, limit=limit)
                raw_items = meta.get("items", [])
                if not raw_items and not meta.get("is_playlist"):
                    raw_items = [{
                        "id": compute_item_hash(source),
                        "title": meta.get("title", "Recording"),
                        "url": source,
                        "date": meta.get("date", ""),
                        "duration": meta.get("duration", 0),
                    }]
        elif source.strip().startswith("<") or any(source.lower().endswith(ext) for ext in [".xml", ".rss", ".atom"]):
            raw_items = self.parse_rss_feed(source)
            if limit and limit > 0:
                raw_items = raw_items[:limit]
        else:
            src_path = Path(source).resolve()
            if src_path.is_dir():
                raw_items = []
                for ext in ("*.mp4", "*.mov", "*.mkv", "*.m4a", "*.mp3", "*.wav"):
                    for f in sorted(src_path.glob(ext)):
                        raw_items.append({
                            "id": compute_item_hash(str(f)),
                            "title": f.stem,
                            "url": str(f),
                            "date": "",
                            "duration": 0,
                        })
                if limit and limit > 0:
                    raw_items = raw_items[:limit]
            else:
                raw_items = [{
                    "id": compute_item_hash(str(src_path)),
                    "title": src_path.stem,
                    "url": str(src_path),
                    "date": "",
                    "duration": 0,
                }]

        # Index in catalog and filter already completed items
        for it in raw_items:
            item_id = it.get("id") or compute_item_hash(it["url"])
            self.catalog.register_item(
                item_id=item_id,
                url=it["url"],
                title=it.get("title", "Untitled"),
                catalog_source=source_name,
                published_date=it.get("date", ""),
                duration_seconds=it.get("duration", 0),
            )

            is_done = self.catalog.is_transcribed(item_id)
            if not is_done or force:
                it["item_id"] = item_id
                discovered_items.append(it)

        return discovered_items

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

            # If user has exported cookies in standard locations, include cookies
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

            # Candidate raw audio files (both new template and legacy mock filename)
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

            convert_cmd = [
                "ffmpeg", "-y",
                "-i", str(local_src),
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

        if not wav_target.exists() or wav_target.stat().st_size == 0:
            raise IngestionError(f"Generated WAV file is missing or empty: {wav_target}")

        return wav_target, meta

    def cleanup_job(self, job_id: str) -> None:
        """Remove temporary directory and partial files for a specific job."""
        job_dir = self.temp_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)


MediaIngestor = MediaIngestorV3
