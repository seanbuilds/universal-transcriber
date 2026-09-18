"""Security and Path Traversal Unit Tests (v2)."""

import unittest
from pathlib import Path
from app_v2 import app
from config_v2 import TRANSCRIPTS_DIR


class TestSecurity(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_path_traversal_blocked_etc_passwd(self):
        """Attempt to exfiltrate /etc/passwd via /api/file must return 403 Access Denied."""
        response = self.client.get("/api/file?path=/etc/passwd")
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Access denied", response.data)

    def test_path_traversal_blocked_dot_dot(self):
        """Attempt to traverse out of TRANSCRIPTS_DIR via ../ must return 403."""
        traversal_path = str(TRANSCRIPTS_DIR / ".." / "sensitive.txt")
        response = self.client.get(f"/api/file?path={traversal_path}")
        self.assertEqual(response.status_code, 403)

    def test_device_node_rejection(self):
        """Attempting to transcribe /dev/zero must be rejected with 400 Bad Request."""
        response = self.client.post("/api/transcribe", json={"source": "/dev/zero"})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"device nodes", response.data)


if __name__ == "__main__":
    unittest.main()
