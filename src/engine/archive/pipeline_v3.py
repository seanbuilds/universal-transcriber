# src/engine/pipeline_v3.py
"""Master Pipeline Coordinator with Neural Embeddings & Dual Clustering (v3).
<!-- v3 – Support for two-pass Agglomerative Hierarchical Clustering (AHC) & VoiceEmbeddingExtractor -->
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from src.engine.ingest_v2 import MediaIngestor
from src.engine.transcribe_v2 import WhisperTranscriber
from src.engine.diarize_v3 import SpeakerDatabaseV3
from src.engine.healer_v2 import TurnCoalescer
from src.engine.export_v2 import TranscriptExporter
from src.engine.queue_v2 import (
    JobQueue,
    STATUS_DOWNLOADING,
    STATUS_TRANSCRIBING,
    STATUS_DIARIZING,
    STATUS_COMPLETED,
    STATUS_FAILED,
)
from src.playbooks.loader_v2 import PlaybookLoader
from config_v2 import TRANSCRIPTS_DIR, TEMP_DIR, DEFAULT_PLAYBOOK, QUEUE_DB_PATH


class TranscriptionPipelineV3:
    """Orchestrates end-to-end media transcription, neural diarization, and healing."""

    def __init__(
        self,
        output_dir: Path = TRANSCRIPTS_DIR,
        model_path: Optional[Path] = None,
        similarity_threshold: float = 0.82,
        clustering_mode: str = "ahc",  # 'ahc' or 'online'
        speaker_library_path: Optional[Path] = None,
    ):
        self.output_dir = output_dir
        self.clustering_mode = clustering_mode
        self.ingestor = MediaIngestor(temp_dir=TEMP_DIR)
        self.transcriber = WhisperTranscriber(model_path=model_path)
        self.speaker_db = SpeakerDatabaseV3(
            storage_path=speaker_library_path,
            similarity_threshold=similarity_threshold,
        )
        self.exporter = TranscriptExporter(base_output_dir=output_dir)
        self.playbook_loader = PlaybookLoader()
        self.queue = JobQueue(db_path=QUEUE_DB_PATH)

    def process(
        self,
        source: str,
        playbook_name: str = DEFAULT_PLAYBOOK,
        job_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> Dict[str, Any]:
        """Execute the full transcription, neural diarization, and self-healing pipeline."""
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
            emit("Extracting audio from source", 15, status=STATUS_DOWNLOADING)
            wav_path, meta = self.ingestor.extract_audio(source, job_id)
            audio_duration = meta.get("duration", 0)

            # 3. Transcribe with Metal GPU Whisper
            emit("Transcribing audio on Metal GPU", 40, status=STATUS_TRANSCRIBING)
            raw_segments = self.transcriber.transcribe(
                wav_path,
                job_dir,
                audio_duration_seconds=float(audio_duration),
            )

            # 4. Neural Acoustic Diarization & Speaker Clustering
            emit(f"Performing neural acoustic diarization ({self.clustering_mode.upper()})", 65, status=STATUS_DIARIZING)
            if self.clustering_mode == "ahc":
                # Two-Pass Global Agglomerative Hierarchical Clustering
                diarized_segments = self.speaker_db.cluster_segments_offline(
                    segments=raw_segments,
                    audio_path=wav_path,
                )
            else:
                # Online Leader Clustering
                diarized_segments = []
                for seg in raw_segments:
                    vec = self.speaker_db.extractor.extract_from_wav_slice(
                        wav_path, seg["start"], seg["end"]
                    )
                    if vec is not None:
                        spk_name, _ = self.speaker_db.match_or_register(vec)
                    else:
                        spk_name = "Speaker_Unassigned"
                    seg_copy = dict(seg)
                    seg_copy["speaker"] = spk_name
                    diarized_segments.append(seg_copy)

            # 5. Self-Healing & Temporal-Bounded Turn Coalescing
            emit("Applying self-healing turn coalescing", 80, status=STATUS_DIARIZING)
            coalescer = TurnCoalescer(playbook=playbook)
            healed_blocks = coalescer.heal_and_coalesce(diarized_segments)

            # 6. Atomic Export to .md, .txt, .srt, .json
            emit("Exporting multi-format transcripts atomically", 90, status=STATUS_COMPLETED)
            exported_paths = self.exporter.export(
                blocks=healed_blocks,
                metadata=meta,
                custom_dir=self.output_dir,
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
                    "json": str(exported_paths["json"]),
                },
            }

            self.queue.mark_completed(job_id, result_payload)
            emit("Completed successfully", 100, status=STATUS_COMPLETED)
            return result_payload

        except Exception as e:
            self.queue.mark_failed(job_id, str(e))
            raise
        finally:
            self.ingestor.cleanup_job(job_id)
