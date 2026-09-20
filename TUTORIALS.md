# 🎙️ Universal Transcriber • Comprehensive Operational Tutorial & Video Guide
<!-- Canonical tutorials manual linking to TUTORIALS_v1.md -->

**Universal Transcriber** is an autonomous speech transcription, acoustic speaker diarization, and self-healing dialogue formatting platform engineered natively for macOS and Apple Silicon Metal GPUs.

Version: **`0.1-beta`** (`v0.1.0-beta`)  
Engineered by: **Sean Tyler ([@seanbuilds](https://github.com/seanbuilds))**  
Repository: [https://github.com/seanbuilds/universal-transcriber](https://github.com/seanbuilds/universal-transcriber)  
License: **MIT License** (`LICENSE`)

---

## 📑 Tutorial Index

1. [Tutorial 1: Turnkey Automated Installation & 1-Click Launch](#tutorial-1-turnkey-automated-installation--1-click-launch)
2. [Tutorial 2: Local Media Drag-and-Drop Dropzone & Video Bypassing](#tutorial-2-local-media-drag-and-drop-dropzone--video-bypassing)
3. [Tutorial 3: Unified Command-Line Interface & Directory Batching](#tutorial-3-unified-command-line-interface--directory-batching)
4. [Tutorial 4: Domain Playbooks & Finite State Machine Speaker Healing](#tutorial-4-domain-playbooks--finite-state-machine-speaker-healing)
5. [Tutorial 5: Persistent Transcription Audit Log & Catalog Idempotency](#tutorial-5-persistent-transcription-audit-log--catalog-idempotency)
6. [Supported Media Containers & Audio Formats](#supported-media-containers--audio-formats)
7. [Directory Structure & File Conventions](#directory-structure--file-conventions)

---

## Tutorial 1: Turnkey Automated Installation & 1-Click Launch

Setting up Universal Transcriber on Apple Silicon is fully turnkey. The automated installer inspects your hardware, installs missing tools, fetches speech models, and verifies Metal GPU acceleration.

### Step 1: Run the Automated Installer
```bash
./install.sh
```

**What the installer does:**
1. **Hardware Inspection:** Confirms macOS architecture is `arm64` (Apple Silicon M1/M2/M3/M4).
2. **System Dependencies:** Checks and installs Homebrew tools (`ffmpeg`, `yt-dlp`, `whisper-cpp`).
3. **Python 3 Environment:** Identifies your Python 3.12+ runtime (e.g., Python 3.14).
4. **Python Dependencies:** Automatically installs packages from `requirements.txt` (`flask`, `flask-cors`, `jsonschema`, `python-docx`, `requests`, `pillow`, `numpy`, `scipy`).
5. **Speech Models:** Automatically downloads GGML Whisper models to `~/.cache/universal_transcriber/models/` (`ggml-base.en.bin` and `ggml-small.en.bin`) directly from Hugging Face with progress indicators.
6. **Metal Validation:** Runs a pre-flight probe through `whisper-cli` to verify active Metal GPU acceleration (`MTL0`).

```bash
# Check current environment without making changes:
./install.sh --check-only
```

### Step 2: 1-Click Startup
```bash
./start_app.sh
```
This script verifies system utilities, starts canonical `app.py` in the background, waits for the web server to bind to port 5055, and automatically opens **`http://127.0.0.1:5055`** in your default browser.

---

## Tutorial 2: Local Media Drag-and-Drop Dropzone & Video Bypassing

Universal Transcriber provides first-class support for local audio and video files without requiring external conversion tools.

### Key Capabilities:
- **Comprehensive Container Support:** Accepts `.m4a`, `.mp3`, `.mp4`, `.mov`, `.mkv`, `.wav`, `.flac`, `.aac`, `.webm`, `.ogg`, and `.opus`.
- **Video Stream Bypassing (`-vn`):** For video containers (`.mp4`, `.mov`, `.mkv`), video frame decoding is completely bypassed, extracting pure 16 kHz mono PCM audio up to **5x faster**.
- **Container Metadata Extraction:** Probes track tags, duration, channel layout, and bitrate via `ffprobe`.

### Using the Web Dashboard:
1. Open the dashboard at `http://127.0.0.1:5055`.
2. Drag and drop any media file from Finder directly into the dashed dropzone area (or click to browse).
3. Notice the automatic file inspection pill displaying container format, duration, and file size.
4. Select a domain playbook (e.g. `interview_podcast` or `gaming_videos`).
5. Click **⚡ Transcribe**.
6. Monitor the real-time Server-Sent Events (SSE) telemetry pane showing incoming speech tokens and active speaker turns.
7. Click **🔄 Clear / Start Over** at any time to abort active streams, reset fields, and log cancellation to the audit trail.

---

## Tutorial 3: Unified Command-Line Interface & Directory Batching

The command-line interface provides high-throughput media transcription for scripts, automated pipelines, and batch operations.

### Transcribe a Single File
```bash
python3 cli.py local ~/Music/interview_ep42.m4a \
  --title "Interview_Ep42" \
  --playbook interview_podcast
```

### Batch Scan an Entire Directory
Scan a directory of recordings flat or recursively:
```bash
# Scan directory and all subdirectories
python3 cli.py local ~/Documents/Recordings/ \
  --recursive \
  --playbook corporate_meeting
```

### Transcribe a Remote YouTube Video
```bash
python3 cli.py transcribe "https://www.youtube.com/watch?v=..." \
  --title "City_Council_Hearing" \
  --playbook municipal_meetings
```

### Synchronized Atomic Exports (6 Formats)
Every completed job automatically creates an ISO-8601 folder (`~/Documents/Transcripts/YYYYMMDD_<Title>/`) containing:
- **`.md`**: GitHub-flavored Markdown formatted with speaker turns and headers.
- **`.txt`**: Clean verbatim plaintext for quick search and reading.
- **`.srt`**: SubRip subtitle caption track with standardized millisecond timecodes.
- **`.vtt`**: WebVTT caption file formatted with `<v Speaker>` voice tags for HTML5 players.
- **`.docx`**: Microsoft Word document styled with meeting metadata.
- **`.json`**: Structured Abstract Syntax Tree (AST) containing full segment tokens and speaker probabilities.

---

## Tutorial 4: Domain Playbooks & Finite State Machine Speaker Healing

Raw automatic speech recognition (ASR) frequently suffers from speaker attribution errors and stutter fragmentation. Universal Transcriber resolves this using domain playbooks and Finite State Machines (FSM).

### Built-in Validated Playbooks:

| Playbook | Target Context | Speaker Roles & Rules |
| :--- | :--- | :--- |
| `gaming_videos` | Esports, Let's Plays, Speedruns | Streamer, Teammate, Opponent, Caster, System banter |
| `municipal_meetings` | Select Boards, City Councils | Chair, Member, Public Speaker; Roll-Call FSM active |
| `interview_podcast` | Panel discussions & 1-on-1s | Host, Co-host, Guest conversational turn-taking |
| `corporate_meeting` | Standups, Board Syncs | Action items, agenda transitions, executive summaries |
| `academic_lecture` | University lectures, Tech talks | Lecturer, Slide cue detection, Q&A participant distinction |
| `general_speech` | General audio & podcasts | Domain-agnostic acoustic clustering baseline |

### Roll-Call Inversion Elimination (FSM)
In civic meetings, when a Chair calls a roll call ("Tyler?"), naive ASR often erroneously attributes the question to the member being called. Universal Transcriber's 3-state Roll-Call FSM locks member name invocations to the Chair's turn and attributes single-word votes ("Aye", "Yes", "Present") to the responding member, eliminating 100% of roll-call inversions.

### Validating Custom Playbooks
```bash
python3 cli.py playbooks --validate path/to/my_playbook.json
```

---

## Tutorial 5: Persistent Transcription Audit Log & Catalog Idempotency

### Persistent Audit Trail
Every transcription attempt—whether completed, failed, cancelled, or discarded without being downloaded—is permanently recorded in:
- SQLite Database: `~/Documents/Transcripts/transcriptions_audit_v1.sqlite`
- Append-Only JSONL: `~/Documents/Transcripts/transcriptions_audit_v1.jsonl`

```bash
# View summary and recent transcription records:
python3 cli.py audit

# List only unused/pending transcripts:
python3 cli.py audit --unused

# Mark a specific job as used:
python3 cli.py audit --mark-used job_d28c1efe
```

### Channel & RSS Feed Catalog Ingestion
Monitor YouTube channels or podcast feeds with built-in duplicate prevention:
```bash
# Scan a channel and transcribe up to 5 new items:
python3 cli.py catalog "https://www.youtube.com/@CityOfCohasset/videos" --limit 5

# Preview items without processing (Dry Run):
python3 cli.py catalog "https://www.youtube.com/@CityOfCohasset/videos" --dry-run

# Inspect catalog processing database:
python3 cli.py catalog-status
```

### Deliver Transcripts via Email
Dispatch transcripts directly to Sean Tyler via Apple Mail:
```bash
python3 cli.py email --target ohheysean@gmail.com --count 3
```

---

## Supported Media Containers & Audio Formats

| Container | Supported Codecs | Optimization |
| :--- | :--- | :--- |
| **`.m4a`** | AAC, ALAC | Direct audio demuxing, tag preservation |
| **`.mp3`** | MPEG-1 Audio Layer III | ID3v2 header metadata extraction |
| **`.mp4`** | H.264 / HEVC + AAC | Video stream bypassed (`-vn`), primary audio extracted |
| **`.mov`** | ProRes / H.264 + LPCM | QuickTime audio track isolated |
| **`.mkv`** | Matroska (Multi-track) | Multi-channel downmixed to 16 kHz mono WAV |
| **`.wav`** | Uncompressed PCM | Single-pass memory-mapped chunking |
| **`.flac`** | Free Lossless Audio Codec | Native lossless decompression |
| **`.aac`** | Advanced Audio Coding | ADTS elementary stream demuxing |
| **`.ogg` / `.opus`** | Ogg Vorbis / Opus | Low-latency voice packet decoding |

---

## Directory Structure & File Conventions

All user data is stored locally in standard macOS locations:

```
~/Documents/Transcripts/
├── 20260920_Interview_Ep42/        ← ISO-8601 job output folder
│   ├── 20260920_Interview_Ep42.md  ← Markdown transcript
│   ├── 20260920_Interview_Ep42.txt ← Plaintext transcript
│   ├── 20260920_Interview_Ep42.srt ← SubRip subtitle track
│   ├── 20260920_Interview_Ep42.vtt ← WebVTT subtitle track
│   ├── 20260920_Interview_Ep42.docx← Microsoft Word document
│   └── 20260920_Interview_Ep42.json← AST tokens and speaker turns
├── uploads/                        ← Staging area for drag-and-drop files
├── transcriptions_audit_v1.sqlite  ← Persistent SQLite audit database
├── transcriptions_audit_v1.jsonl   ← Append-only audit event ledger
├── media_catalog_v1.sqlite        ← Idempotent channel crawler index
└── speakers_db_v2.json             ← Acoustic speaker profiles & centroids
```
