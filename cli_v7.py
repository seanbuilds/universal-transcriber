#!/usr/bin/env python3
"""Universal Transcriber CLI (v7).
<!-- v7 – Official 0.1-beta product release: version 0.1.0-beta branding, canonical config_v5 integration, and complete media orchestration -->

Usage:
  python cli.py local <File-or-Folder> [--recursive] [--title <name>] [--playbook <name>] [--clustering {ahc,online}]
  python cli.py transcribe <URL-or-File> [--title <name>] [--playbook <name>] [--clustering {ahc,online}] [--output <dir>]
  python cli.py batch <Playlist-or-Folder> [--playbook <name>] [--clustering {ahc,online}]
  python cli.py audit [--limit <N>] [--unused] [--mark-used <job_id>]
  python cli.py catalog <Channel-or-RSS> [--playbook <name>] [--limit <N>] [--force] [--dry-run]
  python cli.py catalog-status
  python cli.py queue [--limit <N>]
  python cli.py playbooks [--validate <file>]
  python cli.py speakers [--library <path>] [--rename <ID> <Name>]
  python cli.py email [--target <address>] [--count <N>]
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
from config_v5 import (
    TRANSCRIPTS_DIR,
    DEFAULT_PLAYBOOK,
    QUEUE_DB_PATH,
    CATALOG_DB_PATH,
    AUDIT_DB_PATH,
    AUDIT_LOG_JSONL_PATH,
    APP_NAME,
    VERSION,
    AUTHOR,
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


def progress_reporter(stage: str, pct: int):
    """Render terminal progress bar."""
    bar_width = 30
    filled = int(bar_width * (pct / 100))
    bar = "█" * filled + "░" * (bar_width - filled)
    print(f"\r[{bar}] {pct:3d}% | {stage:<35}", end="", flush=True)
    if pct >= 100:
        print()


def segment_reporter(seg):
    """Live stream detected transcription segment."""
    ts = seg.get("ts", "00:00:00")
    speaker = seg.get("speaker", "SPEAKER_00")
    text = seg.get("text", "").strip()
    print(f"\n  [{ts}] \033[1;36m{speaker}\033[0m: {text}")


def cmd_transcribe(args):
    """Execute single source transcription."""
    global active_job_id
    import uuid
    active_job_id = f"job_{uuid.uuid4().hex[:8]}"

    pipeline = TranscriptionPipelineV6(
        clustering_mode=args.clustering,
        speaker_library_path=args.library,
    )

    print(f"🎙️ Universal Transcriber v{VERSION} • Processing: {args.input}")
    print(f"Playbook:   {args.playbook}")
    print(f"Clustering: {args.clustering.upper()}")
    if args.title:
        print(f"ISO Title:  {args.title}")
    print("-" * 65)

    res = pipeline.process(
        source=args.input,
        playbook_name=args.playbook,
        output_dir=args.output,
        custom_name=args.title,
        job_id=active_job_id,
        progress_callback=progress_reporter,
        segment_callback=segment_reporter,
    )

    print("\n" + "=" * 65)
    print("✅ Transcription Complete!")
    print(f"Title:         {res.get('title')}")
    print(f"Duration:      {res.get('duration_str')}")
    print(f"Speakers:      {res.get('speaker_count')}")
    print(f"Word Count:    {res.get('word_count')}")
    print(f"ISO Directory: {res.get('iso_output_dir')}")
    print("\nGenerated Formats:")
    for fmt, p in res.get("files", {}).items():
        print(f"  • {fmt.upper():<5} -> {p}")
    print("=" * 65)


def cmd_local(args):
    """Transcribe local media file or scan directory."""
    target = Path(args.target).resolve()
    if not target.exists():
        print(f"❌ Error: Path does not exist: {args.target}", file=sys.stderr)
        sys.exit(1)

    ingestor = MediaIngestorV4()

    if target.is_file():
        ext = target.suffix.lower()
        if ext not in SUPPORTED_LOCAL_EXTENSIONS:
            supported_str = ", ".join(sorted(SUPPORTED_LOCAL_EXTENSIONS))
            print(f"❌ Error: Unsupported file format '{ext}'. Supported formats: {supported_str}", file=sys.stderr)
            sys.exit(1)

        args.input = str(target)
        cmd_transcribe(args)

    elif target.is_dir():
        pattern = "**/*" if args.recursive else "*"
        found_files = []
        for p in target.glob(pattern):
            if p.is_file() and p.suffix.lower() in SUPPORTED_LOCAL_EXTENSIONS:
                found_files.append(p)

        found_files.sort()
        if not found_files:
            supported_str = ", ".join(sorted(SUPPORTED_LOCAL_EXTENSIONS))
            print(f"⚠️ No supported media files found in: {target} (supported: {supported_str})")
            sys.exit(0)

        print(f"📁 Found {len(found_files)} media file(s) in {target} (recursive={args.recursive}):")
        for i, f in enumerate(found_files, 1):
            print(f"  {i:2d}. {f.name} ({f.stat().st_size / (1024*1024):.1f} MB)")
        print("-" * 65)

        for i, media_file in enumerate(found_files, 1):
            print(f"\n[{i}/{len(found_files)}] Processing: {media_file.name}")
            args.input = str(media_file)
            args.title = None
            try:
                cmd_transcribe(args)
            except Exception as e:
                print(f"❌ Failed to transcribe {media_file.name}: {e}", file=sys.stderr)


def cmd_batch(args):
    """Execute batch processing over playlist or directory."""
    pipeline = TranscriptionPipelineV6(
        clustering_mode=args.clustering,
        speaker_library_path=args.library,
    )
    print(f"📦 Universal Transcriber • Batch Processing: {args.source}")
    print(f"Playbook: {args.playbook} | Clustering: {args.clustering.upper()}")
    print("-" * 65)

    results = pipeline.process_batch(
        source=args.source,
        playbook_name=args.playbook,
        output_dir=args.output,
        progress_callback=progress_reporter,
    )

    print("\n" + "=" * 65)
    print(f"🎉 Batch Finished: {len(results)} items successfully processed.")
    for r in results:
        print(f"  • {r.get('title')} ({r.get('duration_str')}) -> {r.get('iso_output_dir')}")
    print("=" * 65)


def cmd_audit(args):
    """Inspect persistent audit trail."""
    logger = TranscriptionAuditLogger(AUDIT_DB_PATH, AUDIT_LOG_JSONL_PATH)

    if args.mark_used:
        ok = logger.mark_job_used(args.mark_used, action="cli_command")
        if ok:
            print(f"✓ Marked job {args.mark_used} as used.")
        else:
            print(f"❌ Job {args.mark_used} not found in audit log.", file=sys.stderr)
            sys.exit(1)
        return

    summary = logger.get_audit_summary()
    entries = logger.list_audit_entries(
        limit=args.limit,
        used_only=False if args.unused else None
    )

    print("=" * 65)
    print("📜 Universal Transcriber • Persistent Audit Log")
    print("=" * 65)
    print(f"Total Transcriptions: {summary.get('total_transcriptions', 0)}")
    print(f"Completed:            {summary.get('completed', 0)}")
    print(f"Failed:               {summary.get('failed', 0)}")
    print(f"Cancelled:            {summary.get('cancelled', 0)}")
    print(f"Used / Consumed:      {summary.get('used', 0)}")
    print(f"Unused / Pending:     {summary.get('unused', 0)}")
    print(f"Total Duration:       {summary.get('total_audio_duration_seconds', 0.0) / 60.0:.1f} minutes")
    print("-" * 65)
    print(f"{'TIMESTAMP':<20} | {'JOB ID':<13} | {'STATUS':<9} | {'USED':<5} | {'TITLE'}")
    print("-" * 65)

    for e in entries:
        ts = e.get("timestamp", "")[:19]
        jid = e.get("job_id", "")
        status = e.get("status", "")
        used_str = "YES" if e.get("used_flag") else "NO"
        title = e.get("title") or e.get("source", "")
        if len(title) > 40:
            title = title[:37] + "..."
        print(f"{ts:<20} | {jid:<13} | {status:<9} | {used_str:<5} | {title}")
    print("=" * 65)


def cmd_catalog(args):
    """Scan channel or RSS feed with idempotent cataloging."""
    from src.engine.ingest_v4 import MediaIngestorV4
    ingestor = MediaIngestorV4()
    cat = MediaCatalog(CATALOG_DB_PATH)
    pipeline = TranscriptionPipelineV6(
        clustering_mode=args.clustering,
    )

    print(f"📡 Universal Transcriber Catalog Ingestion: {args.source}")
    items = ingestor.extract_playlist_items(args.source)
    print(f"Discovered {len(items)} items from source.")

    new_items = []
    for it in items:
        if args.force or not cat.is_processed(it["id"]):
            new_items.append(it)

    print(f"Items to process: {len(new_items)} (Skipped {len(items) - len(new_items)} previously completed)")

    if args.dry_run:
        print("\n[Dry Run] Items that would be processed:")
        for it in new_items[:args.limit if args.limit > 0 else len(new_items)]:
            print(f"  • {it.get('title')} ({it.get('url')})")
        return

    to_process = new_items[:args.limit] if args.limit > 0 else new_items
    for i, it in enumerate(to_process, 1):
        print(f"\n[{i}/{len(to_process)}] Processing: {it.get('title')}")
        cat.mark_discovered(it["id"], it.get("url"), it.get("title"))
        try:
            res = pipeline.process(
                source=it["url"],
                playbook_name=args.playbook,
                output_dir=args.output,
                progress_callback=progress_reporter,
            )
            cat.mark_completed(
                video_id=it["id"],
                output_dir=res.get("iso_output_dir", ""),
                duration=res.get("duration", 0),
                speakers=res.get("speaker_count", 0),
            )
        except Exception as e:
            cat.mark_failed(it["id"], str(e))
            print(f"❌ Failed: {e}", file=sys.stderr)


def cmd_catalog_status(args):
    """Show catalog database summary."""
    cat = MediaCatalog(CATALOG_DB_PATH)
    stats = cat.get_stats()
    items = cat.get_recent_items(limit=15)

    print("=" * 65)
    print("📊 Universal Transcriber Media Catalog Status")
    print("=" * 65)
    print(f"Total Discovered: {stats.get('total', 0)}")
    print(f"Completed:        {stats.get('completed', 0)}")
    print(f"Pending:          {stats.get('pending', 0)}")
    print(f"Failed:           {stats.get('failed', 0)}")
    print("-" * 65)
    print(f"{'DISCOVERED':<19} | {'STATUS':<9} | {'TITLE'}")
    print("-" * 65)
    for it in items:
        ts = it.get("discovered_at", "")[:19]
        st = it.get("status", "")
        title = it.get("title", "")
        if len(title) > 40:
            title = title[:37] + "..."
        print(f"{ts:<19} | {st:<9} | {title}")
    print("=" * 65)


def cmd_queue(args):
    """Show background queue status."""
    jq = JobQueue(QUEUE_DB_PATH)
    jobs = jq.list_jobs(limit=args.limit)

    print("=" * 65)
    print(f"📋 Pipeline Background Queue (Last {len(jobs)} jobs)")
    print("=" * 65)
    print(f"{'JOB ID':<12} | {'STATUS':<10} | {'STAGE / ERROR':<20} | {'URL'}")
    print("-" * 65)
    for j in jobs:
        msg = j.get("error_message") or j.get("stage_message") or ""
        if len(msg) > 20:
            msg = msg[:17] + "..."
        url = j.get("source_url", "")
        if len(url) > 30:
            url = url[:27] + "..."
        print(f"{j.get('job_id'):<12} | {j.get('status'):<10} | {msg:<20} | {url}")
    print("=" * 65)


def cmd_playbooks(args):
    """List or validate domain playbooks."""
    loader = PlaybookLoaderV3()

    if args.validate:
        p = Path(args.validate).resolve()
        if not p.exists():
            print(f"❌ File not found: {p}", file=sys.stderr)
            sys.exit(1)
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            is_valid, err = loader.validate_dict(data)
            if is_valid:
                print(f"✅ Playbook '{p.name}' strictly conforms to Schema v7!")
            else:
                print(f"❌ Playbook validation failed: {err}", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"❌ Error reading JSON: {e}", file=sys.stderr)
            sys.exit(1)
        return

    pbs = loader.list_available()
    print("=" * 65)
    print("📚 Universal Transcriber • Available Domain Playbooks")
    print("=" * 65)
    for pb in pbs:
        print(f"\n• \033[1;33m{pb.get('name')}\033[0m (v{pb.get('version')})")
        print(f"  Description: {pb.get('description')}")
        print(f"  Speakers:    {pb.get('expected_speakers', 'dynamic')}")
        print(f"  Formatting:  {pb.get('formatting', {}).get('style', 'standard')}")
        terms = pb.get("terminology", [])
        if terms:
            print(f"  Terms:       {len(terms)} custom domain vocabulary entries")
    print("=" * 65)


def cmd_speakers(args):
    """List or rename acoustic speaker profiles."""
    sdb = SpeakerDatabaseV3(library_path=args.library)

    if args.rename:
        spk_id, new_name = args.rename
        if spk_id not in sdb.profiles:
            print(f"❌ Speaker ID '{spk_id}' not found in database.", file=sys.stderr)
            sys.exit(1)
        sdb.profiles[spk_id]["name"] = new_name
        sdb.save()
        print(f"✅ Renamed speaker '{spk_id}' to '{new_name}'")
        return

    print("=" * 65)
    print(f"👥 Acoustic Speaker Profiles ({len(sdb.profiles)} registered)")
    print(f"Database: {sdb.library_path}")
    print("=" * 65)
    print(f"{'SPEAKER ID':<15} | {'NAME':<25} | {'SAMPLES':<8} | {'EMBEDDING'}")
    print("-" * 65)
    for s_id, data in sorted(sdb.profiles.items()):
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
        description=f"{APP_NAME} CLI (v{VERSION}) • Engineered by @{AUTHOR}\n"
                    "Autonomous, Apple Silicon-accelerated speech transcription & diarization platform."
    )
    parser.add_argument(
        "--version", action="version", version=f"{APP_NAME} v{VERSION} (@{AUTHOR})"
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
