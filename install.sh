#!/usr/bin/env bash
# Canonical installer entrypoint for Universal Transcriber (0.1-beta).
# <!-- Canonical alias executing install_v1.sh -->

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/install_v1.sh" "$@"
