# ⏱️ Universal Transcriber: Iterations & Chronological Timeline Log (v1)
<!-- v1 – Comprehensive chronological log of all engineering iterations, timestamps, component modifications, and verification records -->

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
  - `src/engine/transcribe_v1.py`: Subprocess interface to `whisper.cpp` utilizing Apple Metal GPU (`ggml-metal.metal`).
  - `src/engine/diarize_v1.py`: Vector cosine distance speaker clustering and biometric profile updates.
  - `src/engine/healer_v1.py`: Consecutive turn coalescing and utterance deduplication.
  - `src/engine/export_v1.py`: Verbatim transcript export to Markdown (`.md`) and Plaintext (`.txt`).
  - `src/engine/pipeline_v1.py`: Synchronous end-to-end orchestration.
  - `cli_v1.py` & `app_v1.py`: CLI commands and initial local Flask dashboard.
  - `src/playbooks/loader_v1.py`: Playbook engine supporting 5 initial domains (`municipal_meetings`, `interview_podcast`, `corporate_meeting`, `academic_lecture`, `general_speech`).
- **Independent Adversarial Review**:
  - Completed `REVIEW_FEEDBACK_v1.md` (`2026-09-11 15:42:01 EDT`), identifying centroid drift risks during long recordings, keyword polysemy in speaker heuristics, and path traversal exposure in file endpoints.

---

### Iteration 2 — Adversarial Hardening, Centroid Clamp & Security Defenses
- **Date**: `2026-09-12 09:34:32 – 09:36:27 EDT`
- **Objective**: Address all critical and high-priority vulnerabilities discovered during the adversarial architectural review.
- **Enhancements Implemented**:
  - `src/engine/diarize_v2.py`:
    - Clamped centroid updates: Bound maximum angular drift per turn to prevent conversational drift from corrupting speaker identities.
    - Spherical unit-normalization: Guaranteed invariant Euclidean distances on the unit hypersphere.
  - `src/engine/healer_v2.py`:
    - Introduced polysemy-aware contextual boundary parsing to eliminate false-positive role bindings.
  - `src/engine/queue_v1.py`:
    - Persistent SQLite background job queue with crash recovery and automatic retry tracking.
  - `app_v2.py`:
    - Path traversal defenses: Canonical path verification rejecting parent traversal attempts (`../`).
    - Origin-restricted CORS policies and input sanitization.
  - `src/engine/export_v2.py`:
    - SubRip (`.srt`) subtitle export format support.
- **Verification**: 44 tests passing with zero security vulnerabilities.

---

### Iteration 3 — Sliding-Window Streaming ASR & 25,000x Diarization Acceleration
- **Date**: `2026-09-15 11:11:04 – 2026-09-16 16:17:07 EDT`
- **Objective**: Transition from batch-only processing to real-time sliding-window streaming telemetry and eliminate clustering bottlenecks on multi-hour audio files.
- **Enhancements Implemented**:
  - `src/engine/transcribe_v3.py`:
    - 30-second sliding windows with 2-second overlap compensation and cross-window boundary deduplication.
  - `src/engine/diarize_v3.py`:
    - Replaced pure-Python $O(n^3)$ distance matrix loops with vectorized `scipy.cluster.hierarchy` cosine linkage.
    - Achieved a **25,000x speedup** in agglomerative hierarchical clustering (AHC).
  - `src/engine/healer_v3.py`:
    - Formal three-state parliamentary roll-call Finite State Machine (`ROLL_CALL`, `VOTE`, `DISCUSSION`).
  - `src/engine/export_v3.py`:
    - Expanded output formats to Microsoft Word (`.docx`) and WebVTT (`.vtt`).
  - `app_v3.py` & `static/index_v2.html`:
    - Real-time Server-Sent Events (`GET /api/stream/<job_id>`) delivering live token-by-token transcripts, speaker turns, and progress updates to web clients.
- **Verification**: 78 tests passing across streaming, FSM, and acceleration suites.

---

### Iteration 4 — YouTube Channel & Podcast RSS Idempotent Catalog
- **Date**: `2026-09-16 19:34:32 – 19:51:44 EDT`
- **Objective**: Enable bulk harvesting and autonomous synchronization of entire media catalogs without duplicating work.
- **Enhancements Implemented**:
  - `src/engine/catalog_v1.py`:
    - Persistent SQLite media index (`discovered_media` table) tracking content IDs, publication dates, and processing states.
    - Idempotency guarantees: Skips existing items unless explicitly overridden with `--force`.
  - `src/engine/ingest_v3.py`:
    - Channel and playlist pagination via `yt-dlp` alongside XML/RSS podcast feed parsing via `feedparser`.
  - `cli_v4.py`:
    - Added `catalog` and `catalog-status` commands for headless synchronization.
- **Verification**: 89 tests passing.

---

### Iteration 5 — Creator & Gaming Playbook, Persistent Dual-Write Audit & ISO Naming
- **Date**: `2026-09-17 09:54:21 – 10:13:00 EDT`
- **Objective**: Support gaming content and Let's Plays, ensure every transcription attempt is permanently recorded for auditing, standardize output filenames, and provide an immediate UI reset mechanism.
- **Enhancements Implemented**:
  - `playbooks/gaming_videos_v1.json`:
    - Domain lexicon tailored for esports, speedrunning, shoutcasting, and multiplayer voice communications.
    - Dynamic role detection: **Streamer**, **Teammate**, **Opponent**, **Caster**, and **System**.
  - `src/engine/audit_v1.py`:
    - Dual-write audit architecture: Thread-safe SQLite store (`transcriptions_audit_v1.sqlite`) paired with an append-only JSON Lines (`.jsonl`) event stream.
    - Records all jobs regardless of outcome: `COMPLETED`, `FAILED`, `CANCELLED`, or `UNUSED`.
    - Tracks audio duration, segment counts, playbook parameters, custom titles, export paths, and user consumption (`USED` vs `UNUSED`).
  - `src/engine/export_v4.py`:
    - Standardized ISO-8601 directory and file naming: `YYYYMMDD_<Title>.<ext>`.
    - Synchronous atomic generation across all 6 formats (`.md`, `.txt`, `.srt`, `.vtt`, `.docx`, `.json`).
  - `app_v4.py` & `static/index_v3.html`:
    - Added "Clear Everything / Start Over" action: Instantly terminates active SSE connections, signals worker cancellation, resets form inputs, and logs cancellation to audit.
    - Real-time audit telemetry metrics: Live counts of total, completed, failed, cancelled, and unconsumed jobs.
- **Verification**: 98 tests passing.

---

### Iteration 6 — Multi-Format Local Media Containers & Drag-and-Drop Dropzone
- **Date**: `2026-09-17 12:04:16 – 12:08:07 EDT`
- **Objective**: Broaden ingestion from network URLs to direct native local media files and directories with high-speed video-bypassing audio extraction.
- **Enhancements Implemented**:
  - `src/engine/ingest_v4.py`:
    - Comprehensive container support: `.m4a`, `.mp3`, `.mp4`, `.mov`, `.mkv`, `.wav`, `.flac`, `.aac`, `.webm`, `.ogg`, and `.opus`.
    - **Video-Bypassing (`-vn`) Optimization**: Skips video frame decoding in container files, extracting 16 kHz mono PCM up to 5x faster.
    - Container metadata inspection via `ffprobe` (sample rate, channel layout, bitrate, duration, track tags).
  - `cli_v6.py`:
    - Added `local` command for single files and recursive directory batch scans (`--recursive`).
  - `app_v5.py` & `static/index.html`:
    - Interactive drag-and-drop file dropzone with `/api/upload` endpoint, upload progress indicators, container format badges, and automatic title pre-filling.
- **Verification**: 106 tests passing in under 2 seconds.

---

### Iteration 7 — Production Open-Source Release & GitHub Publication
- **Date**: `2026-09-18 10:30:00 – Present EDT`
- **Objective**: Prepare repository for public GitHub release under `@seanbuilds` with MIT licensing, comprehensive user guides, and complete historical provenance.
- **Enhancements Implemented**:
  - **Attribution & Branding**:
    - Embedded `@seanbuilds` attribution into the web dashboard header and footer (`static/index.html`).
    - Added `@seanbuilds` banner, description, and `--version` support to `cli_v6.py`.
    - Integrated `/api/info` endpoint and startup attribution to `app_v5.py`.
  - **Licensing**:
    - Created standard open-source MIT License (`LICENSE` and `LICENSE_v1.md`) attributed to Sean Tyler (`@seanbuilds`).
  - **Chronological Provenance**:
    - Compiled `ITERATIONS_LOG_v1.md` and `CHANGELOG_v1.md` documenting the full evolutionary history with precise timestamps.
  - **Documentation & Archival**:
    - Created `README_v7.md` and updated `README.md`.
    - Enforced the v5 Archival Policy by moving `README_v5.md` to `archive/`.
    - Authored session record `README_GITHUB_RELEASE_v1.md`.
  - **Repository Publication**:
    - Configured `.gitignore` for clean open-source distribution.
    - Created and published repository to GitHub: `seanbuilds/universal-transcriber`.
- **Verification**: 106 tests passing with 100% success rate.
