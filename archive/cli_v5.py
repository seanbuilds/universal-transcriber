#!/usr/bin/env python3
"""Universal Transcriber CLI (v5).
<!-- v5 – Persistent audit trail inspection, ISO-8601 YYYYMMDD custom naming, gaming playbook support, and multi-format exports -->

Usage:
  python cli_v5.py transcribe <URL-or-File> [--title <name>] [--playbook <name>] [--clustering {ahc,online}] [--output <dir>]
  python cli_v5.py batch <Playlist-or-Folder> [--playbook <name>] [--clustering {ahc,online}]
  python cli_v5.py audit [--limit <N>] [--unused] [--mark-used <job_id>]
  python cli_v5.py catalog <Channel-or-RSS> [--playbook <name>] [--limit <N>] [--force] [--dry-run]
  python cli_v5.py catalog-status
  python cli_v5.py queue [--limit <N>]
  python cli_v5.py playbooks [--validate <file>]
  python cli_v5.py speakers [--library <path>] [--rename <ID> <Name>]
  python cli_v5.py email [--target <address>] [--count <N>]
"""

import argparse
import json
import os
import signal
import sys
from pathlib import Path

from src.engine.pipeline_v5 import TranscriptionPipelineV5
from src.engine.diarize_v3 import SpeakerDatabaseV3
from src.engine.queue_v2 import JobQueue
from src.engine.catalog_v1 import MediaCatalog
from src.engine.audit_v1 import TranscriptionAuditLogger
from src.engine.ingest_v3 import MediaIngestorV3
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
            pipeline = TranscriptionPipelineV5()
            pipeline.cancel(active_job_id, reason="Process interrupted by user (SIGINT)")
            ingestor = MediaIngestorV3()
            ingestor.cleanup_job(active_job_id)
        except Exception:
            pass
    sys.exit(130)


signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGTERM, sigint_handler)


def cmd_transcribe(args):
    """Run transcription on a single file or URL with ISO naming and audit tracking."""
    global active_job_id
    library_path = Path(args.library) if args.library else None
    pipeline = TranscriptionPipelineV5(
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

    print("Starting transcription (v5 Streaming & Audit Engine):")
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
    pipeline = TranscriptionPipelineV5(
        output_dir=Path(args.output) if args.output else TRANSCRIPTS_DIR,
        clustering_mode=args.clustering,
        speaker_library_path=library_path,
    )
    ingestor = MediaIngestorV3()
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
            for ext in ("*.mp4", "*.mov", "*.mkv", "*.m4a", "*.mp3", "*.wav"):
                for f in sorted(src_path.glob(ext)):
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
    print(f"  SQLite Audit DB:    {AUDIT_DB_PATH}")
    print(f"  JSONL Audit Stream: {AUDIT_LOG_JSONL_PATH}")

    filter_desc = "Unused Jobs" if args.unused else f"Latest {len(entries)} Jobs"
    print(f"\nAudit Records ({filter_desc}):")
    print(f"{'Job ID':<14} | {'Status':<11} | {'Playbook':<16} | {'Usage':<8} | {'Created (UTC)':<19} | {'ISO Title / File'}")
    print("-" * 95)
    for e in entries:
        created = e.get("created_at", "")[:19].replace("T", " ")
        usage = "USED" if e.get("used_flag") == 1 else "UNUSED"
        title = e.get("custom_name") or (e.get("export_dir") or "").split("/")[-1] or "(Untitled)"
        print(f"{e['job_id']:<14} | {e['status']:<11} | {e['playbook']:<16} | {usage:<8} | {created:<19} | {title[:28]}")


def cmd_catalog(args):
    """Scan YouTube channel, playlist, or RSS feed with SQLite idempotency."""
    catalog = MediaCatalog(CATALOG_DB_PATH)
    ingestor = MediaIngestorV3(catalog=catalog)

    print(f"Scanning catalog source: {args.source}")
    unprocessed = ingestor.discover_catalog(args.source, force=args.force, limit=args.limit)

    if args.limit and args.limit > 0:
        unprocessed = unprocessed[:args.limit]

    print(f"Discovered {len(unprocessed)} unprocessed items (Force={args.force}).")
    for i, it in enumerate(unprocessed, 1):
        print(f"  [{i}] {it.get('title', 'Untitled')} ({it['url']})")

    if args.dry_run:
        print("\nDry run mode enabled. No transcription performed.")
        return

    if not unprocessed:
        print("All catalog items are already transcribed. Nothing to do.")
        return

    pipeline = TranscriptionPipelineV5(
        output_dir=Path(args.output) if args.output else TRANSCRIPTS_DIR,
        clustering_mode=args.clustering,
    )

    for i, item in enumerate(unprocessed, 1):
        print(f"\n{'='*65}")
        print(f"[{i}/{len(unprocessed)}] Ingesting from catalog: {item.get('title')}")
        print(f"{'='*65}")
        try:
            pipeline.process(
                source=item["url"],
                playbook_name=args.playbook,
                progress_callback=lambda s, p: print(f"  [{p:3d}%] {s}"),
            )
        except Exception as e:
            print(f"  Error processing catalog item: {e}", file=sys.stderr)


def cmd_catalog_status(args):
    """Display summary of discovered and transcribed catalog items."""
    catalog = MediaCatalog(CATALOG_DB_PATH)
    stats = catalog.get_stats()
    entries = catalog.list_entries(limit=30)

    print("\nMedia Catalog Status:")
    print("=" * 65)
    for k, v in stats.items():
        print(f"  {k.capitalize():<15}: {v}")
    print("\nLatest 30 Catalog Entries:")
    print(f"{'Item ID':<18} | {'Status':<12} | {'Discovered':<19} | {'Title'}")
    print("-" * 75)
    for e in entries:
        disc = e.get("discovered_at", "")[:19]
        print(f"{e['item_id']:<18} | {e['status']:<12} | {disc:<19} | {e.get('title', '')[:30]}")


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
    """List or validate domain playbooks."""
    loader = PlaybookLoaderV3()
    if args.validate:
        p = Path(args.validate).resolve()
        if not p.exists():
            print(f"File not found: {p}", file=sys.stderr)
            sys.exit(1)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            valid, err = loader.validate_dict(data)
            if valid:
                print(f"✓ Playbook '{p.name}' is VALID according to JSON Schema v7.")
            else:
                print(f"✗ Playbook validation FAILED: {err}", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
        return

    pbs = loader.list_available()
    print("Available Domain Playbooks (Validated against JSON Schema v7):")
    print("=" * 75)
    for p in pbs:
        print(f" • {p['name']:<22} (Default Role: {p['default_role']}, Roster: {p['roster_count']} members)")
        if p.get('description'):
            print(f"   {p['description']}")
        print()


def cmd_speakers(args):
    """Inspect or manage persistent speaker voice library."""
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
    print("-" * 65)
    for spk_id, prof in sorted(db.profiles.items()):
        name = prof.get("name", spk_id)
        count = prof.get("sample_count", 1)
        print(f"{spk_id:<14} | {name:<25} | {count:<8}")


def cmd_email(args):
    """Deliver completed transcripts via email or stage them to outbox."""
    from src.engine.mailer_v1 import TranscriptMailerV1
    mailer = TranscriptMailerV1(recipient=args.target)
    print(f"Dispatching recent transcripts to: {args.target}")
    results = mailer.deliver_recent_transcripts(count=args.count, recipient=args.target)
    if not results:
        print("No completed transcripts found to deliver.")
        return

    print(f"\nDispatched {len(results)} transcript(s):")
    for r in results:
        status_tag = f"[{r['status'].upper()}]"
        path_info = f" -> {r['path']}" if "path" in r else ""
        print(f"  {status_tag:<10} {r['subject']}{path_info}")


def main():
    parser = argparse.ArgumentParser(description="Universal Transcriber CLI (v5)")
    subparsers = parser.add_subparsers(dest="command", required=True)

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
