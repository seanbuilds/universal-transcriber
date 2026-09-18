"""Master Pipeline Coordinator with Streaming ASR, Roll-Call FSM, and Catalog Tracking (v4).
<!-- v4 – Streaming Whisper sliding windows, Roll-Call FSM, catalog idempotency, and DOCX/VTT exporters -->
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from src.engine.ingest_v3 import MediaIngestorV3
from src.engine.transcribe_v3 import WhisperTranscriberV3
from src.engine.diarize_v3 import SpeakerDatabaseV3
from src.engine.healer_v3 import TurnCoalescerV3
from src.engine.export_v3 import TranscriptExporterV3
from src.engine.catalog_v1 import MediaCatalog
from src.engine.queue_v2 import (
    JobQueue,
    STATUS_DOWNLOADING,
    STATUS_TRANSCRIBING,
    STATUS_DIARIZING,
    STATUS_COMPLETED,
    STATUS_FAILED,
)
from src.playbooks.loader_v3 import PlaybookLoaderV3
from config_v3 import (
    TRANSCRIPTS_DIR,
    TEMP_DIR,
    DEFAULT_PLAYBOOK,
    QUEUE_DB_PATH,
    CATALOG_DB_PATH,
)


class TranscriptionPipelineV4:
    """Orchestrates end-to-end streaming transcription, neural diarization, FSM healing, and multi-format export."""

    def __init__(
        self,
        output_dir: Path = TRANSCRIPTS_DIR,
        model_path: Optional[Path] = None,
        similarity_threshold: float = 0.82,
        clustering_mode: str = "ahc",  # 'ahc' or 'online'
        speaker_library_path: Optional[Path] = None,
        enable_streaming: bool = True,
    ):
        self.output_dir = output_dir
        self.clustering_mode = clustering_mode
        self.enable_streaming = enable_streaming
        self.catalog = MediaCatalog(db_path=CATALOG_DB_PATH)
        self.ingestor = MediaIngestorV3(temp_dir=TEMP_DIR, catalog=self.catalog)
        self.transcriber = WhisperTranscriberV3(model_path=model_path)
        self.speaker_db = SpeakerDatabaseV3(
            storage_path=speaker_library_path,
            similarity_threshold=similarity_threshold,
        )
        self.exporter = TranscriptExporterV3(base_output_dir=output_dir)
        self.playbook_loader = PlaybookLoaderV3()
        self.queue = JobQueue(db_path=QUEUE_DB_PATH)

    def process(
        self,
        source: str,
        playbook_name: str = DEFAULT_PLAYBOOK,
        job_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        segment_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute the end-to-end pipeline with streaming telemetry and idempotency updates."""
        job_id = job_id or f"job_{uuid.uuid4().hex[:8]}"
        job_dir = TEMP_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        self.queue.enqueue(job_id=job_id, source_url=source, playbook=playbook_name)
        self.catalog.mark_processing(source)

        def emit(stage: str, percent: int, status: str = STATUS_TRANSCRIBING):
            self.queue.update_progress(job_id, status=status, progress_pct=percent, message=stage)
            if progress_callback:
                progress_callback(stage, percent)

        try:
            # 1. Load and Validate Playbook
            emit(f"Loading playbook '{playbook_name}'", 5, status=STATUS_DOWNLOADING)
            playbook = self.playbook_loader.load(playbook_name)

            # 2. Ingest Source and Standardize Audio
            emit("Extracting audio from source", 15, status=STATUS_DOWNLOADING)
            wav_path, meta = self.ingestor.extract_audio(source, job_id)
            audio_duration = float(meta.get("duration", 0.0))

            # 3. Streaming ASR Transcription
            emit("Transcribing audio with sliding window streaming", 35, status=STATUS_TRANSCRIBING)

            if self.enable_streaming:
                raw_segments = self.transcriber.transcribe_streaming(
                    wav_path=wav_path,
                    output_dir=job_dir,
                    audio_duration_seconds=audio_duration,
                    segment_callback=segment_callback,
                    progress_callback=lambda pct, msg: emit(f"Transcribing: {msg}", 35 + int(pct * 0.3)),
                )
            else:
                raw_segments = self.transcriber.transcribe(
                    wav_path=wav_path,
                    output_dir=job_dir,
                    audio_duration_seconds=audio_duration,
                )
                if segment_callback:
                    for seg in raw_segments:
                        segment_callback(seg)

            # 4. Neural Acoustic Diarization
            emit(f"Performing neural acoustic diarization ({self.clustering_mode.upper()})", 70, status=STATUS_DIARIZING)
            if self.clustering_mode == "ahc":
                diarized_segments = self.speaker_db.cluster_segments_offline(
                    segments=raw_segments,
                    audio_path=wav_path,
                )
            else:
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

            # 5. Roll-Call FSM & Self-Healing Turn Coalescing
            emit("Applying parliamentary roll-call FSM and dialogue coalescing", 85, status=STATUS_DIARIZING)
            coalescer = TurnCoalescerV3(playbook=playbook)
            healed_blocks = coalescer.heal_and_coalesce(diarized_segments)

            # 6. Multi-Format Atomic Export (MD, TXT, SRT, VTT, DOCX, JSON)
            emit("Exporting multi-format transcripts atomically", 95, status=STATUS_COMPLETED)
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
                    "vtt": str(exported_paths["vtt"]),
                    "docx": str(exported_paths["docx"]),
                    "json": str(exported_paths["json"]),
                },
            }

            self.queue.mark_completed(job_id, result_payload)
            self.catalog.mark_completed(source, str(exported_paths["dir"]))
            emit("Completed successfully", 100, status=STATUS_COMPLETED)
            return result_payload

        except Exception as e:
            self.queue.mark_failed(job_id, str(e))
            self.catalog.mark_failed(source, str(e))
            raise
        finally:
            self.ingestor.cleanup_job(job_id)


TranscriptionPipeline = TranscriptionPipelineV4
