"""Atomic Multi-Format Transcript Exporter (v2).
<!-- v2 – Atomic temp-and-replace writes, sanitized folder naming, bounded SRT timecodes -->
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from config_v2 import TRANSCRIPTS_DIR


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp format: HH:MM:SS,mmm."""
    seconds = max(0.0, float(seconds))
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msec = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msec:03d}"


def sanitize_name(name: str) -> str:
    """Strictly sanitize string for safe folder and file naming (no traversal sequences)."""
    clean = re.sub(r'[^a-zA-Z0-9_\- ]', '', name).strip('. ')
    return clean[:60] or "Untitled"


def atomic_write_text(target_path: Path, content: str) -> None:
    """Write text atomically via temporary file and atomic rename."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(target_path)


class TranscriptExporter:
    """Exports structured transcript blocks into Markdown, Plaintext, SRT, and JSON atomically."""

    def __init__(self, base_output_dir: Path = TRANSCRIPTS_DIR):
        self.base_output_dir = base_output_dir

    def export(
        self,
        blocks: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        custom_dir: Optional[Path] = None
    ) -> Dict[str, Path]:
        """Save all formats to target folder atomically, returning paths of created files."""
        raw_title = metadata.get("title", "Untitled Recording")
        raw_date = metadata.get("date", "")

        safe_title = sanitize_name(raw_title)
        safe_date = sanitize_name(raw_date)
        folder_name = f"{safe_date}_{safe_title}" if safe_date else safe_title

        target_dir = (custom_dir or self.base_output_dir) / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        md_path = target_dir / f"{folder_name}.md"
        txt_path = target_dir / f"{folder_name}.txt"
        srt_path = target_dir / f"{folder_name}.srt"
        json_path = target_dir / f"{folder_name}.json"

        participants = sorted(list(set(b.get("speaker", "Speaker") for b in blocks if b.get("speaker"))))

        # 1. Markdown
        md_lines = [
            f"# {raw_title}",
            "",
            f"**Date**: {raw_date or 'N/A'}  ",
            f"**Source**: {metadata.get('source', 'N/A')}  ",
            f"**Duration**: {metadata.get('duration_str', 'N/A')}  ",
            "",
            "### Participants",
            "",
        ]
        for p in participants:
            md_lines.append(f"- **{p}**")
        md_lines.extend([
            "",
            "---",
            "",
            "## Verbatim Transcript",
            "",
        ])
        for b in blocks:
            md_lines.append(f"### [{b.get('ts', '00:00:00')}] {b.get('speaker', 'Speaker')}")
            md_lines.append("")
            md_lines.append(b.get("text", ""))
            md_lines.append("")

        atomic_write_text(md_path, "\n".join(md_lines))

        # 2. Plaintext
        txt_lines = [
            "=" * 80,
            raw_title,
            "=" * 80,
            f"Date: {raw_date or 'N/A'}",
            f"Source: {metadata.get('source', 'N/A')}",
            f"Duration: {metadata.get('duration_str', 'N/A')}",
            "Participants:",
        ]
        for p in participants:
            txt_lines.append(f"  - {p}")
        txt_lines.extend([
            "=" * 80,
            "",
        ])
        for b in blocks:
            txt_lines.append(f"[{b.get('ts', '00:00:00')}] {b.get('speaker', 'Speaker')}: {b.get('text', '')}")
            txt_lines.append("")

        atomic_write_text(txt_path, "\n".join(txt_lines))

        # 3. Subtitles (.srt) with monotonic timestamps
        srt_lines = []
        for idx, b in enumerate(blocks, 1):
            s_val = max(0.0, float(b.get("start", 0.0)))
            e_val = max(s_val + 0.5, float(b.get("end", s_val + 3.0)))
            s_time = format_srt_timestamp(s_val)
            e_time = format_srt_timestamp(e_val)
            srt_lines.append(str(idx))
            srt_lines.append(f"{s_time} --> {e_time}")
            srt_lines.append(f"{b.get('speaker', 'Speaker')}: {b.get('text', '')}")
            srt_lines.append("")

        atomic_write_text(srt_path, "\n".join(srt_lines))

        # 4. JSON
        json_data = {
            "metadata": metadata,
            "participants": participants,
            "total_blocks": len(blocks),
            "transcript": blocks
        }
        atomic_write_text(json_path, json.dumps(json_data, indent=2))

        return {
            "dir": target_dir,
            "md": md_path,
            "txt": txt_path,
            "srt": srt_path,
            "json": json_path
        }
