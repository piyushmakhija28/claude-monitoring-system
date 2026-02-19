#!/usr/bin/env python3
"""
Script Name: clear-session-handler.py
Version: 1.0.0
Last Modified: 2026-02-18
Description: Detects /clear command usage via UserPromptSubmit hook.
             Compares current transcript message count vs last known count.
             If count decreased or transcript changed = /clear was used.
             Action: Save old session, create new one.

Detection Logic:
  - Tracks transcript_path + message count in ~/.claude/.hook-state.json
  - If msg_count < last_msg_count  -> /clear detected (count dropped)
  - If transcript_path changed     -> new conversation/window detected
  - If msg_count == 0 + no prior   -> fresh start

Windows-Safe: No Unicode chars (ASCII only, cp1252 compatible)
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime

# Windows: ASCII-only output (no Unicode/emojis)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

MEMORY_BASE = Path.home() / '.claude' / 'memory'
CURRENT_DIR = MEMORY_BASE / 'current'
SESSIONS_DIR = MEMORY_BASE / 'sessions'
CURRENT_SESSION_FILE = MEMORY_BASE / '.current-session.json'
HOOK_STATE_FILE = Path.home() / '.claude' / '.hook-state.json'
CLEAR_LOG = MEMORY_BASE / 'logs' / 'clear-events.log'
VOICE_SCRIPT = CURRENT_DIR / 'voice-notifier.py'


# =============================================================================
# LOGGING
# =============================================================================

def log_event(msg):
    """Log to clear-events.log (ASCII only)"""
    CLEAR_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(CLEAR_LOG, 'a', encoding='utf-8') as f:
            f.write(f"{ts} | {msg}\n")
    except Exception:
        pass


# =============================================================================
# HOOK STDIN
# =============================================================================

def read_hook_stdin():
    """Read JSON data from Claude Code hook stdin"""
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            if raw and raw.strip():
                return json.loads(raw.strip())
    except Exception:
        pass
    return {}


# =============================================================================
# TRANSCRIPT ANALYSIS
# =============================================================================

def count_transcript_messages(transcript_path):
    """
    Count user+assistant messages in transcript file.
    Returns:
      -1  = cannot read / unknown state
       0  = file empty or doesn't exist (fresh conversation)
      N>0 = N messages found
    """
    if not transcript_path:
        return -1

    path = Path(transcript_path)

    if not path.exists():
        return 0  # No file = definitely fresh

    try:
        content = path.read_text(encoding='utf-8', errors='replace').strip()
        if not content:
            return 0  # Empty file = fresh

        count = 0

        # Try JSONL format (one JSON object per line) - Claude Code default
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                if isinstance(msg, dict):
                    role = msg.get('role', '') or msg.get('type', '')
                    if role in ('user', 'assistant', 'human'):
                        count += 1
            except Exception:
                pass

        if count > 0:
            return count

        # Try single JSON array
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return len([m for m in data
                            if isinstance(m, dict)
                            and m.get('role') in ('user', 'assistant', 'human')])
            if isinstance(data, dict):
                msgs = data.get('messages', data.get('conversation', []))
                return len([m for m in msgs
                            if isinstance(m, dict)
                            and m.get('role') in ('user', 'assistant', 'human')])
        except Exception:
            pass

        # File exists and has content but can't parse = assume has messages
        return 99

    except Exception:
        return -1


# =============================================================================
# STATE TRACKING
# =============================================================================

def read_state():
    """Read the hook state file"""
    if not HOOK_STATE_FILE.exists():
        return {}
    try:
        with open(HOOK_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def write_state(transcript_path, msg_count):
    """Update hook state with current values"""
    state = {
        'last_transcript_path': str(transcript_path) if transcript_path else '',
        'last_msg_count': msg_count,
        'updated_at': datetime.now().isoformat()
    }
    try:
        HOOK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HOOK_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def detect_clear(current_transcript_path, current_msg_count):
    """
    Compare current state vs last state to detect /clear.
    Returns (is_fresh, reason_string)
    """
    state = read_state()
    last_transcript = state.get('last_transcript_path', '')
    last_count = state.get('last_msg_count', -1)

    # Case 1: No previous state at all - fresh start
    if not last_transcript and current_msg_count <= 1:
        return True, 'first_ever_conversation'

    # Case 2: Transcript file changed - new conversation/window
    if (last_transcript
            and current_transcript_path
            and str(current_transcript_path) != last_transcript):
        return True, f'transcript_changed_from_{Path(last_transcript).name}_to_{Path(str(current_transcript_path)).name}'

    # Case 3: Message count dropped - /clear was used
    if (last_count != -1
            and current_msg_count != -1
            and current_msg_count < last_count):
        return True, f'msg_count_dropped_from_{last_count}_to_{current_msg_count}'

    # Case 4: Transcript empty with same path - cleared
    if (last_transcript
            and current_transcript_path
            and str(current_transcript_path) == last_transcript
            and current_msg_count == 0
            and last_count > 0):
        return True, f'transcript_emptied_was_{last_count}_now_0'

    return False, 'ongoing_conversation'


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

def get_current_session_id():
    """Get active session ID from .current-session.json"""
    if not CURRENT_SESSION_FILE.exists():
        return None
    try:
        with open(CURRENT_SESSION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('current_session_id')
    except Exception:
        return None


def close_current_session(session_id):
    """Mark session as COMPLETED and remove the current session marker"""
    if not session_id:
        return False

    # Update session JSON file with end time
    session_file = SESSIONS_DIR / f'{session_id}.json'
    if session_file.exists():
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            data['end_time'] = datetime.now().isoformat()
            data['status'] = 'COMPLETED'
            data['closed_reason'] = 'clear_command_detected_by_hook'

            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            log_event(f"Session closed and saved: {session_id}")
        except Exception as e:
            log_event(f"Error updating session file {session_id}: {e}")

    # Delete .current-session.json so 3-level-flow creates a fresh session
    if CURRENT_SESSION_FILE.exists():
        try:
            CURRENT_SESSION_FILE.unlink()
            log_event(f"Removed .current-session.json (cleared for {session_id})")
        except Exception as e:
            log_event(f"Error removing current session file: {e}")

    return True


def speak_fast_pyttsx3(text):
    """
    Fast offline TTS using pyttsx3 - no network, no edge-tts delay.
    Launches as DETACHED subprocess so it survives after hook exits.
    Text passed as sys.argv[1] to avoid all quoting/escaping issues.
    Primary method for clear notifications (instant, offline).
    """
    # Inline script reads text from sys.argv[1] - no quoting issues
    inline = (
        "import sys,pyttsx3;"
        "e=pyttsx3.init();"
        "voices=e.getProperty('voices');"
        "kws=['zira','heera','hazel','female','aria','jenny','neerja'];"
        "fid=next((v.id for v in voices if any(k in v.name.lower() for k in kws)),None);"
        "fid=fid or (voices[1].id if len(voices)>1 else (voices[0].id if voices else None));"
        "e.setProperty('voice',fid) if fid else None;"
        "e.setProperty('rate',155);"
        "e.setProperty('volume',0.95);"
        "e.say(sys.argv[1]);"
        "e.runAndWait()"
    )
    try:
        subprocess.Popen(
            [sys.executable, '-c', inline, text],  # text passed as argv[1], no shell escaping needed
            creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
            if sys.platform == 'win32' else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log_event(f"[pyttsx3-fast] Detached process launched: {text[:60]}")
    except Exception as e:
        log_event(f"[pyttsx3-fast] Failed: {e} - trying edge-tts")
        speak_async_edgetts(text)


def speak_async_edgetts(text):
    """
    Fallback: Launch voice-notifier.py (edge-tts) as detached process.
    Slower (needs network) but better Indian voice quality.
    """
    if not VOICE_SCRIPT.exists():
        log_event(f"[voice] voice-notifier.py not found at {VOICE_SCRIPT}")
        return
    try:
        subprocess.Popen(
            [sys.executable, str(VOICE_SCRIPT), text],
            creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
            if sys.platform == 'win32' else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True
        )
        log_event(f"[voice] EdgeTTS async launched: {text[:60]}")
    except Exception as e:
        log_event(f"[voice] EdgeTTS failed to launch: {e}")


def speak_async(text):
    """
    Main speak entry: edge-tts PRIMARY (Indian Neerja voice), pyttsx3 fallback.
    edge-tts = Indian en-IN-NeerjaNeural voice (needs network, 2-3s delay but sounds Indian)
    pyttsx3  = British/US voice (offline, instant but NOT Indian sounding)
    """
    speak_async_edgetts(text)


def create_new_session(reason=''):
    """Create a brand new session via session-id-generator.py"""
    sess_script = CURRENT_DIR / 'session-id-generator.py'
    if not sess_script.exists():
        log_event(f"ERROR: session-id-generator.py not found at {sess_script}")
        return None

    desc = f"New session after /clear at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    if reason:
        desc += f" ({reason})"

    try:
        result = subprocess.run(
            [sys.executable, str(sess_script), 'create', '--description', desc],
            capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=15
        )

        new_session_id = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith('SESSION-'):
                new_session_id = line
                break

        if new_session_id:
            log_event(f"New session created: {new_session_id} (reason: {reason})")
            return new_session_id
        else:
            log_event(f"ERROR: Could not parse session ID from output: {result.stdout[:200]}")
            return None

    except Exception as e:
        log_event(f"ERROR creating session: {e}")
        return None


# =============================================================================
# MAIN
# =============================================================================

def main():
    hook_data = read_hook_stdin()

    transcript_path = hook_data.get('transcript_path', '')
    prompt = hook_data.get('prompt', '')
    prompt_preview = prompt[:80].replace('\n', ' ')

    # Count messages in current transcript
    current_msg_count = count_transcript_messages(transcript_path)

    log_event(
        f"Hook fired | msg_count={current_msg_count} | "
        f"transcript={transcript_path} | prompt='{prompt_preview}'"
    )

    # If we can't determine state at all, skip
    if current_msg_count == -1 and not transcript_path:
        log_event("Cannot determine conversation state - skipping")
        # Still update state with what we know
        write_state(transcript_path, current_msg_count)
        sys.exit(0)

    # Detect if this is a fresh conversation
    is_fresh, reason = detect_clear(transcript_path, current_msg_count)

    if is_fresh:
        log_event(f"[CLEAR DETECTED] reason={reason}")

        current_session = get_current_session_id()

        if current_session:
            # Save and close the old session
            print(f"[SESSION] /clear detected - saving: {current_session}")
            close_current_session(current_session)
            print(f"[SESSION] Old session saved: {current_session}")

            # Create fresh session
            new_session = create_new_session(reason=reason)
            if new_session:
                print(f"[SESSION] New session started: {new_session}")
                log_event(f"Session transition complete: {current_session} -> {new_session}")
                # Voice: emotional girlfriend style - short, expressive
                import random
                gf_messages = [
                    "Arre yaar, naya session! Bata kya soch raha hai.",
                    "Oye oye, clear kar diya tune. Chalo kya plan hai.",
                    "Aww, fresh start mil gaya. Bol ab kya karna hai.",
                    "Haha, clear! Theek hai, bata kya hai agenda.",
                ]
                speak_async(random.choice(gf_messages))
            else:
                print(f"[SESSION] Warning: Could not create new session")
                log_event("Warning: Failed to create new session after /clear")
        else:
            # No existing session - just create a new one
            # (3-level-flow will also try to create if none exists, but we do it here
            #  so it's ready before 3-level-flow reads it)
            new_session = create_new_session(reason=reason)
            if new_session:
                print(f"[SESSION] First session created: {new_session}")
                # Voice: first session - warm, welcoming emotion
                import random
                first_messages = [
                    "Arre, aa gaya tu. Naya session ready hai, bata kya karna hai.",
                    "Aww, finally. Main yahaan hun, bol kya chahiye.",
                    "Oye, session shuru. Kya plan hai aaj.",
                ]
                speak_async(random.choice(first_messages))

    else:
        log_event(f"Ongoing conversation ({reason}) - no session change")

    # Always update state with current values for next call comparison
    write_state(transcript_path, current_msg_count)

    sys.exit(0)


if __name__ == '__main__':
    main()
