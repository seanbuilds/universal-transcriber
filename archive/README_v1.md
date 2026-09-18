# 🎙️ Universal Transcriber

**High-Performance Audio & Video Transcription Engine for macOS (Apple Silicon)**

Universal Transcriber is an autonomous, domain-agnostic media transcription suite built for Apple Silicon Macs. It extracts audio from YouTube (single videos, playlists, or channels) and local media files, transcribes speech at up to **28x real-time speed** using Apple's Metal GPU, clusters speaker voices persistently across recordings, and heals fragmented speech into natural conversational paragraphs.

Domain-specific conversational patterns—such as parliamentary roll calls, podcast Q&A, corporate status updates, and university lectures—are handled cleanly via modular **Playbooks**.

---

## Key Features

- **Universal Input Ingestion**: Supports YouTube URLs, full playlists, channels, or local media files (`.mp4`, `.mov`, `.mkv`, `.m4a`, `.wav`, `.mp3`).
- **Apple Silicon Metal GPU**: Utilizes `whisper-cli` or `mlx-whisper` on your M-series GPU for fast, private, offline transcription.
- **Persistent Speaker Profiles**: Cross-session voice fingerprinting (`speakers_db_v1.json`). Name a speaker once and they are recognized automatically in subsequent sessions.
- **Self-Healing Turn Coalescing**: Solves Whisper's fragmentation problem by merging short 2–3 second utterances into cohesive paragraphs and removing sliding-window overlap stutters.
- **Modular Playbook System**: Pluggable domain intelligence rules for municipal hearings, podcasts, corporate meetings, and lectures.
- **Multi-Format Export**: Generates synchronized Markdown (`.md`), Plaintext (`.txt`), Subtitles (`.srt`), and structured JSON (`.json`) into `~/Documents/Transcripts/`.
- **Dual Interfaces**: Full-featured command-line interface (`cli_v1.py`) plus a local glassmorphic web dashboard (`app_v1.py`).

---

## Quick Start

### 1. Requirements
Ensure standard local command-line tools are available:
```bash
brew install whisper-cpp ffmpeg
pip3 install yt-dlp flask flask-cors
```

### 2. Command-Line Usage

#### Transcribe a Video or Local File
```bash
# General speech (default)
python3 cli_v1.py transcribe "https://www.youtube.com/watch?v=..."

# Using a domain playbook
python3 cli_v1.py transcribe "https://www.youtube.com/watch?v=..." --playbook municipal_meetings

# Local video file
python3 cli_v1.py transcribe "/Users/dad/Downloads/meeting_recording.mp4" --playbook corporate_meeting
```

#### List Available Playbooks
```bash
python3 cli_v1.py playbooks
```

#### Manage Persistent Speaker Profiles
```bash
# View all recognized speaker profiles
python3 cli_v1.py speakers

# Rename a detected speaker profile
python3 cli_v1.py speakers --rename Speaker_A "Craig MacLellan"
```

### 3. Web Interface

Start the local web dashboard:
```bash
python3 app_v1.py
# → Open http://127.0.0.1:5055 in your browser
```
From the web UI, you can paste URLs or local paths, choose a domain playbook, watch live progress, and view or download completed transcripts.

---

## Playbook Ecosystem

Playbooks define conversational rules, speaker roles, and vocabulary cues:

| Playbook | Purpose | Key Heuristics |
| :--- | :--- | :--- |
| **`general_speech`** | Default for any general audio | Domain-agnostic turn coalescing and voice clustering. |
| **`municipal_meetings`** | City Councils, Select Boards, School Committees | Parliamentary procedure, roll calls, motions ("So moved", "Second"), Chair yields, committee rosters. |
| **`interview_podcast`** | 1-on-1 and panel podcasts, journalistic interviews | Host vs. Guest roles, Q&A cadence, introductions, and wrap-ups. |
| **`corporate_meeting`** | Standups, executive reviews, cross-functional syncs | Meeting leader attribution, status updates, blockers, and next steps. |
| **`academic_lecture`** | University lectures, keynotes, webinars | Primary lecturer presentation sections vs. student/audience Q&A. |

### Adding a Custom Playbook
Create a new JSON file in `playbooks/<name>_v1.json`:
```json
{
  "name": "legal_deposition",
  "version": "v1",
  "description": "Court depositions and legal hearings",
  "default_role": "Attorney",
  "roles": ["Attorney", "Witness", "Court Reporter", "Judge"],
  "cues": {
    "attorney": ["state your name", "objection", "let the record reflect"],
    "witness": ["to the best of my recollection", "i do", "yes sir"],
    "judge": ["overruled", "sustained", "approach the bench"]
  }
}
```

---

## Output Structure

Every completed transcription creates a timestamped folder under `~/Documents/Transcripts/`:

```
~/Documents/Transcripts/
└── 2026-07-29_Cohasset_School_Committee_Meeting/
    ├── 2026-07-29_Cohasset_School_Committee_Meeting.md    # Markdown with headers & speaker turns
    ├── 2026-07-29_Cohasset_School_Committee_Meeting.txt   # Clean plaintext verbatim transcript
    ├── 2026-07-29_Cohasset_School_Committee_Meeting.srt   # Timecoded SubRip subtitles
    └── 2026-07-29_Cohasset_School_Committee_Meeting.json  # Segment metadata & timestamps
```

---

## Verification & Tests

Run the full automated test suite:
```bash
python3 -m unittest discover -s tests -p "test_*_v1.py"
```

---

## Architecture

```
joyful-davinci/
├── config_v1.py             # Configuration (paths, models, audio specs)
├── cli_v1.py                # Command-line interface
├── app_v1.py                # Web server & API
├── playbooks/               # Domain playbook definitions
│   ├── general_speech_v1.json
│   ├── municipal_meetings_v1.json
│   ├── interview_podcast_v1.json
│   ├── corporate_meeting_v1.json
│   └── academic_lecture_v1.json
├── src/
│   ├── engine/
│   │   ├── ingest_v1.py     # yt-dlp + ffmpeg media extraction
│   │   ├── transcribe_v1.py # Metal GPU Whisper engine
│   │   ├── diarize_v1.py    # Persistent voice vector clustering
│   │   ├── healer_v1.py     # Self-healing turn coalescer & deduplicator
│   │   ├── export_v1.py     # Markdown, TXT, SRT, JSON exporters
│   │   └── pipeline_v1.py   # Master pipeline orchestrator
│   └── playbooks/
│       └── loader_v1.py     # Dynamic playbook parser & matcher
└── tests/                   # Automated unit test suite
```
