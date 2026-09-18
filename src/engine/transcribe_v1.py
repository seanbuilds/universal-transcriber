"""Metal GPU Whisper Transcription Engine (v1)."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from config_v1 import WHISPER_MODEL_CANDIDATES


class TranscriptionError(Exception):
    """Raised when ASR transcription fails."""
    pass


class WhisperTranscriber:
    """Executes Whisper models with Apple Silicon Metal acceleration."""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or self.find_best_model()

    @staticmethod
    def find_best_model() -> Optional[Path]:
        """Search standard macOS paths for pre-downloaded ggml Whisper models."""
        for candidate in WHISPER_MODEL_CANDIDATES:
            p = Path(candidate).expanduser().resolve()
            if p.exists() and p.is_file():
                return p
        return None

    def transcribe(self, wav_path: Path, output_dir: Path) -> List[Dict[str, Any]]:
        """Transcribe 16kHz WAV file into timestamped segment dictionaries."""
        if not wav_path.exists():
            raise TranscriptionError(f"Audio file not found: {wav_path}")

        whisper_bin = shutil.which("whisper-cli")
        if whisper_bin and self.model_path and self.model_path.exists():
            return self._run_whisper_cli(whisper_bin, wav_path, output_dir)

        # Fallback to mlx-whisper
        return self._run_mlx_whisper(wav_path)

    def _run_whisper_cli(self, whisper_bin: str, wav_path: Path, output_dir: Path) -> List[Dict[str, Any]]:
        """Run whisper-cli binary on Apple Silicon Metal GPU."""
        output_base = output_dir / "whisper_raw"
        cmd = [
            whisper_bin,
            "-m", str(self.model_path),
            "-f", str(wav_path),
            "-oj",
            "-of", str(output_base),
            "-t", "8",
            "--print-progress", "false"
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
            if res.returncode != 0:
                raise TranscriptionError(f"whisper-cli failed: {res.stderr}")
        except subprocess.TimeoutExpired:
            raise TranscriptionError("whisper-cli timed out.")

        json_file = output_dir / "whisper_raw.json"
        if not json_file.exists():
            raise TranscriptionError("whisper-cli completed but did not produce whisper_raw.json")

        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception as e:
            raise TranscriptionError(f"Failed to parse whisper-cli JSON output: {e}")

        segments = []
        for item in data.get("transcription", []):
            offsets = item.get("offsets", {})
            from_ms = offsets.get("from", 0)
            to_ms = offsets.get("to", 0)
            text = item.get("text", "").strip()
            if not text:
                continue

            start_s = from_ms / 1000.0
            end_s = to_ms / 1000.0
            ts_str = f"{int(start_s // 3600):02d}:{int((start_s % 3600) // 60):02d}:{int(start_s % 60):02d}"

            segments.append({
                "start": start_s,
                "end": end_s,
                "ts": ts_str,
                "text": text
            })

        return segments

    def _run_mlx_whisper(self, wav_path: Path) -> List[Dict[str, Any]]:
        """Fallback execution using mlx-whisper on Apple Silicon GPU."""
        try:
            import mlx_whisper
        except ImportError:
            raise TranscriptionError(
                "Neither whisper-cli with a downloaded model nor mlx-whisper was found. "
                "Install whisper.cpp via `brew install whisper-cpp` or install mlx-whisper."
            )

        try:
            result = mlx_whisper.transcribe(
                str(wav_path),
                path_or_hf_repo="mlx-community/whisper-large-v3-turbo"
            )
        except Exception as e:
            raise TranscriptionError(f"mlx-whisper failed: {e}")

        segments = []
        for s in result.get("segments", []):
            text = s.get("text", "").strip()
            if not text:
                continue
            start_s = float(s.get("start", 0.0))
            end_s = float(s.get("end", 0.0))
            ts_str = f"{int(start_s // 3600):02d}:{int((start_s % 3600) // 60):02d}:{int(start_s % 60):02d}"
            segments.append({
                "start": start_s,
                "end": end_s,
                "ts": ts_str,
                "text": text
            })

        return segments
