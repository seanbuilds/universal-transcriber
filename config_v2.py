"""Configuration settings for Universal Transcriber (v2).
<!-- v2 – Hardened paths, adaptive timeouts, security constraints, and SQLite queue configuration -->
"""

import os
import multiprocessing
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).parent.resolve()
PLAYBOOKS_DIR = BASE_DIR / "playbooks"
SRC_DIR = BASE_DIR / "src"

# Default User Transcripts Directory (macOS standard)
TRANSCRIPTS_DIR = Path.home() / "Documents" / "Transcripts"
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

# User-scoped Cache Directory (avoids shared /tmp risks)
CACHE_DIR = Path.home() / ".cache" / "universal_transcriber"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR = CACHE_DIR / "jobs"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Persistent Databases
SPEAKERS_DB_PATH = TRANSCRIPTS_DIR / "speakers_db_v2.json"
QUEUE_DB_PATH = TRANSCRIPTS_DIR / "pipeline_queue_v1.sqlite"

# Audio Settings
SAMPLE_RATE = 16000
CHANNELS = 1
AUDIO_FORMAT = "pcm_s16le"

# Adaptive Timeout Limits
MIN_TRANSCRIBE_TIMEOUT_SECONDS = 1800  # 30 minutes minimum
TIMEOUT_MULTIPLIER = 0.4               # 40% of audio duration added to base timeout
MAX_DOWNLOAD_TIMEOUT_SECONDS = 3600    # 1 hour max download for 4h+ high-def video streams

# Hardware / Threading
CPU_COUNT = multiprocessing.cpu_count()
RECOMMENDED_THREADS = max(4, min(CPU_COUNT - 2, 10))  # Balances P-cores on Apple Silicon

# Default Whisper Model Candidates (ordered by preference)
WHISPER_MODEL_CANDIDATES = [
    Path.home() / "COUNCIL/models/ggml-small.en-q5_1.bin",
    Path.home() / "COUNCIL/models/ggml-medium.en-q5_0.bin",
    CACHE_DIR / "models/ggml-small.en-q5_1.bin",
    Path.home() / "models/ggml-small.en-q5_1.bin",
    Path.home() / "models/ggml-medium.en-q5_0.bin",
    Path.home() / ".cache/whisper/ggml-small.en.bin",
    Path("/opt/homebrew/share/whisper-cpp/models/ggml-small.en.bin"),
    Path("/opt/homebrew/share/whisper-cpp/models/ggml-medium.en.bin"),
]

# Web Server & Security Settings
WEB_HOST = "127.0.0.1"
WEB_PORT = 5055
ALLOWED_CORS_ORIGINS = [
    "http://127.0.0.1:5055",
    "http://localhost:5055"
]

# Default Playbook
DEFAULT_PLAYBOOK = "general_speech"
