#!/usr/bin/env python3
"""Universal Transcriber Web Interface & Telemetry API (v6).
<!-- v6 – Official 0.1-beta product release: version 0.1.0-beta telemetry, canonical config integration, local dropzone, and persistent audit trail -->
"""

import json
import os
import queue
import re
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional

from flask import Flask, request, jsonify, send_file, send_from_directory, Response
from flask_cors import CORS

from src.engine.pipeline_v6 import TranscriptionPipelineV6
from src.engine.ingest_v4 import SUPPORTED_LOCAL_EXTENSIONS
from src.playbooks.loader_v3 import PlaybookLoaderV3, PlaybookValidationError
from src.engine.diarize_v3 import SpeakerDatabaseV3
from src.engine.queue_v2 import JobQueue
from src.engine.catalog_v1 import MediaCatalog
from src.engine.audit_v1 import TranscriptionAuditLogger
from config_v5 import (
    BASE_DIR,
    WEB_HOST,
    WEB_PORT,
    DEFAULT_PLAYBOOK,
    TRANSCRIPTS_DIR,
    ALLOWED_CORS_ORIGINS,
    QUEUE_DB_PATH,
    CATALOG_DB_PATH,
    PLAYBOOKS_DIR,
    AUDIT_DB_PATH,
    AUDIT_LOG_JSONL_PATH,
    APP_NAME,
    VERSION,
    AUTHOR,
    GITHUB_REPO,
)

app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="")

# Restrict CORS to explicit local origins
CORS(app, resources={r"/api/*": {"origins": ALLOWED_CORS_ORIGINS}})

# Dedicated uploads directory for drag-and-drop local files
UPLOADS_DIR = TRANSCRIPTS_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

pipeline = TranscriptionPipelineV6()
playbook_loader = PlaybookLoaderV3()
speaker_db = SpeakerDatabaseV3()
job_queue = JobQueue(QUEUE_DB_PATH)
catalog = MediaCatalog(CATALOG_DB_PATH)
audit_logger = TranscriptionAuditLogger(AUDIT_DB_PATH, AUDIT_LOG_JSONL_PATH)

# In-memory pub/sub broker for SSE real-time streaming
_subscribers_lock = threading.Lock()
_subscribers: Dict[str, List[queue.Queue]] = {}
_event_history: Dict[str, List[Dict[str, Any]]] = {}


def publish_event(job_id: str, event_type: str, data: Dict[str, Any]) -> None:
    """Thread-safe broadcast of SSE events to all connected clients for a job."""
    evt = {"type": event_type, "data": data}
    with _subscribers_lock:
        if job_id not in _event_history:
            _event_history[job_id] = []
        _event_history[job_id].append(evt)

        for q in _subscribers.get(job_id, []):
            try:
                q.put_nowait(evt)
            except queue.Full:
                pass


@app.route("/")
def index():
    """Serve main web interface."""
    return send_from_directory(str(BASE_DIR / "static"), "index.html")


@app.route("/api/playbooks", methods=["GET"])
def get_playbooks():
    """List available validated domain playbooks."""
    return jsonify(playbook_loader.list_available())


@app.route("/api/playbooks/validate", methods=["POST"])
def validate_playbook():
    """Validate a domain playbook candidate against JSON Schema v7."""
    data = request.get_json(silent=True) or {}
    is_valid, err = playbook_loader.validate_dict(data)
    if not is_valid:
        return jsonify({"valid": False, "error": err}), 400
    return jsonify({"valid": True, "message": "Playbook schema validation passed."})


@app.route("/api/playbooks", methods=["POST"])
def create_playbook():
    """Register a new custom domain playbook after strict JSON Schema v7 validation."""
    data = request.get_json(silent=True) or {}
    is_valid, err = playbook_loader.validate_dict(data)
    if not is_valid:
        return jsonify({"error": f"Schema validation failed: {err}"}), 400

    name = data["name"].strip().lower()
    target_path = PLAYBOOKS_DIR / f"{name}_v1.json"
    if target_path.exists():
        return jsonify({"error": f"Playbook '{name}' already exists."}), 409

    target_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return jsonify({
        "success": True,
        "name": name,
        "path": str(target_path),
        "message": "Playbook validated and saved successfully."
    })


@app.route("/api/speakers", methods=["GET"])
def get_speakers():
    """List registered speaker profiles."""
    profiles = []
    for spk_id, prof in speaker_db.profiles.items():
        profiles.append({
            "id": spk_id,
            "name": prof.get("name", spk_id),
            "sample_count": prof.get("sample_count", 1)
        })
    return jsonify(profiles)


@app.route("/api/speakers/<speaker_id>/name", methods=["POST"])
def rename_speaker(speaker_id):
    """Rename a speaker profile."""
    data = request.get_json(silent=True) or {}
    new_name = data.get("name", "").strip()
    if not new_name:
        return jsonify({"error": "Name cannot be empty"}), 400

    if speaker_id not in speaker_db.profiles:
        return jsonify({"error": f"Speaker ID '{speaker_id}' not found"}), 404

    speaker_db.profiles[speaker_id]["name"] = new_name
    speaker_db.save()
    return jsonify({"success": True, "id": speaker_id, "name": new_name})


@app.route("/api/catalog", methods=["GET"])
def get_catalog():
    """List discovered catalog items and summary stats."""
    stats = catalog.get_stats()
    items = catalog.get_recent_items(limit=50)
    return jsonify({
        "stats": stats,
        "items": items
    })


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """Upload a local audio or video file (.m4a, .mp3, .mp4, .mov, .mkv, .wav, etc.) for transcription."""
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "No file selected"}), 400

    original_name = Path(f.filename).name
    ext = Path(original_name).suffix.lower()
    if ext not in SUPPORTED_LOCAL_EXTENSIONS:
        supported_str = ", ".join(sorted(SUPPORTED_LOCAL_EXTENSIONS))
        return jsonify({
            "error": f"Unsupported media format '{ext}'. Supported formats: {supported_str}"
        }), 400

    clean_stem = re.sub(r'[^a-zA-Z0-9_\- ]', '_', Path(original_name).stem).strip()
    target_filename = f"{uuid.uuid4().hex[:6]}_{clean_stem}{ext}"
    upload_path = UPLOADS_DIR / target_filename
    f.save(str(upload_path))

    # Probe metadata
    meta = pipeline.ingestor.inspect_source(str(upload_path))
    size_mb = upload_path.stat().st_size / (1024 * 1024)

    return jsonify({
        "success": True,
        "path": str(upload_path),
        "filename": original_name,
        "title": meta.get("title") or clean_stem.replace("_", " ").title(),
        "clean_stem": clean_stem,
        "duration": meta.get("duration", 0),
        "duration_str": meta.get("duration_str", "00:00:00"),
        "format": meta.get("format", ext.lstrip(".")),
        "media_type": meta.get("media_type", "audio"),
        "size_bytes": upload_path.stat().st_size,
        "size_str": f"{size_mb:.2f} MB",
    })


@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    """List recent background jobs."""
    limit = int(request.args.get("limit", 20))
    return jsonify(job_queue.list_jobs(limit=limit))


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """Get status of a specific background job from queue or audit trail."""
    job = job_queue.get_job(job_id)
    if not job:
        audit_entry = audit_logger.get_job(job_id)
        if audit_entry:
            job = {
                "job_id": job_id,
                "status": audit_entry.get("status", "").lower(),
                "error_message": audit_entry.get("error_message"),
                "stage_message": audit_entry.get("error_message") or audit_entry.get("status"),
                "result": audit_entry if audit_entry.get("status") == "COMPLETED" else None,
                "progress_pct": 100 if audit_entry.get("status") == "COMPLETED" else 0,
            }
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id):
    """Cancel a running or pending job and record cancellation in the audit trail."""
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "User initiated clear / cancel from dashboard")

    # Update job queue and audit log
    pipeline.cancel(job_id, reason=reason)

    # Broadcast SSE cancel event so connected clients reset
    publish_event(job_id, "cancelled", {"job_id": job_id, "reason": reason})

    return jsonify({"success": True, "job_id": job_id, "message": "Job cancelled and logged to audit trail."})


@app.route("/api/audit", methods=["GET"])
def get_audit_trail():
    """Retrieve persistent transcription audit trail and usage metrics."""
    limit = request.args.get("limit", 25, type=int)
    unused_only = request.args.get("unused", "false").lower() == "true"

    summary = audit_logger.get_audit_summary()
    entries = audit_logger.list_audit_entries(
        limit=limit,
        used_only=False if unused_only else None
    )

    return jsonify({
        "summary": summary,
        "entries": entries,
    })


@app.route("/api/audit/<job_id>/mark-used", methods=["POST"])
def mark_audit_job_used(job_id):
    """Mark a transcription as used / consumed."""
    data = request.get_json(silent=True) or {}
    action = data.get("action", "web_viewed")
    success = audit_logger.mark_job_used(job_id, action=action)
    if not success:
        return jsonify({"error": f"Job ID '{job_id}' not found in audit log"}), 404
    return jsonify({"success": True, "job_id": job_id, "used_flag": 1})


@app.route("/api/stream/<job_id>")
def stream_telemetry(job_id):
    """Server-Sent Events (SSE) telemetry stream emitting real-time progress and tokens."""
    # Check if job exists in persistent queue or audit database
    job_record = job_queue.get_job(job_id)
    audit_record = audit_logger.get_job(job_id)
    with _subscribers_lock:
        in_memory = job_id in _event_history or job_id in _subscribers

    if not job_record and not audit_record and not in_memory:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404

    client_queue = queue.Queue()
    with _subscribers_lock:
        if job_id not in _subscribers:
            _subscribers[job_id] = []
        _subscribers[job_id].append(client_queue)

        # Backfill any events already emitted
        history = list(_event_history.get(job_id, []))

    def event_generator():
        try:
            # Replay past events
            for evt in history:
                yield f"event: {evt['type']}\ndata: {json.dumps(evt['data'])}\n\n"
                if evt["type"] in ("completed", "error", "cancelled"):
                    return

            # If job was already marked completed/failed in DB before client connected
            if job_record and job_record.get("status") == "completed" and not history:
                res = json.loads(job_record.get("result_json", "{}"))
                yield f"event: completed\ndata: {json.dumps(res)}\n\n"
                return

            # Stream live events
            while True:
                try:
                    evt = client_queue.get(timeout=25.0)
                    yield f"event: {evt['type']}\ndata: {json.dumps(evt['data'])}\n\n"
                    if evt["type"] in ("completed", "error", "cancelled"):
                        break
                except queue.Empty:
                    # Keep-alive comment
                    yield ": ping\n\n"
        finally:
            with _subscribers_lock:
                if job_id in _subscribers:
                    if client_queue in _subscribers[job_id]:
                        _subscribers[job_id].remove(client_queue)
                    if not _subscribers[job_id]:
                        _subscribers.pop(job_id, None)

    return Response(
        event_generator(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


@app.route("/api/transcribe", methods=["POST"])
def transcribe_async():
    """Trigger background transcription pipeline with streaming telemetry, ISO naming, and audit recording."""
    data = request.get_json(silent=True) or {}
    source = data.get("source", "").strip()
    playbook = data.get("playbook", DEFAULT_PLAYBOOK).strip()
    clustering = data.get("clustering", "ahc").strip()
    custom_name = data.get("custom_name") or data.get("name") or data.get("title")

    if not source:
        return jsonify({"error": "Missing 'source' parameter"}), 400

    if not (source.startswith("http://") or source.startswith("https://")):
        src_path = Path(source).resolve()
        if not src_path.exists():
            return jsonify({"error": f"File does not exist: {source}"}), 400
        if not src_path.is_file():
            return jsonify({"error": "Target must be a regular media file (device nodes rejected)."}), 400

    job_id = f"job_{uuid.uuid4().hex[:8]}"

    # Synchronously register in persistent queue and audit logger before returning 202
    job_queue.enqueue(job_id=job_id, source_url=source, playbook=playbook)
    audit_logger.log_job_started(
        job_id=job_id,
        source=source,
        playbook=playbook,
        clustering_mode=clustering,
        custom_name=custom_name,
    )

    def on_progress(stage: str, percent: int):
        publish_event(job_id, "progress", {
            "job_id": job_id,
            "status": "processing",
            "progress_pct": percent,
            "stage_message": stage,
        })

    def on_segment(segment: Dict[str, Any]):
        publish_event(job_id, "segment", segment)

    def worker_thread():
        try:
            p = TranscriptionPipelineV6(clustering_mode=clustering)
            result = p.process(
                source=source,
                playbook_name=playbook,
                job_id=job_id,
                progress_callback=on_progress,
                segment_callback=on_segment,
                custom_name=custom_name,
            )
            publish_event(job_id, "completed", result)
        except Exception as e:
            publish_event(job_id, "error", {"error": str(e), "job_id": job_id})

    t = threading.Thread(target=worker_thread, daemon=True)
    t.start()

    return jsonify({
        "status": "accepted",
        "job_id": job_id,
        "stream_url": f"/api/stream/{job_id}",
        "message": "Transcription job queued and persistent audit log initialized."
    }), 202


@app.route("/api/file", methods=["GET"])
def get_file_legacy():
    """Legacy file download endpoint with path traversal protection."""
    path_param = request.args.get("path", "").strip()
    if not path_param:
        return jsonify({"error": "Missing 'path' parameter"}), 400

    safe_path = Path(path_param).resolve()
    transcripts_root = TRANSCRIPTS_DIR.resolve()

    if not str(safe_path).startswith(str(transcripts_root)):
        return jsonify({"error": "Access denied. Path outside allowed directory."}), 403

    if not safe_path.exists() or not safe_path.is_file():
        return jsonify({"error": "File not found"}), 404

    return send_file(str(safe_path), as_attachment=False)


@app.route("/api/files/<path:file_path>")
def download_transcript_file(file_path):
    """Serve exported transcript files for direct download and mark job as used."""
    safe_path = Path("/" + file_path.lstrip("/")).resolve()
    transcripts_root = TRANSCRIPTS_DIR.resolve()

    if not str(safe_path).startswith(str(transcripts_root)):
        return jsonify({"error": "Access denied. Outside transcripts directory."}), 403

    if not safe_path.exists() or not safe_path.is_file():
        return jsonify({"error": "File not found"}), 404

    # Locate job in audit DB that produced this file and mark used
    for entry in audit_logger.list_audit_entries(limit=50):
        fmap = entry.get("files", {})
        if any(str(safe_path) == str(p) for p in fmap.values()):
            audit_logger.mark_job_used(entry["job_id"], action="download")
            break

    return send_file(str(safe_path), as_attachment=False)


@app.route("/api/info")
def get_system_info():
    """Return system metadata and attribution."""
    return jsonify({
        "name": APP_NAME,
        "version": VERSION,
        "author": AUTHOR,
        "repository": GITHUB_REPO,
        "license": "MIT",
        "metal_acceleration": True,
        "supported_containers": list(sorted(SUPPORTED_LOCAL_EXTENSIONS)),
    })


def main():
    print(f"Universal Transcriber Web Interface (v{VERSION}) • Engineered by @{AUTHOR}")
    print(f"Server URL:    http://{WEB_HOST}:{WEB_PORT}")
    print(f"Uploads Dir:   {UPLOADS_DIR}")
    print(f"Audit Store:   {AUDIT_DB_PATH}")
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
