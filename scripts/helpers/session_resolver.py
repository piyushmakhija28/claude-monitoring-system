# ruff: noqa: F821
"""helpers/session_resolver.py - Shared session ID resolution.

Common logic for resolving the current Claude Code session ID,
used by pre_tool_enforcer, post_tool_tracker, and github_operations.

Session resolution order:
  1. Per-project session file (multi-window isolation)
  2. Legacy global .current-session.json (backward compat)
  3. session-progress.json (may be stale)

Windows-safe: ASCII only, no Unicode characters.
"""
import json
import os
from pathlib import Path


def get_current_session_id():
    """Get the current session ID with multiple fallback sources.

    Returns:
        str or None: Session ID string, or None if unavailable.
    """
    # Method 1: Per-project session file
    try:
        from project_session import get_project_session_file

        proj_file = get_project_session_file()
        if proj_file and Path(proj_file).exists():
            with open(proj_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            sid = data.get("session_id", "")
            if sid:
                return sid
    except Exception:
        pass

    # Method 2: Legacy global session file
    try:
        legacy_file = Path.home() / ".claude" / "memory" / ".current-session.json"
        if legacy_file.exists():
            with open(legacy_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            sid = data.get("session_id", "")
            if sid:
                return sid
    except Exception:
        pass

    # Method 3: CLAUDE_SESSION_ID env var
    sid = os.environ.get("CLAUDE_SESSION_ID", "")
    if sid:
        return sid

    return None
