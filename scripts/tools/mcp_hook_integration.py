"""
MCP Hook Integration - Enables AUTO-ROUTE mode in pre-tool-enforcer.py

Provides utilities for detecting MCP availability and suggesting/routing to MCPs
when tool optimization rules are triggered. This module bridges the hook layer
with the MCP plugin system.

Usage in pre-tool-enforcer.py:
    from mcp_hook_integration import should_suggest_mcp, get_mcp_suggestion_message

    # In check_read()
    if is_large_file and mcp_available:
        message = get_mcp_suggestion_message('read', file_size)
        # Output message suggesting MCP as option
"""

import json
from pathlib import Path
from typing import Dict, Optional


def _get_mcp_config_from_flow_trace() -> Dict[str, bool]:
    """Load MCP configuration from flow-trace.json if available.

    Returns:
        Dict with keys:
        - mcp_filesystem_enabled: bool
        - mcp_auto_routing_enabled: bool
        - mcp_available_mcps: list
    """
    try:
        # Try to find current session flow-trace
        session_id = _get_current_session_id()
        if not session_id:
            return {"mcp_filesystem_enabled": False, "mcp_auto_routing_enabled": False}

        trace_file = Path.home() / ".claude" / "memory" / "logs" / "sessions" / session_id / "flow-trace.json"

        if not trace_file.exists():
            return {"mcp_filesystem_enabled": False, "mcp_auto_routing_enabled": False}

        with open(trace_file, "r", encoding="utf-8", errors="replace") as f:
            trace_data = json.load(f)

        # Extract MCP info from final_decision if available
        final_decision = trace_data.get("final_decision", {})

        return {
            "mcp_filesystem_enabled": final_decision.get("mcp_filesystem_enabled", False),
            "mcp_auto_routing_enabled": final_decision.get("mcp_auto_routing_enabled", False),
            "mcp_available_mcps": final_decision.get("mcp_servers_available", []),
        }

    except Exception:
        # Silent fail - return defaults
        return {"mcp_filesystem_enabled": False, "mcp_auto_routing_enabled": False}


def _get_current_session_id() -> Optional[str]:
    """Get current session ID from environment or flag file."""
    try:
        # Try from environment
        if "CLAUDE_SESSION_ID" in __import__("os").environ:
            return __import__("os").environ["CLAUDE_SESSION_ID"]

        # Try from flag file
        flag_dir = Path.home() / ".claude" / ".session"
        flag_file = flag_dir / "current-session-id"

        if flag_file.exists():
            return flag_file.read_text(encoding="utf-8", errors="replace").strip()

        return None
    except Exception:
        return None


def should_suggest_mcp() -> bool:
    """Check if MCP AUTO-ROUTE should be suggested to Claude.

    Returns:
        True if filesystem MCP is enabled and auto-routing is allowed
    """
    config = _get_mcp_config_from_flow_trace()
    return config.get("mcp_filesystem_enabled", False) and config.get("mcp_auto_routing_enabled", False)


def get_mcp_read_suggestion() -> str:
    """Get suggestion message for Read tool when file is too large.

    Returns:
        Message suggesting MCP as alternative to offset/limit chunking
    """
    return (
        "\n[MCP OPTION] Use Filesystem MCP read_smart() for automatic chunking "
        "(no offset/limit needed - handles large files automatically)"
    )


def get_mcp_grep_suggestion() -> str:
    """Get suggestion message for Grep tool without head_limit.

    Returns:
        Message suggesting MCP as alternative to manual head_limit
    """
    return (
        "\n[MCP OPTION] Use Filesystem MCP grep_smart() with automatic result limiting "
        "(no head_limit needed - handles large output automatically)"
    )


def enhance_read_blocking_message(original_message: str, file_size_kb: int) -> str:
    """Enhance Read blocking message with MCP suggestion if available.

    Args:
        original_message: Original blocking message
        file_size_kb: File size in KB

    Returns:
        Enhanced message with MCP option if MCP is enabled
    """
    if should_suggest_mcp():
        return (
            f"{original_message}\n"
            f"OR\n"
            f"2. Use Filesystem MCP read_smart(file_path) - automatically handles "
            f"files up to any size with built-in chunking (0-500 lines per call)."
        )
    return original_message


def enhance_grep_blocking_message(original_message: str) -> str:
    """Enhance Grep blocking message with MCP suggestion if available.

    Args:
        original_message: Original blocking message

    Returns:
        Enhanced message with MCP option if MCP is enabled
    """
    if should_suggest_mcp():
        return (
            f"{original_message}\n"
            f"OR\n"
            f"2. Use Filesystem MCP grep_smart(pattern, directory) - automatically "
            f"limits results to 50 matches (no head_limit needed)."
        )
    return original_message


def log_mcp_routing_decision(operation: str, tool_name: str, mcp_suggested: bool) -> None:
    """Log MCP routing decision for monitoring.

    Args:
        operation: Operation name (read_smart, grep_smart, etc.)
        tool_name: Original tool name (Read, Grep, etc.)
        mcp_suggested: Whether MCP was suggested
    """
    try:
        # Silent logging - don't interfere with normal hook output
        log_entry = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "tool": tool_name,
            "mcp_operation": operation,
            "mcp_suggested": mcp_suggested,
        }

        # Write to metrics file for later analysis
        metrics_dir = Path.home() / ".claude" / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)

        # Append to metrics log
        metrics_file = metrics_dir / "mcp-routing.jsonl"
        with open(metrics_file, "a", encoding="utf-8", errors="replace") as f:
            f.write(json.dumps(log_entry) + "\n")

    except Exception:
        # Never fail on logging
        pass
