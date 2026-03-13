#!/usr/bin/env python
"""
Step 8: GitHub Issue Creator

Converts task prompt into a GitHub issue for tracking.
Creates issue with title, body (full prompt), and labels.

Input: JSON via stdin or environment variables
Output: JSON with issue_id, issue_url
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

DEBUG = os.getenv("CLAUDE_DEBUG") == "1"


def create_github_issue(task_type: str, complexity: int, user_message: str, prompt_content: str, tasks: list, project_root: str = ".") -> dict:
    """Create a GitHub issue from task information.

    Args:
        task_type: Type of task (e.g., "Feature", "Bug Fix")
        complexity: Complexity score (1-10)
        user_message: User's original request
        prompt_content: Full execution prompt
        tasks: List of tasks from task breakdown
        project_root: Root directory of project

    Returns:
        dict with issue_id, issue_url, or error status
    """
    try:
        # Create title
        title = f"[{task_type}] Complexity-{complexity}/10 - {user_message[:60]}"

        # Create body with checklist
        body_parts = [
            "# Execution Task\n",
            prompt_content,
            "\n\n## Implementation Checklist\n"
        ]

        for i, task in enumerate(tasks[:15], 1):  # Show first 15 tasks
            if isinstance(task, dict):
                task_desc = task.get('description', task.get('id', f'Task {i}'))
            else:
                task_desc = str(task)
            body_parts.append(f"- [ ] {task_desc}")

        body = "\n".join(body_parts)

        # Create labels
        labels = [task_type, f"complexity-{min(complexity, 10)}"]

        if DEBUG:
            print(f"[GITHUB-ISSUE-CREATOR] Would create issue:", file=sys.stderr)
            print(f"  Title: {title}", file=sys.stderr)
            print(f"  Labels: {labels}", file=sys.stderr)

        # Phase 2: Mock implementation (would use gh CLI in production)
        # In production: would run: gh issue create --title "$title" --body "$body" --label "$labels"

        return {
            "status": "OK",
            "issue_id": "42",
            "issue_url": f"https://github.com/{project_root}/issues/42",
            "issue_created": True,
            "title": title,
            "labels": labels,
            "message": "Issue created successfully (mock)"
        }

    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "issue_created": False
        }


def main():
    """Main entry point."""
    try:
        # Parse input from command line args or stdin
        task_type = os.environ.get("TASK_TYPE", "Feature")
        complexity = int(os.environ.get("COMPLEXITY", "5"))
        user_message = os.environ.get("USER_MESSAGE", "No message provided")
        prompt_content = os.environ.get("PROMPT_CONTENT", "")
        tasks_json = os.environ.get("TASKS", "[]")
        project_root = os.environ.get("PROJECT_ROOT", ".")

        try:
            tasks = json.loads(tasks_json)
        except:
            tasks = []

        # Create issue
        result = create_github_issue(
            task_type=task_type,
            complexity=complexity,
            user_message=user_message,
            prompt_content=prompt_content,
            tasks=tasks,
            project_root=project_root
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
