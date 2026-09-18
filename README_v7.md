# 🎙️ Universal Transcriber

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: macOS Apple Silicon](https://img.shields.io/badge/Platform-macOS%20Apple%20Silicon%20(Metal)-black.svg)](https://apple.com)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org)
[![Engineered by: @seanbuilds](https://img.shields.io/badge/Engineered%20by-%40seanbuilds-6366f1.svg)](https://github.com/seanbuilds)
[![Tests: 106 Passing](https://img.shields.io/badge/Tests-106%20Passing-success.svg)](tests/)

<!-- v7 – Production GitHub release, MIT License attribution to @seanbuilds, iterations history, and multi-format engine documentation -->

**Universal Transcriber** is an autonomous, high-performance speech transcription and neural speaker diarization platform engineered specifically for Apple Silicon Macs (M1/M2/M3/M4). 

Built by **Sean Tyler ([@seanbuilds](https://github.com/seanbuilds))**, it leverages Apple's Metal GPU framework (`MTL0`) to perform local transcription up to **30x faster than real-time**, clusters speaker voices with vectorized hierarchical algorithms, heals fragmented utterances using domain-specific finite state machines, logs every transcription attempt to a persistent audit store, and synchronizes atomic exports across 6 industry-standard formats.

---

## 🚀 Key Platform Capabilities

1. **Multi-Format Local Media Container Support (`ingest_v4.py`)**:
   - Native audio and video extraction across **`.m4a`, `.mp3`, `.mp4`, `.mov`, `.mkv`, `.wav`, `.flac`, `.aac`, `.webm`, `.ogg`, and `.opus`**.
   - **Video-Bypassing Optimization (`-vn`)**: Bypasses costly video stream frame decoding for video containers, extracting pure 16 kHz mono PCM audio up to 5x faster.
   - Container metadata inspection via `ffprobe` (sample rate, channel layout, bitrate, duration, track tags).

2. **Drag & Drop Local Media Web Dropzone (`app_v5.py`, `static/index.html`)**:
   - Interactive browser dropzone accepting local media files with real-time upload progress indicators.
   - Dedicated `/api/upload` endpoint staging uploads to `~/Documents/Transcripts/uploads/`.
   - Automatic format pill tags, file duration badges, and title pre-filling.

3. **Dedicated Local CLI Command (`cli_v6.py local`)**:
   - Transcribe single files: `python3 cli_v6.py local recording.m4a --playbook gaming_videos --title Match_Finals`.
   - Batch-scan directories (flat or recursive): `python3 cli_v6.py local /path/to/media/ --recursive --playbook general_speech`.

4. **Domain Playbooks — Gaming Videos & Esports (`gaming_videos_v1.json`)**:
   - Tailored domain lexicon and cues for esports shoutcasting, Let's Plays, speedruns, and squad banter.
   - Distinct speaker role detection: **Streamer**, **Teammate**, **Opponent**, **Caster**, and **System**.
   - Additional playbooks included: Municipal Meetings, Interviews & Podcasts, Corporate Meetings, Academic Lectures, and General Speech.
   - Validated strictly against JSON Schema v7 (`playbooks/schema_v1.json`).

5. **Persistent Transcription Audit Trail (`audit_v1.py`)**:
   - Thread-safe SQLite audit store (`~/Documents/Transcripts/transcriptions_audit_v1.sqlite`) paired with an append-only JSON Lines event stream (`transcriptions_audit_v1.jsonl`).
   - **Logs every single transcription attempt** whether completed, failed, cancelled, or discarded without being downloaded/used.
   - Comprehensive metadata tracking: Job ID, UTC timestamps, source media, custom titles, playbook, clustering mode, audio duration, segment counts, export paths, and consumption status (`USED` vs `UNUSED`).

6. **Standardized ISO-8601 Filename Formatting (`export_v4.py`)**:
   - Uniform directory and multi-format file naming: `YYYYMMDD_<Title>` (e.g., `20260918_Match_Finals`).
   - Supports user-specified custom titles and falls back to media metadata or current UTC date.
   - Synchronous generation across all 6 atomic formats: Markdown (`.md`), Plaintext (`.txt`), SubRip Subtitles (`.srt`), WebVTT (`.vtt`), Word Document (`.docx`), and AST Data (`.json`).

7. **"Clear Everything / Start Over" UI Action (`static/index.html`, `app_v5.py`)**:
   - Dedicated reset button immediately aborts active Server-Sent Events (SSE) streams, signals background job cancellation, clears input fields, resets progress bars, and restores initial readiness.

8. **Sliding-Window Streaming ASR & Real-Time Telemetry (`app_v5.py`)**:
   - 30-second sliding windows with 2-second overlap compensation via `WhisperTranscriberV3`.
   - Real-time Server-Sent Events (`GET /api/stream/<job_id>`) delivering live ASR tokens, active speaker identification, and progress percentages to web clients.

9. **Ultra-Accelerated Neural Acoustic Diarization (`diarize_v3.py` & `embeddings_v1.py`)**:
   - Vectorized `scipy.cluster.hierarchy` cosine linkage delivering a **25,000x speedup** over pure-Python clustering ($O(n^2)$ C implementation vs $O(n^3)$ interpreted loops).

10. **YouTube Channel & RSS Feed Catalog Idempotency (`catalog_v1.py`)**:
    - Persistent SQLite media index tracking content IDs, publication dates, and processing states.
    - Prevents duplicate downloads and transcription of previously processed content.

---

## 📦 System Prerequisites

### 1. Homebrew System Dependencies (macOS)
```bash
brew install whisper-cpp ffmpeg yt-dlp
```

### 2. Python 3.12+ Runtime Packages
```bash
pip3 install flask flask-cors jsonschema python-docx requests pillow numpy scipy
```

---

## 💻 Command-Line Interface (`cli_v6.py`)

### Transcribe Local Media Files
```bash
# Transcribe single local audio or video file with ISO naming and custom title
python3 cli_v6.py local /path/to/podcast.m4a --title "Episode_42" --playbook interview_podcast

# Transcribe local video file (automatically skips video decoding, extracts audio only)
python3 cli_v6.py local /path/to/gameplay.mp4 --title "Speedrun_PB" --playbook gaming_videos

# Scan an entire directory for all media files (.m4a, .mp3, .mp4, .mov, .wav, .flac)
python3 cli_v6.py local /path/to/recordings/ --recursive --playbook corporate_meeting
```

### Transcribe Remote Media (YouTube / Podcasts)
```bash
# Transcribe YouTube video with custom title and domain playbook
python3 cli_v6.py transcribe "https://www.youtube.com/watch?v=..." --title "Council_Hearing" --playbook municipal_meetings
```

### Inspect Persistent Audit Trail
```bash
# Summary of all transcription attempts (completed, failed, cancelled, unused)
python3 cli_v6.py audit

# List only unused/discarded recordings
python3 cli_v6.py audit --unused

# Mark a specific job ID as viewed/used
python3 cli_v6.py audit --mark-used job_6ebd501e
```

### Manage Speaker Profiles & Biometrics
```bash
# List all registered speakers and centroid norm metrics
python3 cli_v6.py speakers

# Rename a speaker turn ID across profiles
python3 cli_v6.py speakers --rename Speaker_01 "Lead Host"
```

### Synchronize Channels & Deliver Transcripts
```bash
# Scan YouTube channel or RSS feed with idempotency
python3 cli_v6.py catalog "https://www.youtube.com/@CityOfCohasset/videos" --limit 5

# Dispatch recent transcripts via email / Apple Mail outbox
python3 cli_v6.py email --count 5 --target ohheysean@gmail.com
```

---

## 🌐 Real-Time Web Dashboard (`app_v5.py`)

The background web server runs at:
```bash
http://127.0.0.1:5055
```

To manually launch:
```bash
python3 app_v5.py
```

### Dashboard Highlights:
- **Drag & Drop Dropzone**: Drop any media file (`.m4a`, `.mp3`, `.mp4`, `.mov`, `.mkv`, `.wav`, etc.) directly from Finder.
- **Upload Progress & Metadata**: Format badges, audio duration, file size, and automatic title prefill.
- **Live Streaming Transcripts**: Real-time token delivery via Server-Sent Events with active speaker badges.
- **Clear Everything / Start Over**: Aborts active jobs, resets UI state, and logs cancellation to audit.
- **Persistent Audit Panel**: Dynamic counter of total, completed, failed, cancelled, and unused recordings, with an auto-updating tabular history.
- **Multi-Format Downloads**: One-click download of `.md`, `.txt`, `.docx`, `.srt`, `.vtt`, and `.json`.

---

## 🧪 Testing & Verification

Execute the complete verification test suite:
```bash
/opt/homebrew/opt/python@3.14/bin/python3 -m pytest -v
```

All 106 unit, integration, multi-domain, local media container, adversarial, and web API concurrency tests pass with 0 failures.

---

## ⏱️ Chronological Iterations Log

For the complete historical record of all development milestones from initial conception to current release, consult:
- [ITERATIONS_LOG_v1.md](ITERATIONS_LOG_v1.md)
- [CHANGELOG_v1.md](CHANGELOG_v1.md)

---

## 📄 License & Attribution

Universal Transcriber is authored and maintained by **Sean Tyler ([@seanbuilds](https://github.com/seanbuilds))** (`ohheysean@gmail.com`).

Licensed under the **MIT License**. See [LICENSE](LICENSE) for full details.
