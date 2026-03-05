#!/usr/bin/env python3
"""
Script Name: voice-notifier.py
Version: 1.0.0
Last Modified: 2026-02-26
Description: Text-to-speech voice notification handler.
             Accepts a text message and speaks it using available TTS engines.

Usage:
    python voice-notifier.py "Your message here"

Features:
    - Cross-platform: Windows (pyttsx3) and Unix (espeak)
    - Graceful fallback: Uses English if Indian voice not available
    - Detached execution: Non-blocking, fire-and-forget
    - Error resilient: Fails silently if TTS not available

Windows-Safe: ASCII only (no Unicode/emojis in print statements)
"""

import sys
import os
import subprocess
from pathlib import Path

# Windows-safe encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

MEMORY_BASE = Path.home() / '.claude' / 'memory'
VOICE_LOG = MEMORY_BASE / 'logs' / 'voice-notifier.log'


def log_voice(msg):
    """Append a timestamped entry to the voice notifier log file.

    Creates the log directory if it does not already exist. Failures to
    write are silently ignored so that logging never interrupts TTS.

    Args:
        msg (str): Message to append to the log.
    """
    VOICE_LOG.parent.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(VOICE_LOG, 'a', encoding='utf-8') as f:
            f.write(f"{ts} | {msg}\n")
    except Exception:
        pass


def speak_windows(text):
    """Speak text on Windows using the pyttsx3 TTS engine.

    Attempts to select an Indian English voice ('en-in') first; falls back
    to the first available English voice if none is found. Speech rate is
    set to 150 WPM. All outcomes are logged to VOICE_LOG.

    Args:
        text (str): Text to be spoken aloud.

    Returns:
        bool: True if the text was spoken successfully, False if pyttsx3
            is not installed or an error occurred.
    """
    try:
        import pyttsx3
        engine = pyttsx3.init()

        # Try to set Indian English voice if available
        voices = engine.getProperty('voices')
        indian_voice = None
        for voice in voices:
            if 'en-in' in voice.languages[0].lower() or 'indian' in voice.name.lower():
                indian_voice = voice.id
                break

        if indian_voice:
            engine.setProperty('voice', indian_voice)
            log_voice(f"[TTS-WINDOWS] Using Indian voice: {indian_voice}")
        else:
            # Fallback to first available English voice
            for voice in voices:
                if any(lang in voice.languages[0].lower() for lang in ['en-us', 'en-gb', 'en']):
                    engine.setProperty('voice', voice.id)
                    log_voice(f"[TTS-WINDOWS] Using fallback voice: {voice.id}")
                    break

        # Set speech rate
        engine.setProperty('rate', 150)

        # Speak
        engine.say(text)
        engine.runAndWait()
        log_voice(f"[TTS-WINDOWS-SUCCESS] Spoke: {text[:60]}")
        return True

    except ImportError:
        log_voice("[TTS-WINDOWS] pyttsx3 not installed - skipping")
        return False
    except Exception as e:
        log_voice(f"[TTS-WINDOWS-ERROR] {str(e)[:100]}")
        return False


def speak_unix(text):
    """Speak text on Unix/Linux using the espeak command-line TTS tool.

    First attempts synthesis with the Indian English voice ('en-in').
    Falls back to the default English voice ('en') if the first attempt
    returns a non-zero exit code. All outcomes are logged to VOICE_LOG.

    Args:
        text (str): Text to be spoken aloud.

    Returns:
        bool: True if espeak exited with code 0, False if espeak is not
            installed, the command timed out, or an error occurred.
    """
    try:
        # Try espeak with Indian English
        cmd = ['espeak', '-v', 'en-in', '-s', '150', text]
        result = subprocess.run(cmd, capture_output=True, timeout=10)

        if result.returncode == 0:
            log_voice(f"[TTS-ESPEAK-SUCCESS] Spoke with en-in: {text[:60]}")
            return True
        else:
            # Fallback to default English
            cmd = ['espeak', '-v', 'en', '-s', '150', text]
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0:
                log_voice(f"[TTS-ESPEAK-SUCCESS] Spoke with fallback: {text[:60]}")
                return True
            else:
                log_voice(f"[TTS-ESPEAK-FAILED] Return code: {result.returncode}")
                return False

    except FileNotFoundError:
        log_voice("[TTS-ESPEAK] espeak not installed - skipping")
        return False
    except Exception as e:
        log_voice(f"[TTS-ESPEAK-ERROR] {str(e)[:100]}")
        return False


def main():
    """Entry point for the voice-notifier CLI.

    Reads the text to speak from command-line arguments (all positional
    args are joined with spaces). Selects the platform-specific TTS
    backend (Windows: pyttsx3, Unix: espeak) and exits 0 on both success
    and silent failure so the calling hook is never interrupted.
    """
    if len(sys.argv) < 2:
        log_voice("[ERROR] No text provided")
        sys.exit(1)

    text = ' '.join(sys.argv[1:])

    if not text or not text.strip():
        log_voice("[ERROR] Empty text provided")
        sys.exit(1)

    log_voice(f"[INIT] Speaking: {text[:80]}")

    # Try platform-specific TTS
    success = False

    if sys.platform == 'win32':
        success = speak_windows(text)
    else:
        success = speak_unix(text)

    if success:
        log_voice("[OK] Voice notification completed")
        sys.exit(0)
    else:
        log_voice("[WARN] TTS failed or not available - silent mode")
        sys.exit(0)  # Don't fail - just be silent


if __name__ == '__main__':
    main()
