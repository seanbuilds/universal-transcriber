#!/usr/bin/env python3
"""Universal Transcriber CLI (v1).

Usage:
  python cli_v1.py transcribe <URL-or-File> [--playbook <name>] [--output <dir>]
  python cli_v1.py batch <Playlist-or-Folder> [--playbook <name>]
  python cli_v1.py playbooks
  python cli_v1.py speakers [--rename <ID> <Name>]
"""

import argparse
import sys
from pathlib import Path

from src.engine.pipeline_v1 import TranscriptionPipeline
from src.engine.diarize_v1 import SpeakerDatabase
from src.playbooks.loader_v1 import PlaybookLoader
from config_v1 import TRANSCRIPTS_DIR, DEFAULT_PLAYBOOK


def cmd_transcribe(args):
    """Run transcription on a single file or URL."""
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
        description="Universal Audio/Video Transcriber for macOS (Apple Silicon)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Transcribe
    p_trans = subparsers.add_parser("transcribe", help="Transcribe a video/audio URL or file")
    p_trans.add_argument("input", help="YouTube URL or local audio/video file")
    p_trans.add_argument("--playbook", default=DEFAULT_PLAYBOOK, help="Domain playbook name")
    p_trans.add_argument("--output", help="Custom output directory")
    p_trans.set_defaults(func=cmd_transcribe)

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
