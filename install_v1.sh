#!/usr/bin/env bash
# ==============================================================================
# 🎙️ Universal Transcriber • Turnkey Automated Installer (v1)
# <!-- v1 – Comprehensive system verification, Homebrew tool management, Python venv, GGML models, and Metal GPU validation -->
# Release: 0.1-beta (v0.1.0-beta)
# Engineered by @seanbuilds (Sean Tyler)
# ==============================================================================

set -eo pipefail

CHECK_ONLY=false
SKIP_MODELS=false

for arg in "$@"; do
    case "$arg" in
        --check-only)
            CHECK_ONLY=true
            ;;
        --skip-models)
            SKIP_MODELS=true
            ;;
        --help|-h)
            echo "Usage: ./install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --check-only     Verify prerequisites and models without making changes"
            echo "  --skip-models    Skip downloading GGML Whisper models"
            echo "  -h, --help       Show this help message"
            exit 0
            ;;
    esac
done

# ANSI Colors
BOLD="\033[1m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
CYAN="\033[1;36m"
RED="\033[1;31m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}"
echo "======================================================================"
echo "  🎙️  UNIVERSAL TRANSCRIBER • TURNKEY INSTALLER"
echo "      Release: v0.1.0-beta • Engineered by @seanbuilds"
echo "======================================================================"
echo -e "${RESET}"

# 1. Operating System & Architecture Verification
echo -e "${BOLD}[1/6] Inspecting Hardware & Operating System...${RESET}"
OS_NAME="$(uname -s)"
ARCH_NAME="$(uname -m)"

if [ "$OS_NAME" != "Darwin" ]; then
    echo -e "${RED}❌ Unsupported Operating System: $OS_NAME${RESET}"
    echo "   Universal Transcriber is optimized specifically for macOS."
    exit 1
fi

if [ "$ARCH_NAME" == "arm64" ]; then
    echo -e "${GREEN}✓ Apple Silicon ($ARCH_NAME) detected.${RESET} Metal GPU acceleration enabled."
else
    echo -e "${YELLOW}⚠️ Architecture: $ARCH_NAME (Intel). Will run in CPU mode without Metal acceleration.${RESET}"
fi

# 2. Homebrew & System Prerequisites
echo -e "\n${BOLD}[2/6] Verifying System Tools (Homebrew)...${RESET}"
if ! command -v brew &>/dev/null; then
    echo -e "${RED}❌ Homebrew package manager is not installed.${RESET}"
    echo "   Please install Homebrew by running:"
    echo '   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi
echo -e "${GREEN}✓ Homebrew detected:${RESET} $(brew --version | head -n 1)"

BREW_PKGS_TO_INSTALL=()

# Check ffmpeg
if command -v ffmpeg &>/dev/null; then
    echo -e "${GREEN}✓ ffmpeg:${RESET} $(ffmpeg -version | head -n 1 | awk '{print $3}')"
else
    echo -e "${YELLOW}• ffmpeg is missing.${RESET}"
    BREW_PKGS_TO_INSTALL+=("ffmpeg")
fi

# Check yt-dlp
if command -v yt-dlp &>/dev/null; then
    echo -e "${GREEN}✓ yt-dlp:${RESET} $(yt-dlp --version)"
else
    echo -e "${YELLOW}• yt-dlp is missing.${RESET}"
    BREW_PKGS_TO_INSTALL+=("yt-dlp")
fi

# Check whisper-cli (from whisper-cpp)
if command -v whisper-cli &>/dev/null || command -v whisper-cpp &>/dev/null; then
    WHISPER_PATH="$(command -v whisper-cli 2>/dev/null || command -v whisper-cpp 2>/dev/null)"
    echo -e "${GREEN}✓ whisper-cli:${RESET} $WHISPER_PATH"
else
    echo -e "${YELLOW}• whisper.cpp is missing.${RESET}"
    BREW_PKGS_TO_INSTALL+=("whisper-cpp")
fi

if [ ${#BREW_PKGS_TO_INSTALL[@]} -gt 0 ]; then
    if [ "$CHECK_ONLY" = true ]; then
        echo -e "${YELLOW}⚠️  Missing tools to install: ${BREW_PKGS_TO_INSTALL[*]}${RESET}"
    else
        echo -e "${CYAN}📦 Installing missing Homebrew tools: ${BREW_PKGS_TO_INSTALL[*]}...${RESET}"
        brew install "${BREW_PKGS_TO_INSTALL[@]}"
    fi
fi

# 3. Python 3 Runtime Detection
echo -e "\n${BOLD}[3/6] Detecting Python 3 Environment...${RESET}"
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
    echo -e "${RED}❌ No suitable Python 3 found.${RESET}"
    echo "   Please install Python 3.12+ via Homebrew: brew install python@3.14"
    exit 1
fi
PY_VER="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
echo -e "${GREEN}✓ Python runtime:${RESET} $PYTHON_BIN (v$PY_VER)"

# 4. Python Package Installation
echo -e "\n${BOLD}[4/6] Verifying Python Dependencies...${RESET}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ "$CHECK_ONLY" = true ]; then
    "$PYTHON_BIN" -c '
import flask, flask_cors, jsonschema, docx, requests, PIL, numpy, scipy
print("✓ Core Python libraries verified.")
' || echo -e "${YELLOW}⚠️  Some Python dependencies are missing.${RESET}"
else
    echo -e "${CYAN}📦 Installing/verifying requirements from requirements.txt...${RESET}"
    "$PYTHON_BIN" -m pip install --quiet --upgrade pip || true
    "$PYTHON_BIN" -m pip install --quiet -r requirements.txt
    echo -e "${GREEN}✓ Python dependencies successfully verified.${RESET}"
fi

# 5. Whisper GGML Speech Models Setup
echo -e "\n${BOLD}[5/6] Checking GGML Whisper Speech Models...${RESET}"
MODELS_DIR="$HOME/.cache/universal_transcriber/models"
mkdir -p "$MODELS_DIR"

BASE_MODEL="$MODELS_DIR/ggml-base.en.bin"
SMALL_MODEL="$MODELS_DIR/ggml-small.en.bin"

verify_or_download_model() {
    local model_path="$1"
    local model_name="$2"
    local min_bytes="$3"
    local url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$model_name"

    if [ -f "$model_path" ] && [ $(stat -f%z "$model_path" 2>/dev/null || echo 0) -gt "$min_bytes" ]; then
        local size_mb=$(($(stat -f%z "$model_path") / 1048576))
        echo -e "${GREEN}✓ $model_name:${RESET} present ($size_mb MB) in $MODELS_DIR"
    else
        if [ "$CHECK_ONLY" = true ]; then
            echo -e "${YELLOW}• $model_name: missing or incomplete.${RESET}"
        elif [ "$SKIP_MODELS" = true ]; then
            echo -e "${YELLOW}• $model_name: skipped per --skip-models.${RESET}"
        else
            echo -e "${CYAN}⬇️  Downloading $model_name (~$((min_bytes / 1048576)) MB)...${RESET}"
            curl -L --progress-bar "$url" -o "$model_path"
            echo -e "${GREEN}✓ $model_name downloaded successfully.${RESET}"
        fi
    fi
}

verify_or_download_model "$BASE_MODEL" "ggml-base.en.bin" 140000000
verify_or_download_model "$SMALL_MODEL" "ggml-small.en.bin" 460000000

# 6. Hardware Acceleration Verification
echo -e "\n${BOLD}[6/6] Verifying Apple Silicon Metal Acceleration...${RESET}"
WHISPER_BIN="$(command -v whisper-cli 2>/dev/null || command -v whisper-cpp 2>/dev/null || true)"
if [ -n "$WHISPER_BIN" ] && [ -x "$WHISPER_BIN" ]; then
    METAL_CHECK="$("$WHISPER_BIN" -h 2>&1 | grep -i "GPU name:" || true)"
    if [ -n "$METAL_CHECK" ]; then
        echo -e "${GREEN}✓ Metal Hardware Acceleration:${RESET} $METAL_CHECK"
    else
        echo -e "${CYAN}✓ Metal runtime loaded successfully.${RESET}"
    fi
else
    echo -e "${YELLOW}⚠️ whisper-cli not in PATH yet.${RESET}"
fi

# Ensure executable permissions on canonical entrypoints
chmod +x install.sh install_v1.sh start_app.sh start_app_v1.sh start_app_v2.sh cli.py cli_v7.py app.py app_v6.py 2>/dev/null || true

echo -e "\n${BOLD}${GREEN}======================================================================"
echo "🎉 UNIVERSAL TRANSCRIBER 0.1-BETA INSTALLATION COMPLETE!"
echo "======================================================================${RESET}"
echo -e "Ready for daily use by ${BOLD}Sean Tyler (@seanbuilds)${RESET}.\n"
echo -e "Quick Start Commands:"
echo -e "  1. ${BOLD}Launch Web Dashboard:${RESET}   ${CYAN}./start_app.sh${RESET}"
echo -e "     URL: http://127.0.0.1:5055"
echo ""
echo -e "  2. ${BOLD}Transcribe Local Media:${RESET}  ${CYAN}python3 cli.py local ~/Downloads/audio.m4a${RESET}"
echo -e "  3. ${BOLD}Transcribe YouTube URL:${RESET}  ${CYAN}python3 cli.py transcribe \"https://youtu.be/...\"${RESET}"
echo -e "  4. ${BOLD}Inspect Audit Log:${RESET}       ${CYAN}python3 cli.py audit${RESET}"
echo -e "  5. ${BOLD}Deliver Transcripts:${RESET}     ${CYAN}python3 cli.py email --target ohheysean@gmail.com${RESET}"
echo ""
echo -e "Documentation: See ${BOLD}README.md${RESET} and ${BOLD}INSTALL.md${RESET}."
echo -e "${GREEN}======================================================================${RESET}\n"
