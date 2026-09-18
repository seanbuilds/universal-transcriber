# 🎙️ Universal Transcriber (v3/v4 Release)
<!-- v3 – Streaming ASR, Parliamentary Roll-Call FSM, SQLite Catalog Idempotency, and DOCX/WebVTT Exporters -->

**High-Performance, Secure Audio & Video Transcription Engine for macOS (Apple Silicon)**

Universal Transcriber is an autonomous, domain-aware media transcription and speaker diarization suite engineered for Apple Silicon Macs. It extracts audio from YouTube channels, playlists, podcast RSS feeds, and local media files, transcribes speech at up to **28x real-time speed** using Apple's Metal GPU, clusters speaker voices persistently across recordings using neural and spherical unit-normalized embeddings, and heals fragmented speech into natural conversational paragraphs.

---

## Architectural Evolution (v3 & v4 Highlights)

Following the strategic roadmap in `improvement_plan_v1.md`, the platform now delivers:

1. **Sliding-Window Streaming ASR & Real-Time Telemetry (Phase 2)**:
   - Chunked transcription with 30-second sliding windows and 2-second overlap compensation via `WhisperTranscriberV3`.
   - Real-time token and segment streaming piped through Server-Sent Events (`GET /api/stream/<job_id>`) in `app_v3.py`.
   - Live web UI dashboard (`static/index_v2.html` / `static/index.html`) featuring real-time scrolling transcript updates, active speaker badges, and dynamic progress bars.

2. **Parliamentary Roll-Call Finite State Machine (FSM) (Phase 3)**:
   - Built a three-state parliamentary FSM (`src/engine/healer_v3.py`) that completely eliminates the historical inversion bug where a presiding officer calling a member's name was erroneously attributed to the member.
   - Preserves Chair attribution when calling members, attributes affirmative/negative vote responses ("Aye", "Present", "Nay") to the target member, and safely handles skipped members.
   - Formal JSON Schema v7 validation for domain playbooks (`src/playbooks/loader_v3.py` and `playbooks/schema_v1.json`), preventing syntax errors and enforcing required structures.

3. **Batch Catalog Ingestion & Archival Idempotency (Phase 4)**:
   - Native discovery for entire YouTube channels, playlists, and RSS/Atom podcast feeds via `MediaIngestorV3`.
   - Thread-safe SQLite catalog index (`src/engine/catalog_v1.py` backed by `media_catalog_v1.sqlite`) with automated deduplication: previously transcribed episodes are skipped automatically unless `--force` is requested.

4. **Multi-Format Export Expansion (DOCX & WebVTT) (Phase 4)**:
   - Native **.docx** export with formatted titles, executive summaries, recording metadata, participant rosters, and bold speaker turns.
   - W3C-compliant **WebVTT (.vtt)** subtitles featuring voice span cues (`<v Speaker Name>Text</v>`) and sub-millisecond timestamps.
   - Preserves Markdown (`.md`), Plaintext (`.txt`), SubRip (`.srt`), and Structured (`.json`) outputs.

---

## Quick Start

### 1. Requirements & Dependencies
```bash
brew install whisper-cpp ffmpeg
pip3 install yt-dlp flask flask-cors jsonschema python-docx requests
```

### 2. Command-Line Interface (`cli_v4.py`)

#### Transcribe a Video or Local File
```bash
# Municipal meeting with roll calls and parliamentary procedure
python3 cli_v4.py transcribe "https://www.youtube.com/watch?v=..." --playbook municipal_meetings

# General speech transcription with AHC clustering
python3 cli_v4.py transcribe "/Users/dad/Downloads/interview.mp4" --clustering ahc
```

#### Batch Catalog Ingestion (YouTube Channels & RSS Feeds)
```bash
# Ingest YouTube channel or playlist with idempotency (skips already transcribed items)
python3 cli_v4.py catalog "https://www.youtube.com/@CohassetTownHall/videos" --playbook municipal_meetings

# Ingest municipal podcast RSS feed (dry-run to inspect items)
python3 cli_v4.py catalog "https://example.com/podcast.xml" --dry-run

# Inspect catalog processing status
python3 cli_v4.py catalog-status
```

#### Manage Playbooks & Speaker Biometrics
```bash
# Validate a custom playbook against JSON Schema v7
python3 cli_v4.py playbooks --validate playbooks/municipal_meetings_v1.json

# Inspect persistent speaker profiles
python3 cli_v4.py speakers
python3 cli_v4.py speakers --rename Speaker_01 "Chair Corey Evans"
```

### 3. Real-Time Streaming Web Dashboard (`app_v3.py`)
```bash
python3 app_v3.py
# → Open http://127.0.0.1:5055 in your browser
```

---

## Automated Verification

Run the full automated test suite:
```bash
python3 -m pytest
```
All 82 automated unit and integration tests verify:
- Sliding-window WAV slicing, SSE subscriber lifecycle, and event streaming (`tests/test_phase2_streaming_v3.py`)
- Roll-Call FSM inversion elimination, lengthy speech vote attribution, acoustic cluster preservation, and JSON Schema v7 validation (`tests/test_phase3_fsm_v3.py`)
- DOCX, WebVTT entity escaping, malformed RSS parsing resilience, and SQLite catalog idempotency (`tests/test_phase4_catalog_export_v4.py`)
- Voice biometrics, unit-norm anti-drift clustering, path traversal protection, and security hardening (`tests/test_*_v2.py`)

---

## Project Structure

```
├── app_v3.py                   # Hardened Web API with SSE streaming telemetry
├── cli_v4.py                   # Master CLI with catalog, batch, and export commands
├── config_v3.py                # System-wide configuration (chunking, paths, timeouts)
├── README_v3.md                # System documentation
├── playbooks/
│   ├── schema_v1.json          # JSON Schema v7 specification for playbooks
│   ├── municipal_meetings_v1.json
│   ├── corporate_meeting_v1.json
│   ├── academic_lecture_v1.json
│   ├── interview_podcast_v1.json
│   └── general_speech_v1.json
├── src/
│   ├── engine/
│   │   ├── catalog_v1.py       # SQLite media catalog & idempotency tracker
│   │   ├── diarize_v3.py       # Two-pass AHC & spherical unit-norm clustering
│   │   ├── embeddings_v1.py    # Voice embedding extraction engine
│   │   ├── export_v3.py        # Atomic exporter (MD, TXT, SRT, VTT, DOCX, JSON)
│   │   ├── healer_v3.py        # Dialogue healer with Roll-Call FSM & cluster retention
│   │   ├── ingest_v3.py        # YouTube channel, RSS, and local media ingestor
│   │   ├── pipeline_v4.py      # Master streaming pipeline coordinator
│   │   ├── queue_v2.py         # SQLite WAL job queue
│   │   └── transcribe_v3.py    # Sliding window streaming Whisper ASR
│   └── playbooks/
│       └── loader_v3.py        # JSON Schema v7 loader & presiding role detector
├── static/
│   ├── index.html              # Real-time SSE dashboard
│   └── index_v2.html           # Versioned web dashboard
└── tests/
    ├── test_phase2_streaming_v3.py
    ├── test_phase3_fsm_v3.py
    ├── test_phase4_catalog_export_v4.py
    └── ... (82 passing tests)
```
