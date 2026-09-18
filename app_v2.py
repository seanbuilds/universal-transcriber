#!/usr/bin/env python3
"""Universal Transcriber Web Interface & API (v2).
<!-- v2 – Patched path traversal, restricted CORS, async worker execution, input sanitization -->
"""

import os
import threading
import uuid
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

from src.engine.pipeline_v2 import TranscriptionPipeline
from src.playbooks.loader_v2 import PlaybookLoader
from src.engine.diarize_v2 import SpeakerDatabase
from src.engine.queue_v1 import JobQueue
from config_v2 import (
    BASE_DIR,
    WEB_HOST,
    WEB_PORT,
    DEFAULT_PLAYBOOK,
    TRANSCRIPTS_DIR,
    ALLOWED_CORS_ORIGINS,
    QUEUE_DB_PATH
)

app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="")

# Finding R4-02 Fix: Restrict CORS to explicit local origin
CORS(app, resources={r"/api/*": {"origins": ALLOWED_CORS_ORIGINS}})

pipeline = TranscriptionPipeline()
playbook_loader = PlaybookLoader()
speaker_db = SpeakerDatabase()
queue = JobQueue(QUEUE_DB_PATH)


@app.route("/")
def index():
    """Serve main web interface."""
    return send_from_directory(str(BASE_DIR / "static"), "index.html")


@app.route("/api/playbooks", methods=["GET"])
def get_playbooks():
    """List available domain playbooks."""
    return jsonify(playbook_loader.list_available())


@app.route("/api/speakers", methods=["GET"])
def get_speakers():
    """List persistent speaker voice profiles."""
    return jsonify(speaker_db.list_speakers())


@app.route("/api/speakers/<speaker_id>/name", methods=["POST"])
def rename_speaker(speaker_id):
    """Rename a speaker profile."""
    data = request.get_json() or {}
    new_name = data.get("name", "").strip()
    if not new_name:
        return jsonify({"error": "Name cannot be empty"}), 400
    speaker_db.rename_speaker(speaker_id, new_name)
    return jsonify({"success": True, "id": speaker_id, "name": new_name})


@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    """List recent jobs and their statuses."""
    limit = int(request.args.get("limit", 20))
    return jsonify(queue.list_jobs(limit=limit))


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """Get status of a specific background job."""
    job = queue.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/transcribe", methods=["POST"])
def transcribe_async():
    """Trigger background transcription pipeline (Finding R4-04 Fix: Non-blocking)."""
    data = request.get_json() or {}
    source = data.get("source", "").strip()
    playbook = data.get("playbook", DEFAULT_PLAYBOOK).strip()

    if not source:
        return jsonify({"error": "Missing 'source' parameter"}), 400

    # Finding R4-03 Fix: Validate input source, reject /dev/ and special device nodes
    if not (source.startswith("http://") or source.startswith("https://")):
        src_path = Path(source).resolve()
        if not src_path.exists():
            return jsonify({"error": f"File does not exist: {source}"}), 400
        if not src_path.is_file():
            return jsonify({"error": "Target must be a regular media file (device nodes, pipes, and directories rejected)."}), 400

    job_id = f"job_{uuid.uuid4().hex[:8]}"
    queue.enqueue(job_id=job_id, source_url=source, playbook=playbook)

    def worker_thread():
        try:
            pipeline.process(source=source, playbook_name=playbook, job_id=job_id)
        except Exception:
            pass

    t = threading.Thread(target=worker_thread, daemon=True)
    t.start()

    return jsonify({
        "status": "accepted",
        "job_id": job_id,
        "message": "Transcription job queued successfully"
    }), 202


@app.route("/api/file", methods=["GET"])
def get_file():
    """Serve a generated transcript file with strict path traversal protection (Finding R4-01 Fix)."""
    file_param = request.args.get("path", "").strip()
    if not file_param:
        return jsonify({"error": "Missing 'path' parameter"}), 400

    # Resolve paths strictly
    resolved_target = Path(file_param).resolve()
    allowed_root = TRANSCRIPTS_DIR.resolve()

    # Verify that resolved target is within the user transcripts directory
    try:
        if not resolved_target.is_relative_to(allowed_root):
            return jsonify({"error": "Access denied: requested file is outside the allowed transcripts directory."}), 403
    except AttributeError:
        # Python < 3.9 compatibility
        if not str(resolved_target).startswith(str(allowed_root)):
            return jsonify({"error": "Access denied: requested file is outside the allowed transcripts directory."}), 403

    if not resolved_target.exists() or not resolved_target.is_file():
        return jsonify({"error": "File not found"}), 404

    return send_file(str(resolved_target), as_attachment=False)


def main():
    print("=" * 65)
    print(" 🎙️ Universal Transcriber Web Server (v2 - Hardened)")
    print(f" URL: http://{WEB_HOST}:{WEB_PORT}")
    print(f" Transcripts Root: {TRANSCRIPTS_DIR}")
    print(f" CORS Allowed Origins: {ALLOWED_CORS_ORIGINS}")
    print("=" * 65)
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False)


if __name__ == "__main__":
    main()
