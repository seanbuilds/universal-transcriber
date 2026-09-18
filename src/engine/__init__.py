"""Core processing engine modules for Universal Transcriber."""
from pathlib import Path

# Allow transparent resolution of archived historical modules (v1-v4)
_archive_dir = str(Path(__file__).parent / "archive")
if _archive_dir not in __path__:
    __path__.append(_archive_dir)
