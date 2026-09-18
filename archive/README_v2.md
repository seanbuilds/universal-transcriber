# 🎙️ Universal Transcriber (v2 - Hardened)
<!-- v2 – Upgraded architecture addressing all findings from REVIEW_FEEDBACK_v1.md -->

**High-Performance, Secure Audio & Video Transcription Engine for macOS (Apple Silicon)**

Universal Transcriber is an autonomous, domain-agnostic media transcription suite built for Apple Silicon Macs. It extracts audio from YouTube (single videos, playlists, or channels) and local media files, transcribes speech at up to **28x real-time speed** using Apple's Metal GPU, clusters speaker voices persistently across recordings using spherical unit-normalized embeddings, and heals fragmented speech into natural conversational paragraphs.

---

## What Was Hardened in v2

Following the independent architectural audit ([REVIEW_FEEDBACK_v1.md](REVIEW_FEEDBACK_v1.md)), version 2 introduces:

1. **Active Acoustic Diarization Pipeline**:
   - `SpeakerDatabase` voice embeddings are now directly extracted from audio segment slices and clustered during transcription rather than relying solely on text regex matching.
2. **Spherical Unit-Norm Vector Math (Anti-Drift)**:
   - Replaced arithmetic Euclidean averaging with unit-sphere normalization and anchor-clamped EMA, completely preventing centroid drift from cannibalizing distinct speaker identities over long recordings.
3. **Temporal Gap–Bounded Turn Coalescing**:
   - Turn coalescing now enforces a 3.0-second silence boundary limit ($\Delta t \le 3.0\text{s}$) and a 60-second block maximum. 15-minute recesses and pauses now cleanly split into separate dialogue blocks instead of collapsing into monolithic text walls.
4. **Critical Web API Security Patches**:
   - Patched path traversal vulnerability in `/api/file` by enforcing strict relative resolution against `TRANSCRIPTS_DIR` (403 Access Denied on any out-of-directory traversal attempt).
   - Replaced wildcard CORS with explicit localhost/127.0.0.1 origin restrictions.
   - Input validation rejecting `/dev/` device nodes, pipes, and unreadable files.
   - Non-blocking asynchronous worker thread execution for Web API calls.
5. **Adaptive Timeout Scaling & Playlist Ingestion**:
   - Replaced the fixed 20-minute timeout with dynamic scaling based on audio duration (scaling gracefully to multi-hour town meetings and podcasts).
   - Full playlist metadata extraction and multi-item batch execution.
6. **Persistent SQLite WAL Job Queue**:
   - Built crash-resilient `JobQueue` backed by SQLite WAL mode (`pipeline_queue_v1.sqlite`), enabling autonomous recovery, progress tracking, and batch runs.
7. **Word-Boundary Anchored Playbook Cues**:
   - Playbook cue detection now utilizes word-boundary regexes (`\b`) to eliminate polysemy false positives (e.g., casual uses of "second" no longer trigger parliamentary motion rules).

---

## Quick Start

### 1. Dependencies
```bash
brew install whisper-cpp ffmpeg
pip3 install yt-dlp flask flask-cors
```

### 2. Command-Line Interface (`cli_v2.py`)

#### Transcribe a Video or Local File
```bash
# General speech (default)
python3 cli_v2.py transcribe "https://www.youtube.com/watch?v=..."

# Municipal meeting with roll calls and parliamentary procedure
python3 cli_v2.py transcribe "https://www.youtube.com/watch?v=..." --playbook municipal_meetings

# Local audio or video file
python3 cli_v2.py transcribe "/Users/dad/Downloads/interview.mp4" --playbook interview_podcast
```

#### Batch Process Playlists or Directories
```bash
# Process an entire YouTube playlist
python3 cli_v2.py batch "https://www.youtube.com/playlist?list=..." --playbook municipal_meetings

# Process all audio/video files in a folder
python3 cli_v2.py batch "/Users/dad/Movies/RecordedMeetings/" --playbook corporate_meeting
```

#### Inspect Persistent Queue
```bash
python3 cli_v2.py queue --limit 25
```

#### List Available Playbooks
```bash
python3 cli_v2.py playbooks
```

#### Manage Persistent Speaker Profiles
```bash
python3 cli_v2.py speakers
python3 cli_v2.py speakers --rename Speaker_01 "Craig MacLellan"
```

### 3. Web Dashboard (`app_v2.py`)
```bash
python3 app_v2.py
# → Open http://127.0.0.1:5055
```

---

## Test Verification

Run all automated unit and security tests:
```bash
python3 -m unittest discover -s tests -p "test_*_v2.py"
```

---

## Directory Structure

```
joyful-davinci/
├── config_v2.py                     # Central configuration & security settings
├── cli_v2.py                        # Hardened terminal CLI with batch & queue support
├── app_v2.py                        # Hardened async Web UI & API server
├── README_v2.md                     # Documentation
├── REVIEW_FEEDBACK_v1.md            # Independent architectural audit report
├── static/
│   └── index.html                   # Web dashboard frontend
├── playbooks/                       # Domain playbook definitions
│   ├── general_speech_v1.json
│   ├── municipal_meetings_v1.json
│   ├── interview_podcast_v1.json
│   ├── corporate_meeting_v1.json
│   └── academic_lecture_v1.json
├── src/
│   ├── engine/
│   │   ├── ingest_v2.py             # Resilient media extraction & playlist parser
│   │   ├── transcribe_v2.py         # Adaptive timeout Metal GPU Whisper engine
│   │   ├── diarize_v2.py            # Unit-sphere anti-drift speaker profiling
│   │   ├── healer_v2.py             # Temporal-bounded turn coalescing
│   │   ├── export_v2.py             # Atomic multi-format file exporter
│   │   ├── queue_v1.py              # Persistent SQLite WAL progress queue
│   │   └── pipeline_v2.py           # Master pipeline orchestrator
│   └── playbooks/
│       └── loader_v2.py             # Word-boundary anchored playbook matcher
└── tests/
    ├── test_security_v2.py          # Path traversal and input security tests
    ├── test_diarize_v2.py           # Centroid stability & normalization tests
    ├── test_healer_v2.py            # Temporal gap and deduplication tests
    ├── test_playbooks_v2.py         # Schema validation & boundary tests
    └── test_queue_v2.py             # SQLite WAL queue lifecycle tests
```
