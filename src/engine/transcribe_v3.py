"""Metal GPU Whisper Streaming Transcription Engine (v3).
<!-- v3 – Chunked sliding window streaming transcription with real-time segment callbacks and wave slicing -->
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import wave
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from config_v3 import (
    WHISPER_MODEL_CANDIDATES,
    MIN_TRANSCRIBE_TIMEOUT_SECONDS,
    TIMEOUT_MULTIPLIER,
    RECOMMENDED_THREADS,
    STREAMING_CHUNK_SECONDS,
    STREAMING_OVERLAP_SECONDS,
)
from src.engine.healer_v2 import safe_deduplicate_overlap


class TranscriptionError(Exception):
    """Raised when ASR transcription fails."""
    pass


def format_timestamp(seconds: float) -> str:
    """Format float seconds to HH:MM:SS."""
    seconds = max(0.0, float(seconds))
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"


class WhisperTranscriberV3:
    """Executes Whisper models with streaming sliding windows and real-time callbacks."""

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

    def calculate_timeout(self, audio_duration_seconds: float) -> int:
        """Calculate adaptive timeout based on audio length."""
        if audio_duration_seconds <= 0:
            return MIN_TRANSCRIBE_TIMEOUT_SECONDS
        adaptive = int(MIN_TRANSCRIBE_TIMEOUT_SECONDS + (audio_duration_seconds * TIMEOUT_MULTIPLIER))
        return max(MIN_TRANSCRIBE_TIMEOUT_SECONDS, adaptive)

    def transcribe(
        self,
        wav_path: Path,
        output_dir: Path,
        audio_duration_seconds: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Monolithic transcription of WAV file."""
        if not wav_path.exists():
            raise TranscriptionError(f"Audio file not found: {wav_path}")

        # Check for mock testing environment
        mock_env = os.environ.get("UNIVERSAL_TRANSCRIBER_MOCK_ASR")
        if mock_env:
            try:
                return json.loads(mock_env)
            except Exception:
                pass

        timeout = self.calculate_timeout(audio_duration_seconds)
        whisper_bin = shutil.which("whisper-cli")

        if whisper_bin and self.model_path and self.model_path.exists():
            try:
                return self._run_whisper_cli(whisper_bin, wav_path, output_dir, use_gpu=True, timeout=timeout)
            except TranscriptionError as e:
                if "Metal" in str(e) or "failed" in str(e).lower():
                    return self._run_whisper_cli(whisper_bin, wav_path, output_dir, use_gpu=False, timeout=timeout)
                raise

        return self._run_mlx_whisper(wav_path)

    def transcribe_streaming(
        self,
        wav_path: Path,
        output_dir: Path,
        audio_duration_seconds: float = 0.0,
        chunk_duration: float = STREAMING_CHUNK_SECONDS,
        overlap: float = STREAMING_OVERLAP_SECONDS,
        segment_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Chunked sliding-window transcription with real-time per-segment callbacks.

        Transcribes audio in overlapping windows, compensating for boundary splits
        and streaming newly transcribed segments immediately to callers.
        """
        if not wav_path.exists():
            raise TranscriptionError(f"Audio file not found: {wav_path}")

        # If audio duration wasn't supplied, inspect directly from WAV header
        if audio_duration_seconds <= 0.0:
            try:
                with wave.open(str(wav_path), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    audio_duration_seconds = frames / float(rate) if rate > 0 else 0.0
            except Exception:
                audio_duration_seconds = 0.0

        # For very short files, run monolithic directly
        if audio_duration_seconds <= chunk_duration or chunk_duration <= 0:
            segments = self.transcribe(wav_path, output_dir, audio_duration_seconds)
            if segment_callback:
                for seg in segments:
                    segment_callback(seg)
            if progress_callback:
                progress_callback(100, "Completed streaming transcription")
            return segments

        step_size = max(1.0, chunk_duration - overlap)
        total_duration = audio_duration_seconds
        current_start = 0.0
        chunk_index = 0
        all_segments: List[Dict[str, Any]] = []
        last_text = ""

        streaming_temp = output_dir / "streaming_chunks"
        streaming_temp.mkdir(parents=True, exist_ok=True)

        try:
            while current_start < total_duration:
                current_chunk_duration = min(chunk_duration, total_duration - current_start)
                if current_chunk_duration < 0.5:
                    break

                chunk_wav = streaming_temp / f"chunk_{chunk_index:05d}.wav"
                self._slice_wav(wav_path, chunk_wav, current_start, current_chunk_duration)

                # Report chunk start
                pct = int(min(99, (current_start / total_duration) * 100))
                if progress_callback:
                    progress_callback(pct, f"Transcribing window at {format_timestamp(current_start)}")

                chunk_segments = self.transcribe(
                    chunk_wav,
                    streaming_temp,
                    audio_duration_seconds=current_chunk_duration,
                )

                for raw_seg in chunk_segments:
                    raw_text = raw_seg.get("text", "").strip()
                    if not raw_text:
                        continue

                    # Adjust timestamps to global timeline
                    global_start = current_start + float(raw_seg.get("start", 0.0))
                    global_end = current_start + float(raw_seg.get("end", 0.0))

                    # Deduplicate overlapping words from window boundary
                    cleaned_text = safe_deduplicate_overlap(last_text, raw_text)
                    if not cleaned_text:
                        continue

                    last_text = cleaned_text
                    seg_dict = {
                        "start": round(global_start, 2),
                        "end": round(global_end, 2),
                        "ts": format_timestamp(global_start),
                        "text": cleaned_text,
                    }
                    all_segments.append(seg_dict)

                    if segment_callback:
                        segment_callback(seg_dict)

                # Clean up chunk WAV immediately to preserve disk space
                if chunk_wav.exists():
                    try:
                        chunk_wav.unlink()
                    except Exception:
                        pass

                current_start += step_size
                chunk_index += 1

            if progress_callback:
                progress_callback(100, "Streaming transcription complete")

            return all_segments

        finally:
            if streaming_temp.exists():
                shutil.rmtree(streaming_temp, ignore_errors=True)

    def _slice_wav(self, src_path: Path, dst_path: Path, start_s: float, duration_s: float) -> None:
        """Fast lossless WAV slicing using the standard library wave module."""
        with wave.open(str(src_path), "rb") as r:
            params = r.getparams()
            framerate = r.getframerate()
            start_frame = int(start_s * framerate)
            num_frames = int(duration_s * framerate)

            total_frames = r.getnframes()
            if start_frame >= total_frames:
                data = b""
            else:
                r.setpos(start_frame)
                data = r.readframes(min(num_frames, total_frames - start_frame))

        with wave.open(str(dst_path), "wb") as w:
            w.setparams(params)
            w.writeframes(data)

    def _run_whisper_cli(
        self,
        whisper_bin: str,
        wav_path: Path,
        output_dir: Path,
        use_gpu: bool,
        timeout: int,
    ) -> List[Dict[str, Any]]:
        """Run whisper-cli binary with specified hardware acceleration."""
        output_base = output_dir / f"whisper_raw_{wav_path.stem}"
        threads = str(RECOMMENDED_THREADS)

        cmd = [
            whisper_bin,
            "-m", str(self.model_path),
            "-f", str(wav_path),
            "-oj",
            "-of", str(output_base),
            "-t", threads,
            "--print-progress", "false",
        ]

        if not use_gpu:
            cmd.append("-ng")

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode != 0:
                raise TranscriptionError(f"whisper-cli failed (GPU={use_gpu}): {res.stderr}")
        except subprocess.TimeoutExpired:
            raise TranscriptionError(f"whisper-cli timed out after {timeout} seconds.")

        json_file = output_dir / f"whisper_raw_{wav_path.stem}.json"
        if not json_file.exists():
            # Try fallback without stem
            alt_json = output_dir / "whisper_raw.json"
            if alt_json.exists():
                json_file = alt_json
            else:
                raise TranscriptionError(f"whisper-cli completed but did not produce {json_file.name}")

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
            ts_str = format_timestamp(start_s)

            segments.append({
                "start": start_s,
                "end": end_s,
                "ts": ts_str,
                "text": text,
            })

        return segments

    def _run_mlx_whisper(self, wav_path: Path) -> List[Dict[str, Any]]:
        """Fallback execution using mlx-whisper on Apple Silicon GPU."""
        try:
            import mlx_whisper
        except ImportError:
            raise TranscriptionError(
                "Neither whisper-cli with a downloaded model nor mlx-whisper was found. "
                "Please run `brew install whisper-cpp` or install mlx-whisper."
            )

        try:
            result = mlx_whisper.transcribe(
                str(wav_path),
                path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
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
            ts_str = format_timestamp(start_s)
            segments.append({
                "start": start_s,
                "end": end_s,
                "ts": ts_str,
                "text": text,
            })

        return segments


WhisperTranscriber = WhisperTranscriberV3
