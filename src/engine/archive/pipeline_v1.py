"""Master Pipeline Coordinator for Universal Transcriber (v1)."""

import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from src.engine.ingest_v1 import MediaIngestor
from src.engine.transcribe_v1 import WhisperTranscriber
from src.engine.diarize_v1 import SpeakerDatabase
from src.engine.healer_v1 import TurnCoalescer
from src.engine.export_v1 import TranscriptExporter
from src.playbooks.loader_v1 import PlaybookLoader, Playbook
from config_v1 import TRANSCRIPTS_DIR, TEMP_DIR, DEFAULT_PLAYBOOK


class TranscriptionPipeline:
    """Orchestrates end-to-end media transcription, healing, and export."""

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

        def emit(stage: str, percent: int):
            if progress_callback:
                progress_callback(stage, percent)

        try:
            # 1. Load Playbook
            emit(f"Loading playbook '{playbook_name}'", 5)
            playbook = self.playbook_loader.load(playbook_name)

            # 2. Ingest / Extract Audio
            emit(f"Extracting audio from source", 15)
            wav_path, meta = self.ingestor.extract_audio(source, job_id)

            # 3. Transcribe with Metal GPU Whisper
            emit("Transcribing audio on Metal GPU", 40)
            segments = self.transcriber.transcribe(wav_path, job_dir)

            # 4. Self-Healing & Turn Coalescing
            emit("Applying self-healing turn coalescing", 75)
            coalescer = TurnCoalescer(playbook=playbook)
            healed_blocks = coalescer.heal_and_coalesce(segments)

            # 5. Export to .md, .txt, .srt, .json
            emit("Exporting multi-format transcripts", 90)
            exported_paths = self.exporter.export(
                blocks=healed_blocks,
                metadata=meta,
                custom_dir=self.output_dir
            )

            emit("Completed successfully", 100)

            return {
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
        finally:
            # Clean temporary job folder
            self.ingestor.cleanup_job(job_id)
