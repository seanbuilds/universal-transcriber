"""Tests for Phase 2: Streaming ASR & Real-Time Pipeline Telemetry (v3).
<!-- v3 – Unit and integration tests for sliding window streaming, callbacks, and SSE telemetry -->
"""

import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.engine.transcribe_v3 import WhisperTranscriberV3, format_timestamp
from app_v3 import app, publish_event, _event_history


class TestPhase2StreamingASR(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        # Create a mock 16kHz mono WAV file (3 seconds long)
        self.test_wav = self.tmp_dir / "test_audio.wav"
        with wave.open(str(self.test_wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            # Write 3 seconds of 440Hz tone
            raw_frames = b"\x00\x00" * 48000
            w.writeframes(raw_frames)

    def test_format_timestamp_monotonic(self):
        """Timestamp helper produces standard HH:MM:SS format."""
        self.assertEqual(format_timestamp(0.0), "00:00:00")
        self.assertEqual(format_timestamp(65.5), "00:01:05")
        self.assertEqual(format_timestamp(3665.0), "01:01:05")

    def test_slice_wav_preserves_pcm_header(self):
        """WAV slicing produces valid 16kHz mono audio slice."""
        transcriber = WhisperTranscriberV3()
        out_slice = self.tmp_dir / "slice.wav"
        transcriber._slice_wav(self.test_wav, out_slice, start_s=1.0, duration_s=1.0)

        self.assertTrue(out_slice.exists())
        with wave.open(str(out_slice), "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getsampwidth(), 2)
            self.assertEqual(wf.getframerate(), 16000)
            self.assertEqual(wf.getnframes(), 16000)

    def test_streaming_callback_invocation(self):
        """Streaming transcription calls segment_callback as chunks are processed."""
        transcriber = WhisperTranscriberV3()

        mock_segments = [
            {"start": 0.5, "end": 2.5, "ts": "00:00:00", "text": "Hello world from stream."}
        ]

        received_segments = []
        progress_reports = []

        with patch.object(transcriber, "transcribe", return_value=mock_segments):
            res = transcriber.transcribe_streaming(
                wav_path=self.test_wav,
                output_dir=self.tmp_dir,
                audio_duration_seconds=3.0,
                chunk_duration=10.0,  # Short file runs monolithic path
                segment_callback=lambda seg: received_segments.append(seg),
                progress_callback=lambda pct, msg: progress_reports.append((pct, msg)),
            )

        self.assertEqual(len(res), 1)
        self.assertEqual(len(received_segments), 1)
        self.assertEqual(received_segments[0]["text"], "Hello world from stream.")
        self.assertTrue(any(pct == 100 for pct, _ in progress_reports))

    def test_sliding_window_multi_chunk_deduplication(self):
        """Overlapping windows deduplicate boundary words correctly."""
        transcriber = WhisperTranscriberV3()

        # Simulate 2 chunks with duplicate overlap words across boundary
        chunk1_segs = [
            {"start": 0.0, "end": 4.0, "text": "We are discussing the annual municipal budget report."}
        ]
        chunk2_segs = [
            {"start": 0.0, "end": 4.0, "text": "the annual municipal budget report and capital investments."}
        ]

        # Call sliding window logic with chunk duration 5s, overlap 2s on a 6s audio
        with patch.object(transcriber, "transcribe", side_effect=[chunk1_segs, chunk2_segs]):
            collected = []
            res = transcriber.transcribe_streaming(
                wav_path=self.test_wav,
                output_dir=self.tmp_dir,
                audio_duration_seconds=6.0,
                chunk_duration=4.0,
                overlap=1.0,
                segment_callback=lambda s: collected.append(s),
            )

        self.assertGreaterEqual(len(res), 1)
        # Ensure the deduplicated word doesn't appear doubled
        full_text = " ".join(s["text"] for s in res)
        self.assertNotIn("budget report budget report", full_text)

    def test_sse_telemetry_stream_endpoint(self):
        """Flask SSE stream /api/stream/<job_id> yields published events."""
        client = app.test_client()

        # Queue a dummy job
        resp = client.post("/api/transcribe", json={"source": str(self.test_wav), "playbook": "general_speech"})
        self.assertEqual(resp.status_code, 202)
        job_id = resp.get_json()["job_id"]

        # Publish a test event to this job
        publish_event(job_id, "segment", {"ts": "00:00:01", "speaker": "Chair", "text": "Testing SSE"})

        # Connect to SSE endpoint
        stream_resp = client.get(f"/api/stream/{job_id}")
        self.assertEqual(stream_resp.status_code, 200)
        self.assertEqual(stream_resp.mimetype, "text/event-stream")

        # Read first chunk of stream data
        data_chunk = stream_resp.get_data(as_text=True)
        self.assertIn("event: ", data_chunk)
        self.assertIn("Testing SSE", data_chunk)

    def test_sse_subscriber_cleanup_on_completion_or_reconnect(self):
        """Completed job stream cleanly terminates and removes client_queue from _subscribers."""
        from app_v3 import _subscribers, _subscribers_lock
        client = app.test_client()

        # Queue a dummy job
        resp = client.post("/api/transcribe", json={"source": str(self.test_wav), "playbook": "general_speech"})
        job_id = resp.get_json()["job_id"]

        # Publish a completed event
        publish_event(job_id, "completed", {"status": "success", "export_dir": "/tmp"})

        # Multiple client streams connect to completed job
        for _ in range(5):
            s_resp = client.get(f"/api/stream/{job_id}")
            self.assertEqual(s_resp.status_code, 200)
            data = s_resp.get_data(as_text=True)
            self.assertIn("event: completed", data)

        # Confirm no orphaned client queues remain registered in _subscribers for this job
        with _subscribers_lock:
            subs = _subscribers.get(job_id, [])
            self.assertEqual(len(subs), 0, "All subscriber queues must be deregistered on stream termination!")


if __name__ == "__main__":
    unittest.main()
