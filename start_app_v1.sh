#!/usr/bin/env bash
# 🎙️ Universal Transcriber • 1-Click Launch Script (v1)
# <!-- v1 – Automated environment check, dependency verification, background server launch, and browser open -->
# Engineered by @seanbuilds

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "🎙️  Universal Transcriber • 1-Click Launcher"
echo "    Engineered by @seanbuilds"
echo "========================================================"

# Determine Python interpreter
PYTHON_BIN=""
if [ -x "/opt/homebrew/opt/python@3.14/bin/python3" ]; then
    PYTHON_BIN="/opt/homebrew/opt/python@3.14/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "❌ Error: Python 3 not found. Please install Python 3.12+ via Homebrew:"
    echo "   brew install python@3.14"
    exit 1
fi

echo "✓ Using Python: $PYTHON_BIN ($($PYTHON_BIN --version))"

# Check system tools
MISSING_TOOLS=()
for tool in ffmpeg yt-dlp; do
    if ! command -v "$tool" &>/dev/null; then
        MISSING_TOOLS+=("$tool")
    fi
done

if ! command -v whisper-cli &>/dev/null && ! command -v whisper-cpp &>/dev/null; then
    MISSING_TOOLS+=("whisper.cpp")
fi

if [ ${#MISSING_TOOLS[@]} -gt 0 ]; then
    echo "⚠️  Missing system utilities: ${MISSING_TOOLS[*]}"
    echo "   Please install them via Homebrew:"
    echo "   brew install ${MISSING_TOOLS[*]}"
    exit 1
fi
echo "✓ System utilities verified (ffmpeg, whisper-cli, yt-dlp)"

# Check if app is already running on port 5055
if curl -s -m 2 http://127.0.0.1:5055/api/info &>/dev/null; then
    echo "✓ Universal Transcriber server is already running on http://127.0.0.1:5055"
else
    echo "🚀 Launching Universal Transcriber web daemon (app_v5.py)..."
    mkdir -p ~/.cache/universal_transcriber
    nohup "$PYTHON_BIN" app_v5.py > ~/.cache/universal_transcriber/web_server.log 2>&1 &
    SERVER_PID=$!
    echo "✓ Web server process started (PID: $SERVER_PID)"
    
    # Wait for server to bind port
    echo "⏳ Waiting for server to become ready..."
    MAX_ATTEMPTS=15
    ATTEMPT=0
    while ! curl -s -m 1 http://127.0.0.1:5055/api/info &>/dev/null; do
        sleep 1
        ATTEMPT=$((ATTEMPT + 1))
        if [ $ATTEMPT -ge $MAX_ATTEMPTS ]; then
            echo "❌ Server failed to respond within 15 seconds. Check logs at:"
            echo "   ~/.cache/universal_transcriber/web_server.log"
            exit 1
        fi
    done
    echo "✓ Server is live and responding at http://127.0.0.1:5055"
fi

# Open browser
echo "🌐 Opening web dashboard in default browser..."
open "http://127.0.0.1:5055"

echo "========================================================"
echo "🎉 Universal Transcriber is ready!"
echo "   Dashboard: http://127.0.0.1:5055"
echo "   Logs:      ~/.cache/universal_transcriber/web_server.log"
echo "========================================================"
