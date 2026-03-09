#!/usr/bin/env python3
"""
Level 3 Step 6 - Tool Usage Optimizer (for LangGraph)

Suggests tool optimization hints based on context usage.
Simpler than full tool-usage-optimizer.py - just JSON output for orchestrator.
"""

import json
import sys
import os


def main():
    """Return tool optimization hints."""
    # Get context percentage from args
    context_pct = 50
    for arg in sys.argv[1:]:
        if arg.startswith('--context='):
            try:
                context_pct = int(arg.split('=')[1])
            except (ValueError, IndexError):
                pass

    # Simple optimization hints based on context
    hints = []
    if context_pct > 85:
        hints.append("Context very high - use Read with offset/limit")
        hints.append("Use Grep with head_limit to reduce output")
        hints.append("Consider archiving old logs")
    elif context_pct > 75:
        hints.append("Context high - optimize Read calls")
        hints.append("Use Grep head_limit for large searches")
    else:
        hints.append("Context normal - standard tool usage OK")

    output = {
        "optimization_hints": hints,
        "read_opts": {
            "use_offset_limit": context_pct > 75,
            "max_lines": 100 if context_pct > 85 else 500
        },
        "grep_opts": {
            "use_head_limit": context_pct > 75,
            "max_results": 50 if context_pct > 85 else 200
        },
        "context_percentage": context_pct,
        "status": "OK"
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
