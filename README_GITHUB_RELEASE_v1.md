# Work Record: GitHub Release, Licensing & Attribution Setup (v1)
<!-- v1 – Record of production GitHub release preparation, MIT licensing, and user attribution for @seanbuilds -->

- **Date**: 2026-09-18
- **Project Path**: `/Users/dad/Documents/antigravity/joyful-davinci`
- **Target Repository**: `https://github.com/seanbuilds/universal-transcriber`
- **Primary Maintainer**: Sean Tyler ([@seanbuilds](https://github.com/seanbuilds) / `ohheysean@gmail.com`)
- **Source Changed**: Yes (web dashboard branding, CLI versioning and banners, app telemetry info endpoint, documentation, and licensing)

---

## 1. Work Executed in This Session

1. **User Attribution & Branding**:
   - Integrated `@seanbuilds` badge in web dashboard header (`static/index.html` and `static/index_v4.html`).
   - Added author attribution and repository link in web footer.
   - Updated `cli_v6.py` argument parser with `--version` ("Universal Transcriber v6.0.0 (@seanbuilds)") and descriptive banners.
   - Updated `app_v5.py` startup banner and added `/api/info` endpoint returning project metadata and attribution.
   - Configured local Git repository user to `seanbuilds` (`ohheysean@gmail.com`).

2. **Open-Source MIT Licensing**:
   - Authored root `LICENSE` and version-tracked `LICENSE_v1.md` containing standard MIT License terms attributed to Sean Tyler (`@seanbuilds`).

3. **Chronological Iterations Log**:
   - Authored comprehensive chronological timeline in `ITERATIONS_LOG_v1.md` (mirrored in `CHANGELOG_v1.md` and `CHANGELOG.md`).
   - Captured complete evolutionary arc from initial concept on 2026-09-05 through v1, v2, v3, v4, v5, v6, and current v7 release.

4. **Documentation & Archival**:
   - Created `README_v7.md` and refreshed root `README.md` with full usage instructions, platform capabilities, and licensing badges.
   - Enforced v5 Archival Policy by moving `README_v5.md` to `archive/` (retaining `README_v6.md` and `README_v7.md` in root).

5. **Clean Repository Configuration**:
   - Created `.gitignore` and `.gitignore_v1` to prevent temporary caches (`__pycache__`, `.pytest_cache`, `.agents`, `._*`) from polluting the public repository.

6. **Automated Verification**:
   - Executed full test suite (`pytest`): 106 passed in 1.96s with zero failures.
   - Restarted background web server (`app_v5.py`) and verified `/api/info` and HTML UI endpoints via HTTP queries.

---

## 2. How to Run / Inspect Artifacts

### Launch Web Dashboard
```bash
# Web server runs at:
http://127.0.0.1:5055

# Or launch directly in terminal:
python3 app_v5.py
```

### Run Command-Line Interface
```bash
# Inspect version and author attribution
python3 cli_v6.py --version

# Transcribe single local audio or video file
python3 cli_v6.py local /path/to/media.m4a --playbook gaming_videos --title "Highlights"

# View audit logs
python3 cli_v6.py audit
```

### Run Test Suite
```bash
/opt/homebrew/opt/python@3.14/bin/python3 -m pytest -v
```

---

## 3. Actual Findings & Outcome

- **Test Suite**: All 106 automated tests pass cleanly across all modules (audio ingestion, Metal ASR, AHC diarization, roll-call FSM healing, multi-format export, catalog deduplication, persistent SQLite/JSONL audit, and web concurrency).
- **Attribution**: The name `@seanbuilds` is visible across the web dashboard, CLI version output, and documentation.
- **GitHub Target**: Configured for publication to `seanbuilds/universal-transcriber`.
