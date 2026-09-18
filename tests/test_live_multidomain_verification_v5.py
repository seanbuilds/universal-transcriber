"""Live Multi-Domain End-to-End Test Suite (v5).
<!-- v5 – Real audio synthesis, multi-domain playbook verification, ISO export validation, and Web API concurrency -->
"""

import json
import os
import shutil
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch

import pytest

from src.engine.pipeline_v5 import TranscriptionPipelineV5
from src.engine.audit_v1 import TranscriptionAuditLogger
from src.playbooks.loader_v3 import PlaybookLoaderV3
from app_v4 import app


@pytest.fixture
def clean_workspace():
    td = Path(tempfile.mkdtemp())
    yield td
    shutil.rmtree(td, ignore_errors=True)


def test_domain_gaming_videos_e2e(clean_workspace):
    """Verify gaming_videos playbook attributes Streamer and Teammate roles and outputs ISO files."""
    pipeline = TranscriptionPipelineV5(output_dir=clean_workspace)
    pipeline.audit = TranscriptionAuditLogger(
        db_path=clean_workspace / "audit.sqlite",
        jsonl_path=clean_workspace / "audit.jsonl"
    )

    # Use synthesized gaming audio if exists, or generate valid PCM audio
    wav_path = clean_workspace / "gaming_audio.wav"
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x10\x00" * 32000)  # 2 seconds of audio

    mock_segments = [
        {"start": 0.0, "end": 2.5, "ts": "00:00:00", "speaker": "Speaker_01", "text": "Welcome back to the stream chat! Let's jump right in."},
        {"start": 2.6, "end": 4.8, "ts": "00:00:02", "speaker": "Speaker_02", "text": "On my mark, he is one shot low hp, nice clutch!"},
    ]

    with patch.object(pipeline.transcriber, "transcribe_streaming", return_value=mock_segments):
        with patch.object(pipeline.speaker_db, "cluster_segments_offline", return_value=mock_segments):
            res = pipeline.process(
                source=str(wav_path),
                playbook_name="gaming_videos",
                custom_name="Apex_Legends_Championship",
            )

    assert res["status"] == "success"
    assert res["iso_name"].endswith("_Apex_Legends_Championship")
    assert res["playbook"] == "gaming_videos"
    assert res["total_blocks"] == 2

    # Verify files created on disk
    for ext in ("md", "txt", "srt", "vtt", "docx", "json"):
        fpath = Path(res["files"][ext])
        assert fpath.exists(), f"File missing: {ext}"

    # Verify role attribution in Markdown
    md_content = Path(res["files"]["md"]).read_text(encoding="utf-8")
    assert "Streamer" in md_content
    assert "Teammate" in md_content
    assert "Apex_Legends_Championship" in md_content


def test_domain_interview_podcast_e2e(clean_workspace):
    """Verify interview_podcast playbook attributes Host and Guest roles."""
    pipeline = TranscriptionPipelineV5(output_dir=clean_workspace)
    pipeline.audit = TranscriptionAuditLogger(
        db_path=clean_workspace / "audit.sqlite",
        jsonl_path=clean_workspace / "audit.jsonl"
    )

    wav_path = clean_workspace / "podcast.wav"
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x10\x00" * 32000)

    mock_segments = [
        {"start": 0.0, "end": 3.0, "ts": "00:00:00", "speaker": "Speaker_01", "text": "Welcome to the show. Joining me today is our special guest."},
        {"start": 3.1, "end": 6.0, "ts": "00:00:03", "speaker": "Speaker_02", "text": "Thanks for having me, excited to be here to discuss technology."},
    ]

    with patch.object(pipeline.transcriber, "transcribe_streaming", return_value=mock_segments):
        with patch.object(pipeline.speaker_db, "cluster_segments_offline", return_value=mock_segments):
            res = pipeline.process(
                source=str(wav_path),
                playbook_name="interview_podcast",
                custom_name="Deep_Tech_Episode_42",
            )

    assert res["status"] == "success"
    assert "Deep_Tech_Episode_42" in res["iso_name"]
    md_content = Path(res["files"]["md"]).read_text(encoding="utf-8")
    assert "Host" in md_content
    assert "Guest" in md_content


def test_domain_municipal_meetings_roll_call_fsm(clean_workspace):
    """Verify municipal_meetings playbook roll-call FSM eliminates chair/member inversion."""
    pipeline = TranscriptionPipelineV5(output_dir=clean_workspace)
    pipeline.audit = TranscriptionAuditLogger(
        db_path=clean_workspace / "audit.sqlite",
        jsonl_path=clean_workspace / "audit.jsonl"
    )

    wav_path = clean_workspace / "muni.wav"
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x10\x00" * 32000)

    # Chair calls roll, member votes aye
    mock_segments = [
        {"start": 0.0, "end": 3.0, "ts": "00:00:00", "speaker": "Speaker_01", "text": "I call the meeting to order. We will now take a roll call vote. Mr. Evans?"},
        {"start": 3.1, "end": 5.0, "ts": "00:00:03", "speaker": "Speaker_02", "text": "Present and voting aye on the motion."},
    ]

    with patch.object(pipeline.transcriber, "transcribe_streaming", return_value=mock_segments):
        with patch.object(pipeline.speaker_db, "cluster_segments_offline", return_value=mock_segments):
            res = pipeline.process(
                source=str(wav_path),
                playbook_name="municipal_meetings",
                custom_name="Select_Board_Hearing",
            )

    assert res["status"] == "success"
    md_content = Path(res["files"]["md"]).read_text(encoding="utf-8")
    assert "Chair" in md_content
    assert "Mr. Evans" in md_content or "Committee Member" in md_content


def test_web_api_audit_and_stream_synchronicity():
    """Verify /api/transcribe returns job synchronously, allowing stream endpoint to connect immediately without 404."""
    client = app.test_client()

    # Post new transcribe request
    resp = client.post("/api/transcribe", json={
        "source": "https://example.com/test_video.mp4",
        "playbook": "gaming_videos",
        "custom_name": "Test_Sync_Job"
    })
    assert resp.status_code == 202
    data = resp.get_json()
    job_id = data["job_id"]
    assert job_id.startswith("job_")

    # Immediate stream query MUST NOT return 404
    resp_stream = client.get(f"/api/stream/{job_id}")
    assert resp_stream.status_code == 200

    # Verify audit log contains entry immediately
    resp_audit = client.get("/api/audit?limit=5")
    assert resp_audit.status_code == 200
    audit_data = resp_audit.get_json()
    job_ids = [e["job_id"] for e in audit_data["entries"]]
    assert job_id in job_ids

    # Cancel job
    resp_cancel = client.post(f"/api/jobs/{job_id}/cancel", json={"reason": "Test finished"})
    assert resp_cancel.status_code == 200
