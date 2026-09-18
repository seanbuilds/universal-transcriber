"""Unit tests for Multi-Format Transcript Exporter (v1)."""

import unittest
import tempfile
from pathlib import Path
from src.engine.export_v1 import TranscriptExporter, format_srt_timestamp


class TestExporter(unittest.TestCase):

    def test_format_srt_timestamp(self):
        self.assertEqual(format_srt_timestamp(0.0), "00:00:00,000")
        self.assertEqual(format_srt_timestamp(65.5), "00:01:05,500")
        self.assertEqual(format_srt_timestamp(3661.125), "01:01:01,125")

    def test_export_all_formats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = TranscriptExporter(base_output_dir=Path(tmpdir))
            blocks = [
                {"ts": "00:00:05", "start": 5.0, "end": 10.0, "speaker": "Host", "text": "Welcome to the show."},
                {"ts": "00:00:11", "start": 11.0, "end": 18.0, "speaker": "Guest", "text": "Thank you for having me."}
            ]
            meta = {
                "title": "Test Episode",
                "date": "2026-09-11",
                "source": "https://example.com/test",
                "duration_str": "00:01:00"
            }

            res = exporter.export(blocks, meta)
            self.assertTrue(res["md"].exists())
            self.assertTrue(res["txt"].exists())
            self.assertTrue(res["srt"].exists())
            self.assertTrue(res["json"].exists())

            # Verify Markdown formatting
            md_content = res["md"].read_text()
            self.assertIn("# Test Episode", md_content)
            self.assertIn("### [00:00:05] Host", md_content)

            # Verify SRT formatting
            srt_content = res["srt"].read_text()
            self.assertIn("00:00:05,000 --> 00:00:10,000", srt_content)


if __name__ == "__main__":
    unittest.main()
