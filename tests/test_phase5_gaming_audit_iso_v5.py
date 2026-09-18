"""Automated test suite for Phase 5 (Gaming Playbook, Audit Logging, ISO Naming, and Clear UI) (v5).
<!-- v5 – Schema verification, audit trail persistence, ISO-8601 export formatting, and web cancellation/usage APIs -->
"""

import json
import os
import sqlite3
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.playbooks.loader_v3 import PlaybookLoaderV3
from src.engine.audit_v1 import TranscriptionAuditLogger
from src.engine.export_v4 import TranscriptExporterV4, build_iso_filename, format_iso_date
from src.engine.pipeline_v5 import TranscriptionPipelineV5
from app_v4 import app


@pytest.fixture
def temp_env():
    """Create isolated temporary directory for databases and transcripts."""
    td = Path(tempfile.mkdtemp())
    yield td
    shutil.rmtree(td, ignore_errors=True)


def test_gaming_playbook_schema_validation():
    """Verify gaming_videos_v1.json validates strictly against JSON Schema v7."""
    loader = PlaybookLoaderV3()
    playbook = loader.load("gaming_videos")

    assert playbook.name == "gaming_videos"
    assert playbook.version == "v1"
    assert playbook.default_role == "Player"
    assert "Streamer" in playbook.roles
    assert "Teammate" in playbook.roles
    assert "Caster" in playbook.roles
    assert "System" in playbook.roles

    # Verify cue detection
    role = playbook.detect_role("welcome back to the stream chat, don't forget to like and subscribe")
    assert role == "Streamer"

    role2 = playbook.detect_role("he's one shot low hp drop me ammo")
    assert role2 == "Teammate"

    role3 = playbook.detect_role("what an insane play taking down the objective")
    assert role3 == "Caster"

    role4 = playbook.detect_role("round one overtime match point")
    assert role4 == "System"


def test_iso_naming_conventions():
    """Verify standardized ISO-8601 YYYYMMDD_<Title> naming across variants."""
    # 1. Standard custom title with ISO date
    name1 = build_iso_filename(
        custom_name="Apex Legends Finals",
        metadata_title="Original Raw Video",
        metadata_date="2026-09-17"
    )
    assert name1 == "20260917_Apex_Legends_Finals"

    # 2. Metadata title fallback when no custom title provided
    name2 = build_iso_filename(
        custom_name=None,
        metadata_title="Speedrun PB Attempt 42",
        metadata_date="20260915"
    )
    assert name2 == "20260915_Speedrun_PB_Attempt_42"

    # 3. Preserves already formatted ISO prefix
    name3 = build_iso_filename(
        custom_name="20260917_Esports_Championship",
        metadata_title="Unused"
    )
    assert name3 == "20260917_Esports_Championship"

    # 4. Fallback to current UTC date when date is missing
    name4 = build_iso_filename(custom_name="Live Stream Highlights", metadata_date="")
    assert len(name4.split("_")[0]) == 8
    assert name4.endswith("_Live_Stream_Highlights")


def test_persistent_audit_logging(temp_env):
    """Verify complete audit logging lifecycle in both SQLite and JSONL."""
    db_path = temp_env / "audit.sqlite"
    jsonl_path = temp_env / "audit.jsonl"

    logger = TranscriptionAuditLogger(db_path=db_path, jsonl_path=jsonl_path)

    # 1. Job Inception / Submission
    logger.log_job_started(
        job_id="job_test01",
        source="https://youtube.com/watch?v=mock_video",
        playbook="gaming_videos",
        clustering_mode="ahc",
        custom_name="Tournament_Match_1",
    )

    entry = logger.get_audit_entry("job_test01")
    assert entry is not None
    assert entry["status"] == "SUBMITTED"
    assert entry["custom_name"] == "Tournament_Match_1"
    assert entry["used_flag"] == 0

    # 2. Progress update
    logger.log_progress("job_test01", "Transcribing", 50, audio_duration=180.0, total_segments=15)
    entry_prog = logger.get_audit_entry("job_test01")
    assert entry_prog["status"] == "PROCESSING"
    assert entry_prog["total_segments"] == 15
    assert entry_prog["audio_duration"] == 180.0

    # 3. Completion
    file_map = {"md": "/tmp/test.md", "txt": "/tmp/test.txt"}
    logger.log_job_completed(
        job_id="job_test01",
        audio_duration=180.0,
        total_segments=25,
        total_blocks=10,
        export_dir="/tmp/export_dir",
        files=file_map,
    )
    entry_done = logger.get_audit_entry("job_test01")
    assert entry_done["status"] == "COMPLETED"
    assert entry_done["files"] == file_map

    # 4. Mark Used
    assert logger.mark_job_used("job_test01", action="downloaded") is True
    entry_used = logger.get_audit_entry("job_test01")
    assert entry_used["used_flag"] == 1

    # 5. Failed Job
    logger.log_job_started("job_fail", "https://example.com/bad", "general_speech")
    logger.log_job_failed("job_fail", "Network connection aborted")
    entry_fail = logger.get_audit_entry("job_fail")
    assert entry_fail["status"] == "FAILED"
    assert "Network connection aborted" in entry_fail["error_message"]

    # 6. Cancelled Job
    logger.log_job_started("job_canc", "https://example.com/cancel", "general_speech")
    logger.log_job_cancelled("job_canc", reason="User cleared form")
    entry_canc = logger.get_audit_entry("job_canc")
    assert entry_canc["status"] == "CANCELLED"

    # 7. Summary Verification
    summary = logger.get_audit_summary()
    assert summary["total_transcriptions_logged"] == 3
    assert summary["completed"] == 1
    assert summary["failed"] == 1
    assert summary["cancelled"] == 1
    assert summary["used"] == 1
    assert summary["unused"] == 2

    # Verify JSONL lines exist and are valid JSON
    assert jsonl_path.exists()
    lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) >= 6
    parsed_jsonl = [json.loads(line) for line in lines]
    event_types = [p["event_type"] for p in parsed_jsonl]
    assert "JOB_STARTED" in event_types
    assert "JOB_COMPLETED" in event_types
    assert "JOB_MARKED_USED" in event_types


def test_export_v4_iso_files_generation(temp_env):
    """Verify Export v4 atomically generates all 6 formats with ISO-8601 prefix."""
    exporter = TranscriptExporterV4(base_output_dir=temp_env)

    blocks = [
        {"ts": "00:00:01", "speaker": "Streamer", "text": "What's up chat! Welcome back.", "start": 1.0, "end": 3.5},
        {"ts": "00:00:04", "speaker": "Teammate", "text": "Ready to drop. On my mark!", "start": 4.0, "end": 6.0},
    ]
    meta = {
        "title": "Valorant Ranked Highlights",
        "date": "2026-09-17",
        "source": "https://twitch.tv/example",
        "duration_str": "00:06:00",
    }

    result = exporter.export(
        blocks=blocks,
        metadata=meta,
        custom_name="Valorant_Grand_Finals",
    )

    iso_name = result["iso_name"]
    assert iso_name == "20260917_Valorant_Grand_Finals"
    assert result["dir"].exists()

    # Check that all 6 files have the exact ISO prefix
    for ext in ("md", "txt", "srt", "vtt", "docx", "json"):
        path = result[ext]
        assert path.exists()
        assert path.name == f"{iso_name}.{ext}"

    # Check WebVTT contains W3C voice spans
    vtt_content = result["vtt"].read_text(encoding="utf-8")
    assert "WEBVTT" in vtt_content
    assert "<v Streamer>What's up chat! Welcome back.</v>" in vtt_content


def test_pipeline_v5_audit_and_iso_execution(temp_env):
    """Test TranscriptionPipelineV5 coordinates audit logging and ISO naming."""
    pipeline = TranscriptionPipelineV5(output_dir=temp_env)
    # Inject isolated audit logger
    pipeline.audit = TranscriptionAuditLogger(
        db_path=temp_env / "audit.sqlite",
        jsonl_path=temp_env / "audit.jsonl"
    )

    # Mock audio extraction and whisper
    dummy_wav = temp_env / "dummy.wav"
    dummy_wav.write_bytes(b"RIFFdummywave")

    with patch.object(pipeline.ingestor, "extract_audio", return_value=(dummy_wav, {"title": "Apex Match", "duration": 10.0, "date": "2026-09-17"})):
        with patch.object(pipeline.transcriber, "transcribe_streaming", return_value=[
            {"ts": "00:00:01", "speaker": "Streamer", "text": "GG let's go", "start": 1.0, "end": 3.0}
        ]):
            with patch.object(pipeline.speaker_db, "cluster_segments_offline", return_value=[
                {"ts": "00:00:01", "speaker": "Streamer", "text": "GG let's go", "start": 1.0, "end": 3.0}
            ]):
                res = pipeline.process(
                    source="https://youtube.com/watch?v=mock123",
                    playbook_name="gaming_videos",
                    custom_name="Apex_Victory",
                )

                assert res["status"] == "success"
                assert res["iso_name"] == "20260917_Apex_Victory"

                # Check audit entry
                audit_entry = pipeline.audit.get_audit_entry(res["job_id"])
                assert audit_entry["status"] == "COMPLETED"
                assert audit_entry["custom_name"] == "Apex_Victory"
                assert audit_entry["total_blocks"] == 1


def test_web_api_endpoints_v4():
    """Verify Flask Web API endpoints for playbooks, audit logs, and job cancellation."""
    client = app.test_client()

    # 1. Playbooks endpoint includes gaming_videos
    resp = client.get("/api/playbooks")
    assert resp.status_code == 200
    playbooks = resp.get_json()
    playbook_names = [p["name"] for p in playbooks]
    assert "gaming_videos" in playbook_names

    # 2. Audit trail endpoint
    resp_audit = client.get("/api/audit")
    assert resp_audit.status_code == 200
    audit_data = resp_audit.get_json()
    assert "summary" in audit_data
    assert "entries" in audit_data

    # 3. Job cancellation endpoint
    resp_canc = client.post("/api/jobs/test_cancel_job/cancel", json={"reason": "User cleared UI"})
    assert resp_canc.status_code == 200
    assert resp_canc.get_json()["success"] is True

    # 4. Mark job used endpoint
    resp_used = client.post("/api/audit/test_cancel_job/used", json={"action": "viewed"})
    assert resp_used.status_code == 200
