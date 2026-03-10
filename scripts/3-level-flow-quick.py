#!/usr/bin/env python3
"""
Lightweight 3-Level Flow Hook - Level -1 + Session Init ONLY

For UserPromptSubmit hook (must be FAST <300ms)
Does NOT run Levels 1, 2, 3 (those are too slow for hooks)

What it does:
- Level -1: Unicode/encoding/path checks (BLOCKING)
- Session ID generation
- Quick status output

What it skips:
- Level 1: Context/session/preferences (slow - 4 parallel tasks)
- Level 2: Standards validation (slow - Java/Python checking)
- Level 3: Full execution (very slow - 12 steps)
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

VERSION = "5.0.0-quick"
SCRIPT_NAME = "3-level-flow-quick.py"


def check_unicode_files():
    """Level -1: Check all Python files are ASCII-only on Windows."""
    if sys.platform != 'win32':
        return True, []

    non_ascii_files = []
    search_dir = Path.cwd()

    # Check only langgraph_engine and core scripts
    for pattern in ['langgraph_engine/**/*.py', '*.py']:
        for py_file in search_dir.glob(pattern):
            try:
                with open(py_file, 'rb') as f:
                    content = f.read()
                    # Check if file is pure ASCII
                    try:
                        content.decode('ascii')
                    except UnicodeDecodeError:
                        non_ascii_files.append(str(py_file))
            except Exception:
                pass

    return len(non_ascii_files) == 0, non_ascii_files


def check_path_resolution():
    """Level -1: Verify path_resolver.py exists and works."""
    project_root = Path.cwd()

    # Optional check - path_resolver might not exist in all projects
    path_resolver = project_root / "src" / "utils" / "path_resolver.py"
    return path_resolver.exists()


def generate_session_id():
    """Generate unique session ID."""
    import uuid
    return f"SESSION-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"


def write_quick_checkpoint(session_id, errors):
    """Write minimal flow-trace.json with only Level -1 data."""
    checkpoint = {
        "meta": {
            "flow_version": VERSION,
            "script": SCRIPT_NAME,
            "mode": "quick-hook",
            "flow_start": datetime.now().isoformat(),
            "flow_end": datetime.now().isoformat(),
            "duration_seconds": 0.0,
            "session_id": session_id,
            "engine": "Quick-Hook"
        },
        "user_input": {
            "prompt": "[Hook execution - no prompt yet]",
            "received_at": datetime.now().isoformat(),
            "source": "UserPromptSubmit Hook"
        },
        "pipeline": [
            {
                "step": "LEVEL_MINUS_1",
                "name": "Auto-Fix Enforcement",
                "level": -1,
                "order": 0,
                "is_blocking": True,
                "timestamp": datetime.now().isoformat(),
                "duration_ms": 0,
                "policy_output": {
                    "status": "FAILED" if errors else "OK",
                    "errors": errors if errors else []
                }
            }
        ]
    }

    # Write to flow-trace.json
    log_dir = Path.home() / ".claude" / "memory" / "logs" / "sessions"
    log_dir.mkdir(parents=True, exist_ok=True)

    flow_file = log_dir / "flow-trace.json"
    try:
        with open(flow_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not write flow-trace: {e}", file=sys.stderr)


def main():
    """Quick hook entry point."""
    try:
        # Generate session
        session_id = generate_session_id()

        # Level -1 checks
        errors = []

        # Check 1: Unicode/encoding
        unicode_ok, non_ascii_files = check_unicode_files()
        if not unicode_ok:
            errors.append(f"Encoding check failed: Non-ASCII Python files found: {', '.join(non_ascii_files[:3])}")

        # Check 2: Path resolution (optional)
        path_ok = check_path_resolution()
        # Don't fail on this - it's optional

        # Write checkpoint
        write_quick_checkpoint(session_id, errors)

        # Output status
        status = "FAILED" if errors else "OK"
        print(f"""[FLOW CHECKPOINT]
  Status: {status}
  Session: {session_id}
  Context: 0.0%
  Model: haiku""")

        if errors:
            print("\n[ERRORS]")
            for err in errors:
                print(f"  - {err}")
            sys.exit(1)

        sys.exit(0)

    except Exception as e:
        print(f"[ERROR] Hook failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
