#!/usr/bin/env python3
"""Universal Transcriber CLI (v6).
<!-- v6 – Native local media container support (.m4a, .mp3, .mp4, .mov, .mkv, .wav, .flac, .aac, .ogg, .opus), dedicated local command, recursive directory scanning, persistent audit logging, and ISO-8601 naming -->

Usage:
  python cli_v6.py local <File-or-Folder> [--recursive] [--title <name>] [--playbook <name>] [--clustering {ahc,online}]
  python cli_v6.py transcribe <URL-or-File> [--title <name>] [--playbook <name>] [--clustering {ahc,online}] [--output <dir>]
  python cli_v6.py batch <Playlist-or-Folder> [--playbook <name>] [--clustering {ahc,online}]
  python cli_v6.py audit [--limit <N>] [--unused] [--mark-used <job_id>]
  python cli_v6.py catalog <Channel-or-RSS> [--playbook <name>] [--limit <N>] [--force] [--dry-run]
  python cli_v6.py catalog-status
  python cli_v6.py queue [--limit <N>]
  python cli_v6.py playbooks [--validate <file>]
  python cli_v6.py speakers [--library <path>] [--rename <ID> <Name>]
  python cli_v6.py email [--target <address>] [--count <N>]
"""

import argparse
import json
import os
import signal
import sys
from pathlib import Path

from src.engine.pipeline_v6 import TranscriptionPipelineV6
from src.engine.diarize_v3 import SpeakerDatabaseV3
from src.engine.queue_v2 import JobQueue
from src.engine.catalog_v1 import MediaCatalog
from src.engine.audit_v1 import TranscriptionAuditLogger
from src.engine.ingest_v4 import MediaIngestorV4, SUPPORTED_LOCAL_EXTENSIONS
from src.playbooks.loader_v3 import PlaybookLoaderV3
from config_v4 import (
    TRANSCRIPTS_DIR,
    DEFAULT_PLAYBOOK,
    QUEUE_DB_PATH,
    CATALOG_DB_PATH,
    AUDIT_DB_PATH,
    AUDIT_LOG_JSONL_PATH,
)

active_job_id = None


def sigint_handler(sig, frame):
    """Gracefully handle Ctrl+C interrupts."""
    print("\n\n[Interrupt] Received stop signal. Cleaning up...", file=sys.stderr)
    if active_job_id:
        try:
            pipeline = TranscriptionPipelineV6()
            pipeline.cancel(active_job_id, reason="Process interrupted by user (SIGINT)")
            ingestor = MediaIngestorV4()
            ingestor.cleanup_job(active_job_id)
        except Exception:
            pass
    sys.exit(130)


signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGTERM, sigint_handler)


def cmd_local(args):
    """Transcribe a local media file (.m4a, .mp3, .mp4, .mov, .wav, etc.) or scan a directory."""
    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target path does not exist: {target_path}", file=sys.stderr)
        sys.exit(1)

    library_path = Path(args.library) if args.library else None
    pipeline = TranscriptionPipelineV6(
        output_dir=Path(args.output) if args.output else TRANSCRIPTS_DIR,
        clustering_mode=args.clustering,
        speaker_library_path=library_path,
    )

    def on_progress(stage: str, percent: int):
        print(f"[{percent:3d}%] {stage}...")

    def on_segment(seg):
        spk = seg.get("speaker")
        prefix = f" [{spk}]" if spk else ""
        print(f"  --> [{seg['ts']}]{prefix} {seg['text']}")

    if target_path.is_file():
        ext = target_path.suffix.lower()
        if ext not in SUPPORTED_LOCAL_EXTENSIONS:
            supported_str = ", ".join(sorted(SUPPORTED_LOCAL_EXTENSIONS))
            print(f"Warning: Extension '{ext}' is not in standard list ({supported_str}), attempting ffmpeg ingest anyway.")

        print("Starting Local Media Transcription (v6 Engine • @seanbuilds):")
        print(f"  Local File:   {target_path}")
        print(f"  File Format:  {ext.lstrip('.').upper()}")
        print(f"  File Size:    {target_path.stat().st_size / (1024 * 1024):.2f} MB")
        print(f"  Custom Title: {args.title or '(Auto-generated ISO)'}")
        print(f"  Playbook:     {args.playbook}")
        print(f"  Clustering:   {args.clustering.upper()}")
        print(f"  Output Root:  {args.output or TRANSCRIPTS_DIR}")
        print("-" * 65)

        try:
            result = pipeline.process(
                source=str(target_path),
                playbook_name=args.playbook,
                custom_name=args.title,
                progress_callback=on_progress,
                segment_callback=on_segment,
            )
            print("-" * 65)
            print("Local Transcription Complete & Persistently Audited!")
            print(f"  ISO ID:    {result['iso_name']}")
            print(f"  Title:     {result['metadata'].get('title', 'Untitled')}")
            print(f"  Duration:  {result['metadata'].get('duration_str', 'N/A')}")
            print(f"  Blocks:    {result['total_blocks']}")
            print(f"  Folder:    {result['export_dir']}")
            print(f"  Markdown:  {result['files']['md']}")
            print(f"  Plaintext: {result['files']['txt']}")
            print(f"  Subtitles: {result['files']['srt']}")
            print(f"  WebVTT:    {result['files']['vtt']}")
            print(f"  DOCX:      {result['files']['docx']}")
            print(f"  JSON:      {result['files']['json']}")
        except Exception as e:
            print(f"\nError: {e}", file=sys.stderr)
            sys.exit(1)

    elif target_path.is_dir():
        files = MediaIngestorV4.scan_directory(target_path, recursive=args.recursive)
        mode_str = "recursive" if args.recursive else "top-level"
        print(f"Scanned directory ({mode_str}): {target_path}")
        print(f"Found {len(files)} supported media files (.m4a, .mp3, .mp4, .mov, .wav, .mkv, .flac).")

        if not files:
            print("No supported media files found.")
            return

        print(f"\nProcessing {len(files)} local files in batch queue...")
        for idx, f in enumerate(files, 1):
            print(f"\n{'='*65}")
            print(f"[{idx}/{len(files)}] Processing: {f.name} ({f.suffix.upper()})")
            print(f"{'='*65}")
            try:
                pipeline.process(
                    source=str(f),
                    playbook_name=args.playbook,
                    custom_name=f.stem,
                    progress_callback=lambda s, p: print(f"  [{p:3d}%] {s}"),
                )
            except Exception as e:
                print(f"  Failed local file {f.name}: {e}", file=sys.stderr)


def cmd_transcribe(args):
    """Run transcription on a single file or URL with ISO naming and audit tracking."""
    global active_job_id
    library_path = Path(args.library) if args.library else None
    pipeline = TranscriptionPipelineV6(
        output_dir=Path(args.output) if args.output else TRANSCRIPTS_DIR,
        clustering_mode=args.clustering,
        speaker_library_path=library_path,
    )

    def on_progress(stage: str, percent: int):
        print(f"[{percent:3d}%] {stage}...")

    def on_segment(seg):
        spk = seg.get("speaker")
        prefix = f" [{spk}]" if spk else ""
        print(f"  --> [{seg['ts']}]{prefix} {seg['text']}")

    print("Starting transcription (v6 Multi-Format & Audit Engine • @seanbuilds):")
    print(f"  Source:       {args.input}")
    print(f"  Custom Title: {args.title or '(Auto-generated ISO)'}")
    print(f"  Playbook:     {args.playbook}")
    print(f"  Clustering:   {args.clustering.upper()}")
    print(f"  Output Root:  {args.output or TRANSCRIPTS_DIR}")
    print("-" * 65)

    try:
        result = pipeline.process(
            source=args.input,
            playbook_name=args.playbook,
            custom_name=args.title,
            progress_callback=on_progress,
            segment_callback=on_segment,
        )
        print("-" * 65)
        print("Transcription Complete & Persistently Audited!")
        print(f"  ISO ID:    {result['iso_name']}")
        print(f"  Title:     {result['metadata'].get('title', 'Untitled')}")
        print(f"  Duration:  {result['metadata'].get('duration_str', 'N/A')}")
        print(f"  Blocks:    {result['total_blocks']}")
        print(f"  Folder:    {result['export_dir']}")
        print(f"  Markdown:  {result['files']['md']}")
        print(f"  Plaintext: {result['files']['txt']}")
        print(f"  Subtitles: {result['files']['srt']}")
        print(f"  WebVTT:    {result['files']['vtt']}")
        print(f"  DOCX:      {result['files']['docx']}")
        print(f"  JSON:      {result['files']['json']}")
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_batch(args):
    """Batch process a playlist or directory with ISO naming and audit logging."""
    library_path = Path(args.library) if args.library else None
    pipeline = TranscriptionPipelineV6(
        output_dir=Path(args.output) if args.output else TRANSCRIPTS_DIR,
        clustering_mode=args.clustering,
        speaker_library_path=library_path,
    )
    ingestor = MediaIngestorV4()
    meta = ingestor.inspect_source(args.source)

    targets = []
    if meta.get("is_playlist"):
        print(f"Found Playlist: {meta['title']} ({len(meta['items'])} items)")
        for item in meta["items"]:
            targets.append((item["url"], item["title"]))
    else:
        src_path = Path(args.source).resolve()
        if src_path.is_dir():
            print(f"Scanning directory: {src_path}")
            found_files = MediaIngestorV4.scan_directory(src_path, recursive=False)
            for f in found_files:
                targets.append((str(f), f.stem))
            print(f"Found {len(targets)} media files in directory.")
        else:
            targets.append((args.source, meta.get("title", "Recording")))

    total = len(targets)
    print(f"\nProcessing {total} targets in batch queue...")
    for idx, (target_src, title) in enumerate(targets, 1):
        print(f"\n{'='*65}")
        print(f"[{idx}/{total}] Processing: {title}")
        print(f"{'='*65}")
        try:
            pipeline.process(
                source=target_src,
                playbook_name=args.playbook,
                custom_name=title,
                progress_callback=lambda s, p: print(f"  [{p:3d}%] {s}"),
            )
        except Exception as e:
            print(f"  Failed target {title}: {e}", file=sys.stderr)


def cmd_audit(args):
    """Inspect persistent audit logs, usage metrics, and unused transcriptions."""
    logger = TranscriptionAuditLogger(AUDIT_DB_PATH, AUDIT_LOG_JSONL_PATH)

    if args.mark_used:
        ok = logger.mark_job_used(args.mark_used, action="cli_inspected")
        if ok:
            print(f"✓ Marked job '{args.mark_used}' as used.")
        else:
            print(f"✗ Job '{args.mark_used}' not found in audit log.", file=sys.stderr)
            sys.exit(1)
        return

    summary = logger.get_audit_summary()
    entries = logger.list_audit_entries(
        limit=args.limit,
        used_only=False if args.unused else None
    )

    print("\nPersistent Transcription Audit Summary:")
    print("=" * 65)
    print(f"  Total Jobs Logged:  {summary['total_transcriptions_logged']}")
    print(f"  Completed:          {summary['completed']}")
    print(f"  Failed:             {summary['failed']}")
    print(f"  Cancelled:          {summary['cancelled']}")
    print(f"  Used / Consumed:    {summary['used']}")
    print(f"  Unused / Pending:   {summary['unused']}")
    print(f"  SQLite Audit DB:    {logger.db_path}")
    print(f"  JSONL Audit Stream: {logger.jsonl_path}")
    print()

    title_label = "Unused Jobs" if args.unused else f"Latest {len(entries)} Jobs"
    print(f"Audit Records ({title_label}):")
    print(f"{'Job ID':<14} | {'Status':<11} | {'Playbook':<16} | {'Usage':<8} | {'Created (UTC)':<19} | {'ISO Title / File'}")
    print("-" * 95)
    for row in entries:
        title = row.get("custom_name") or Path(row.get("source", "")).name
        used_str = "USED" if row.get("used_flag") else "UNUSED"
        dt_str = row.get("created_at", "")[:19].replace("T", " ")
        print(f"{row['job_id']:<14} | {row['status']:<11} | {row.get('playbook',''):<16} | {used_str:<8} | {dt_str:<19} | {title[:30]}")


def cmd_catalog(args):
    """Scan and process items from a channel or RSS feed with idempotency."""
    catalog = MediaCatalog(db_path=CATALOG_DB_PATH)
    ingestor = MediaIngestorV4(catalog=catalog)
    pipeline = TranscriptionPipelineV6(
        output_dir=Path(args.output) if args.output else TRANSCRIPTS_DIR,
        clustering_mode=args.clustering,
    )

    print(f"Inspecting catalog source: {args.source}")
    meta = ingestor.inspect_source(args.source, limit=args.limit)
    items = meta.get("items", [])

    if not items:
        print(f"Source: {meta['title']} (Single item)")
        items = [{
            "id": meta.get("id", "single_item"),
            "title": meta.get("title", "Recording"),
            "url": args.source,
            "duration": meta.get("duration", 0),
            "date": meta.get("date", ""),
        }]

    print(f"Discovered {len(items)} items in feed/channel.")
    registered = catalog.register_discovered_items(args.source, items)
    print(f"Registered/updated {registered} items in persistent catalog database.")

    to_process = []
    for item in items:
        if args.force or catalog.is_pending(item["url"]):
            to_process.append(item)
        else:
            print(f"  [Skipping] Already completed: {item['title']}")

    print(f"\n{len(to_process)} items pending transcription.")
    if args.dry_run:
        print("Dry run requested. Exiting without processing.")
        return

    for idx, item in enumerate(to_process, 1):
        print(f"\n{'='*65}")
        print(f"[{idx}/{len(to_process)}] Processing: {item['title']}")
        print(f"{'='*65}")
        try:
            pipeline.process(
                source=item["url"],
                playbook_name=args.playbook,
                custom_name=item["title"],
                progress_callback=lambda s, p: print(f"  [{p:3d}%] {s}"),
            )
        except Exception as e:
            print(f"  Failed: {e}", file=sys.stderr)


def cmd_catalog_status(args):
    """Show catalog database summary statistics and recent discovered items."""
    catalog = MediaCatalog(db_path=CATALOG_DB_PATH)
    stats = catalog.get_stats()
    print("\nMedia Catalog Summary Statistics:")
    print("=" * 45)
    print(f"  Total Discovered: {stats['total_discovered']}")
    print(f"  Completed:        {stats['completed']}")
    print(f"  Pending:          {stats['pending']}")
    print(f"  Failed:           {stats['failed']}")
    print(f"  Database Path:    {CATALOG_DB_PATH}")

    recent = catalog.get_recent_items(limit=10)
    if recent:
        print("\nRecent Catalog Items:")
        print(f"{'Status':<12} | {'Title':<40} | {'URL'}")
        print("-" * 80)
        for r in recent:
            print(f"{r['status']:<12} | {r['title'][:38]:<40} | {r['source_url']}")


def cmd_queue(args):
    """Inspect the background persistent job queue."""
    q = JobQueue(db_path=QUEUE_DB_PATH)
    jobs = q.list_jobs(limit=args.limit)
    print(f"\nBackground Job Queue (Showing up to {args.limit}):")
    print(f"{'Job ID':<14} | {'Status':<12} | {'Progress':<8} | {'Playbook':<18} | {'Source'}")
    print("-" * 80)
    for j in jobs:
        print(f"{j['job_id']:<14} | {j['status']:<12} | {j.get('progress', 0):>3}%     | {j.get('playbook',''):<18} | {j['source_url'][:35]}")


def cmd_playbooks(args):
    """List or validate domain playbooks."""
    loader = PlaybookLoaderV3()
    if args.validate:
        p_path = Path(args.validate).resolve()
        if not p_path.exists():
            print(f"Error: Playbook file '{p_path}' not found.", file=sys.stderr)
            sys.exit(1)
        valid, err = loader.validate_file(p_path)
        if valid:
            print(f"✓ Playbook '{p_path.name}' passed strict JSON Schema v7 validation.")
        else:
            print(f"✗ Playbook '{p_path.name}' validation FAILED:\n  {err}", file=sys.stderr)
            sys.exit(1)
        return

    playbooks = loader.list_available()
    print("\nAvailable Domain Playbooks:")
    print(f"{'Name':<20} | {'Roles':<35} | {'Description'}")
    print("-" * 85)
    for p in playbooks:
        roles_str = ", ".join(p["roles"][:4]) + ("..." if len(p["roles"]) > 4 else "")
        print(f"{p['name']:<20} | {roles_str:<35} | {p['description']}")


def cmd_speakers(args):
    """List or rename speaker biometrics profiles."""
    lib_path = Path(args.library) if args.library else None
    spk_db = SpeakerDatabaseV3(library_path=lib_path)

    if args.rename:
        spk_id, new_name = args.rename
        if spk_id not in spk_db.profiles:
            print(f"Error: Speaker '{spk_id}' not found in database.", file=sys.stderr)
            sys.exit(1)
        spk_db.profiles[spk_id]["name"] = new_name
        spk_db.save()
        print(f"✓ Successfully renamed '{spk_id}' to '{new_name}'.")
        return

    print("\nSpeaker Biometric Voice Profiles:")
    print(f"{'Speaker ID':<15} | {'Assigned Name':<25} | {'Samples':<8} | {'Embedding Centroid'}")
    print("-" * 75)
    for s_id, data in spk_db.profiles.items():
        name = data.get("name", s_id)
        samples = data.get("sample_count", 1)
        norm = data.get("centroid_norm", 1.0)
        print(f"{s_id:<15} | {name:<25} | {samples:<8} | 192-D (norm: {norm:.3f})")


def cmd_email(args):
    """Deliver transcripts via email or outbox."""
    from src.engine.mailer_v1 import TranscriptMailerV1
    mailer = TranscriptMailerV1()
    print(f"Searching for {args.count} recent transcripts to deliver to {args.target}...")
    results = mailer.deliver_recent_transcripts(
        transcripts_dir=TRANSCRIPTS_DIR,
        target_email=args.target,
        limit=args.count,
    )
    print(f"Dispatch summary: {len(results)} items processed.")
    for r in results:
        status_tag = "DELIVERED" if r["status"] == "sent" else "STAGED"
        path_info = f" ({r['outbox_path']})" if r.get("outbox_path") else ""
        print(f"  {status_tag:<10} {r['subject']}{path_info}")


def main():
    parser = argparse.ArgumentParser(
        description="Universal Transcriber CLI (v6) • Engineered by @seanbuilds\n"
                    "Autonomous, Apple Silicon-accelerated speech transcription & diarization platform."
    )
    parser.add_argument(
        "--version", action="version", version="Universal Transcriber v6.0.0 (@seanbuilds)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # local
    p_local = subparsers.add_parser("local", help="Transcribe local media file or scan directory (.m4a, .mp3, .mp4, .mov, etc.)")
    p_local.add_argument("target", help="Local media file or directory to scan")
    p_local.add_argument("--recursive", "-r", action="store_true", help="Recursively scan subdirectories if target is a folder")
    p_local.add_argument("--title", "--name", dest="title", help="Custom name/title for single file")
    p_local.add_argument("--playbook", default=DEFAULT_PLAYBOOK, help="Domain playbook")
    p_local.add_argument("--clustering", choices=["ahc", "online"], default="ahc", help="Clustering mode")
    p_local.add_argument("--library", help="Path to custom speaker profiles JSON")
    p_local.add_argument("--output", help="Custom output directory")
    p_local.set_defaults(func=cmd_local)

    # transcribe
    p_transcribe = subparsers.add_parser("transcribe", help="Transcribe a video/audio source")
    p_transcribe.add_argument("input", help="URL or path to media file")
    p_transcribe.add_argument("--title", "--name", dest="title", help="Custom name/title (formatted to ISO YYYYMMDD_<Title>)")
    p_transcribe.add_argument("--playbook", default=DEFAULT_PLAYBOOK, help="Domain playbook (e.g. gaming_videos, municipal_meetings)")
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

    # audit
    p_audit = subparsers.add_parser("audit", help="Inspect persistent audit logs of every transcription attempt")
    p_audit.add_argument("--limit", type=int, default=25, help="Number of records to show")
    p_audit.add_argument("--unused", action="store_true", help="Show only unconsumed/unused transcriptions")
    p_audit.add_argument("--mark-used", dest="mark_used", help="Mark a specific job ID as used")
    p_audit.set_defaults(func=cmd_audit)

    # catalog
    p_cat = subparsers.add_parser("catalog", help="Scan YouTube channel or RSS feed with idempotency")
    p_cat.add_argument("source", help="YouTube Channel, Playlist URL, or RSS feed")
    p_cat.add_argument("--playbook", default=DEFAULT_PLAYBOOK, help="Domain playbook")
    p_cat.add_argument("--clustering", choices=["ahc", "online"], default="ahc", help="Clustering mode")
    p_cat.add_argument("--limit", type=int, default=0, help="Max items to process (0 = all)")
    p_cat.add_argument("--force", action="store_true", help="Re-transcribe items already completed")
    p_cat.add_argument("--dry-run", action="store_true", help="Scan and list items without processing")
    p_cat.add_argument("--output", help="Custom output directory")
    p_cat.set_defaults(func=cmd_catalog)

    # catalog-status
    p_cstat = subparsers.add_parser("catalog-status", help="Show catalog stats and recent discovered items")
    p_cstat.set_defaults(func=cmd_catalog_status)

    # queue
    p_queue = subparsers.add_parser("queue", help="Inspect background job queue")
    p_queue.add_argument("--limit", type=int, default=20, help="Number of records to show")
    p_queue.set_defaults(func=cmd_queue)

    # playbooks
    p_playbooks = subparsers.add_parser("playbooks", help="List or validate domain playbooks")
    p_playbooks.add_argument("--validate", help="Validate a custom playbook JSON file against Schema v7")
    p_playbooks.set_defaults(func=cmd_playbooks)

    # speakers
    p_speakers = subparsers.add_parser("speakers", help="List or rename speaker profiles")
    p_speakers.add_argument("--library", help="Path to custom speaker profiles JSON")
    p_speakers.add_argument("--rename", nargs=2, metavar=("ID", "NAME"), help="Rename speaker ID")
    p_speakers.set_defaults(func=cmd_speakers)

    # email
    p_email = subparsers.add_parser("email", help="Deliver completed transcripts via email or stage to outbox")
    p_email.add_argument("--target", default="ohheysean@gmail.com", help="Target email address")
    p_email.add_argument("--count", type=int, default=5, help="Number of recent transcripts to deliver")
    p_email.set_defaults(func=cmd_email)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
