"""Master Pipeline Coordinator with Live Acoustic Diarization & SQLite Tracking (v2).
<!-- v2 – Direct acoustic voice embedding extraction, persistent queue integration, adaptive timeouts -->
"""

import math
import struct
import wave
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from src.engine.ingest_v2 import MediaIngestor
from src.engine.transcribe_v2 import WhisperTranscriber
from src.engine.diarize_v2 import SpeakerDatabase, normalize_vector
from src.engine.healer_v2 import TurnCoalescer
from src.engine.export_v2 import TranscriptExporter
from src.engine.queue_v2 import JobQueue, STATUS_DOWNLOADING, STATUS_TRANSCRIBING, STATUS_DIARIZING, STATUS_COMPLETED, STATUS_FAILED
from src.playbooks.loader_v2 import PlaybookLoader, Playbook
from config_v2 import TRANSCRIPTS_DIR, TEMP_DIR, DEFAULT_PLAYBOOK, QUEUE_DB_PATH


def extract_acoustic_embedding(wav_path: Path, start_s: float, end_s: float, num_bands: int = 64) -> List[float]:
    """Extract an acoustic frequency-energy vector from a WAV slice."""
    try:
        with wave.open(str(wav_path), "rb") as wf:
            framerate = wf.getframerate()
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()

            start_frame = max(0, int(start_s * framerate))
            end_frame = min(wf.getnframes(), int(end_s * framerate))
            frame_count = end_frame - start_frame

            if frame_count <= 0:
                return [0.0] * num_bands

            wf.setpos(start_frame)
            raw_bytes = wf.readframes(frame_count)

            if sampwidth == 2:
                fmt = f"<{len(raw_bytes)//2}h"
                samples = struct.unpack(fmt, raw_bytes)
            else:
                return [0.0] * num_bands

            if n_channels > 1:
                samples = samples[::n_channels]

            # Compute banded energy distribution
            chunk_len = max(1, len(samples) // num_bands)
            bands = []
            for b in range(num_bands):
                chunk = samples[b * chunk_len : (b + 1) * chunk_len]
                if chunk:
                    rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
                    bands.append(rms)
                else:
                    bands.append(0.0)

            return normalize_vector(bands)
    except Exception:
        return [0.0] * num_bands


class TranscriptionPipeline:
    """Orchestrates end-to-end media transcription, acoustic diarization, and healing."""

    def __init__(
        self,
        output_dir: Path = TRANSCRIPTS_DIR,
        model_path: Optional[Path] = None,
        similarity_threshold: float = 0.82
    ):
        self.output_dir = output_dir
        self.ingestor = MediaIngestor(temp_dir=TEMP_DIR)
        self.transcriber = WhisperTranscriber(model_path=model_path)
        self.speaker_db = SpeakerDatabase(similarity_threshold=similarity_threshold)
        self.exporter = TranscriptExporter(base_output_dir=output_dir)
        self.playbook_loader = PlaybookLoader()
        self.queue = JobQueue(db_path=QUEUE_DB_PATH)

    def process(
        self,
        source: str,
        playbook_name: str = DEFAULT_PLAYBOOK,
        job_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> Dict[str, Any]:
        """Execute the full transcription and self-healing pipeline for a single source."""
        job_id = job_id or f"job_{uuid.uuid4().hex[:8]}"
        job_dir = TEMP_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        self.queue.enqueue(job_id=job_id, source_url=source, playbook=playbook_name)

        def emit(stage: str, percent: int, status: str = STATUS_TRANSCRIBING):
            self.queue.update_progress(job_id, status=status, progress_pct=percent, message=stage)
            if progress_callback:
                progress_callback(stage, percent)

        try:
            # 1. Load Playbook
            emit(f"Loading playbook '{playbook_name}'", 5, status=STATUS_DOWNLOADING)
            playbook = self.playbook_loader.load(playbook_name)

            # 2. Ingest / Extract Audio
            emit(f"Extracting audio from source", 15, status=STATUS_DOWNLOADING)
            wav_path, meta = self.ingestor.extract_audio(source, job_id)
            audio_duration = meta.get("duration", 0)

            # 3. Transcribe with Metal GPU Whisper (adaptive timeout)
            emit("Transcribing audio on Metal GPU", 40, status=STATUS_TRANSCRIBING)
            raw_segments = self.transcriber.transcribe(
                wav_path,
                job_dir,
                audio_duration_seconds=float(audio_duration)
            )

            # 4. Live Acoustic Diarization & Voice Matching (Finding R2-01 Fix!)
            emit("Extracting acoustic voice vectors & clustering speakers", 65, status=STATUS_DIARIZING)
            diarized_segments = []
            for seg in raw_segments:
                emb = extract_acoustic_embedding(wav_path, seg["start"], seg["end"])
                spk_id = self.speaker_db.match_or_register(emb, session_id=job_id)
                display_name = self.speaker_db.get_display_name(spk_id)
                seg_copy = dict(seg)
                seg_copy["speaker"] = display_name
                seg_copy["acoustic_speaker_id"] = spk_id
                diarized_segments.append(seg_copy)

            self.speaker_db.save(force=True)

            # 5. Self-Healing & Temporal-Bounded Turn Coalescing
            emit("Applying self-healing turn coalescing", 80, status=STATUS_DIARIZING)
            coalescer = TurnCoalescer(playbook=playbook)
            healed_blocks = coalescer.heal_and_coalesce(diarized_segments)

            # 6. Atomic Export to .md, .txt, .srt, .json
            emit("Exporting multi-format transcripts atomically", 90, status=STATUS_COMPLETED)
            exported_paths = self.exporter.export(
                blocks=healed_blocks,
                metadata=meta,
                custom_dir=self.output_dir
            )

            result_payload = {
                "status": "success",
                "job_id": job_id,
                "metadata": meta,
                "playbook": playbook.name,
                "total_blocks": len(healed_blocks),
                "export_dir": str(exported_paths["dir"]),
                "files": {
                    "md": str(exported_paths["md"]),
                    "txt": str(exported_paths["txt"]),
                    "srt": str(exported_paths["srt"]),
                    "json": str(exported_paths["json"])
                }
            }

            self.queue.mark_completed(job_id, result_payload)
            emit("Completed successfully", 100, status=STATUS_COMPLETED)
            return result_payload

        except Exception as e:
            self.queue.mark_failed(job_id, str(e))
            raise
        finally:
            self.ingestor.cleanup_job(job_id)
