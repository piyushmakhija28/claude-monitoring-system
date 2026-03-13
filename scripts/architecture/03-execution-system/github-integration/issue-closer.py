#!/usr/bin/env python
"""
Step 12: Issue Closer

Closes GitHub issue after successful PR merge.

Posts closing comment with PR link, summary, test results, and next steps.

Input: JSON via stdin or environment variables
Output: JSON with issue_closed status
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

DEBUG = os.getenv("CLAUDE_DEBUG") == "1"


def close_github_issue(issue_id: str, pr_url: str, review_passed: bool, implementation_summary: str = "") -> dict:
    """Close a GitHub issue after implementation.

    Posts a closing comment with:
    - PR link
    - Implementation summary
    - Test results
    - Next steps

    Args:
        issue_id: GitHub issue ID
        pr_url: URL of PR that closes this issue
        review_passed: Whether code review passed
        implementation_summary: Summary of implementation

    Returns:
        dict with issue_closed status
    """
    try:
        if DEBUG:
            print(f"[ISSUE-CLOSER] Closing issue #{issue_id}", file=sys.stderr)

        # Create closing comment
        closing_comment = f"""## ✅ Implementation Complete

**Issue #{issue_id}** has been successfully implemented.

### PR Details
- **PR**: {pr_url}
- **Status**: {'✅ Ready to Merge' if review_passed else '⚠️ Needs Fixes'}

### Summary
{implementation_summary if implementation_summary else 'Implementation completed as per requirements.'}

### What's Next?
1. PR will be automatically merged after approval
2. Changes will be deployed to production
3. Thank you for reporting this issue!

---
*Closed by automation on {datetime.now().isoformat()}*
"""

        if DEBUG:
            print(f"[ISSUE-CLOSER] Closing comment: {closing_comment[:100]}...", file=sys.stderr)

        # Phase 2: Mock implementation (would use gh CLI in production)
        # In production: would run:
        # gh issue comment {issue_id} --body "$closing_comment"
        # gh issue close {issue_id}

        return {
            "status": "OK",
            "issue_closed": True,
            "issue_id": issue_id,
            "closing_comment": closing_comment,
            "closed_at": datetime.now().isoformat(),
            "message": "Issue closed successfully (mock)"
        }

    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "issue_closed": False
        }


def main():
    """Main entry point."""
    try:
        # Parse input from environment variables
        issue_id = os.environ.get("ISSUE_ID", "0")
        pr_url = os.environ.get("PR_URL", "")
        review_passed = os.environ.get("REVIEW_PASSED", "true").lower() == "true"
        implementation_summary = os.environ.get("IMPLEMENTATION_SUMMARY", "")

        # Close issue
        result = close_github_issue(
            issue_id=issue_id,
            pr_url=pr_url,
            review_passed=review_passed,
            implementation_summary=implementation_summary
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
