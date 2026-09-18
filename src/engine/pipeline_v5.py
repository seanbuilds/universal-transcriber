"""Master Pipeline Coordinator with Streaming ASR, Audit Logging, and ISO Naming (v5).
<!-- v5 – Persistent audit logging of every transcription attempt, ISO-8601 YYYYMMDD naming, custom title overrides, and gaming playbook integration -->
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from src.engine.ingest_v3 import MediaIngestorV3
from src.engine.transcribe_v3 import WhisperTranscriberV3
from src.engine.diarize_v3 import SpeakerDatabaseV3
from src.engine.healer_v3 import TurnCoalescerV3
from src.engine.export_v4 import TranscriptExporterV4
from src.engine.catalog_v1 import MediaCatalog
from src.engine.audit_v1 import TranscriptionAuditLogger
from src.engine.queue_v2 import (
    JobQueue,
    STATUS_DOWNLOADING,
    STATUS_TRANSCRIBING,
    STATUS_DIARIZING,
    STATUS_COMPLETED,
    STATUS_FAILED,
)
from src.playbooks.loader_v3 import PlaybookLoaderV3
from config_v4 import (
    TRANSCRIPTS_DIR,
    TEMP_DIR,
    DEFAULT_PLAYBOOK,
    QUEUE_DB_PATH,
    CATALOG_DB_PATH,
    AUDIT_DB_PATH,
    AUDIT_LOG_JSONL_PATH,
)


class TranscriptionPipelineV5:
    """Orchestrates end-to-end streaming transcription, neural diarization, FSM healing, ISO export, and persistent audit logging."""

    def __init__(
        self,
        output_dir: Path = TRANSCRIPTS_DIR,
        model_path: Optional[Path] = None,
        similarity_threshold: float = 0.82,
        clustering_mode: str = "ahc",  # 'ahc' or 'online'
        speaker_library_path: Optional[Path] = None,
        enable_streaming: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.clustering_mode = clustering_mode
        self.enable_streaming = enable_streaming
        self.catalog = MediaCatalog(db_path=CATALOG_DB_PATH)
        self.audit = TranscriptionAuditLogger(db_path=AUDIT_DB_PATH, jsonl_path=AUDIT_LOG_JSONL_PATH)
        self.ingestor = MediaIngestorV3(temp_dir=TEMP_DIR, catalog=self.catalog)
        self.transcriber = WhisperTranscriberV3(model_path=model_path)
        self.speaker_db = SpeakerDatabaseV3(
            storage_path=speaker_library_path,
            similarity_threshold=similarity_threshold,
        )
        self.exporter = TranscriptExporterV4(base_output_dir=output_dir)
        self.playbook_loader = PlaybookLoaderV3()
        self.queue = JobQueue(db_path=QUEUE_DB_PATH)

    def cancel(self, job_id: str, reason: str = "User cancelled or cleared transcription") -> None:
        """Explicitly cancel and record cancelled state in both queue and persistent audit log."""
        self.queue.mark_failed(job_id, f"Cancelled: {reason}")
        self.audit.log_job_cancelled(job_id, reason=reason)

    def process(
        self,
        source: str,
        playbook_name: str = DEFAULT_PLAYBOOK,
        job_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        segment_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        custom_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute the end-to-end pipeline with streaming telemetry, ISO naming, and audit recording."""
        job_id = job_id or f"job_{uuid.uuid4().hex[:8]}"
        job_dir = TEMP_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # 0. Immediate Persistent Audit Logging of Job Inception
        self.audit.log_job_started(
            job_id=job_id,
            source=source,
            playbook=playbook_name,
            clustering_mode=self.clustering_mode,
            custom_name=custom_name,
        )
        self.queue.enqueue(job_id=job_id, source_url=source, playbook=playbook_name)
        self.catalog.mark_processing(source)

        total_segments_received = 0
        audio_duration = 0.0

        def emit(stage: str, percent: int, status: str = STATUS_TRANSCRIBING):
            self.queue.update_progress(job_id, status=status, progress_pct=percent, message=stage)
            self.audit.log_progress(
                job_id=job_id,
                stage=stage,
                percent=percent,
                audio_duration=audio_duration,
                total_segments=total_segments_received,
            )
            if progress_callback:
                progress_callback(stage, percent)

        def intercepted_segment_cb(seg: Dict[str, Any]):
            nonlocal total_segments_received
            total_segments_received += 1
            if segment_callback:
                segment_callback(seg)

        try:
            # 1. Load and Validate Playbook
            emit(f"Loading playbook '{playbook_name}'", 5, status=STATUS_DOWNLOADING)
            playbook = self.playbook_loader.load(playbook_name)

            # 2. Ingest Source and Standardize Audio
            emit("Extracting audio from source", 15, status=STATUS_DOWNLOADING)
            wav_path, meta = self.ingestor.extract_audio(source, job_id)
            audio_duration = float(meta.get("duration", 0.0))
            if custom_name:
                meta["custom_title"] = custom_name

            # 3. Streaming ASR Transcription
            emit("Transcribing audio with sliding window streaming", 35, status=STATUS_TRANSCRIBING)

            if self.enable_streaming:
                raw_segments = self.transcriber.transcribe_streaming(
                    wav_path=wav_path,
                    output_dir=job_dir,
                    audio_duration_seconds=audio_duration,
                    segment_callback=intercepted_segment_cb,
                    progress_callback=lambda pct, msg: emit(f"Transcribing: {msg}", 35 + int(pct * 0.3)),
                )
            else:
                raw_segments = self.transcriber.transcribe(
                    wav_path=wav_path,
                    output_dir=job_dir,
                    audio_duration_seconds=audio_duration,
                )
                for seg in raw_segments:
                    intercepted_segment_cb(seg)

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

            # 5. Domain FSM & Self-Healing Turn Coalescing
            emit(f"Applying '{playbook.name}' dialogue coalescing and role healing", 85, status=STATUS_DIARIZING)
            coalescer = TurnCoalescerV3(playbook=playbook)
            healed_blocks = coalescer.heal_and_coalesce(diarized_segments)

            # 6. Multi-Format Atomic Export with Standardized ISO-8601 Naming
            emit("Exporting multi-format transcripts with ISO-8601 naming", 95, status=STATUS_COMPLETED)
            exported_paths = self.exporter.export(
                blocks=healed_blocks,
                metadata=meta,
                custom_dir=self.output_dir,
                custom_name=custom_name,
            )

            file_map = {
                "md": str(exported_paths["md"]),
                "txt": str(exported_paths["txt"]),
                "srt": str(exported_paths["srt"]),
                "vtt": str(exported_paths["vtt"]),
                "docx": str(exported_paths["docx"]),
                "json": str(exported_paths["json"]),
            }

            result_payload = {
                "status": "success",
                "job_id": job_id,
                "iso_name": exported_paths["iso_name"],
                "metadata": meta,
                "playbook": playbook.name,
                "total_blocks": len(healed_blocks),
                "total_segments": len(raw_segments),
                "export_dir": str(exported_paths["dir"]),
                "files": file_map,
            }

            # Mark persistent records
            emit("Completed successfully", 100, status=STATUS_COMPLETED)
            self.queue.mark_completed(job_id, result_payload)
            self.catalog.mark_completed(source, str(exported_paths["dir"]))
            self.audit.log_job_completed(
                job_id=job_id,
                audio_duration=audio_duration,
                total_segments=len(raw_segments),
                total_blocks=len(healed_blocks),
                export_dir=str(exported_paths["dir"]),
                files=file_map,
            )
            return result_payload

        except Exception as e:
            err_str = str(e)
            self.queue.mark_failed(job_id, err_str)
            self.catalog.mark_failed(source, err_str)
            self.audit.log_job_failed(job_id, err_str)
            raise
        finally:
            self.ingestor.cleanup_job(job_id)


TranscriptionPipeline = TranscriptionPipelineV5
