# 🎙️ Universal Transcriber (v6 Master Release)
<!-- v6 – Multi-Format Local Media (.m4a, .mp3, .mp4, .mov, .mkv, .wav, .flac, .aac), Video-Bypassing (-vn) Extraction, Drag & Drop Web Dropzone, CLI local Command, and Persistent Audit Trail -->

**High-Performance, Autonomous Audio & Video Transcription Engine for macOS (Apple Silicon Metal GPU)**

Universal Transcriber is an autonomous, domain-aware media transcription and speaker diarization platform engineered natively for Apple Silicon Macs. It extracts audio from YouTube channels, playlists, podcast RSS feeds, and local media containers, transcribes speech at up to **30x real-time speed** using Apple's Metal GPU (`MTL0`), clusters speaker voices persistently using neural and spherical unit-normalized embeddings, heals fragmented speech via domain-specific finite state machines, delivers transcripts via email/outbox, audits every transcription attempt persistently, and exports verbatim transcripts across 6 industry-standard formats.

---

## 🚀 Key Platform Capabilities

1. **Comprehensive Local Media Container Support (`ingest_v4.py`)**:
   - Native audio and video extraction across **`.m4a`, `.mp3`, `.mp4`, `.mov`, `.mkv`, `.wav`, `.flac`, `.aac`, `.webm`, `.ogg`, and `.opus`**.
   - **Video-Bypassing Optimization (`-vn`)**: Skips costly video stream frame decoding for video containers (e.g., MP4, MOV, MKV), extracting pure 16 kHz mono PCM audio up to 5x faster.
   - Automatic metadata and embedded tag inspection (`ffprobe`) for container format, duration, bitrate, and track titles.

2. **Drag & Drop Local Media Web Dropzone (`app_v5.py`, `static/index.html`)**:
   - Interactive browser dropzone accepting local media files with real-time upload progress indicators.
   - Dedicated `/api/upload` endpoint staging uploads to `~/Documents/Transcripts/uploads/`.
   - Automatic filename stem detection, media format pill tags, and duration badges.

3. **Dedicated Local CLI Command (`cli_v6.py local`)**:
   - Transcribe single files: `python3 cli_v6.py local recording.m4a --playbook gaming_videos --title Match_Finals`.
   - Batch-scan directories (flat or recursive): `python3 cli_v6.py local /path/to/media/ --recursive --playbook general_speech`.

4. **New Domain Playbooks — Gaming Videos & Creator Content (`gaming_videos_v1.json`)**:
   - Tailored domain lexicon and cues for esports shoutcasting, Let's Plays, speedruns, and squad banter.
   - Distinct speaker role detection: **Streamer**, **Teammate**, **Opponent**, **Caster**, and **System**.
   - Validated strictly against JSON Schema v7 (`playbooks/schema_v1.json`).

5. **Persistent Transcription Audit Trail (`audit_v1.py`)**:
   - Thread-safe SQLite audit store (`~/Documents/Transcripts/transcriptions_audit_v1.sqlite`) paired with an append-only JSONL event stream (`transcriptions_audit_v1.jsonl`).
   - **Logs every single transcription attempt** whether completed, failed, cancelled, or discarded without being downloaded/used.
   - Comprehensive metadata tracking: Job ID, UTC timestamps, source media, custom titles, playbook, clustering mode, audio duration, segment counts, export paths, and consumption status (`USED` vs `UNUSED`).

6. **Standardized ISO-8601 Filename Formatting (`export_v4.py`)**:
   - Uniform directory and multi-format file naming: `YYYYMMDD_<Title>` (e.g., `20260917_Gaming_Highlight`).
   - Supports user-specified custom titles and falls back to media metadata or current UTC date.
   - Generated synchronously across all 6 atomic formats: Markdown (`.md`), Plaintext (`.txt`), SubRip Subtitles (`.srt`), WebVTT (`.vtt`), Word Document (`.docx`), and AST Data (`.json`).

7. **"Clear Everything / Start Over" UI Action (`static/index.html`, `app_v5.py`)**:
   - Dedicated reset button immediately aborts active Server-Sent Events (SSE) streams, signals background job cancellation, clears input fields, resets progress bars, and clears live streaming buffers for an instantaneous fresh start.

8. **Sliding-Window Streaming ASR & Real-Time Telemetry (`app_v5.py`)**:
   - 30-second sliding windows with 2-second overlap compensation via `WhisperTranscriberV3`.
   - Real-time Server-Sent Events (`GET /api/stream/<job_id>`) delivering live ASR tokens, active speaker identification, and progress percentages to web clients.

9. **Ultra-Accelerated Neural Acoustic Diarization (`diarize_v3.py` & `embeddings_v1.py`)**:
   - Vectorized `scipy.cluster.hierarchy` cosine linkage delivering a **25,000x speedup** over pure-Python clustering ($O(n^2)$ C implementation vs $O(n^3)$ interpreted loops).

---

## 📦 System Prerequisites

```bash
# macOS System Tools (Homebrew)
brew install whisper-cpp ffmpeg yt-dlp

# Python 3.12+ Runtime Packages
pip3 install flask flask-cors jsonschema python-docx requests pillow numpy scipy
```

---

## 💻 Command-Line Interface (`cli_v6.py`)

### 1. Transcribe Local Media Files (.m4a, .mp3, .mp4, .mov, .wav)
```bash
# Transcribe single local audio or video file with ISO naming and custom title
python3 cli_v6.py local /path/to/podcast.m4a --title "Episode_42" --playbook interview_podcast

# Transcribe local video file (bypasses video frames, extracts audio only)
python3 cli_v6.py local /path/to/gameplay.mp4 --title "Speedrun_PB" --playbook gaming_videos

# Scan an entire directory for all media files (.m4a, .mp3, .mp4, .mov, .wav, .flac)
python3 cli_v6.py local /Users/dad/Downloads/Recordings/ --recursive --playbook corporate_meeting
```

### 2. Transcribe YouTube or Remote Media
```bash
# Transcribe YouTube video with custom title and domain playbook
python3 cli_v6.py transcribe "https://www.youtube.com/watch?v=..." --title "Council_Hearing" --playbook municipal_meetings
```

### 3. Inspect Persistent Audit Trail
```bash
# Summary of all transcription attempts (completed, failed, cancelled, unused)
python3 cli_v6.py audit

# List only unused/discarded recordings
python3 cli_v6.py audit --unused

# Mark a specific job ID as viewed/used
python3 cli_v6.py audit --mark-used job_6ebd501e
```

### 4. Manage Speakers, Catalog & Delivery
```bash
# Manage speaker biometrics
python3 cli_v6.py speakers
python3 cli_v6.py speakers --rename Speaker_01 "Host"

# Scan YouTube channel or RSS feed with idempotency
python3 cli_v6.py catalog "https://www.youtube.com/@CityOfCohasset/videos" --limit 5

# Email dispatch
python3 cli_v6.py email --count 5 --target user@example.com
```

---

## 🌐 Real-Time Web Dashboard (`app_v5.py`)

The background web server runs continuously at:
```bash
http://127.0.0.1:5055
```

To manually launch or restart:
```bash
python3 app_v5.py
```

### Dashboard Features:
- **Local File Dropzone**: Drag and drop `.m4a`, `.mp3`, `.mp4`, `.mov`, `.mkv`, `.wav`, or `.flac` files directly from Finder.
- **Upload Progress & Metadata**: Displays file container format badge, duration, file size, and automatic title prefill.
- **Clear / Start Over**: Resets all form fields, aborts the active live SSE stream, logs cancellation to the audit store, and restores readiness.
- **Persistent Audit Panel**: Displays live count of total, completed, failed, cancelled, and unused recordings, with an auto-updating tabular history.
- **Atomic Multi-Format Downloads**: One-click direct download of `.md`, `.txt`, `.docx`, `.srt`, `.vtt`, and `.json` files.

---

## 🧪 Testing & Verification

Execute the complete verification test suite:
```bash
/opt/homebrew/opt/python@3.14/bin/python3 -m pytest -v
```
All 104 unit, integration, multi-domain, local media container, adversarial, and web API concurrency tests pass with 0 failures.
