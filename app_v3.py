#!/usr/bin/env python3
"""Universal Transcriber Web Interface & Telemetry API (v3).
<!-- v3 – Server-Sent Events (SSE) streaming telemetry, JSON Schema v7 playbook validation, DOCX/WebVTT file delivery -->
"""

import json
import os
import queue
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional

from flask import Flask, request, jsonify, send_file, send_from_directory, Response
from flask_cors import CORS

from src.engine.pipeline_v4 import TranscriptionPipelineV4
from src.playbooks.loader_v3 import PlaybookLoaderV3, PlaybookValidationError
from src.engine.diarize_v3 import SpeakerDatabaseV3
from src.engine.queue_v2 import JobQueue
from src.engine.catalog_v1 import MediaCatalog
from config_v3 import (
    BASE_DIR,
    WEB_HOST,
    WEB_PORT,
    DEFAULT_PLAYBOOK,
    TRANSCRIPTS_DIR,
    ALLOWED_CORS_ORIGINS,
    QUEUE_DB_PATH,
    CATALOG_DB_PATH,
    PLAYBOOKS_DIR,
)

app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="")

# Restrict CORS to explicit local origins
CORS(app, resources={r"/api/*": {"origins": ALLOWED_CORS_ORIGINS}})

pipeline = TranscriptionPipelineV4()
playbook_loader = PlaybookLoaderV3()
speaker_db = SpeakerDatabaseV3()
job_queue = JobQueue(QUEUE_DB_PATH)
catalog = MediaCatalog(CATALOG_DB_PATH)

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
            except Exception:
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
    data = request.get_json() or {}
    is_valid, err = playbook_loader.validate_dict(data)
    if not is_valid:
        return jsonify({"valid": False, "error": err}), 400
    return jsonify({"valid": True, "message": "Playbook schema validation passed."})


@app.route("/api/playbooks", methods=["POST"])
def create_playbook():
    """Register a new custom domain playbook after strict JSON Schema v7 validation."""
    data = request.get_json() or {}
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
    }), 201


@app.route("/api/speakers", methods=["GET"])
def get_speakers():
    """List persistent speaker voice profiles."""
    profiles = []
    for spk_id, prof in sorted(speaker_db.profiles.items()):
        profiles.append({
            "id": spk_id,
            "name": prof.get("name", spk_id),
            "sample_count": prof.get("sample_count", 1)
        })
    return jsonify(profiles)


@app.route("/api/speakers/<speaker_id>/name", methods=["POST"])
def rename_speaker(speaker_id):
    """Rename a speaker profile."""
    data = request.get_json() or {}
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
    status = request.args.get("status")
    limit = int(request.args.get("limit", 50))
    entries = catalog.list_entries(status=status, limit=limit)
    stats = catalog.get_stats()
    return jsonify({"stats": stats, "entries": entries})


@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    """List recent background jobs."""
    limit = int(request.args.get("limit", 20))
    return jsonify(job_queue.list_jobs(limit=limit))


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """Get status of a specific background job."""
    job = job_queue.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/stream/<job_id>", methods=["GET"])
def stream_job_telemetry(job_id):
    """Server-Sent Events (SSE) telemetry stream emitting real-time progress and live ASR tokens."""
    job = job_queue.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    def event_generator():
        client_queue = queue.Queue()
        with _subscribers_lock:
            if job_id not in _subscribers:
                _subscribers[job_id] = []
            _subscribers[job_id].append(client_queue)

        try:
            with _subscribers_lock:
                history = list(_event_history.get(job_id, []))

            for evt in history:
                yield f"event: {evt['type']}\ndata: {json.dumps(evt['data'])}\n\n"
                if evt["type"] in ("completed", "error"):
                    return

            # If job already completed according to database
            current = job_queue.get_job(job_id)
            if current and current.get("status") == "completed" and current.get("result"):
                yield f"event: completed\ndata: {json.dumps(current['result'])}\n\n"
                return
            elif current and current.get("status") == "failed":
                yield f"event: error\ndata: {json.dumps({'error': current.get('error_message', 'Job failed')})}\n\n"
                return

            while True:
                try:
                    evt = client_queue.get(timeout=25.0)
                    yield f"event: {evt['type']}\ndata: {json.dumps(evt['data'])}\n\n"
                    if evt["type"] in ("completed", "error"):
                        break
                except queue.Empty:
                    # Send periodic keep-alive comment
                    yield ": keepalive\n\n"
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
    """Trigger background transcription pipeline with streaming telemetry."""
    data = request.get_json() or {}
    source = data.get("source", "").strip()
    playbook = data.get("playbook", DEFAULT_PLAYBOOK).strip()
    clustering = data.get("clustering", "ahc").strip()

    if not source:
        return jsonify({"error": "Missing 'source' parameter"}), 400

    if not (source.startswith("http://") or source.startswith("https://")):
        src_path = Path(source).resolve()
        if not src_path.exists():
            return jsonify({"error": f"File does not exist: {source}"}), 400
        if not src_path.is_file():
            return jsonify({"error": "Target must be a regular media file (device nodes rejected)."}), 400

    job_id = f"job_{uuid.uuid4().hex[:8]}"
    job_queue.enqueue(job_id=job_id, source_url=source, playbook=playbook)

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
            p = TranscriptionPipelineV4(clustering_mode=clustering)
            result = p.process(
                source=source,
                playbook_name=playbook,
                job_id=job_id,
                progress_callback=on_progress,
                segment_callback=on_segment,
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
        "message": "Transcription job queued and streaming telemetry initialized."
    }), 202


@app.route("/api/file", methods=["GET"])
def get_file():
    """Serve generated transcript files with strict path traversal protection."""
    file_param = request.args.get("path", "").strip()
    if not file_param:
        return jsonify({"error": "Missing 'path' parameter"}), 400

    resolved_target = Path(file_param).resolve()
    allowed_root = TRANSCRIPTS_DIR.resolve()

    try:
        if not resolved_target.is_relative_to(allowed_root):
            return jsonify({"error": "Access denied: requested file is outside allowed transcripts directory."}), 403
    except AttributeError:
        if not str(resolved_target).startswith(str(allowed_root)):
            return jsonify({"error": "Access denied: requested file is outside allowed transcripts directory."}), 403

    if not resolved_target.exists() or not resolved_target.is_file():
        return jsonify({"error": "File not found"}), 404

    as_attachment = request.args.get("download", "0") == "1"
    return send_file(str(resolved_target), as_attachment=as_attachment)


def main():
    print("=" * 70)
    print(" 🎙️ Universal Transcriber Web Server (v3 - Streaming & Telemetry)")
    print(f" URL: http://{WEB_HOST}:{WEB_PORT}")
    print(f" Transcripts Root: {TRANSCRIPTS_DIR}")
    print(f" CORS Allowed Origins: {ALLOWED_CORS_ORIGINS}")
    print("=" * 70)
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False)


if __name__ == "__main__":
    main()
