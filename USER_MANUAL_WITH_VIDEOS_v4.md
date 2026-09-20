# Universal Transcriber: Multimedia User Manual & Video Guides (v4)

<!-- v4 – Comprehensive Multimedia User Manual with 5 Embedded Video Tutorials with Male Voice Narration covering Turnkey Installation (install.sh), 1-Click Launch (start_app.sh), Local Media Dropzone (.m4a, .mp3, .mp4, .mov), CLI Batch Scanning, Domain Playbooks with FSM Role Healing, and Persistent Audit Logging -->

Welcome to the **Universal Transcriber 0.1-Beta** operational manual. This guide pairs comprehensive step-by-step written instructions with high-definition video walkthroughs narrated by a clear, natural male voice.

- **Product Release:** `0.1-beta` (`v0.1.0-beta`)
- **Author & Maintainer:** Sean Tyler ([@seanbuilds](https://github.com/seanbuilds))
- **Primary Contact:** `ohheysean@gmail.com`
- **Target Architecture:** Apple Silicon Macs (M1/M2/M3/M4 Metal GPU `MTL0`)
- **License:** MIT License (`LICENSE`)

---

## 📑 Manual Table of Contents

1. [Tutorial 1: Turnkey Installation & 1-Click Startup](#tutorial-1-turnkey-installation--1-click-startup)
2. [Tutorial 2: Local Media Drag-and-Drop Dropzone & Video Bypassing](#tutorial-2-local-media-drag-and-drop-dropzone--video-bypassing)
3. [Tutorial 3: Unified Command-Line Interface & Directory Batching](#tutorial-3-unified-command-line-interface--directory-batching)
4. [Tutorial 4: Domain Playbooks & Finite State Machine Speaker Healing](#tutorial-4-domain-playbooks--finite-state-machine-speaker-healing)
5. [Tutorial 5: Persistent Transcription Audit Log & Catalog Idempotency](#tutorial-5-persistent-transcription-audit-log--catalog-idempotency)
6. [Supported Containers & Optimization Reference](#supported-containers--optimization-reference)
7. [Storage Directories & File Hygiene](#storage-directories--file-hygiene)

---

## Tutorial 1: Turnkey Installation & 1-Click Startup

This video tutorial demonstrates how to perform a completely automated setup on macOS Apple Silicon using `install.sh`, verify dependencies, fetch speech models, and launch the web dashboard in one click using `start_app.sh`.

https://github.com/user-attachments/assets/tutorial_01_install_and_launch_v1
*(Local video track: [docs/videos/tutorial_01_install_and_launch_v1.mp4](docs/videos/tutorial_01_install_and_launch_v1.mp4))*

### Step-by-Step Instructions:

#### 1. Automated 1-Command Installation
Clone the repository and run the turnkey installer:
```bash
git clone https://github.com/seanbuilds/universal-transcriber.git
cd universal-transcriber
./install.sh
```

**Automated Setup Stages:**
- **Stage 1 (Hardware):** Verifies macOS Apple Silicon architecture (`arm64`).
- **Stage 2 (System Tools):** Verifies and installs Homebrew tools (`ffmpeg`, `yt-dlp`, `whisper-cpp`).
- **Stage 3 (Python Environment):** Automatically selects Python 3.12+ (e.g. `python@3.14`).
- **Stage 4 (Dependencies):** Installs Python packages from `requirements.txt` (`flask`, `flask-cors`, `jsonschema`, `python-docx`, `requests`, `pillow`, `numpy`, `scipy`).
- **Stage 5 (Models):** Downloads GGML Whisper models to `~/.cache/universal_transcriber/models/`:
  - `ggml-base.en.bin` (141 MB)
  - `ggml-small.en.bin` (465 MB)
- **Stage 6 (GPU Check):** Confirms Apple Silicon Metal framework (`MTL0`).

#### 2. 1-Click Launch
```bash
./start_app.sh
```
The script boots `app.py` in the background, waits for port 5055 to become active, and automatically launches your browser to **`http://127.0.0.1:5055`**.

---

## Tutorial 2: Local Media Drag-and-Drop Dropzone & Video Bypassing

This video tutorial walks through transcribing local media files directly from Finder, leveraging the video stream bypass optimization (`-vn`) to decode audio up to 5x faster, and monitoring real-time Server-Sent Events (SSE).

https://github.com/user-attachments/assets/tutorial_02_local_media_dropzone_v1
*(Local video track: [docs/videos/tutorial_02_local_media_dropzone_v1.mp4](docs/videos/tutorial_02_local_media_dropzone_v1.mp4))*

### Step-by-Step Instructions:

1. **Open Dashboard:** Navigate to `http://127.0.0.1:5055` in Safari, Chrome, or Firefox.
2. **Drag & Drop:** Drag any media container (`.m4a`, `.mp3`, `.mp4`, `.mov`, `.mkv`, `.wav`, `.flac`) into the dashed dropzone.
3. **Inspect Probed Metadata:** The interface uploads the staged file to `~/Documents/Transcripts/uploads/` and displays:
   - Format pill (e.g., `M4A`, `MP4`, `MOV`)
   - Duration badge (e.g., `00:18:45`)
   - Clean ISO title prefill
4. **Choose Playbook:** Select the relevant domain rules (e.g., `interview_podcast` or `gaming_videos`).
5. **Start Transcription:** Click **⚡ Transcribe**.
6. **Watch Real-Time Streaming:** The Server-Sent Events stream (`GET /api/stream/<job_id>`) delivers live tokens, active speaker turn badges (`SPEAKER_00`, `SPEAKER_01`), and progress percentages.
7. **Reset State:** Click **🔄 Clear / Start Over** at any time to abort the active stream, clear fields, and log cancellation to the audit database.

---

## Tutorial 3: Unified Command-Line Interface & Directory Batching

This video tutorial demonstrates the CLI workflows for transcribing single files, batch-scanning directories recursively, and inspecting standardized atomic export files.

https://github.com/user-attachments/assets/tutorial_03_cli_local_and_batch_v1
*(Local video track: [docs/videos/tutorial_03_cli_local_and_batch_v1.mp4](docs/videos/tutorial_03_cli_local_and_batch_v1.mp4))*

### Step-by-Step Instructions:

#### 1. Transcribe a Single Local File
```bash
python3 cli.py local ~/Music/board_hearing.m4a \
  --title "Select_Board_Hearing" \
  --playbook municipal_meetings
```

#### 2. Recursively Scan and Batch Transcribe a Directory
```bash
python3 cli.py local ~/Documents/Recordings/ \
  --recursive \
  --playbook corporate_meeting
```

#### 3. Transcribe Remote Streams
```bash
python3 cli.py transcribe "https://www.youtube.com/watch?v=..." \
  --title "Town_Forum" \
  --playbook municipal_meetings
```

#### 4. Access Exported Formats
Every completed transcription generates an ISO-8601 job folder (`~/Documents/Transcripts/YYYYMMDD_<Title>/`) containing:
- **`*.md`**: Formatted Markdown dialogue blocks.
- **`*.txt`**: Verbatim plaintext for search indexing.
- **`*.srt`**: Timecoded SubRip captions.
- **`*.vtt`**: WebVTT caption file with voice tags (`<v Speaker>`).
- **`*.docx`**: Formatted Microsoft Word document.
- **`*.json`**: Structured AST tokens, word confidences, and speaker turns.

---

## Tutorial 4: Domain Playbooks & Finite State Machine Speaker Healing

This video tutorial details the 6 built-in domain playbooks, JSON Schema v7 validation, and how the Finite State Machine (FSM) eliminates roll-call vote inversion and attribution drift.

https://github.com/user-attachments/assets/tutorial_04_playbooks_and_healing_v1
*(Local video track: [docs/videos/tutorial_04_playbooks_and_healing_v1.mp4](docs/videos/tutorial_04_playbooks_and_healing_v1.mp4))*

### Step-by-Step Instructions:

#### 1. Inspect Available Playbooks
```bash
python3 cli.py playbooks
```

| Playbook | Context | Distinct Speaker Roles |
| :--- | :--- | :--- |
| `gaming_videos` | Esports & Gaming | Streamer, Teammate, Opponent, Caster, System |
| `municipal_meetings` | Civic Hearings | Chair, Member, Public Speaker (Roll-Call FSM active) |
| `interview_podcast` | Panel discussions | Host, Co-host, Guest conversational turn-taking |
| `corporate_meeting` | Executive reviews | Action items, agenda transitions, executive summaries |
| `academic_lecture` | Technical lectures | Lecturer, Slide cue detection, Q&A blocks |
| `general_speech` | General audio | Domain-agnostic acoustic clustering baseline |

#### 2. Roll-Call Inversion Elimination
During roll-call votes, when a Chair calls a name ("Tyler?"), standard ASR often erroneously attributes the turn to Member Tyler. Universal Transcriber's 3-state FSM (`IDLE` → `CALLING` → `AWAITING_VOTE`) guarantees that:
- The member's name remains attributed to the Chair's turn.
- The single-word vote ("Aye", "Yes", "Present") is attributed to the responding member.

#### 3. Validate Custom Playbooks
```bash
python3 cli.py playbooks --validate custom_playbook.json
```

---

## Tutorial 5: Persistent Transcription Audit Log & Catalog Idempotency

This video tutorial explores the persistent SQLite and JSONL audit stores, tracking consumed versus unused transcripts, and automating YouTube channel crawlers with duplicate avoidance.

https://github.com/user-attachments/assets/tutorial_05_audit_and_catalog_v1
*(Local video track: [docs/videos/tutorial_05_audit_and_catalog_v1.mp4](docs/videos/tutorial_05_audit_and_catalog_v1.mp4))*

### Step-by-Step Instructions:

#### 1. Inspect Persistent Audit Trail
```bash
# Display summary metrics and recent transcription attempts:
python3 cli.py audit

# Filter to only unused / discarded transcripts:
python3 cli.py audit --unused

# Mark a specific job ID as used / consumed:
python3 cli.py audit --mark-used job_d28c1efe
```

#### 2. Crawl YouTube Channels with Idempotency
```bash
# Ingest up to 5 new videos from a channel (skips previously completed items):
python3 cli.py catalog "https://www.youtube.com/@CityOfCohasset/videos" --limit 5

# Preview discovered items without downloading (Dry Run):
python3 cli.py catalog "https://www.youtube.com/@CityOfCohasset/videos" --dry-run

# Check catalog statistics:
python3 cli.py catalog-status
```

#### 3. Dispatch Transcripts via Email
```bash
python3 cli.py email --target ohheysean@gmail.com --count 3
```

---

## Supported Containers & Optimization Reference

| Container | Codec / Layout | Ingestion Optimization |
| :--- | :--- | :--- |
| **`.m4a`** | AAC / ALAC | Direct audio demuxing, `ffprobe` tag extraction |
| **`.mp3`** | MPEG-1 Layer III | ID3v2 header metadata preservation |
| **`.mp4`** | H.264/HEVC + AAC | **Video bypassing (`-vn`)**, `0:a:0` primary audio downmix |
| **`.mov`** | ProRes/H.264 + LPCM | QuickTime audio stream isolation with `-vn` |
| **`.mkv`** | Matroska (Multi-track) | Multi-channel downmixing (5.1/7.1 to 16 kHz mono) |
| **`.wav`** | Uncompressed PCM | Single-pass memory-mapped chunking |
| **`.flac`** | Free Lossless Audio | Native lossless decompression |
| **`.aac`** | Advanced Audio Coding | ADTS elementary stream demuxing |
| **`.ogg` / `.opus`**| Ogg Vorbis / Opus | Low-latency voice packet decoding |

---

## Storage Directories & File Hygiene

All data is organized cleanly within your user environment:

- `~/Documents/Transcripts/YYYYMMDD_<Title>/` — ISO-8601 job output folder (6 formats).
- `~/Documents/Transcripts/uploads/` — Staging directory for drag-and-drop media files.
- `~/Documents/Transcripts/transcriptions_audit_v1.sqlite` — Persistent SQLite audit index.
- `~/Documents/Transcripts/transcriptions_audit_v1.jsonl` — Append-only JSON Lines event ledger.
- `~/Documents/Transcripts/media_catalog_v1.sqlite` — Idempotent channel crawler index.
- `~/Documents/Transcripts/speakers_db_v2.json` — Persistent acoustic speaker profiles and voice centroids.
- `~/.cache/universal_transcriber/models/` — GGML Whisper model binaries.
- `~/.cache/universal_transcriber/web_server.log` — Background web server execution log.
