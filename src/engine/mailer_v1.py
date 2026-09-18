"""Automated Transcript Email Delivery and Outbox Staging Engine (v1).
<!-- v1 – Transcript packaging, MIME multi-attachment email delivery, SMTP & offline outbox staging -->
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import List, Dict, Any, Optional

from config_v3 import TRANSCRIPTS_DIR
from src.engine.catalog_v1 import MediaCatalog

DEFAULT_RECIPIENT = "ohheysean@gmail.com"
DEFAULT_OUTBOX_DIR = TRANSCRIPTS_DIR / "outbox"


class TranscriptMailerV1:
    """Dispatches verbatim transcripts via SMTP or stages them into an offline outbox."""

    def __init__(
        self,
        recipient: str = DEFAULT_RECIPIENT,
        outbox_dir: Path = DEFAULT_OUTBOX_DIR,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_pass: Optional[str] = None,
    ):
        self.recipient = recipient
        self.outbox_dir = Path(outbox_dir)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        self.smtp_host = smtp_host or os.environ.get("SMTP_HOST")
        self.smtp_port = int(smtp_port or os.environ.get("SMTP_PORT", 587))
        self.smtp_user = smtp_user or os.environ.get("SMTP_USER")
        self.smtp_pass = smtp_pass or os.environ.get("SMTP_PASS")

    def package_transcript(
        self,
        transcript_dir: Path,
        title: str = "",
        recipient: Optional[str] = None,
    ) -> EmailMessage:
        """Create a MIME EmailMessage with .md and .txt transcript attachments."""
        transcript_dir = Path(transcript_dir).resolve()
        meeting_title = title or transcript_dir.name.replace("_", " ")
        to_email = recipient or self.recipient

        msg = EmailMessage()
        msg["Subject"] = f"🎙️ Verbatim Transcript: {meeting_title}"
        msg["From"] = self.smtp_user or "transcriber-daemon@local.internal"
        msg["To"] = to_email
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()

        # Find .md and .txt files in folder
        md_files = list(transcript_dir.glob("*.md"))
        txt_files = list(transcript_dir.glob("*.txt"))
        docx_files = list(transcript_dir.glob("*.docx"))

        summary_text = f"""Hello Sean,

Your automated transcription pipeline has completed processing for:
  Title:  {meeting_title}
  Folder: {transcript_dir}

Attached are the verbatim transcripts in Markdown (.md) and Plaintext (.txt) format.
Additional formats (WebVTT, SRT, DOCX) are archived locally in the transcript folder.

--
Universal Transcriber Autonomous Engine (Apple Silicon Metal Accelerated)
"""
        msg.set_content(summary_text)

        # Attach Markdown
        for md in md_files:
            try:
                content = md.read_bytes()
                msg.add_attachment(
                    content,
                    maintype="text",
                    subtype="markdown",
                    filename=md.name,
                )
            except Exception:
                pass

        # Attach Plaintext
        for txt in txt_files:
            try:
                content = txt.read_bytes()
                msg.add_attachment(
                    content,
                    maintype="text",
                    subtype="plain",
                    filename=txt.name,
                )
            except Exception:
                pass

        # Attach DOCX if present
        for docx in docx_files:
            try:
                content = docx.read_bytes()
                msg.add_attachment(
                    content,
                    maintype="application",
                    subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                    filename=docx.name,
                )
            except Exception:
                pass

        return msg

    def send(self, msg: EmailMessage) -> Dict[str, Any]:
        """Send via SMTP or stage into offline outbox directory if SMTP is unconfigured."""
        subject = msg["Subject"]
        recipient = msg["To"]

        # Attempt SMTP if host is provided
        if self.smtp_host:
            try:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15.0) as server:
                    server.starttls()
                    if self.smtp_user and self.smtp_pass:
                        server.login(self.smtp_user, self.smtp_pass)
                    server.send_message(msg)
                return {
                    "status": "sent",
                    "mode": "smtp",
                    "recipient": recipient,
                    "subject": subject,
                }
            except Exception as e:
                # Fall through to outbox staging on network/auth error
                pass

        # Offline Staging: Save .eml file into outbox
        safe_subject = "".join(c for c in subject if c.isalnum() or c in (" ", "_", "-")).strip()
        safe_subject = safe_subject.replace(" ", "_")[:60]
        eml_path = self.outbox_dir / f"{safe_subject}_{msg['Message-ID'][1:9]}.eml"

        with open(eml_path, "wb") as f:
            f.write(bytes(msg))

        return {
            "status": "staged",
            "mode": "outbox",
            "recipient": recipient,
            "subject": subject,
            "path": str(eml_path),
            "outbox_path": str(eml_path),
        }

    def deliver_recent_transcripts(
        self,
        count: int = 5,
        recipient: Optional[str] = None,
        catalog: Optional[MediaCatalog] = None,
        target_email: Optional[str] = None,
        limit: Optional[int] = None,
        transcripts_dir: Optional[Path] = None,
    ) -> List[Dict[str, Any]]:
        """Deliver up to `count` most recent completed transcripts."""
        cat = catalog or MediaCatalog()
        to_email = target_email or recipient or self.recipient
        max_count = limit if limit is not None else count
        root_dir = Path(transcripts_dir) if transcripts_dir else TRANSCRIPTS_DIR
        results = []

        if not root_dir.exists():
            return results

        # Find completed transcript folders in root_dir
        candidate_dirs = [
            d for d in root_dir.iterdir()
            if d.is_dir() and d.name not in ("outbox", "uploads") and list(d.glob("*.md"))
        ]

        # Sort by modification time (most recent first)
        candidate_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        selected = candidate_dirs[:max_count]

        for t_dir in selected:
            msg = self.package_transcript(t_dir, recipient=to_email)
            res = self.send(msg)
            results.append(res)

        return results


TranscriptMailer = TranscriptMailerV1
