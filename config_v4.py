"""Configuration settings for Universal Transcriber (v4).
<!-- v4 – Audit persistence paths, ISO date naming conventions, and domain playbook extensions -->
"""

import os
import multiprocessing
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).parent.resolve()
PLAYBOOKS_DIR = BASE_DIR / "playbooks"
PLAYBOOK_SCHEMA_PATH = PLAYBOOKS_DIR / "schema_v1.json"
SRC_DIR = BASE_DIR / "src"

# Default User Transcripts Directory (macOS standard)
TRANSCRIPTS_DIR = Path.home() / "Documents" / "Transcripts"
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

# User-scoped Cache Directory
CACHE_DIR = Path.home() / ".cache" / "universal_transcriber"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR = CACHE_DIR / "jobs"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Persistent Databases & Audit Stores
SPEAKERS_DB_PATH = TRANSCRIPTS_DIR / "speakers_db_v2.json"
QUEUE_DB_PATH = TRANSCRIPTS_DIR / "pipeline_queue_v1.sqlite"
CATALOG_DB_PATH = TRANSCRIPTS_DIR / "media_catalog_v1.sqlite"
AUDIT_DB_PATH = TRANSCRIPTS_DIR / "transcriptions_audit_v1.sqlite"
AUDIT_LOG_JSONL_PATH = TRANSCRIPTS_DIR / "transcriptions_audit_v1.jsonl"

# Audio Settings
SAMPLE_RATE = 16000
CHANNELS = 1
AUDIO_FORMAT = "pcm_s16le"

# Adaptive Timeout Limits
MIN_TRANSCRIBE_TIMEOUT_SECONDS = 1800  # 30 minutes minimum
TIMEOUT_MULTIPLIER = 0.4               # 40% of audio duration added to base timeout
MAX_DOWNLOAD_TIMEOUT_SECONDS = 3600    # 1 hour max download for large media streams

# Streaming ASR Parameters
STREAMING_CHUNK_SECONDS = 30.0         # 30-second sliding window
STREAMING_OVERLAP_SECONDS = 2.0        # 2-second overlap compensation

# Hardware / Threading
CPU_COUNT = multiprocessing.cpu_count()
RECOMMENDED_THREADS = max(4, min(CPU_COUNT - 2, 10))  # Apple Silicon performance core distribution

# Default Whisper Model Candidates (ordered by preference)
WHISPER_MODEL_CANDIDATES = [
    CACHE_DIR / "models/ggml-small.en.bin",
    CACHE_DIR / "models/ggml-base.en.bin",
    CACHE_DIR / "models/ggml-small.en-q5_1.bin",
    CACHE_DIR / "models/ggml-medium.en.bin",
    Path.home() / "COUNCIL/models/ggml-small.en-q5_1.bin",
    Path.home() / "COUNCIL/models/ggml-medium.en-q5_0.bin",
    Path.home() / "models/ggml-small.en.bin",
    Path.home() / "models/ggml-base.en.bin",
    Path.home() / ".cache/whisper/ggml-small.en.bin",
    Path("/opt/homebrew/share/whisper-cpp/models/ggml-small.en.bin"),
    Path("/opt/homebrew/share/whisper-cpp/models/ggml-base.en.bin"),
]

# Web Server & Telemetry Settings
WEB_HOST = "127.0.0.1"
WEB_PORT = 5055
ALLOWED_CORS_ORIGINS = [
    "http://127.0.0.1:5055",
    "http://localhost:5055"
]

# Default Playbook
DEFAULT_PLAYBOOK = "general_speech"
