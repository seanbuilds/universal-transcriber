# Universal Transcriber • Installation & Setup Guide
<!-- Canonical installation guide linking to INSTALL_v1.md -->

**Universal Transcriber** is an autonomous speech transcription, acoustic speaker diarization, and self-healing dialogue formatting platform engineered for macOS and Apple Silicon Metal GPUs.

Version: **`0.1-beta`** (`v0.1.0-beta`)  
Engineered by: **Sean Tyler ([@seanbuilds](https://github.com/seanbuilds))**  
Contact: `ohheysean@gmail.com`

---

## 1. System Requirements

- **Operating System:** macOS Sonoma (14.0+) or macOS Sequoia (15.0+) recommended.
- **Hardware Architecture:** Apple Silicon (`arm64`: M1, M2, M3, M4 family) strongly recommended for native Metal GPU acceleration. (Intel x86_64 is supported in CPU fallback mode).
- **Disk Storage:** ~2 GB available for GGML Whisper models, temporary extraction buffers, and transcript exports.
- **Memory (RAM):** 8 GB minimum; 16 GB+ recommended for large audio processing batches.

---

## 2. Turnkey Automated Installation (Recommended)

Universal Transcriber provides a single-command automated installer that checks your hardware, installs required Homebrew utilities, configures Python dependencies, downloads speech models, and verifies Metal acceleration.

### Quick Start:

```bash
# 1. Clone or open the repository
git clone https://github.com/seanbuilds/universal-transcriber.git
cd universal-transcriber

# 2. Run the automated installer
./install.sh
```

### What `install.sh` Does Automatically:
1. **Hardware Verification:** Verifies Apple Silicon architecture (`arm64`) and active Metal GPU framework (`MTL0`).
2. **System Dependencies:** Verifies or installs Homebrew packages:
   - `ffmpeg` (audio/video demuxing, video stream bypass with `-vn`, 16 kHz PCM conversion)
   - `yt-dlp` (stream extraction for YouTube URLs, playlists, and RSS feeds)
   - `whisper-cpp` (provides `whisper-cli` with native Apple Silicon Metal GPU inference)
3. **Python Runtime:** Detects Python 3.12+ (or installs via Homebrew if absent).
4. **Python Dependencies:** Automatically installs:
   - `flask` & `flask-cors` (web server and SSE streaming telemetry)
   - `jsonschema` (strict JSON Schema v7 validation for domain playbooks)
   - `python-docx` (Microsoft Word transcript export)
   - `requests` (model retrieval and network operations)
   - `numpy` & `scipy` (acoustic diarization and Agglomerative Hierarchical Clustering)
5. **Whisper Speech Models:** Ensures the required GGML models are present in `~/.cache/universal_transcriber/models/`:
   - `ggml-base.en.bin` (~141 MB) — ultra-fast baseline
   - `ggml-small.en.bin` (~465 MB) — high-accuracy default
   *(Downloads directly from Hugging Face with progress indicator if not already cached).*
6. **Self-Check & GPU Test:** Runs a pre-flight probe through `whisper-cli` to verify Metal acceleration is active.

### Installer Flags:
```bash
# Check current environment without making changes or downloading
./install.sh --check-only

# Skip model downloads (if you already have GGML models in custom paths)
./install.sh --skip-models
```

---

## 3. Manual Installation (Step-by-Step Alternative)

If you prefer to configure your environment manually instead of running `install.sh`:

### Step 1: Install Homebrew Utilities
```bash
brew install ffmpeg yt-dlp whisper-cpp python@3.14
```

### Step 2: Set Up Python Dependencies
```bash
# Using existing Python 3 or virtual environment:
python3 -m pip install -r requirements.txt
```

### Step 3: Fetch Speech Models
```bash
mkdir -p ~/.cache/universal_transcriber/models

# Download ggml-base.en.bin
curl -L --progress-bar \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin \
  -o ~/.cache/universal_transcriber/models/ggml-base.en.bin

# Download ggml-small.en.bin
curl -L --progress-bar \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin \
  -o ~/.cache/universal_transcriber/models/ggml-small.en.bin
```

---

## 4. First-Run Verification

### 1. Verify CLI Version & Playbooks
```bash
python3 cli.py --version
# Expected: Universal Transcriber v0.1.0-beta (@seanbuilds)

python3 cli.py playbooks
# Displays validated domain playbooks (municipal_meetings, gaming_videos, etc.)
```

### 2. Verify Metal Hardware Acceleration
```bash
whisper-cli -h 2>&1 | grep -i "GPU name:"
# Expected on Apple Silicon: ggml_metal_device_init: GPU name: MTL0 (Apple M...)
```

### 3. Launch Web Dashboard (1-Click)
```bash
./start_app.sh
```
This boots the local web daemon in the background and opens `http://127.0.0.1:5055` in your default browser.

---

## 5. Storage Directories & Paths

By default, Universal Transcriber organizes all outputs and caches according to macOS filesystem conventions:

| Location | Purpose |
| :--- | :--- |
| `~/Documents/Transcripts/` | Root output directory for completed transcripts |
| `~/Documents/Transcripts/YYYYMMDD_<Title>/` | ISO-8601 job folder containing all 6 export formats |
| `~/Documents/Transcripts/uploads/` | Staging area for drag-and-drop local audio/video files |
| `~/Documents/Transcripts/transcriptions_audit_v1.sqlite` | Persistent SQLite audit database tracking every job |
| `~/Documents/Transcripts/transcriptions_audit_v1.jsonl` | Append-only JSONL event ledger |
| `~/Documents/Transcripts/speakers_db_v2.json` | Persistent acoustic speaker profiles & voice centroids |
| `~/.cache/universal_transcriber/models/` | GGML Whisper model binaries (`ggml-small.en.bin`, etc.) |
| `~/.cache/universal_transcriber/web_server.log` | Background web server log output |

---

## 6. Troubleshooting & FAQs

### Port 5055 is Already in Use
If port 5055 is occupied by an earlier server process:
```bash
# Check what is using port 5055
lsof -i :5055

# Terminate existing instance
pkill -f "app.py" || pkill -f "app_v5.py"
```

### Whisper Model Fallback
If `ggml-small.en.bin` is missing, the engine automatically checks for `ggml-base.en.bin` or downloads the missing model on demand, logging the action to the terminal.

### Video Files Taking Long to Ingest
Universal Transcriber's ingestion engine passes `-vn` directly to `ffmpeg`, completely bypassing video decompression for container formats like `.mp4`, `.mov`, and `.mkv`. Extraction to 16 kHz mono WAV is typically completed within seconds.

---

## 7. Uninstallation

To remove Universal Transcriber:
```bash
# Remove cache and downloaded models (~1.5 GB)
rm -rf ~/.cache/universal_transcriber

# (Optional) Remove saved transcripts and audit databases
# rm -rf ~/Documents/Transcripts

# Remove the project repository folder
rm -rf /path/to/universal-transcriber
```
