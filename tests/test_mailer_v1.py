"""Unit tests for TranscriptMailerV1 (v1).
<!-- v1 – Testing MIME packaging, attachment verification, and outbox staging -->
"""

import email
import tempfile
import unittest
from pathlib import Path

from src.engine.mailer_v1 import TranscriptMailerV1


class TestTranscriptMailerV1(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.outbox_dir = self.tmp_dir / "outbox"
        self.mailer = TranscriptMailerV1(
            recipient="ohheysean@gmail.com",
            outbox_dir=self.outbox_dir,
        )

        # Create a mock completed transcript folder
        self.transcript_dir = self.tmp_dir / "2026-09-16_School_Committee"
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        (self.transcript_dir / "transcript.md").write_text("# Verbatim Transcript\n\n[00:00:00] Chair: Order.")
        (self.transcript_dir / "transcript.txt").write_text("[00:00:00] Chair: Order.")

    def test_package_transcript_creates_valid_mime(self):
        """Transcript packaging produces valid MIME message with attachments."""
        msg = self.mailer.package_transcript(self.transcript_dir, title="School Committee Meeting")
        self.assertEqual(msg["To"], "ohheysean@gmail.com")
        self.assertIn("School Committee Meeting", msg["Subject"])

        attachments = [part.get_filename() for part in msg.iter_attachments()]
        self.assertIn("transcript.md", attachments)
        self.assertIn("transcript.txt", attachments)

    def test_send_stages_eml_in_outbox(self):
        """When SMTP is unconfigured, send() stages an RFC 822 .eml packet in outbox."""
        msg = self.mailer.package_transcript(self.transcript_dir)
        res = self.mailer.send(msg)

        self.assertEqual(res["status"], "staged")
        self.assertEqual(res["mode"], "outbox")
        self.assertTrue(Path(res["path"]).exists())

        # Verify parsing of the written .eml file
        with open(res["path"], "rb") as f:
            parsed = email.message_from_binary_file(f)
            self.assertEqual(parsed["To"], "ohheysean@gmail.com")

    def test_deliver_recent_transcripts(self):
        """deliver_recent_transcripts stages up to N most recent folders."""
        with tempfile.TemporaryDirectory() as base_tmp:
            base_dir = Path(base_tmp)
            for i in range(3):
                d = base_dir / f"Meeting_{i}"
                d.mkdir()
                (d / "notes.md").write_text(f"Meeting {i}")

            outbox = base_dir / "outbox"
            mailer = TranscriptMailerV1(recipient="test@example.com", outbox_dir=outbox)

            # Patch TRANSCRIPTS_DIR to base_dir
            from unittest.mock import patch
            with patch("src.engine.mailer_v1.TRANSCRIPTS_DIR", base_dir):
                results = mailer.deliver_recent_transcripts(count=2)

            self.assertEqual(len(results), 2)
            for r in results:
                self.assertEqual(r["status"], "staged")
                self.assertTrue(Path(r["path"]).exists())


if __name__ == "__main__":
    unittest.main()
