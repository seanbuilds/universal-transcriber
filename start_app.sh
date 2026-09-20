#!/usr/bin/env bash
# Canonical 1-click launch script for Universal Transcriber (0.1-beta).
# <!-- Canonical alias executing start_app_v2.sh -->

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/start_app_v2.sh" "$@"
