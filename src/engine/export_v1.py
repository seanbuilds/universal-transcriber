"""Multi-Format Transcript Exporter (v1)."""

import json
import re
from pathlib import Path
from typing import List, Dict, Any

from config_v1 import TRANSCRIPTS_DIR


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp format: HH:MM:SS,mmm."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msec = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msec:03d}"


def sanitize_folder_name(name: str) -> str:
    """Strip illegal filename characters and clean whitespace."""
    clean = re.sub(r'[\\/:*?"<>|]', '', name).strip('. ')
    return clean[:80] or "Untitled_Recording"


class TranscriptExporter:
    """Exports structured transcript blocks into Markdown, Plaintext, SRT, and JSON."""

    def __init__(self, base_output_dir: Path = TRANSCRIPTS_DIR):
        self.base_output_dir = base_output_dir

    def export(
        self,
        blocks: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        custom_dir: Path = None
    ) -> Dict[str, Path]:
        """Save all formats to target folder, returning paths of created files."""
        title = metadata.get("title", "Untitled Recording")
        date_str = metadata.get("date", "")
        safe_title = sanitize_folder_name(title)
        folder_name = f"{date_str}_{safe_title}" if date_str else safe_title

        target_dir = (custom_dir or self.base_output_dir) / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        md_path = target_dir / f"{folder_name}.md"
        txt_path = target_dir / f"{folder_name}.txt"
        srt_path = target_dir / f"{folder_name}.srt"
        json_path = target_dir / f"{folder_name}.json"

        # Unique participant list
        participants = sorted(list(set(b.get("speaker", "Speaker") for b in blocks if b.get("speaker"))))

        # 1. Markdown
        md_lines = [
            f"# {title}",
            "",
            f"**Date**: {date_str or 'N/A'}  ",
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

        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        # 2. Plaintext
        txt_lines = [
            "=" * 80,
            title,
            "=" * 80,
            f"Date: {date_str or 'N/A'}",
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

        txt_path.write_text("\n".join(txt_lines), encoding="utf-8")

        # 3. Subtitles (.srt)
        srt_lines = []
        for idx, b in enumerate(blocks, 1):
            s_time = format_srt_timestamp(b.get("start", 0.0))
            e_time = format_srt_timestamp(b.get("end", b.get("start", 0.0) + 3.0))
            srt_lines.append(str(idx))
            srt_lines.append(f"{s_time} --> {e_time}")
            srt_lines.append(f"{b.get('speaker', 'Speaker')}: {b.get('text', '')}")
            srt_lines.append("")

        srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

        # 4. JSON
        json_data = {
            "metadata": metadata,
            "participants": participants,
            "total_blocks": len(blocks),
            "transcript": blocks
        }
        json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")

        return {
            "dir": target_dir,
            "md": md_path,
            "txt": txt_path,
            "srt": srt_path,
            "json": json_path
        }
