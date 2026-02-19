#!/usr/bin/env python3
"""
Script Name: stop-notifier.py
Version: 1.0.0
Last Modified: 2026-02-18
Description: Stop hook - speaks Hinglish session summary when all work is done.

HOW IT WORKS:
  1. Fires on every Claude 'Stop' event (after each AI response)
  2. Checks for ~/.claude/.session-work-done flag file
  3. If flag EXISTS: reads summary text, speaks it in girl voice, deletes flag
  4. If flag ABSENT: stays completely silent (most responses)

HOW TO TRIGGER:
  Claude writes the flag file when all tasks are complete.
  The CLAUDE.md instructs Claude to do this automatically.
  You can also manually create it:
    echo "Bhai sab kaam ho gaya!" > ~/.claude/.session-work-done

FLAG FILE FORMAT:
  Plain text file with the Hinglish message to speak.
  Example content: "Bhai, sab kaam ho gaya! Maine 3 services banaye aur deploy bhi kar diya. Ab aaram karo!"

Windows-Safe: ASCII only (no Unicode/emojis in print statements)
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime

# Windows ASCII-safe encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

MEMORY_BASE = Path.home() / '.claude' / 'memory'
CURRENT_DIR = MEMORY_BASE / 'current'
VOICE_SCRIPT = CURRENT_DIR / 'voice-notifier.py'

# Flag file - Claude writes this when all tasks complete
WORK_DONE_FLAG = Path.home() / '.claude' / '.session-work-done'

# Log file
STOP_LOG = MEMORY_BASE / 'logs' / 'stop-notifier.log'


# =============================================================================
# LOGGING
# =============================================================================

def log_s(msg):
    STOP_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(STOP_LOG, 'a', encoding='utf-8') as f:
            f.write(f"{ts} | {msg}\n")
    except Exception:
        pass


# =============================================================================
# READ HOOK STDIN
# =============================================================================

def read_hook_stdin():
    """Read JSON data from Claude Code Stop hook stdin"""
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            if raw and raw.strip():
                return json.loads(raw.strip())
    except Exception:
        pass
    return {}


# =============================================================================
# SESSION DATA
# =============================================================================

def get_session_summary_from_data():
    """
    Generate a Hinglish summary from session JSON data.
    Used as fallback if flag file has no content.
    """
    try:
        current_session_file = MEMORY_BASE / '.current-session.json'
        if not current_session_file.exists():
            return None

        with open(current_session_file, 'r', encoding='utf-8') as f:
            sess_ref = json.load(f)

        session_id = sess_ref.get('current_session_id', '')
        if not session_id:
            return None

        session_file = MEMORY_BASE / 'sessions' / f'{session_id}.json'
        if not session_file.exists():
            return None

        with open(session_file, 'r', encoding='utf-8') as f:
            sess_data = json.load(f)

        flow_runs = sess_data.get('flow_runs', 0)
        last_task_type = sess_data.get('last_task_type', 'General')
        last_complexity = sess_data.get('last_complexity', 1)

        # Girlfriend style - emotional, short, natural
        if flow_runs <= 1:
            summary = f"Haan ho gaya yaar. {last_task_type} wala ready hai, dekh le."
        elif flow_runs <= 3:
            summary = f"Waah, {flow_runs} kaam kar diye. Sab check kar le."
        else:
            summary = f"Oye waah, {flow_runs} cheezein ho gayi. {last_task_type} focus tha. Dekh le."

        return summary

    except Exception as e:
        log_s(f"Error generating session summary: {e}")
        return None


# =============================================================================
# SPEAK VIA voice-notifier.py
# =============================================================================

def speak_summary(text):
    """Call voice-notifier.py to speak the summary"""
    if not VOICE_SCRIPT.exists():
        log_s(f"[ERROR] voice-notifier.py not found at {VOICE_SCRIPT}")
        print(f"[STOP-NOTIFIER] {text}")
        return

    try:
        # Run voice-notifier - this launches async audio playback and returns quickly
        result = subprocess.run(
            [sys.executable, str(VOICE_SCRIPT), text],
            timeout=25,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        log_s(f"[voice] Spoke summary (rc={result.returncode}): {text[:80]}")
    except subprocess.TimeoutExpired:
        log_s("[voice] Timeout - audio still playing in background")
    except Exception as e:
        log_s(f"[voice] Error: {e}")
        print(f"[STOP-NOTIFIER] {text}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    hook_data = read_hook_stdin()
    stop_hook_active = hook_data.get('stop_hook_active', False)

    log_s(f"Stop hook fired | stop_hook_active={stop_hook_active} | flag_exists={WORK_DONE_FLAG.exists()}")

    # Check for the work-done flag
    if not WORK_DONE_FLAG.exists():
        # No flag = Claude is still working or this is a mid-session response
        # Stay completely silent
        sys.exit(0)

    # Flag found! Read the summary message
    try:
        summary_text = WORK_DONE_FLAG.read_text(encoding='utf-8').strip()
    except Exception as e:
        log_s(f"Error reading flag file: {e}")
        summary_text = ''

    # Delete the flag immediately (one-time notification - won't repeat)
    try:
        WORK_DONE_FLAG.unlink()
        log_s("Flag file deleted (one-time notification)")
    except Exception as e:
        log_s(f"Could not delete flag file: {e}")

    # Use flag content, or generate from session data if empty
    if not summary_text:
        summary_text = get_session_summary_from_data()

    if not summary_text:
        summary_text = "Haan ho gaya yaar. Dekh le."

    log_s(f"Speaking: {summary_text[:120]}")
    print(f"[STOP-NOTIFIER] Speaking session summary...")
    speak_summary(summary_text)

    sys.exit(0)


if __name__ == '__main__':
    main()
