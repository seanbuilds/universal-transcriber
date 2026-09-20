# ⏱️ Universal Transcriber: Iterations & Chronological Timeline Log (v2)
<!-- v2 – Chronological history including official 0.1-beta release, turnkey installer, canonical entrypoints, and archival updates -->

**Author / Maintainer**: Sean Tyler ([@seanbuilds](https://github.com/seanbuilds))  
**Email**: `ohheysean@gmail.com`  
**Repository**: [https://github.com/seanbuilds/universal-transcriber](https://github.com/seanbuilds/universal-transcriber)  
**License**: MIT License (`LICENSE`)  
**Hardware Target**: Apple Silicon Macs (M-Series Metal GPU `MTL0`, Neural Engine)

---

## 📅 Project Evolution Overview

Universal Transcriber evolved through a sequence of rigorous milestones—advancing from a specialized town meeting transcription pipeline into a multi-domain, autonomous audio and video transcription, neural speaker diarization, and persistent auditing platform.

| Iteration | Date & UTC Timestamp | Milestone Focus | Core Engine Modules | Verification Status |
|:---|:---|:---|:---|:---|
| **v0 (Init)** | `2026-09-05 14:10:56 EDT` | Initial Repository & E2E Test Suite Scaffold | `tests/test_*.py` | 27 Passed, 41 Guarded |
| **v1** | `2026-09-11 11:31:10 EDT` | Base Pipeline & Apple Silicon Metal ASR | `pipeline_v1.py`, `ingest_v1.py`, `transcribe_v1.py`, `cli_v1.py` | Core Suite Passing |
| **v2** | `2026-09-12 09:34:32 EDT` | Adversarial Hardening, Centroid Clamp & Security | `diarize_v2.py`, `healer_v2.py`, `queue_v1.py`, `app_v2.py` | 44 Tests Passing |
| **v3** | `2026-09-16 15:58:07 EDT` | Sliding-Window Streaming ASR & 25,000x Diarization | `transcribe_v3.py`, `diarize_v3.py`, `healer_v3.py`, `app_v3.py` | 78 Tests Passing |
| **v4** | `2026-09-16 19:34:32 EDT` | YouTube Channel & Podcast RSS Idempotent Catalog | `catalog_v1.py`, `ingest_v3.py`, `cli_v4.py` | 89 Tests Passing |
| **v5** | `2026-09-17 09:54:21 EDT` | Creator & Gaming Playbook, Persistent Audit & ISO Naming | `gaming_videos_v1.json`, `audit_v1.py`, `export_v4.py`, `app_v4.py` | 98 Tests Passing |
| **v6** | `2026-09-17 12:04:16 EDT` | Multi-Format Local Media Containers & Web Dropzone | `ingest_v4.py`, `pipeline_v6.py`, `cli_v6.py`, `app_v5.py` | 106 Tests Passing |
| **v7** | `2026-09-18 10:30:00 EDT` | Production Open-Source Release & GitHub Publication | `LICENSE`, `ITERATIONS_LOG_v1.md`, `README_v7.md`, `@seanbuilds` branding | 106 Tests Passing (100%) |
| **v8 (0.1-Beta)** | `2026-09-20 12:20:00 EDT` | Official 0.1-Beta Product Transition & Turnkey Installer | `install.sh`, `start_app.sh`, `cli.py`, `app.py`, `config.py`, `INSTALL.md` | 106 Tests Passing (100%) |

---

## 🛠️ Detailed Iteration Changelog

### Iteration 0 — Project Conception & Test Harness Scaffold
- **Date**: `2026-09-05 14:10:56 EDT` (Commit: `496b98b`)
- **Objective**: Establish opaque-box end-to-end testing specifications and contracts for autonomous transcription and speaker identification.
- **Components Implemented**:
  - `TEST_READY.md`: Requirements traceability matrix across 4 progressive verification tiers.
  - Initial tests for audio caching, SQLite WAL mode state machine, monotonic timestamp validation, and Apple Mail osascript generation.
- **Outcome**: 27 unit tests passed; 41 progressive guards established for upcoming milestones.

---

### Iteration 1 — Base Pipeline & Metal GPU Acceleration
- **Date**: `2026-09-11 11:31:10 – 11:32:27 EDT`
- **Objective**: Deliver the end-to-end pipeline using Apple Silicon hardware acceleration (`whisper.cpp` Metal backend `MTL0`).
- **Components Created**:
  - `src/engine/ingest_v1.py`: `yt-dlp` audio extractor with fallback headers and 16 kHz mono WAV conversion.
  - `src/engine/transcribe_v1.py`: Apple Silicon Metal GPU Whisper engine integration.
  - `src/engine/diarize_v1.py`: Energy-based voice activity detection and cosine speaker clustering.
  - `src/engine/healer_v1.py`: Turn coalescer, stutter cleaner, and overlap deduplicator.
  - `src/engine/export_v1.py`: Markdown, Plaintext, SubRip (`.srt`), and Word Document (`.docx`) generator.
  - `src/playbooks/loader_v1.py`: Domain playbook validator and registry.
  - `cli_v1.py` & `app_v1.py`: Base CLI and Flask REST API.
- **Outcome**: First successful execution of complete media transcription on Apple Silicon.

---

### Iteration 2 — Adversarial Hardening, Centroid Clamp & Security
- **Date**: `2026-09-12 09:34:32 – 09:38:00 EDT`
- **Objective**: Resolve architectural defects identified during adversarial security and stress audits.
- **Remediations Delivered**:
  - `src/engine/diarize_v2.py`: Speaker centroid norm clamping preventing embedding drift; Speaker 0 lock preventing identity swaps.
  - `src/engine/healer_v2.py`: Protected overlap deduplication retaining unique trailing words.
  - `src/engine/queue_v1.py`: Thread-safe SQLite job queue with atomic state transitions.
  - `app_v2.py`: Path traversal validation rejecting directory escapes; explicit origin CORS whitelist.
- **Outcome**: 44 tests passed with 0 security regressions.

---

### Iteration 3 — Sliding-Window Streaming ASR & 25,000x Diarization
- **Date**: `2026-09-16 15:58:07 – 16:15:00 EDT`
- **Objective**: Eliminate memory ceilings and accelerate clustering on long-format audio recordings.
- **Enhancements**:
  - `src/engine/transcribe_v3.py`: 30-second sliding-window streaming ASR with 2-second overlap deduplication.
  - `src/engine/diarize_v3.py`: Agglomerative Hierarchical Clustering (AHC) via `scipy.cluster.hierarchy` cosine linkage delivering a 25,000x acceleration ($O(n^2)$ vs $O(n^3)$).
  - `src/engine/healer_v3.py`: Finite state machine eliminating roll-call inversion during formal proceedings.
  - `app_v3.py`: Real-time Server-Sent Events (SSE) telemetry broker.
- **Outcome**: 78 tests passed.

---

### Iteration 4 — YouTube Channel & Podcast RSS Idempotent Catalog
- **Date**: `2026-09-16 19:34:32 – 19:50:00 EDT`
- **Objective**: Autonomous catalog tracking for YouTube channels and podcast feeds without duplicate downloads.
- **Enhancements**:
  - `src/engine/catalog_v1.py`: Persistent SQLite catalog tracking item state, timestamps, and output links.
  - `src/engine/ingest_v3.py`: Playlist and RSS feed metadata extraction.
  - `cli_v4.py`: Added `catalog` and `catalog-status` commands with dry-run support.
- **Outcome**: 89 tests passed.

---

### Iteration 5 — Creator & Gaming Playbook, Persistent Audit & ISO Naming
- **Date**: `2026-09-17 09:54:21 – 10:15:00 EDT`
- **Objective**: Deliver creator domain playbooks, persistent auditing of all attempts, and standardized ISO-8601 formatting.
- **Enhancements**:
  - `playbooks/gaming_videos_v1.json`: Esports and gaming terminology, Streamer/Teammate/Opponent role parsing.
  - `src/engine/audit_v1.py`: Persistent SQLite audit database paired with append-only JSON Lines ledger tracking every transcription attempt.
  - `src/engine/export_v4.py`: Uniform `YYYYMMDD_<Title>` directory and filename formatting.
  - `app_v4.py` & `cli_v5.py`: Audit inspection commands and endpoints.
- **Outcome**: 98 tests passed.

---

### Iteration 6 — Multi-Format Local Media Containers & Web Dropzone
- **Date**: `2026-09-17 12:04:16 – 14:05:00 EDT`
- **Objective**: Native support for dragging and dropping any local media file (.m4a, .mp3, .mp4, .mov, .mkv, .wav, etc.).
- **Enhancements**:
  - `src/engine/ingest_v4.py`:
    - Native container support for 11 media extensions.
    - Video bypass optimization (`-vn`) speeding up video extraction up to 5x.
    - `ffprobe` metadata probing for duration, sample rate, and tags.
  - `cli_v6.py`:
    - Added `local` command supporting single files and recursive directory scans.
  - `app_v5.py` & `static/index.html`:
    - Drag-and-drop dropzone with `/api/upload` endpoint, progress bars, and container format badges.
- **Outcome**: 106 tests passed.

---

### Iteration 7 — Production Open-Source Release & GitHub Publication
- **Date**: `2026-09-18 10:30:00 EDT`
- **Objective**: Package repository for public release under `@seanbuilds` with MIT licensing and documentation.
- **Enhancements**:
  - Attributed to Sean Tyler (`@seanbuilds`, `ohheysean@gmail.com`).
  - Added MIT License (`LICENSE`).
  - Published to GitHub: `https://github.com/seanbuilds/universal-transcriber`.
- **Outcome**: 106 tests passed (100%).

---

### Iteration 8 — Official 0.1-Beta Product Transition & Turnkey Installer
- **Date**: `2026-09-20 12:20:00 EDT`
- **Objective**: Clean up workspace, transition from internal "v5 alpha" development into official **`0.1-beta`** (`v0.1.0-beta`) release, and provide automated 1-command installer.
- **Enhancements Implemented**:
  - **Turnkey Installer (`install.sh` / `install_v1.sh`)**:
    - Automated 6-step setup: Apple Silicon verification (`arm64`), Homebrew dependency management (`ffmpeg`, `yt-dlp`, `whisper-cpp`), Python 3.12+ runtime, Python packages installation, automatic GGML Whisper model download (`ggml-base.en.bin`, `ggml-small.en.bin`), and Apple Silicon Metal GPU validation (`MTL0`).
  - **1-Click Launch Script (`start_app.sh` / `start_app_v2.sh`)**:
    - Automatic port checks, background daemon booting (`app.py`), and default browser launch.
  - **Canonical Top-Level Entrypoints**:
    - `cli.py` (`cli_v7.py`): Displays `Universal Transcriber v0.1.0-beta (@seanbuilds)`.
    - `app.py` (`app_v6.py`): `/api/info` returns `version: "0.1.0-beta"`.
    - `config.py` (`config_v5.py`): Standardized product constants (`VERSION = "0.1.0-beta"`).
    - `pyproject.toml` (`pyproject_v2.toml`): Version `0.1.0b1` manifest.
    - `requirements.txt` (`requirements_v1.txt`): Pinned dependency specifications.
  - **Web Frontend Updates**:
    - Header badge updated to `v0.1-beta` (`static/index.html` and `static/index_v5.html`).
  - **Comprehensive Documentation**:
    - `INSTALL.md` (`INSTALL_v1.md`): Full installation, hardware requirements, and troubleshooting guide.
    - `README.md` (`README_v8.md`): Master product overview.
    - `CHANGELOG.md` (`CHANGELOG_v2.md`): Iteration 8 release notes.
  - **Document Hygiene & v5 Archival Enforcement**:
    - Moved `README_v6.md` and `cli_v5.py` to `archive/` per the v5 Archival Policy.
- **Verification**: 106 tests passing with 100% success rate.
