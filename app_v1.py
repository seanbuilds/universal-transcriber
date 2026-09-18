#!/usr/bin/env python3
"""Universal Transcriber Web Interface & API (v1)."""

import os
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

from src.engine.pipeline_v1 import TranscriptionPipeline
from src.playbooks.loader_v1 import PlaybookLoader
from src.engine.diarize_v1 import SpeakerDatabase
from config_v1 import BASE_DIR, WEB_HOST, WEB_PORT, DEFAULT_PLAYBOOK, TRANSCRIPTS_DIR

app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="")
CORS(app)

pipeline = TranscriptionPipeline()
playbook_loader = PlaybookLoader()
speaker_db = SpeakerDatabase()


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


@app.route("/api/transcribe", methods=["POST"])
def transcribe():
    """Trigger transcription pipeline for given source."""
    data = request.get_json() or {}
    source = data.get("source", "").strip()
    playbook = data.get("playbook", DEFAULT_PLAYBOOK).strip()

    if not source:
        return jsonify({"error": "Missing 'source' parameter"}), 400

    try:
        result = pipeline.process(source=source, playbook_name=playbook)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/file", methods=["GET"])
def get_file():
    """Serve a generated transcript file for viewing or downloading."""
    file_path = request.args.get("path", "").strip()
    if not file_path:
        return "Missing path", 400
    p = Path(file_path).resolve()
    # Security: ensure path is within TRANSCRIPTS_DIR or BASE_DIR
    if not p.exists() or not p.is_file():
        return "File not found", 404
    return send_file(str(p), as_attachment=False)


def main():
    print("=" * 65)
    print(" 🎙️ Universal Transcriber Web Server (v1)")
    print(f" URL: http://{WEB_HOST}:{WEB_PORT}")
    print(f" Output Folder: {TRANSCRIPTS_DIR}")
    print("=" * 65)
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False)


if __name__ == "__main__":
    main()
