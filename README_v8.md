# 🎙️ Universal Transcriber

[![Release: v0.1.0-beta](https://img.shields.io/badge/Release-v0.1.0--beta-blueviolet.svg)](https://github.com/seanbuilds/universal-transcriber/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: macOS Apple Silicon](https://img.shields.io/badge/Platform-macOS%20Apple%20Silicon%20(Metal)-black.svg)](https://apple.com)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org)
[![Engineered by: @seanbuilds](https://img.shields.io/badge/Engineered%20by-%40seanbuilds-6366f1.svg)](https://github.com/seanbuilds)
[![Tests: 126 Passing](https://img.shields.io/badge/Tests-126%20Passing-success.svg)](tests/)

<!-- Canonical README linking to README_v8.md -->

**Universal Transcriber** is an autonomous, high-performance speech transcription and acoustic speaker diarization platform engineered specifically for Apple Silicon Macs (M1/M2/M3/M4).

Built by **Sean Tyler ([@seanbuilds](https://github.com/seanbuilds))**, it leverages Apple's native Metal GPU framework (`MTL0`) to perform local transcription up to **30x faster than real-time**, clusters speaker voices with vectorized hierarchical algorithms, heals fragmented utterances using domain-specific finite state machines, logs every transcription attempt to a persistent audit store, and synchronizes atomic exports across 6 industry-standard formats.

---

## ⚡ Quick Start (Turnkey 0.1-Beta Setup)

Universal Transcriber is packaged for zero-friction setup on macOS Apple Silicon.

### 1. Run the Automated Installer
```bash
git clone https://github.com/seanbuilds/universal-transcriber.git
cd universal-transcriber
./install.sh
```
The automated installer verifies your hardware, installs any missing Homebrew utilities (`ffmpeg`, `yt-dlp`, `whisper-cpp`), configures Python dependencies, downloads GGML Whisper models to `~/.cache/universal_transcriber/models/`, and validates Metal GPU acceleration.

### 2. Launch the Web Dashboard (1-Click)
```bash
./start_app.sh
```
This boots the background web daemon and opens **`http://127.0.0.1:5055`** in your default browser.

For complete manual setup instructions and options, see [**INSTALL.md**](INSTALL.md).

---

## 🚀 Key Platform Capabilities

1. **Turnkey Setup & 1-Click Launch (`install.sh`, `start_app.sh`)**:
   - Automated environment verification, Homebrew tool management, Python virtual environment, GGML speech model downloads, and Metal GPU verification.
   - Clean top-level canonical entrypoints: `cli.py`, `app.py`, and `config.py`.

2. **Multi-Format Local Media Container Support (`src/engine/ingest_v4.py`)**:
   - Native audio and video ingestion across **`.m4a`, `.mp3`, `.mp4`, `.mov`, `.mkv`, `.wav`, `.flac`, `.aac`, `.webm`, `.ogg`, and `.opus`**.
   - **Video-Bypassing Optimization (`-vn`)**: Bypasses costly video stream frame decoding for video containers, extracting pure 16 kHz mono PCM audio up to 5x faster.
   - Container metadata inspection via `ffprobe` (sample rate, channel layout, bitrate, duration, track tags).

3. **Drag & Drop Local Media Web Dropzone (`app.py`, `static/index.html`)**:
   - Interactive browser dropzone accepting local media files with real-time upload progress indicators.
   - Dedicated `/api/upload` endpoint staging uploads to `~/Documents/Transcripts/uploads/`.
   - Automatic format pill tags, file duration badges, and title pre-filling.

4. **Dedicated Local CLI Command (`cli.py local`)**:
   - Transcribe single files: `python3 cli.py local recording.m4a --playbook gaming_videos --title Match_Finals`.
   - Batch-scan directories (flat or recursive): `python3 cli.py local /path/to/media/ --recursive --playbook general_speech`.

5. **Domain Playbooks (`playbooks/`)**:
   - Tailored domain lexicons and formatting rules for specific recording contexts:
     - **Gaming Videos & Esports** (`gaming_videos_v1.json`): Streamer, Teammate, Opponent, Caster role detection.
     - **Municipal Meetings** (`municipal_meetings_v1.json`): Roll-call votes, procedural motions, public comment periods.
     - **Interviews & Podcasts** (`interview_podcast_v1.json`): Host, Co-host, Guest conversational turn coalescence.
     - **Corporate Meetings** (`corporate_meeting_v1.json`): Action items, agenda transitions, executive summaries.
     - **Academic Lectures** (`academic_lecture_v1.json`): Technical nomenclature, Q&A distinction.
     - **General Speech** (`general_speech_v1.json`): Robust general-purpose transcription.
   - Validated strictly against JSON Schema v7 (`playbooks/schema_v1.json`).

6. **Persistent Transcription Audit Trail (`src/engine/audit_v1.py`)**:
   - Thread-safe SQLite audit store (`~/Documents/Transcripts/transcriptions_audit_v1.sqlite`) paired with an append-only JSON Lines event stream (`transcriptions_audit_v1.jsonl`).
   - **Logs every single transcription attempt** whether completed, failed, cancelled, or discarded without being downloaded/used.
   - Comprehensive metadata tracking: Job ID, UTC timestamps, source media, custom titles, playbook, clustering mode, audio duration, segment counts, export paths, and consumption status (`USED` vs `UNUSED`).

7. **Standardized ISO-8601 Filename Formatting (`src/engine/export_v4.py`)**:
   - Uniform directory and multi-format file naming: `YYYYMMDD_<Title>` (e.g., `20260920_Match_Finals`).
   - Supports user-specified custom titles and falls back to media metadata or current UTC date.
   - Synchronous generation across all 6 atomic formats: Markdown (`.md`), Plaintext (`.txt`), SubRip Subtitles (`.srt`), WebVTT (`.vtt`), Word Document (`.docx`), and AST Data (`.json`).

8. **"Clear Everything / Start Over" UI Action (`static/index.html`, `app.py`)**:
   - Dedicated reset button immediately aborts active Server-Sent Events (SSE) streams, signals background job cancellation, clears input fields, resets progress bars, and restores initial readiness.

9. **Sliding-Window Streaming ASR & Real-Time Telemetry (`app.py`)**:
   - 30-second sliding windows with 2-second overlap compensation via `WhisperTranscriberV3`.
   - Real-time Server-Sent Events (`GET /api/stream/<job_id>`) delivering live ASR tokens, active speaker identification, and progress percentages to web clients.

10. **Ultra-Accelerated Acoustic Diarization (`src/engine/diarize_v3.py` & `src/engine/embeddings_v1.py`)**:
    - Vectorized `scipy.cluster.hierarchy` cosine linkage delivering a **25,000x speedup** over pure-Python clustering ($O(n^2)$ C implementation vs $O(n^3)$ interpreted loops).

11. **YouTube Channel & RSS Feed Catalog Idempotency (`src/engine/catalog_v1.py`)**:
    - Persistent SQLite media index tracking content IDs, publication dates, and processing states to eliminate redundant downloads.

12. **YouTube Playlist Breakdown & Placeholder Staging (`src/engine/playlist_v1.py`)**:
    - Inspects YouTube playlists without downloading media (`yt-dlp --flat-playlist`).
    - Displays an upfront interactive confirmation warning with video count, total estimated audio duration, and target directory.
    - Stages a dedicated collection folder (`~/Documents/Transcripts/Playlists/YYYYMMDD_<Title>/`) with `playlist_manifest.json`, `PLAYLIST_INDEX.md`, and individual `.pending` placeholder files for every single video (ensuring 0% chance of missed videos).
    - Sequentially transcribes each video step-by-step with isolated error handling (a single private/failed video does not crash the playlist run).
    - Supports crash-resilient resumption (`--resume`), skipping already-completed items.

13. **Danger Zone UI History Clear & Disk Preservation Guarantee (`static/index.html`, `app.py`)**:
    - Crimson-accented "Danger Zone" card at the bottom of the dashboard with an interactive modal confirmation (`⚠️ Are you sure?`).
    - Clears the UI audit history and job queue without touching physical files: all transcript folders, media, and multi-format files in `~/Documents/Transcripts/` remain 100% untouched on disk (`POST /api/audit/clear`).

14. **1-Click Clipboard Copy Commands & Ubiquitous Meeting / URL Display (`static/index.html`, `src/engine/export_v4.py`)**:
    - Fast 1-click `📋 Copy` buttons across all input fields, results cards, tables, and modal dialogs.
    - Inline `📋 Copy URL` and `📋 Copy Name` inside input fields, with a `📋 Copy Command` CLI generator.
    - Results card metadata header displaying Meeting Name and YouTube / Source URL, paired with `📋 Copy All Info`, `📋 Copy Transcript`, and `📥 Copy into Input Boxes`.
    - All 6 generated export files (`.md`, `.txt`, `.srt`, `.vtt`, `.docx`, `.json`) include the Meeting Name and YouTube / Source URL in headers and metadata.

15. **Atomic Post-Transcription Local Folder & Multi-Format Generation (`src/engine/export_v4.py`, `src/engine/pipeline_v6.py`)**:
    - **Strict Timing Guarantee**: Output folders and final export files are created strictly **after** all 5 pipeline processing steps (*Ingest → Preprocess → Metal Streaming ASR → Neural Diarization → Role Healing*) succeed without error.
    - **100% Local Multi-Format Suite**: Dedicated local folder generated under `~/Documents/Transcripts/` for each completed job, containing all 6 supported formats (`.md`, `.txt`, `.srt`, `.vtt`, `.docx`, `.json`) verified on disk with non-zero file sizes and atomic rollback safety.
    - **macOS Finder Reveal Integration**: Direct `📂 Reveal in Finder` action button via `POST /api/open-folder` (`/usr/bin/open <path>`) with directory containment security.
    - **Results & Playlist Tracker Cards**: Local Files Card showing full folder path and 6 individual file copy buttons; playlist batch tracker displays local folders with inline Finder and Copy buttons.

---

## 💻 Command-Line Interface (`cli.py`)

Universal Transcriber provides a unified CLI entrypoint:

```bash
# Check installed CLI version
python3 cli.py --version
# Output: Universal Transcriber v0.1.0-beta (@seanbuilds)
```

### Transcribe Local Media Files
```bash
# Transcribe single local audio or video file with ISO naming and custom title
python3 cli.py local ~/Music/podcast.m4a --title "Episode_42" --playbook interview_podcast

# Transcribe local video file (automatically skips video decoding, extracts audio only)
python3 cli.py local ~/Movies/gameplay.mp4 --title "Speedrun_PB" --playbook gaming_videos

# Scan an entire directory for all media files (.m4a, .mp3, .mp4, .mov, .wav, .flac)
python3 cli.py local ~/Documents/Recordings/ --recursive --playbook corporate_meeting
```

### Transcribe YouTube Playlists & Remote Media
```bash
# Break down and transcribe a YouTube playlist with upfront confirmation and placeholder staging
python3 cli.py playlist "https://www.youtube.com/playlist?list=PL..." --playbook municipal_meetings

# Inspect playlist items without downloading or creating files (Dry Run)
python3 cli.py playlist "https://www.youtube.com/playlist?list=PL..." --dry-run

# Transcribe YouTube video with custom title and domain playbook
python3 cli.py transcribe "https://www.youtube.com/watch?v=..." --title "Council_Hearing" --playbook municipal_meetings
```

### Inspect Persistent Audit Trail
```bash
# Summary of all transcription attempts (completed, failed, cancelled, unused)
python3 cli.py audit

# List only unused/discarded recordings
python3 cli.py audit --unused

# Mark a specific job ID as viewed/used
python3 cli.py audit --mark-used job_6ebd501e
```

### Manage Speaker Profiles & Biometrics
```bash
# List all registered speakers and centroid norm metrics
# Deliver completed transcripts via email
python3 cli.py email --count 5 --target ohheysean@gmail.com
```

---

## 🌐 Real-Time Web Dashboard (`app.py`)

The background web server runs at:
```
http://127.0.0.1:5055
```

Launch with:
```bash
./start_app.sh
```

### Dashboard Highlights:
- **Drag & Drop Dropzone**: Drop any media file (`.m4a`, `.mp3`, `.mp4`, `.mov`, `.mkv`, `.wav`, etc.) directly from Finder.
- **Interactive Playlist Staging**: Detects playlist URLs, pops up upfront confirmation modal with item counts and projected folders, stages placeholder files, and tracks step-by-step progress.
- **Upload Progress & Metadata**: Format badges, audio duration, file size, and automatic title prefill.
- **Live Streaming Transcripts**: Real-time token delivery via Server-Sent Events with active speaker badges.
- **Local Files Box & Finder Reveal**: Direct `📂 Reveal in Finder` action opening the local export folder, with 6 individual file copy buttons for `.md`, `.txt`, `.srt`, `.vtt`, `.docx`, and `.json`.
- **1-Click Copy Toolbar**: Instant `📋 Copy` actions on inputs (`Copy URL`, `Copy Name`), CLI commands (`Copy Command`), and results (`Copy All Info`, `Copy Transcript`, `Copy into Input Boxes`).
- **Danger Zone History Clear**: Crimson card at the bottom of the dashboard with modal confirmation (`⚠️ Are you sure?`) to clear UI audit history while keeping local disk files 100% intact.
- **Clear Everything / Start Over**: Aborts active jobs, resets UI state, and logs cancellation to audit.
- **Persistent Audit Panel**: Dynamic counter of total, completed, failed, cancelled, and unused recordings, with an auto-updating tabular history showing Meeting Names and Source URLs.
- **Multi-Format Downloads**: One-click download of `.md`, `.txt`, `.docx`, `.srt`, `.vtt`, and `.json`.

---

## 🧪 Testing & Verification

Execute the complete verification test suite:
```bash
PYTHONPATH=. pytest -v
```

All **126** unit, integration, multi-domain, local media container, playlist staging, danger zone history clear, and post-transcription export tests pass with 0 failures across all 23 test modules (`126 passed in ~3.5s`).

---

## ⏱️ Chronological Iterations Log

For the complete historical record of all development milestones from initial conception to the 0.1-beta release, consult:
- [ITERATIONS_LOG_v1.md](ITERATIONS_LOG_v1.md)
- [CHANGELOG.md](CHANGELOG.md)
- [INSTALL.md](INSTALL.md)
- [TUTORIALS.md](TUTORIALS.md)
- [USER_MANUAL.md](USER_MANUAL.md) (Interactive video tutorials narrated with male voice)

---

## 📄 License & Attribution

Universal Transcriber is authored and maintained by **Sean Tyler ([@seanbuilds](https://github.com/seanbuilds))** (`ohheysean@gmail.com`).

Licensed under the **MIT License**. See [LICENSE](LICENSE) for full details.
