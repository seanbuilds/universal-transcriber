#!/usr/bin/env python3
"""Generate Clean Multimedia Tutorial Videos with Male Voice Narration for Universal Transcriber 0.1-Beta.
<!-- v1 – Automated rendering of 5 high-definition MP4 tutorial videos with synced male voice narration (Reed), animated macOS UI, and live waveforms -->
"""

import math
import os
import shutil
import struct
import subprocess
import wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).parent.parent.resolve()
VIDEOS_DIR = BASE_DIR / "docs" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
SCRATCH_DIR = Path("/tmp/tutorial_generation")
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

# System Fonts
FONT_MONO_SMALL = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 13)
FONT_MONO_BOLD = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 15)
FONT_TITLE = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", 22)
FONT_SUBTITLE = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", 14)
FONT_BADGE = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", 13)
FONT_BIG = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", 18)

WIDTH = 1280
HEIGHT = 720
FPS = 10

def draw_window(draw, x, y, w, h, title, subtitle=None):
    """Draw a macOS-style dark card container with traffic lights."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=(21, 24, 36), outline=(38, 44, 64), width=1)
    # Header bar
    draw.rounded_rectangle([x, y, x + w, y + 36], radius=10, fill=(26, 30, 46))
    draw.rectangle([x, y + 20, x + w, y + 36], fill=(26, 30, 46))
    draw.line([x, y + 36, x + w, y + 36], fill=(38, 44, 64), width=1)
    # Traffic lights
    draw.ellipse([x + 12, y + 12, x + 22, y + 22], fill=(239, 68, 68))
    draw.ellipse([x + 28, y + 12, x + 38, y + 22], fill=(245, 158, 11))
    draw.ellipse([x + 44, y + 12, x + 54, y + 22], fill=(16, 185, 129))
    # Title
    draw.text((x + 64, y + 10), title, fill=(255, 255, 255), font=FONT_BADGE)
    if subtitle:
        draw.text((x + w - 240, y + 10), subtitle, fill=(148, 163, 184), font=FONT_MONO_SMALL)

def draw_waveform(draw, x, y, w, h, t, total_t, samples, sample_rate):
    """Render an animated audio waveform at the bottom of the frame."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=(12, 15, 25), outline=(38, 44, 64), width=1)
    draw.text((x + 16, y + 8), "🎙️ NARRATION (MALE VOICE • REED)", fill=(99, 102, 241), font=FONT_BADGE)
    
    # Progress text
    draw.text((x + w - 120, y + 8), f"{t:04.1f}s / {total_t:04.1f}s", fill=(148, 163, 184), font=FONT_MONO_SMALL)

    # Bars
    num_bars = 48
    bar_width = (w - 32) / num_bars
    center_y = y + 34
    max_h = 16

    sample_idx = int(t * sample_rate)
    window_size = int(0.08 * sample_rate)

    for i in range(num_bars):
        offset = int((i - num_bars / 2) * (window_size / num_bars))
        target_idx = sample_idx + offset
        val = 0.0
        if 0 <= target_idx < len(samples):
            val = abs(samples[target_idx]) / 32768.0
        val = max(0.08, min(1.0, val * 2.2 + 0.1 * math.sin(t * 8.0 + i * 0.4)))
        bar_h = val * max_h
        bx = x + 16 + i * bar_width
        
        # Color based on progress
        color = (16, 185, 129) if (i / num_bars) <= (t / total_t) else (56, 189, 248)
        draw.line([bx, center_y - bar_h, bx, center_y + bar_h], fill=color, width=3)


def build_video_1():
    """Tutorial 1: Turnkey Automated Installation & 1-Click Launch."""
    name = "tutorial_01_install_and_launch_v1"
    output_mp4 = VIDEOS_DIR / f"{name}.mp4"
    print(f"\n--- Generating {name} ---")

    narration = (
        "Welcome to Universal Transcriber version zero point one beta, engineered by Sean Tyler. "
        "Setting up on Apple Silicon is fully turnkey. Run install dot s-h to verify system tools, "
        "download speech models, and validate Metal GPU acceleration. "
        "Then launch start app dot s-h to boot the server and open your web dashboard."
    )
    
    aiff_path = SCRATCH_DIR / f"{name}.aiff"
    wav_path = SCRATCH_DIR / f"{name}.wav"
    subprocess.run(["say", "-v", "Reed (English (US))", narration, "-o", str(aiff_path)], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(aiff_path), "-ar", "44100", "-ac", "1", str(wav_path)], check=True, stderr=subprocess.DEVNULL)
    
    with wave.open(str(wav_path), "rb") as wf:
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        samples = struct.unpack(f"{n_frames}h", raw)
        sample_rate = wf.getframerate()
    
    total_seconds = n_frames / sample_rate
    total_frames = int(FPS * total_seconds)

    frames_dir = SCRATCH_DIR / f"{name}_frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    for f_idx in range(total_frames):
        t = f_idx / FPS
        img = Image.new("RGB", (WIDTH, HEIGHT), (11, 13, 20))
        draw = ImageDraw.Draw(img)

        # Header
        draw.text((WIDTH // 2 - 250, 18), "🎙️ Universal Transcriber (0.1-Beta)", fill=(255, 255, 255), font=FONT_TITLE)
        draw.text((WIDTH // 2 - 270, 48), "Turnkey Automated Installation (install.sh) & 1-Click Startup (start_app.sh)", fill=(148, 163, 184), font=FONT_SUBTITLE)

        # Window 1: ./install.sh Terminal Execution
        draw_window(draw, 40, 80, 580, 520, "Terminal — ./install.sh (Automated Setup)")
        lines1 = [
            ("$ ./install.sh", (255, 255, 255)),
            ("=================================================================", (99, 102, 241)),
            ("  🎙️ UNIVERSAL TRANSCRIBER • TURNKEY INSTALLER", (255, 255, 255)),
            ("      Release: v0.1.0-beta • Engineered by @seanbuilds", (165, 180, 252)),
            ("=================================================================", (99, 102, 241)),
            ("", (0,0,0)),
            ("[1/6] Inspecting Hardware & Operating System...", (203, 213, 225)),
            ("  ✓ Apple Silicon (arm64) detected. Metal GPU enabled.", (16, 185, 129)),
            ("", (0,0,0)),
            ("[2/6] Verifying System Tools (Homebrew)...", (203, 213, 225)),
            ("  ✓ ffmpeg: 9.0.1  |  yt-dlp: 2026.08.19", (16, 185, 129)),
            ("  ✓ whisper-cli: /opt/homebrew/bin/whisper-cli", (16, 185, 129)),
            ("", (0,0,0)),
            ("[3/6] Detecting Python 3 Environment...", (203, 213, 225)),
            ("  ✓ Python runtime: python@3.14 (v3.14.7)", (16, 185, 129)),
            ("", (0,0,0)),
            ("[4/6] Verifying Python Dependencies...", (203, 213, 225)),
            ("  ✓ Requirements verified (flask, jsonschema, docx, numpy, scipy)", (16, 185, 129)),
            ("", (0,0,0)),
            ("[5/6] Checking GGML Whisper Speech Models...", (203, 213, 225)),
            ("  ✓ ggml-base.en.bin: present (141 MB)", (16, 185, 129)),
            ("  ✓ ggml-small.en.bin: present (465 MB)", (16, 185, 129)),
            ("", (0,0,0)),
            ("[6/6] Verifying Apple Silicon Metal Acceleration...", (203, 213, 225)),
            ("  ✓ Metal Acceleration: GPU name: MTL0 (Apple M4 Pro)", (56, 189, 248)),
            ("", (0,0,0)),
            ("🎉 Installation Complete! Ready for daily use.", (16, 185, 129)),
        ]

        visible_lines = min(len(lines1), int((t / (total_seconds * 0.75)) * len(lines1)) + 4)
        cy = 126
        for line, col in lines1[:visible_lines]:
            draw.text((56, cy), line, fill=col, font=FONT_MONO_SMALL)
            cy += 16

        # Window 2: ./start_app.sh & Web Dashboard Launch
        draw_window(draw, 650, 80, 590, 520, "Terminal & Browser — 1-Click Launch")
        lines2 = [
            ("$ ./start_app.sh", (255, 255, 255)),
            ("========================================================", (16, 185, 129)),
            ("🎙️ Universal Transcriber • 1-Click Launcher", (255, 255, 255)),
            ("   Release: v0.1.0-beta • Engineered by @seanbuilds", (165, 180, 252)),
            ("========================================================", (16, 185, 129)),
            ("✓ Python runtime: python@3.14 verified", (16, 185, 129)),
            ("✓ System utilities verified (ffmpeg, whisper-cli, yt-dlp)", (16, 185, 129)),
            ("🚀 Launching Universal Transcriber web daemon (app.py)...", (56, 189, 248)),
            ("✓ Web server process started (PID: 76210)", (203, 213, 225)),
            ("⏳ Waiting for server to become ready...", (245, 158, 11)),
            ("✓ Server is live and responding at http://127.0.0.1:5055", (16, 185, 129)),
            ("🌐 Opening web dashboard in default browser...", (56, 189, 248)),
        ]

        if t >= 11.0:
            vlines2 = len(lines2)
        elif t >= 6.0:
            vlines2 = int(((t - 6.0) / 5.0) * len(lines2))
        else:
            vlines2 = 1

        cy2 = 126
        for line, col in lines2[:vlines2]:
            draw.text((666, cy2), line, fill=col, font=FONT_MONO_SMALL)
            cy2 += 16

        # Simulated browser card inside window 2
        if t >= 13.0:
            bx, by, bw, bh = 666, 320, 558, 260
            draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=8, fill=(15, 18, 28), outline=(59, 130, 246), width=1)
            draw.text((bx + 14, by + 12), "🌐 http://127.0.0.1:5055/ • Web Dashboard (v0.1-beta)", fill=(255, 255, 255), font=FONT_BADGE)
            draw.rounded_rectangle([bx + 14, by + 40, bx + bw - 14, by + 100], radius=6, fill=(21, 24, 36), outline=(38, 44, 64))
            draw.text((bx + 26, by + 52), "🎙️ Universal Transcriber", fill=(255, 255, 255), font=FONT_BIG)
            draw.rounded_rectangle([bx + 240, by + 50, bx + 320, by + 72], radius=10, fill=(5, 150, 105))
            draw.text((bx + 248, by + 54), "v0.1-beta", fill=(255, 255, 255), font=FONT_BADGE)
            draw.text((bx + 26, by + 78), "Engineered by @seanbuilds • Metal GPU Streaming ASR", fill=(148, 163, 184), font=FONT_MONO_SMALL)

            draw.rounded_rectangle([bx + 14, by + 114, bx + bw - 14, by + 240], radius=6, fill=(12, 16, 28), outline=(51, 65, 85), width=1)
            draw.text((bx + bw // 2 - 120, by + 140), "📂 Drag & Drop Audio or Video (.m4a, .mp3, .mp4)", fill=(203, 213, 225), font=FONT_BADGE)
            draw.text((bx + bw // 2 - 100, by + 165), "Automatic video bypass (-vn) & 16kHz WAV downmix", fill=(148, 163, 184), font=FONT_MONO_SMALL)
            draw.rounded_rectangle([bx + bw // 2 - 60, by + 195, bx + bw // 2 + 60, by + 225], radius=6, fill=(99, 102, 241))
            draw.text((bx + bw // 2 - 42, by + 203), "⚡ Ready", fill=(255, 255, 255), font=FONT_BADGE)

        draw_waveform(draw, 40, 615, 1200, 90, t, total_seconds, samples, sample_rate)
        img.save(frames_dir / f"frame_{f_idx:04d}.png")

    subprocess.run([
        "ffmpeg", "-y", "-r", str(FPS),
        "-i", str(frames_dir / "frame_%04d.png"),
        "-i", str(wav_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        str(output_mp4)
    ], check=True, stderr=subprocess.DEVNULL)
    shutil.rmtree(frames_dir, ignore_errors=True)
    print(f"✓ Video 1 compiled: {output_mp4} ({total_seconds:.1f}s)")


def build_video_2():
    """Tutorial 2: Local Media Drag-and-Drop Dropzone & Video Bypass."""
    name = "tutorial_02_local_media_dropzone_v1"
    output_mp4 = VIDEOS_DIR / f"{name}.mp4"
    print(f"\n--- Generating {name} ---")

    narration = (
        "Universal Transcriber makes local file transcription effortless. "
        "Drag and drop any M4A, MP3, MP4, or MOV file into the web dropzone. "
        "The engine automatically bypasses video decoding using minus v n, saving significant compute "
        "while extracting pristine 16 kilohertz mono audio. "
        "Watch real-time streaming tokens and speaker turns appear live."
    )
    
    aiff_path = SCRATCH_DIR / f"{name}.aiff"
    wav_path = SCRATCH_DIR / f"{name}.wav"
    subprocess.run(["say", "-v", "Reed (English (US))", narration, "-o", str(aiff_path)], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(aiff_path), "-ar", "44100", "-ac", "1", str(wav_path)], check=True, stderr=subprocess.DEVNULL)
    
    with wave.open(str(wav_path), "rb") as wf:
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        samples = struct.unpack(f"{n_frames}h", raw)
        sample_rate = wf.getframerate()
    
    total_seconds = n_frames / sample_rate
    total_frames = int(FPS * total_seconds)

    frames_dir = SCRATCH_DIR / f"{name}_frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    for f_idx in range(total_frames):
        t = f_idx / FPS
        img = Image.new("RGB", (WIDTH, HEIGHT), (11, 13, 20))
        draw = ImageDraw.Draw(img)

        draw.text((WIDTH // 2 - 260, 18), "🎙️ Universal Transcriber (Web Dropzone)", fill=(255, 255, 255), font=FONT_TITLE)
        draw.text((WIDTH // 2 - 280, 48), "Multi-Format Ingestion (.m4a, .mp3, .mp4, .mov) • Video Bypass (-vn) • Streaming ASR", fill=(148, 163, 184), font=FONT_SUBTITLE)

        draw_window(draw, 40, 80, 580, 520, "Web Dashboard — Drag & Drop Media Ingestion")
        
        dz_color = (99, 102, 241) if (3.0 <= t <= 10.0) else (51, 65, 85)
        dz_bg = (19, 25, 46) if (3.0 <= t <= 10.0) else (12, 16, 28)
        draw.rounded_rectangle([60, 130, 600, 240], radius=8, fill=dz_bg, outline=dz_color, width=2)

        if t < 4.0:
            draw.text((180, 160), "📂 Drag & Drop Any Media File Here", fill=(255, 255, 255), font=FONT_BIG)
            draw.text((150, 195), "Supports .m4a, .mp3, .mp4, .mov, .wav, .flac, .aac, .mkv", fill=(148, 163, 184), font=FONT_MONO_SMALL)
        elif t < 8.0:
            draw.text((160, 160), "⏳ Uploading interview_recording.m4a...", fill=(99, 102, 241), font=FONT_BIG)
            up_p = int(((t - 4.0) / 4.0) * 100)
            draw.rounded_rectangle([120, 200, 540, 212], radius=4, fill=(8, 10, 18))
            draw.rounded_rectangle([120, 200, 120 + int(420 * (up_p / 100.0)), 212], radius=4, fill=(99, 102, 241))
        else:
            draw.rounded_rectangle([80, 150, 580, 215], radius=6, fill=(24, 32, 53), outline=(45, 59, 91))
            draw.rounded_rectangle([96, 166, 150, 196], radius=4, fill=(59, 130, 246))
            draw.text((106, 172), "M4A", fill=(255, 255, 255), font=FONT_BADGE)
            draw.text((165, 172), "interview_recording.m4a • 00:18:45 • 24.8 MB", fill=(203, 213, 225), font=FONT_MONO_SMALL)
            draw.text((510, 172), "✓ Ready", fill=(16, 185, 129), font=FONT_BADGE)

        draw.text((60, 260), "DOMAIN PLAYBOOK", fill=(148, 163, 184), font=FONT_BADGE)
        draw.rounded_rectangle([60, 280, 300, 316], radius=6, fill=(12, 15, 25), outline=(38, 44, 64))
        draw.text((74, 290), "interview_podcast (v3)", fill=(245, 158, 11), font=FONT_MONO_SMALL)

        draw.text((320, 260), "ISO TITLE PREFILL", fill=(148, 163, 184), font=FONT_BADGE)
        draw.rounded_rectangle([320, 280, 600, 316], radius=6, fill=(12, 15, 25), outline=(38, 44, 64))
        title_val = "Interview_Recording" if t >= 8.0 else ""
        draw.text((334, 290), title_val, fill=(56, 189, 248) if title_val else (148, 163, 184), font=FONT_MONO_SMALL)

        prog = min(100, int(((t - 9.0) / (total_seconds - 10.0)) * 100)) if t >= 9.0 else 0
        draw.text((60, 340), f"TRANSCRIPTION PROGRESS: {prog}%", fill=(148, 163, 184), font=FONT_BADGE)
        draw.rounded_rectangle([60, 360, 600, 376], radius=4, fill=(12, 15, 25))
        if prog > 0:
            draw.rounded_rectangle([60, 360, 60 + int(540 * (prog / 100.0)), 376], radius=4, fill=(16, 185, 129))

        stage_txt = "Awaiting input" if t < 8.0 else ("Ready to transcribe" if t < 9.0 else "Sliding window ASR & AHC diarization...")
        if prog >= 100:
            stage_txt = "✓ Completed! Atomic export generated across 6 formats."
        draw.text((60, 395), stage_txt, fill=(16, 185, 129) if prog >= 100 else (203, 213, 225), font=FONT_MONO_SMALL)

        draw.rounded_rectangle([60, 430, 240, 470], radius=6, fill=(99, 102, 241))
        draw.text((95, 442), "⚡ Transcribe", fill=(255, 255, 255), font=FONT_BIG)
        draw.rounded_rectangle([260, 430, 420, 470], radius=6, fill=(30, 36, 54), outline=(55, 65, 81))
        draw.text((280, 444), "🔄 Clear / Reset", fill=(203, 213, 225), font=FONT_BADGE)

        draw_window(draw, 650, 80, 590, 520, "Live Telemetry Stream — SSE (GET /api/stream/<id>)")
        sse_box_y = 130
        draw.rounded_rectangle([670, sse_box_y, 1220, 580], radius=8, fill=(8, 9, 15), outline=(38, 44, 64))

        stream_items = [
            ("[00:00:00]", "SPEAKER_00 (Host)", "Welcome to today's episode. We have a special guest with us.", (56, 189, 248)),
            ("[00:00:05]", "SPEAKER_01 (Guest)", "Thank you Sean, it is fantastic to be here today.", (16, 185, 129)),
            ("[00:00:10]", "SPEAKER_00 (Host)", "Let's dive right into the architectural upgrades in 0.1-beta.", (56, 189, 248)),
            ("[00:00:16]", "SPEAKER_01 (Guest)", "The video bypass optimization with minus v n is brilliant.", (16, 185, 129)),
            ("[00:00:22]", "SPEAKER_00 (Host)", "Exactly, extracting pure PCM audio up to 5x faster.", (56, 189, 248)),
        ]

        visible_items = min(len(stream_items), int(((t - 10.0) / 2.5) + 1)) if t >= 10.0 else 0
        sy = sse_box_y + 16
        if visible_items == 0:
            draw.text((780, sse_box_y + 180), "Awaiting transcription stream...", fill=(100, 116, 139), font=FONT_BIG)
        else:
            for ts_tag, spk, text, col in stream_items[:visible_items]:
                draw.text((685, sy), ts_tag, fill=(99, 102, 241), font=FONT_MONO_BOLD)
                draw.text((780, sy), spk, fill=col, font=FONT_MONO_BOLD)
                draw.text((685, sy + 22), text, fill=(226, 232, 240), font=FONT_MONO_SMALL)
                draw.line([685, sy + 48, 1205, sy + 48], fill=(22, 26, 41), width=1)
                sy += 62

        draw_waveform(draw, 40, 615, 1200, 90, t, total_seconds, samples, sample_rate)
        img.save(frames_dir / f"frame_{f_idx:04d}.png")

    subprocess.run([
        "ffmpeg", "-y", "-r", str(FPS),
        "-i", str(frames_dir / "frame_%04d.png"),
        "-i", str(wav_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        str(output_mp4)
    ], check=True, stderr=subprocess.DEVNULL)
    shutil.rmtree(frames_dir, ignore_errors=True)
    print(f"✓ Video 2 compiled: {output_mp4} ({total_seconds:.1f}s)")


def build_video_3():
    """Tutorial 3: Unified Command-Line Interface & Directory Batching."""
    name = "tutorial_03_cli_local_and_batch_v1"
    output_mp4 = VIDEOS_DIR / f"{name}.mp4"
    print(f"\n--- Generating {name} ---")

    narration = (
        "For power users, the CLI provides lightning-fast local and remote media transcription. "
        "Run python3 cli dot py local with your audio file, or pass the recursive flag on any directory "
        "to batch process entire folders. "
        "Transcripts are automatically exported into standardized ISO-8601 folders across six formats."
    )
    
    aiff_path = SCRATCH_DIR / f"{name}.aiff"
    wav_path = SCRATCH_DIR / f"{name}.wav"
    subprocess.run(["say", "-v", "Reed (English (US))", narration, "-o", str(aiff_path)], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(aiff_path), "-ar", "44100", "-ac", "1", str(wav_path)], check=True, stderr=subprocess.DEVNULL)
    
    with wave.open(str(wav_path), "rb") as wf:
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        samples = struct.unpack(f"{n_frames}h", raw)
        sample_rate = wf.getframerate()
    
    total_seconds = n_frames / sample_rate
    total_frames = int(FPS * total_seconds)

    frames_dir = SCRATCH_DIR / f"{name}_frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    for f_idx in range(total_frames):
        t = f_idx / FPS
        img = Image.new("RGB", (WIDTH, HEIGHT), (11, 13, 20))
        draw = ImageDraw.Draw(img)

        draw.text((WIDTH // 2 - 250, 18), "🎙️ Universal Transcriber (CLI Automation)", fill=(255, 255, 255), font=FONT_TITLE)
        draw.text((WIDTH // 2 - 270, 48), "Unified Entrypoint (cli.py) • Single File & Recursive Batch Scanning • 6 Export Formats", fill=(148, 163, 184), font=FONT_SUBTITLE)

        draw_window(draw, 40, 80, 580, 520, "Terminal — python3 cli.py local (Single File)")
        lines1 = [
            ("$ python3 cli.py --version", (255, 255, 255)),
            ("Universal Transcriber v0.1.0-beta (@seanbuilds)", (16, 185, 129)),
            ("", (0,0,0)),
            ("$ python3 cli.py local ~/Music/board_hearing.m4a \\", (255, 255, 255)),
            ("    --title 'Select_Board_Hearing' \\", (255, 255, 255)),
            ("    --playbook municipal_meetings", (255, 255, 255)),
            ("🎙️ Universal Transcriber v0.1.0-beta • Processing: board_hearing.m4a", (165, 180, 252)),
            ("Playbook:   municipal_meetings | Clustering: AHC", (148, 163, 184)),
            ("ISO Title:  Select_Board_Hearing", (148, 163, 184)),
            ("-----------------------------------------------------------------", (51, 65, 85)),
            ("[ 15%] Extracting audio (16 kHz mono downmix)...", (56, 189, 248)),
            ("[ 35%] Transcribing audio with sliding window streaming...", (99, 102, 241)),
            ("  [00:00:00] Chair: We will begin roll-call on motion to approve.", (245, 158, 11)),
            ("  [00:00:04] Member Tyler: Aye.", (16, 185, 129)),
            ("[ 70%] Performing neural acoustic diarization (AHC)...", (99, 102, 241)),
            ("[ 85%] Applying 'municipal_meetings' FSM role healing...", (165, 180, 252)),
            ("[ 95%] Exporting multi-format transcripts with ISO-8601 naming...", (16, 185, 129)),
            ("=================================================================", (51, 65, 85)),
            ("✅ Transcription Complete!", (16, 185, 129)),
            ("Title: Select_Board_Hearing | Duration: 00:42:15 | Speakers: 5", (203, 213, 225)),
            ("ISO Directory: ~/Documents/Transcripts/20260920_Select_Board_Hearing/", (56, 189, 248)),
        ]

        vlines1 = min(len(lines1), int((t / (total_seconds * 0.55)) * len(lines1)) + 2)
        cy1 = 126
        for line, col in lines1[:vlines1]:
            draw.text((56, cy1), line, fill=col, font=FONT_MONO_SMALL)
            cy1 += 17

        draw_window(draw, 650, 80, 590, 520, "Terminal — Batch Directory Scan & Formats")
        lines2 = [
            ("$ python3 cli.py local ~/Documents/Recordings/ --recursive", (255, 255, 255)),
            ("📁 Found 4 media file(s) in ~/Documents/Recordings/ (recursive=True):", (245, 158, 11)),
            ("   1. council_march.mp4 (142.5 MB)", (203, 213, 225)),
            ("   2. interview_ep01.m4a (28.4 MB)", (203, 213, 225)),
            ("   3. strategy_sync.mov (88.1 MB)", (203, 213, 225)),
            ("   4. podcast_raw.wav (45.0 MB)", (203, 213, 225)),
            ("-----------------------------------------------------------------", (51, 65, 85)),
            ("[1/4] Processing: council_march.mp4 -> Completed", (16, 185, 129)),
            ("[2/4] Processing: interview_ep01.m4a -> Completed", (16, 185, 129)),
            ("[3/4] Processing: strategy_sync.mov -> Completed", (16, 185, 129)),
            ("[4/4] Processing: podcast_raw.wav -> Completed", (16, 185, 129)),
            ("", (0,0,0)),
            ("🎉 Batch Finished: 4 items successfully processed.", (16, 185, 129)),
            ("", (0,0,0)),
            ("Synchronized Atomic Exports (6 Formats):", (255, 255, 255)),
            ("  • .MD   -> GitHub-flavored Markdown with speaker dialogue blocks", (165, 180, 252)),
            ("  • .TXT  -> Clean verbatim plaintext for quick search & read", (165, 180, 252)),
            ("  • .SRT  -> SubRip subtitle timecoded captioning track", (165, 180, 252)),
            ("  • .VTT  -> WebVTT voice-tagged cue format for web HTML5 players", (165, 180, 252)),
            ("  • .DOCX -> Microsoft Word document with formatted headers", (165, 180, 252)),
            ("  • .JSON -> Structured JSON Abstract Syntax Tree (AST)", (165, 180, 252)),
        ]

        vlines2 = min(len(lines2), int((max(0.0, t - 6.0) / (total_seconds - 6.0)) * len(lines2)) + 3) if t >= 6.0 else 0
        cy2 = 126
        for line, col in lines2[:vlines2]:
            draw.text((666, cy2), line, fill=col, font=FONT_MONO_SMALL)
            cy2 += 17

        draw_waveform(draw, 40, 615, 1200, 90, t, total_seconds, samples, sample_rate)
        img.save(frames_dir / f"frame_{f_idx:04d}.png")

    subprocess.run([
        "ffmpeg", "-y", "-r", str(FPS),
        "-i", str(frames_dir / "frame_%04d.png"),
        "-i", str(wav_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        str(output_mp4)
    ], check=True, stderr=subprocess.DEVNULL)
    shutil.rmtree(frames_dir, ignore_errors=True)
    print(f"✓ Video 3 compiled: {output_mp4} ({total_seconds:.1f}s)")


def build_video_4():
    """Tutorial 4: Domain Playbooks & Finite State Machine Speaker Healing."""
    name = "tutorial_04_playbooks_and_healing_v1"
    output_mp4 = VIDEOS_DIR / f"{name}.mp4"
    print(f"\n--- Generating {name} ---")

    narration = (
        "Universal Transcriber includes tailored domain playbooks for gaming videos, "
        "municipal meetings, podcasts, and corporate reviews. "
        "Each playbook applies specialized lexicons and finite state machines "
        "to eliminate speaker attribution errors and roll-call vote inversions."
    )
    
    aiff_path = SCRATCH_DIR / f"{name}.aiff"
    wav_path = SCRATCH_DIR / f"{name}.wav"
    subprocess.run(["say", "-v", "Reed (English (US))", narration, "-o", str(aiff_path)], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(aiff_path), "-ar", "44100", "-ac", "1", str(wav_path)], check=True, stderr=subprocess.DEVNULL)
    
    with wave.open(str(wav_path), "rb") as wf:
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        samples = struct.unpack(f"{n_frames}h", raw)
        sample_rate = wf.getframerate()
    
    total_seconds = n_frames / sample_rate
    total_frames = int(FPS * total_seconds)

    frames_dir = SCRATCH_DIR / f"{name}_frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    for f_idx in range(total_frames):
        t = f_idx / FPS
        img = Image.new("RGB", (WIDTH, HEIGHT), (11, 13, 20))
        draw = ImageDraw.Draw(img)

        draw.text((WIDTH // 2 - 260, 18), "🎙️ Universal Transcriber (Domain Playbooks)", fill=(255, 255, 255), font=FONT_TITLE)
        draw.text((WIDTH // 2 - 280, 48), "Modular Playbook Registry • JSON Schema v7 Validation • FSM Speaker Role Healing", fill=(148, 163, 184), font=FONT_SUBTITLE)

        draw_window(draw, 40, 80, 580, 520, "Playbook Registry (playbooks/)")
        pbs = [
            ("gaming_videos", "Esports, Let's Plays, Speedruns (Streamer, Caster, Opponent)", (245, 158, 11)),
            ("municipal_meetings", "Formal civic proceedings with Roll-Call FSM election", (56, 189, 248)),
            ("interview_podcast", "Host, Co-host, and Guest conversational turn taking", (165, 180, 252)),
            ("corporate_meeting", "Action items, agenda transitions, executive summaries", (16, 185, 129)),
            ("academic_lecture", "Technical terminology, slide transitions, Q&A blocks", (244, 114, 182)),
            ("general_speech", "Domain-agnostic acoustic clustering baseline", (148, 163, 184)),
        ]

        draw.text((56, 130), "VALIDATED PLAYBOOKS (Schema v7 Strict Compliance):", fill=(255, 255, 255), font=FONT_BADGE)
        py = 158
        for name_str, desc, col in pbs:
            draw.rounded_rectangle([56, py, 600, py + 52], radius=6, fill=(15, 18, 28), outline=(38, 44, 64))
            draw.text((70, py + 8), f"• {name_str}_v1.json", fill=col, font=FONT_MONO_BOLD)
            draw.text((70, py + 28), desc, fill=(148, 163, 184), font=FONT_MONO_SMALL)
            py += 62

        draw.rounded_rectangle([56, 525, 600, 565], radius=6, fill=(16, 36, 26), outline=(16, 185, 129))
        draw.text((80, 536), "✓ All 6 playbooks pass jsonschema.validate() against schema_v1.json", fill=(52, 211, 153), font=FONT_MONO_SMALL)

        draw_window(draw, 650, 80, 590, 520, "Finite State Machine (FSM) Speaker Healing")
        draw.text((670, 130), "PROBLEM: ROLL-CALL INVERSION IN RAW ASR", fill=(239, 68, 68), font=FONT_BADGE)
        draw.rounded_rectangle([670, 150, 1220, 240], radius=6, fill=(28, 16, 20), outline=(127, 29, 29))
        raw_lines = [
            ("Raw Segment 1: Chair says 'Tyler?'", (203, 213, 225)),
            ("Raw Segment 2: Tyler responds 'Aye.'", (203, 213, 225)),
            ("⚠️ Flawed ASR Error: Attributes 'Tyler?' turn to Member Tyler instead of Chair!", (239, 68, 68)),
        ]
        ry = 160
        for l, c in raw_lines:
            draw.text((685, ry), l, fill=c, font=FONT_MONO_SMALL)
            ry += 24

        draw.text((670, 265), "SOLUTION: 3-STATE ROLL-CALL FSM IN HEALER_V3", fill=(16, 185, 129), font=FONT_BADGE)
        draw.rounded_rectangle([670, 285, 1220, 480], radius=6, fill=(12, 28, 20), outline=(6, 95, 70))
        
        draw.rounded_rectangle([690, 310, 830, 360], radius=6, fill=(19, 42, 31), outline=(16, 185, 129))
        draw.text((725, 326), "IDLE", fill=(255, 255, 255), font=FONT_MONO_BOLD)
        draw.text((840, 326), "→ Trigger 'roll call' →", fill=(148, 163, 184), font=FONT_MONO_SMALL)

        draw.rounded_rectangle([990, 310, 1200, 360], radius=6, fill=(19, 42, 31), outline=(16, 185, 129))
        draw.text((1050, 326), "CALLING", fill=(56, 189, 248), font=FONT_MONO_BOLD)

        draw.text((690, 385), "• While in CALLING state, roster member names stay locked to Chair turn.", fill=(203, 213, 225), font=FONT_MONO_SMALL)
        draw.text((690, 415), "• Single-word answers ('Aye', 'Yes', 'Present') transition to AWAITING_VOTE.", fill=(203, 213, 225), font=FONT_MONO_SMALL)
        draw.text((690, 445), "• 100% elimination of speaker inversion proven across regression tests.", fill=(52, 211, 153), font=FONT_MONO_SMALL)

        draw_waveform(draw, 40, 615, 1200, 90, t, total_seconds, samples, sample_rate)
        img.save(frames_dir / f"frame_{f_idx:04d}.png")

    subprocess.run([
        "ffmpeg", "-y", "-r", str(FPS),
        "-i", str(frames_dir / "frame_%04d.png"),
        "-i", str(wav_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        str(output_mp4)
    ], check=True, stderr=subprocess.DEVNULL)
    shutil.rmtree(frames_dir, ignore_errors=True)
    print(f"✓ Video 4 compiled: {output_mp4} ({total_seconds:.1f}s)")


def build_video_5():
    """Tutorial 5: Persistent Transcription Audit Log & Catalog Idempotency."""
    name = "tutorial_05_audit_and_catalog_v1"
    output_mp4 = VIDEOS_DIR / f"{name}.mp4"
    print(f"\n--- Generating {name} ---")

    narration = (
        "Every transcription attempt is persistently tracked in SQLite and JSON lines audit stores, "
        "recording audio durations, segment counts, and whether files have been consumed. "
        "Use the catalog command to monitor YouTube channels and podcast feeds "
        "without ever transcribing the same episode twice."
    )
    
    aiff_path = SCRATCH_DIR / f"{name}.aiff"
    wav_path = SCRATCH_DIR / f"{name}.wav"
    subprocess.run(["say", "-v", "Reed (English (US))", narration, "-o", str(aiff_path)], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(aiff_path), "-ar", "44100", "-ac", "1", str(wav_path)], check=True, stderr=subprocess.DEVNULL)
    
    with wave.open(str(wav_path), "rb") as wf:
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        samples = struct.unpack(f"{n_frames}h", raw)
        sample_rate = wf.getframerate()
    
    total_seconds = n_frames / sample_rate
    total_frames = int(FPS * total_seconds)

    frames_dir = SCRATCH_DIR / f"{name}_frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    for f_idx in range(total_frames):
        t = f_idx / FPS
        img = Image.new("RGB", (WIDTH, HEIGHT), (11, 13, 20))
        draw = ImageDraw.Draw(img)

        draw.text((WIDTH // 2 - 260, 18), "🎙️ Universal Transcriber (Audit & Catalog)", fill=(255, 255, 255), font=FONT_TITLE)
        draw.text((WIDTH // 2 - 280, 48), "Persistent SQLite Audit Trail • Usage Tracking (USED/UNUSED) • Channel Idempotency", fill=(148, 163, 184), font=FONT_SUBTITLE)

        draw_window(draw, 40, 80, 580, 520, "Audit Store — SQLite & JSONL (audit_v1.py)")
        lines1 = [
            ("$ python3 cli.py audit", (255, 255, 255)),
            ("=================================================================", (99, 102, 241)),
            ("📜 Universal Transcriber • Persistent Audit Log", (255, 255, 255)),
            ("=================================================================", (99, 102, 241)),
            ("Completed: 32  |  Failed: 4  |  Cancelled: 12", (16, 185, 129)),
            ("Used / Consumed: 2  |  Unused / Discarded: 46", (245, 158, 11)),
            ("Total Audio Processed: 412.5 minutes", (56, 189, 248)),
            ("-----------------------------------------------------------------", (51, 65, 85)),
            (f"{'TIMESTAMP':<18} | {'JOB ID':<12} | {'STATUS':<9} | {'USED':<4} | {'TITLE'}", (148, 163, 184)),
            ("-----------------------------------------------------------------", (51, 65, 85)),
            ("2026-09-20 12:21:42 | job_d28c1efe | COMPLETED | NO   | Test_01_Beta_Release", (203, 213, 225)),
            ("2026-09-20 12:18:10 | job_4ef9c2c3 | COMPLETED | YES  | Episode_42_Interview", (16, 185, 129)),
            ("2026-09-20 12:05:30 | job_04c67815 | CANCELLED | NO   | Stream_Abort_Reset", (239, 68, 68)),
            ("2026-09-20 11:45:12 | job_fa307ba2 | COMPLETED | NO   | Planning_Board_Hear", (203, 213, 225)),
            ("2026-09-20 11:10:04 | job_ffe5cde5 | COMPLETED | NO   | Gaming_Finals_Speed", (203, 213, 225)),
            ("", (0,0,0)),
            ("Key Audit Capabilities:", (255, 255, 255)),
            ("  • Tracks ALL jobs (including discarded / un-downloaded)", (165, 180, 252)),
            ("  • Mark used: python3 cli.py audit --mark-used <job_id>", (56, 189, 248)),
            ("  • Dual backend: SQLite index + Append-only JSONL stream", (16, 185, 129)),
        ]

        vlines1 = min(len(lines1), int((t / (total_seconds * 0.55)) * len(lines1)) + 3)
        cy1 = 126
        for line, col in lines1[:vlines1]:
            draw.text((56, cy1), line, fill=col, font=FONT_MONO_SMALL)
            cy1 += 17

        draw_window(draw, 650, 80, 590, 520, "Catalog Ingestion & Idempotency (catalog_v1.py)")
        lines2 = [
            ("$ python3 cli.py catalog 'https://youtube.com/@Cohasset/videos'", (255, 255, 255)),
            ("📡 Universal Transcriber Catalog Ingestion", (245, 158, 11)),
            ("Discovered 14 items from channel source.", (203, 213, 225)),
            ("Items to process: 1 (Skipped 13 previously completed)", (16, 185, 129)),
            ("-----------------------------------------------------------------", (51, 65, 85)),
            ("[1/1] Processing: Select Board Meeting (Sept 18)", (56, 189, 248)),
            ("  • Ingesting audio stream...", (148, 163, 184)),
            ("  • Transcribing with Metal acceleration...", (99, 102, 241)),
            ("  • Diarizing with AHC (5 speakers)...", (165, 180, 252)),
            ("  • Saved to ~/Documents/Transcripts/20260918_Select_Board/", (16, 185, 129)),
            ("✓ Catalog updated: item marked COMPLETED in media_catalog_v1.sqlite", (16, 185, 129)),
            ("", (0,0,0)),
            ("$ python3 cli.py catalog-status", (255, 255, 255)),
            ("Total Discovered: 14 | Completed: 14 | Pending: 0 | Failed: 0", (16, 185, 129)),
            ("", (0,0,0)),
            ("$ python3 cli.py email --target ohheysean@gmail.com --count 1", (255, 255, 255)),
            ("✓ Delivered transcript package to Sean Tyler via Apple Mail outbox.", (16, 185, 129)),
        ]

        vlines2 = min(len(lines2), int((max(0.0, t - 6.0) / (total_seconds - 6.0)) * len(lines2)) + 3) if t >= 6.0 else 0
        cy2 = 126
        for line, col in lines2[:vlines2]:
            draw.text((666, cy2), line, fill=col, font=FONT_MONO_SMALL)
            cy2 += 17

        draw_waveform(draw, 40, 615, 1200, 90, t, total_seconds, samples, sample_rate)
        img.save(frames_dir / f"frame_{f_idx:04d}.png")

    subprocess.run([
        "ffmpeg", "-y", "-r", str(FPS),
        "-i", str(frames_dir / "frame_%04d.png"),
        "-i", str(wav_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        str(output_mp4)
    ], check=True, stderr=subprocess.DEVNULL)
    shutil.rmtree(frames_dir, ignore_errors=True)
    print(f"✓ Video 5 compiled: {output_mp4} ({total_seconds:.1f}s)")


if __name__ == "__main__":
    print("Building all 5 video tutorials with male narration...")
    build_video_1()
    build_video_2()
    build_video_3()
    build_video_4()
    build_video_5()
    print("\n🎉 All 5 video tutorials generated successfully with male voice narration!")
