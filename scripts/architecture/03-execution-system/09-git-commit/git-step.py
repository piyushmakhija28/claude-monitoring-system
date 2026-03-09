#!/usr/bin/env python3
"""
Level 3 Step 9 - Git Commit Preparation

Check if commit is ready and prepare commit message.
"""

import json
import sys
import subprocess
from pathlib import Path


def main():
    """Check git status and prepare commit."""
    try:
        # Check if there are staged changes
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )

        has_changes = bool(result.stdout.strip())

        output = {
            "commit_ready": has_changes,
            "message": "Ready for commit" if has_changes else "No changes to commit",
            "version": "1.0.0",
            "status": "OK"
        }

    except Exception:
        output = {
            "commit_ready": False,
            "message": "Git check failed",
            "version": "1.0.0",
            "status": "OK"
        }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
