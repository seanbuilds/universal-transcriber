"""Master Pipeline Coordinator with Multi-Format Local Media Support, Streaming ASR, and ISO Naming (v6).
<!-- v6 – First-class local media container support (.m4a, .mp3, .mp4, .mov, .mkv, .wav, .flac, .aac), ffprobe tags, video-bypassing, persistent audit logging, and ISO-8601 naming -->
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from src.engine.ingest_v4 import MediaIngestorV4, SUPPORTED_LOCAL_EXTENSIONS
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


class TranscriptionPipelineV6:
    """Orchestrates end-to-end streaming transcription, multi-format media ingestion, neural diarization, FSM healing, ISO export, and persistent audit logging."""

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
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.clustering_mode = clustering_mode
        self.enable_streaming = enable_streaming

        self.catalog = MediaCatalog(db_path=CATALOG_DB_PATH)
        self.queue = JobQueue(db_path=QUEUE_DB_PATH)
        self.audit = TranscriptionAuditLogger(
            db_path=AUDIT_DB_PATH,
            jsonl_path=AUDIT_LOG_JSONL_PATH
        )
        self.ingestor = MediaIngestorV4(temp_dir=self.temp_dir, catalog=self.catalog)
        self.transcriber = WhisperTranscriberV3(model_path=model_path)
        self.speaker_db = SpeakerDatabaseV3(
            storage_path=speaker_library_path,
            similarity_threshold=similarity_threshold,
        )
        self.exporter = TranscriptExporterV4(base_output_dir=self.output_dir)
        self.playbook_loader = PlaybookLoaderV3()

    def cancel(self, job_id: str, reason: str = "User requested cancellation") -> None:
        """Cancel an active or pending job and record cancellation in persistent audit log."""
        self.queue.mark_failed(job_id, f"Cancelled: {reason}")
        self.audit.log_job_cancelled(job_id, reason=reason)
        self.ingestor.cleanup_job(job_id)

    def process(
        self,
        source: str,
        playbook_name: str = DEFAULT_PLAYBOOK,
        output_dir: Optional[Any] = None,
        job_id: Optional[str] = None,
        custom_name: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        segment_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute the end-to-end transcription, multi-format media ingest, diarization, healing, ISO export, and audit pipeline."""
        job_id = job_id or f"job_{uuid.uuid4().hex[:8]}"
        job_dir = self.temp_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Register in audit log and queue
        self.queue.enqueue(job_id=job_id, source_url=source, playbook=playbook_name)
        self.audit.log_job_started(
            job_id=job_id,
            source=source,
            playbook=playbook_name,
            clustering_mode=self.clustering_mode,
            custom_name=custom_name,
        )

        audio_duration = 0.0
        total_segments_received = 0

        def emit(stage: str, percent: int, status: str = STATUS_DOWNLOADING):
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

            # 2. Ingest Source and Standardize Audio (with video bypassing and tag inspection)
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
                )
                for seg in raw_segments:
                    intercepted_segment_cb(seg)

            emit("Transcribing: Completed streaming transcription", 65, status=STATUS_TRANSCRIBING)

            # 4. Neural Acoustic Diarization
            clustering_label = "AHC" if self.clustering_mode == "ahc" else "Online"
            emit(f"Performing neural acoustic diarization ({clustering_label})", 70, status=STATUS_DIARIZING)

            if self.clustering_mode == "ahc":
                diarized_segments = self.speaker_db.cluster_segments_offline(
                    segments=raw_segments,
                    audio_path=wav_path,
                )
            else:
                diarized_segments = []
                for seg in raw_segments:
                    spk = self.speaker_db.identify_or_register(
                        audio_path=wav_path,
                        start_time=seg["start"],
                        end_time=seg["end"],
                    )
                    seg_copy = dict(seg)
                    seg_copy["speaker"] = spk
                    diarized_segments.append(seg_copy)

            # 5. Playbook-Driven Dialogue Coalescing & Role Healing
            emit(f"Applying '{playbook.name}' dialogue coalescing and role healing", 85, status=STATUS_DIARIZING)
            coalescer = TurnCoalescerV3(playbook=playbook)
            healed_blocks = coalescer.heal_and_coalesce(diarized_segments)

            # 6. Multi-Format Atomic Export with Standardized ISO-8601 Naming
            emit("Exporting multi-format transcripts with ISO-8601 naming", 95, status=STATUS_COMPLETED)
            effective_out_dir = Path(output_dir) if output_dir else self.output_dir
            exported_paths = self.exporter.export(
                blocks=healed_blocks,
                metadata=meta,
                custom_dir=effective_out_dir,
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

            distinct_speakers = set(b.get("speaker") for b in healed_blocks if b.get("speaker"))
            total_words = sum(len(b.get("text", "").split()) for b in healed_blocks)
            display_title = meta.get("custom_title") or meta.get("title") or exported_paths["iso_name"]

            result_payload = {
                "status": "success",
                "job_id": job_id,
                "title": display_title,
                "duration": audio_duration,
                "duration_str": meta.get("duration_str", "00:00:00"),
                "speaker_count": len(distinct_speakers),
                "word_count": total_words,
                "iso_name": exported_paths["iso_name"],
                "iso_output_dir": str(exported_paths["dir"]),
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


TranscriptionPipeline = TranscriptionPipelineV6
