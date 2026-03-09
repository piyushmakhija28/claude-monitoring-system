#!/usr/bin/env python3
"""
Level 3 Step 8 - Progress Tracking

Track task progress and incomplete work.
"""

import json
import sys


def main():
    """Return progress tracking info."""
    # Simple progress tracking
    output = {
        "progress": {
            "percentage": 50,
            "completed_steps": 6,
            "total_steps": 12,
            "current_step": 8
        },
        "incomplete_work": [],
        "status": "OK"
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
