"""helpers/flow_trace_reader.py - Shared flow trace loading.

Common logic for reading flow-trace.json from the current session,
used by pre_tool_enforcer, post_tool_tracker, and other hook scripts.

Context chain: 3-level-flow.py writes flow-trace.json -> hooks read it.

Windows-safe: ASCII only, no Unicode characters.
"""

import json
from pathlib import Path


def load_flow_trace_context(session_id=None):
    """Load flow-trace.json context for the current session.

    Reads the flow trace written by 3-level-flow.py to get task context
    (task_type, complexity, model, skill).

    Args:
        session_id: Optional session ID. If None, attempts to resolve it.

    Returns:
        dict: Context dict with task_type, complexity, model, skill keys.
              Empty dict if unavailable.
    """
    if not session_id:
        try:
            from .session_resolver import get_current_session_id

            session_id = get_current_session_id()
        except Exception:
            return {}

    if not session_id:
        return {}

    try:
        memory_base = Path.home() / ".claude" / "memory"
        trace_file = memory_base / "logs" / "sessions" / session_id / "flow-trace.json"
        if not trace_file.exists():
            return {}

        with open(trace_file, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # v4.4.0+: array of traces - use latest entry
        if isinstance(raw, list) and raw:
            data = raw[-1]
        elif isinstance(raw, dict):
            data = raw
        else:
            return {}

        final_decision = data.get("final_decision", {})
        return {
            "task_type": final_decision.get("task_type", ""),
            "complexity": final_decision.get("complexity", 0),
            "model": final_decision.get("model_selected", ""),
            "skill": final_decision.get("skill_or_agent", ""),
        }
    except Exception:
        return {}


def load_raw_flow_trace(session_id=None):
    """Load the raw flow-trace.json dict for the current session.

    Unlike load_flow_trace_context(), this returns the full trace data
    (pipeline steps, level results, etc.) without extraction.

    Args:
        session_id: Optional session ID. If None, attempts to resolve it.

    Returns:
        dict or None: Raw trace data, or None if unavailable.
    """
    if not session_id:
        try:
            from .session_resolver import get_current_session_id

            session_id = get_current_session_id()
        except Exception:
            return None

    if not session_id:
        return None

    try:
        memory_base = Path.home() / ".claude" / "memory"
        trace_file = memory_base / "logs" / "sessions" / session_id / "flow-trace.json"
        if not trace_file.exists():
            return None

        with open(trace_file, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if isinstance(raw, list) and raw:
            return raw[-1]
        elif isinstance(raw, dict):
            return raw
        return None
    except Exception:
        return None
