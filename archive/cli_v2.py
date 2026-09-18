#!/usr/bin/env python3
"""Universal Transcriber CLI (v2).
<!-- v2 – Added batch processing, graceful SIGINT cleanup, persistent queue inspection -->

Usage:
  python cli_v2.py transcribe <URL-or-File> [--playbook <name>] [--output <dir>]
  python cli_v2.py batch <Playlist-or-Folder> [--playbook <name>]
  python cli_v2.py queue [--limit <N>]
  python cli_v2.py playbooks
  python cli_v2.py speakers [--rename <ID> <Name>]
"""

import argparse
import glob
import os
import signal
import sys
from pathlib import Path

from src.engine.pipeline_v2 import TranscriptionPipeline
from src.engine.diarize_v2 import SpeakerDatabase
from src.engine.queue_v2 import JobQueue
from src.engine.ingest_v2 import MediaIngestor
from src.playbooks.loader_v2 import PlaybookLoader
from config_v2 import TRANSCRIPTS_DIR, DEFAULT_PLAYBOOK, QUEUE_DB_PATH

active_job_id = None


def sigint_handler(sig, frame):
    """Gracefully handle Ctrl+C interrupts."""
    print("\n\n[Interrupt] Received stop signal. Cleaning up...", file=sys.stderr)
    if active_job_id:
        try:
            ingestor = MediaIngestor()
            ingestor.cleanup_job(active_job_id)
        except Exception:
            pass
    sys.exit(130)


signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGTERM, sigint_handler)


def cmd_transcribe(args):
    """Run transcription on a single file or URL."""
    global active_job_id
    pipeline = TranscriptionPipeline(output_dir=Path(args.output) if args.output else TRANSCRIPTS_DIR)

    def on_progress(stage: str, percent: int):
        print(f"[{percent:3d}%] {stage}...")

    print(f"Starting transcription:")
    print(f"  Source:   {args.input}")
    print(f"  Playbook: {args.playbook}")
    print(f"  Output:   {args.output or TRANSCRIPTS_DIR}")
    print("-" * 60)

    try:
        result = pipeline.process(
            source=args.input,
            playbook_name=args.playbook,
            progress_callback=on_progress
        )
        print("-" * 60)
        print(" Transcription Complete!")
        print(f"  Title:     {result['metadata']['title']}")
        print(f"  Duration:  {result['metadata']['duration_str']}")
        print(f"  Blocks:    {result['total_blocks']}")
        print(f"  Folder:    {result['export_dir']}")
        print(f"  Markdown:  {result['files']['md']}")
        print(f"  Plaintext: {result['files']['txt']}")
        print(f"  Subtitles: {result['files']['srt']}")
    except Exception as e:
        print(f"\n Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_batch(args):
    """Batch process a YouTube playlist or a local directory of audio files."""
    pipeline = TranscriptionPipeline(output_dir=Path(args.output) if args.output else TRANSCRIPTS_DIR)
    ingestor = MediaIngestor()
    meta = ingestor.inspect_source(args.source)

    targets = []
    if meta.get("is_playlist"):
        print(f"Found YouTube Playlist: {meta['title']} ({len(meta['items'])} items)")
        for item in meta["items"]:
            targets.append((item["url"], item["title"]))
    else:
        src_path = Path(args.source).resolve()
        if src_path.is_dir():
            print(f"Scanning directory: {src_path}")
            for ext in ("*.mp4", "*.mov", "*.mkv", "*.m4a", "*.mp3", "*.wav"):
                for f in sorted(src_path.glob(ext)):
                    targets.append((str(f), f.stem))
            print(f"Found {len(targets)} media files in directory.")
        else:
            targets.append((args.source, meta.get("title", "Recording")))

    if not targets:
        print("No media items found to process.")
        return

    print(f"\nProcessing {len(targets)} items in batch:")
    print("=" * 60)

    for idx, (target_url, title) in enumerate(targets, 1):
        print(f"\n[{idx}/{len(targets)}] Processing: {title}")
        print(f"Source: {target_url}")
        try:
            res = pipeline.process(source=target_url, playbook_name=args.playbook)
            print(f" Saved: {res['files']['md']}")
        except Exception as e:
            print(f" Failed item {idx}: {e}", file=sys.stderr)


def cmd_queue(args):
    """View status of persistent background job queue."""
    queue = JobQueue(QUEUE_DB_PATH)
    jobs = queue.list_jobs(limit=args.limit)
    if not jobs:
        print("Queue is empty.")
        return

    print(f"Persistent Queue Status ({len(jobs)} recent jobs):")
    print("=" * 75)
    for j in jobs:
        print(f" • [{j['job_id']}] {j['status'].upper():<13} ({j['progress_pct']:3d}%) {j['title'][:35]:<36} {j['stage_message']}")


def cmd_playbooks(args):
    """List available domain playbooks."""
    loader = PlaybookLoader()
    pbs = loader.list_available()
    print("Available Domain Playbooks:")
    print("=" * 70)
    for p in pbs:
        print(f" • {p['name']:<22} (Default Role: {p['default_role']})")
        if p['description']:
            print(f"   {p['description']}")
        print()


def cmd_speakers(args):
    """List or rename persistent speaker profiles."""
    db = SpeakerDatabase()
    if args.rename:
        spk_id, new_name = args.rename
        db.rename_speaker(spk_id, new_name)
        print(f"Updated: {spk_id} -> '{new_name}'")
        return

    speakers = db.list_speakers()
    if not speakers:
        print("No speaker profiles recorded yet.")
        return

    print("Persistent Speaker Profiles:")
    print("=" * 60)
    for s in speakers:
        print(f" • [{s['id']}] {s['name']} (Sessions: {s['sessions_count']}, Samples: {s['samples_count']})")


def main():
    parser = argparse.ArgumentParser(
        prog="universal-transcriber",
        description="Universal Audio/Video Transcriber for macOS (v2)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Transcribe
    p_trans = subparsers.add_parser("transcribe", help="Transcribe a video/audio URL or file")
    p_trans.add_argument("input", help="YouTube URL or local audio/video file")
    p_trans.add_argument("--playbook", default=DEFAULT_PLAYBOOK, help="Domain playbook name")
    p_trans.add_argument("--output", help="Custom output directory")
    p_trans.set_defaults(func=cmd_transcribe)

    # Batch
    p_batch = subparsers.add_parser("batch", help="Batch process a playlist or local media directory")
    p_batch.add_argument("source", help="YouTube playlist URL or directory of media files")
    p_batch.add_argument("--playbook", default=DEFAULT_PLAYBOOK, help="Domain playbook name")
    p_batch.add_argument("--output", help="Custom output directory")
    p_batch.set_defaults(func=cmd_batch)

    # Queue
    p_queue = subparsers.add_parser("queue", help="Inspect persistent job queue status")
    p_queue.add_argument("--limit", type=int, default=20, help="Number of jobs to list")
    p_queue.set_defaults(func=cmd_queue)

    # Playbooks
    p_play = subparsers.add_parser("playbooks", help="List available playbooks")
    p_play.set_defaults(func=cmd_playbooks)

    # Speakers
    p_spk = subparsers.add_parser("speakers", help="View or rename speaker profiles")
    p_spk.add_argument("--rename", nargs=2, metavar=("ID", "NAME"), help="Rename speaker ID to human name")
    p_spk.set_defaults(func=cmd_speakers)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
