#!/usr/bin/env python
"""
Step 9: Branch Creator

Creates a feature branch from main for implementation.

Input: JSON via stdin or environment variables (issue_id, task_type)
Output: JSON with branch_name, branch_created status
"""

import json
import sys
import os
import subprocess
from pathlib import Path

DEBUG = os.getenv("CLAUDE_DEBUG") == "1"


def create_branch(issue_id: str, task_type: str, base_branch: str = "main") -> dict:
    """Create a feature branch from main.

    Args:
        issue_id: GitHub issue ID
        task_type: Type of task (e.g., "Feature", "Bug Fix")
        base_branch: Base branch to branch from (default: main)

    Returns:
        dict with branch_name, branch_created status
    """
    try:
        # Create branch name: {issue_id}-{task_type}
        task_label = task_type.lower().replace(" ", "-")
        branch_name = f"{issue_id}-{task_label}"

        if DEBUG:
            print(f"[BRANCH-CREATOR] Creating branch: {branch_name}", file=sys.stderr)

        # Phase 2: Mock implementation (would use git CLI in production)
        # In production: would run:
        # git checkout -b {branch_name} {base_branch}
        # git push -u origin {branch_name}

        # Check if git is available (optional, for debug)
        try:
            result = subprocess.run(
                ["git", "status"],
                capture_output=True,
                text=True,
                timeout=5
            )
            git_available = result.returncode == 0
        except:
            git_available = False

        return {
            "status": "OK",
            "branch_name": branch_name,
            "branch_created": True,
            "git_available": git_available,
            "message": f"Branch '{branch_name}' created successfully (mock)"
        }

    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "branch_created": False
        }


def main():
    """Main entry point."""
    try:
        # Parse input from environment variables
        issue_id = os.environ.get("ISSUE_ID", "0")
        task_type = os.environ.get("TASK_TYPE", "feature")
        base_branch = os.environ.get("BASE_BRANCH", "main")

        # Create branch
        result = create_branch(
            issue_id=issue_id,
            task_type=task_type,
            base_branch=base_branch
        )

        # Output as JSON
        print(json.dumps(result))
        sys.exit(0)

    except Exception as e:
        error_result = {
            "status": "ERROR",
            "error": str(e)
        }
        print(json.dumps(error_result))
        sys.exit(1)


if __name__ == "__main__":
    main()
