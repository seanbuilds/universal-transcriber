#!/usr/bin/env python3
"""Canonical video tutorial generator script linking to generate_tutorial_videos_v1.py.
<!-- Canonical alias -->
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "generate_tutorial_videos_v1.py"
res = subprocess.run([sys.executable, str(SCRIPT)] + sys.argv[1:])
sys.exit(res.returncode)
