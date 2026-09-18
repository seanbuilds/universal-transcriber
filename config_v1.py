"""Configuration settings for Universal Transcriber (v1)."""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).parent.resolve()
PLAYBOOKS_DIR = BASE_DIR / "playbooks"
SRC_DIR = BASE_DIR / "src"

# Default User Transcripts Directory (macOS standard)
TRANSCRIPTS_DIR = Path.home() / "Documents" / "Transcripts"
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

# Temporary Processing Directory
TEMP_DIR = Path("/tmp/universal_transcriber")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Persistent Speaker Database
SPEAKERS_DB_PATH = BASE_DIR / "speakers_db_v1.json"

# Audio Settings
SAMPLE_RATE = 16000
CHANNELS = 1
AUDIO_FORMAT = "pcm_s16le"

# Default Whisper Model Candidates (ordered by preference)
WHISPER_MODEL_CANDIDATES = [
    Path.home() / "COUNCIL/models/ggml-small.en-q5_1.bin",
    Path.home() / "COUNCIL/models/ggml-medium.en-q5_0.bin",
    Path.home() / "models/ggml-small.en-q5_1.bin",
    Path.home() / "models/ggml-medium.en-q5_0.bin",
    Path.home() / ".cache/whisper/ggml-small.en.bin",
    Path("/opt/homebrew/share/whisper-cpp/models/ggml-small.en.bin"),
    Path("/opt/homebrew/share/whisper-cpp/models/ggml-medium.en.bin"),
]

# Web Server Settings
WEB_HOST = "127.0.0.1"
WEB_PORT = 5055

# Default Playbook
DEFAULT_PLAYBOOK = "general_speech"
