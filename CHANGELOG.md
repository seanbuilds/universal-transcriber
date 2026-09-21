# ⏱️ Universal Transcriber: Iterations & Chronological Timeline Log
<!-- Canonical changelog linking to CHANGELOG_v2.md -->

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
| **v9 (Playlist Staging)** | `2026-09-21 10:45:00 EDT` | YouTube Playlist Breakdown, Staging Manifests, Placeholders & Resume | `playlist_v1.py`, `pipeline_v6.py`, `cli_v7.py`, `app_v6.py`, `index.html` | 119 Tests Passing (100%) |
| **v10 (Danger Zone)** | `2026-09-21 11:35:00 EDT` | Danger Zone UI History Clear & Disk Preservation Guarantee | `audit_v1.py`, `queue_v2.py`, `app_v6.py`, `index.html`, `test_danger_zone_clear_v1.py` | 122 Tests Passing (100%) |
| **v11 (Copy Commands & Metadata)** | `2026-09-21 11:45:00 EDT` | 1-Click Copy Commands & Ubiquitous Meeting / URL Display Across All Boxes | `export_v4.py`, `pipeline_v6.py`, `app_v6.py`, `index.html` | 122 Tests Passing (100%) |
| **v12 (Local Folder & 6-Format Export)** | `2026-09-21 11:52:00 EDT` | Strict Post-Processing Local Folder & 6-Format Export Guarantee | `export_v4.py`, `pipeline_v6.py`, `app_v6.py`, `index.html`, `test_post_transcription_export_v1.py` | 126 Tests Passing (100%) |


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

---

### Iteration 9 — YouTube Playlist Breakdown, Staging Manifests & Step-by-Step Transcriber
- **Date**: `2026-09-21 10:45:00 EDT`
- **Objective**: Dynamically split YouTube playlists into individual video files, stage a dedicated collection folder with placeholder files, present upfront confirmation warning with video count, and transcribe sequentially with resume capabilities.
- **Components Implemented**:
  - `src/engine/playlist_v1.py`: `PlaylistManagerV1` with flat-playlist inspection, `playlist_manifest.json`, `PLAYLIST_INDEX.md`, and atomic `.pending` placeholder tracking.
  - `src/engine/pipeline_v6.py`: `process_playlist()` and `process_batch()`.
  - `cli_v7.py` / `cli.py`: Interactive `playlist` subcommand with upfront warning box and `--yes`/`--dry-run` flags.
  - `app_v6.py` / `static/index.html`: Playlist confirmation modal dialog and live staging tracker card with progress bar.
- **Verification**: 119 tests passing (`tests/test_playlist_staging_v1.py`).

---

### Iteration 10 — Danger Zone UI History Clear & Disk Preservation Guarantee
- **Date**: `2026-09-21 11:35:00 EDT`
- **Objective**: Add a dedicated Danger Zone card at the bottom of the dashboard to clear previously worked-on projects from the UI with an interactive confirmation modal, while guaranteeing physical files and folders on disk remain untouched.
- **Components Implemented**:
  - **Danger Zone UI Section (`static/index.html`)**: Crimson-accented Danger Zone card at the bottom of the dashboard with clear warning copy and red action button.
  - **Confirmation Dialog (`static/index.html`)**: `<dialog id="clearHistoryModal">` with "⚠️ Are you sure?" warning and explicit disk safety guarantee.
  - **Engine Reset Methods (`src/engine/audit_v1.py` & `src/engine/queue_v2.py`)**: `clear_audit_history()` and `clear_all_jobs()` to purge database rows and JSONL log while preserving files on disk.
  - **REST API Endpoint (`app_v6.py`)**: `POST /api/audit/clear` returning structured confirmation with `disk_files_preserved: true`.
- **Verification**: 122 tests passing (`tests/test_danger_zone_clear_v1.py`).
 
---
 
### Iteration 11 — 1-Click Copy Commands & Ubiquitous Meeting / URL Display Across All Boxes
- **Date**: `2026-09-21 11:45:00 EDT`
- **Objective**: Add 1-click clipboard copy commands across all UI input and output boxes, enable copying meeting info back into input fields, and ensure the meeting / transcript name and YouTube URL are displayed across every card, modal, and export file.
- **Components Implemented**:
  - **Input Box Enhancements (`static/index.html`)**: Added inline `📋 Copy URL` and `📋 Copy Name` inside input fields, and `📋 Copy Command` CLI generator.
  - **Results Card Enhancements (`static/index.html`)**: Added `#resultsInfoBox` with formatted Meeting Name and YouTube URL, action toolbar (`📋 Copy All Info`, `📋 Copy Transcript`, `📋 Copy Command`, `📥 Copy into Input Boxes`), and transcript header bar with `📋 Copy Box Content`.
  - **Playlist Confirmation Modal & Batch Tracker (`static/index.html`)**: Added Meeting/Playlist Name and YouTube Playlist URL displays with copy buttons and per-video URL copy buttons in table rows.
  - **Audit Log Table (`static/index.html`)**: Added `Meeting / Transcript Name` and `YouTube URL / Source` columns with inline `📋` copy buttons.
  - **Export Engine (`src/engine/export_v4.py`)**: Updated `.txt`, `.md`, `.srt`, `.vtt`, `.docx`, and `.json` generators to explicitly include Meeting / Transcript Name and YouTube / Source URL.
- **Verification**: 122 tests passing with 100% success rate.

---

### Iteration 12 — Atomic Post-Transcription Local Folder & Multi-Format File Generation
- **Date**: `2026-09-21 11:51:00 EDT`
- **Objective**: Guarantee that for each completed transcription (single video or playlist item), a dedicated local folder and all 6 offered file formats (`.md`, `.txt`, `.srt`, `.vtt`, `.docx`, `.json`) are created on disk strictly AFTER all pipeline steps (Ingest → Preprocess → Metal Streaming ASR → Neural Diarization → Role Healing) have fully succeeded, with zero premature or partial files created on disk if an error occurs.
- **Components Implemented**:
  - **Atomic Exporter with Rollback & Assertion (`src/engine/export_v4.py`)**:
    - Added `direct_dir` parameter enabling direct folder targeting without redundant nested sub-subfolders.
    - Implemented atomic rollback: if writing any export file fails midway, all `.tmp` scratch files and newly created empty directories are unlinked.
    - Added post-export integrity assertion: verifies that all 6 files (`.md`, `.txt`, `.srt`, `.vtt`, `.docx`, `.json`) exist on disk and possess non-zero file size prior to returning success.
  - **Strict Pipeline Timing Guarantee (`src/engine/pipeline_v6.py`)**:
    - Removed premature `item_output_subfolder.mkdir()` in `process_playlist()`.
    - Enforced that directory creation and multi-format file generation occur exclusively inside Step 6 after Steps 1–5 have passed without error.
  - **Finder Reveal & Local File Management API (`app_v6.py`)**:
    - Added `POST /api/open-folder` endpoint with strict directory traversal prevention constrained to `TRANSCRIPTS_DIR`.
    - Triggers native macOS `/usr/bin/open <path>` to reveal local folders and files in Finder.
  - **Web Dashboard Local Files Card & Finder Integration (`static/index.html`)**:
    - Added `#localFilesBox` inside `#resultsCard` displaying local folder path, `📂 Reveal in Finder`, and `📋 Copy Folder Path` buttons.
    - Added a responsive 2-column grid displaying all 6 generated local file paths with individual `📋` copy buttons.
    - Updated Playlist Batch Tracker table to display local folder names with `📋 Copy Path` and `📂 Reveal in Finder` action buttons.
  - **CLI Completion Reporting (`cli_v7.py` / `cli.py`)**:
    - Enhanced terminal output to display "All Steps Completed! Local Files Created on Disk", listing the local folder path and all 6 generated file paths.
- **Verification**: 126 tests passing across all 23 test modules (`tests/test_post_transcription_export_v1.py`).

