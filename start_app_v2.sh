#!/usr/bin/env bash
# ==============================================================================
# 🎙️ Universal Transcriber • 1-Click Launch Script (v2)
# <!-- v2 – Launch canonical app.py, pre-flight model check, and 0.1-beta branding -->
# Release: 0.1-beta (v0.1.0-beta)
# Engineered by @seanbuilds (Sean Tyler)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "🎙️  Universal Transcriber • 1-Click Launcher"
echo "    Release: v0.1.0-beta • Engineered by @seanbuilds"
echo "========================================================"

# Determine Python interpreter
PYTHON_BIN=""
for candidate in \
    "/opt/homebrew/opt/python@3.14/bin/python3" \
    "/opt/homebrew/opt/python@3.13/bin/python3" \
    "/opt/homebrew/opt/python@3.12/bin/python3" \
    "/opt/homebrew/bin/python3" \
    "$(command -v python3 2>/dev/null)"
do
    if [ -x "$candidate" ]; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Error: Python 3 not found. Please run ./install.sh"
    exit 1
fi

echo "✓ Python runtime: $PYTHON_BIN ($($PYTHON_BIN --version))"

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
    echo "   Please run ./install.sh to automatically install missing dependencies."
    exit 1
fi
echo "✓ System utilities verified (ffmpeg, whisper-cli, yt-dlp)"

# Pre-flight Whisper model check
MODELS_DIR="$HOME/.cache/universal_transcriber/models"
if [ ! -f "$MODELS_DIR/ggml-base.en.bin" ] && [ ! -f "$MODELS_DIR/ggml-small.en.bin" ]; then
    echo "⚠️  Whisper models missing from $MODELS_DIR. Running installer to fetch them..."
    bash ./install.sh
fi

# Check if server is already responding on port 5055
if curl -s -m 2 http://127.0.0.1:5055/api/info &>/dev/null; then
    echo "✓ Universal Transcriber server is already running on http://127.0.0.1:5055"
else
    echo "🚀 Launching Universal Transcriber web daemon (app.py)..."
    mkdir -p ~/.cache/universal_transcriber
    nohup "$PYTHON_BIN" app.py > ~/.cache/universal_transcriber/web_server.log 2>&1 &
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
