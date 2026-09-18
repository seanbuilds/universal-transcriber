#!/usr/bin/env python3
"""Universal Transcriber CLI (v3).
<!-- v3 – Support for two-pass AHC clustering, persistent speaker libraries, and biometrics -->

Usage:
  python cli_v3.py transcribe <URL-or-File> [--playbook <name>] [--clustering {ahc,online}] [--library <path>]
  python cli_v3.py batch <Playlist-or-Folder> [--playbook <name>] [--clustering {ahc,online}]
  python cli_v3.py queue [--limit <N>]
  python cli_v3.py playbooks
  python cli_v3.py speakers [--library <path>] [--rename <ID> <Name>]
"""

import argparse
import os
import signal
import sys
from pathlib import Path

from src.engine.pipeline_v3 import TranscriptionPipelineV3
from src.engine.diarize_v3 import SpeakerDatabaseV3
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
    library_path = Path(args.library) if args.library else None
    pipeline = TranscriptionPipelineV3(
        output_dir=Path(args.output) if args.output else TRANSCRIPTS_DIR,
        clustering_mode=args.clustering,
        speaker_library_path=library_path,
    )

    def on_progress(stage: str, percent: int):
        print(f"[{percent:3d}%] {stage}...")

    print("Starting transcription (v3 Engine):")
    print(f"  Source:     {args.input}")
    print(f"  Playbook:   {args.playbook}")
    print(f"  Clustering: {args.clustering.upper()}")
    print(f"  Output:     {args.output or TRANSCRIPTS_DIR}")
    print("-" * 60)

    try:
        result = pipeline.process(
            source=args.input,
            playbook_name=args.playbook,
            progress_callback=on_progress,
        )
        print("-" * 60)
        print("Transcription Complete!")
        print(f"  Title:     {result['metadata']['title']}")
        print(f"  Duration:  {result['metadata']['duration_str']}")
        print(f"  Blocks:    {result['total_blocks']}")
        print(f"  Folder:    {result['export_dir']}")
        print(f"  Markdown:  {result['files']['md']}")
        print(f"  Plaintext: {result['files']['txt']}")
        print(f"  Subtitles: {result['files']['srt']}")
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_batch(args):
    """Batch process a YouTube playlist or a local directory of audio files."""
    library_path = Path(args.library) if args.library else None
    pipeline = TranscriptionPipelineV3(
        output_dir=Path(args.output) if args.output else TRANSCRIPTS_DIR,
        clustering_mode=args.clustering,
        speaker_library_path=library_path,
    )
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

    total = len(targets)
    print(f"\nProcessing {total} targets in batch queue...")
    for idx, (target_src, title) in enumerate(targets, 1):
        print(f"\n{'='*60}")
        print(f"[{idx}/{total}] Processing: {title}")
        print(f"{'='*60}")
        try:
            pipeline.process(
                source=target_src,
                playbook_name=args.playbook,
                progress_callback=lambda s, p: print(f"  [{p:3d}%] {s}"),
            )
        except Exception as e:
            print(f"  Failed target {title}: {e}", file=sys.stderr)


def cmd_queue(args):
    """Inspect persistent SQLite job queue."""
    queue = JobQueue(db_path=QUEUE_DB_PATH)
    jobs = queue.list_jobs(limit=args.limit)

    print(f"\nPersistent Job Queue (Latest {len(jobs)} jobs):")
    print(f"{'ID':<14} | {'Status':<12} | {'Progress':<8} | {'Playbook':<18} | {'Source / Title'}")
    print("-" * 80)
    for j in jobs:
        print(f"{j['job_id']:<14} | {j['status']:<12} | {j['progress_pct']:>6}%  | {j['playbook']:<18} | {j['source_url'][:30]}")


def cmd_playbooks(args):
    """List available domain playbooks."""
    loader = PlaybookLoader()
    pbs = loader.list_available()
    print("Available Domain Playbooks:")
    print("=" * 70)
    for p in pbs:
        print(f" • {p['name']:<22} (Default Role: {p['default_role']})")
        if p.get('description'):
            print(f"   {p['description']}")
        print()


def cmd_speakers(args):
    """Inspect or manage persistent speaker library."""
    lib_path = Path(args.library) if args.library else None
    db = SpeakerDatabaseV3(storage_path=lib_path)

    if args.rename:
        spk_id, new_name = args.rename
        if spk_id in db.profiles:
            db.profiles[spk_id]["name"] = new_name
            db.save()
            print(f"Renamed {spk_id} -> '{new_name}'")
        else:
            print(f"Speaker ID '{spk_id}' not found.", file=sys.stderr)
            sys.exit(1)
        return

    print(f"\nPersistent Speaker Library ({len(db.profiles)} profiles):")
    print(f"{'ID':<14} | {'Name':<25} | {'Samples':<8}")
    print("-" * 60)
    for spk_id, prof in sorted(db.profiles.items()):
        name = prof.get("name", spk_id)
        count = prof.get("sample_count", 1)
        print(f"{spk_id:<14} | {name:<25} | {count:<8}")


def main():
    parser = argparse.ArgumentParser(description="Universal Transcriber CLI (v3)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # transcribe
    p_transcribe = subparsers.add_parser("transcribe", help="Transcribe a video/audio source")
    p_transcribe.add_argument("input", help="URL or path to media file")
    p_transcribe.add_argument("--playbook", default=DEFAULT_PLAYBOOK, help="Domain playbook")
    p_transcribe.add_argument("--clustering", choices=["ahc", "online"], default="ahc", help="Clustering mode")
    p_transcribe.add_argument("--library", help="Path to custom speaker profiles JSON")
    p_transcribe.add_argument("--output", help="Custom output directory")
    p_transcribe.set_defaults(func=cmd_transcribe)

    # batch
    p_batch = subparsers.add_parser("batch", help="Batch process a playlist or directory")
    p_batch.add_argument("source", help="Playlist URL or directory path")
    p_batch.add_argument("--playbook", default=DEFAULT_PLAYBOOK, help="Domain playbook")
    p_batch.add_argument("--clustering", choices=["ahc", "online"], default="ahc", help="Clustering mode")
    p_batch.add_argument("--library", help="Path to custom speaker profiles JSON")
    p_batch.add_argument("--output", help="Custom output directory")
    p_batch.set_defaults(func=cmd_batch)

    # queue
    p_queue = subparsers.add_parser("queue", help="Inspect background job queue")
    p_queue.add_argument("--limit", type=int, default=20, help="Number of records to show")
    p_queue.set_defaults(func=cmd_queue)

    # playbooks
    p_playbooks = subparsers.add_parser("playbooks", help="List domain playbooks")
    p_playbooks.set_defaults(func=cmd_playbooks)

    # speakers
    p_speakers = subparsers.add_parser("speakers", help="List or rename speaker profiles")
    p_speakers.add_argument("--library", help="Path to custom speaker profiles JSON")
    p_speakers.add_argument("--rename", nargs=2, metavar=("ID", "NAME"), help="Rename speaker ID")
    p_speakers.set_defaults(func=cmd_speakers)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
