"""
GitHub Integration - PyGithub wrapper for Level 3 automation.

Provides:
- Issue creation with labels and description
- Pull request creation and merge
- Issue closure with comments
- GitHub metadata tracking

Uses: PyGithub library (python-github)
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime

from loguru import logger

try:
    from github import Github
    _GITHUB_AVAILABLE = True
except ImportError:
    _GITHUB_AVAILABLE = False
    logger.warning("PyGithub not installed. GitHub integration disabled.")


class GitHubIntegration:
    """Manages GitHub operations for Level 3 automation."""

    def __init__(self, token: Optional[str] = None, repo_path: str = "."):
        """
        Initialize GitHub integration.

        Args:
            token: GitHub personal access token (from GITHUB_TOKEN env var if None)
            repo_path: Local repository path (used for detecting repo info from git remote)
        """
        if not _GITHUB_AVAILABLE:
            raise RuntimeError("PyGithub not installed. Install with: pip install PyGithub")

        # Get token from environment
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise RuntimeError("GITHUB_TOKEN environment variable not set")

        # Initialize GitHub client
        self.gh = Github(self.token)
        self.repo = self._get_repo(repo_path)

        if self.repo:
            logger.info(f"GitHub integration initialized: {self.repo.full_name}")
        else:
            logger.warning("Could not determine GitHub repository")

    def _get_repo(self, repo_path: str):
        """Detect repository from local git remote."""
        try:
            import subprocess
            from pathlib import Path

            repo_dir = Path(repo_path)

            # Get remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                logger.error("Cannot get git remote URL")
                return None

            remote_url = result.stdout.strip()

            # Parse owner/repo from URL
            # Supports: https://github.com/owner/repo.git or git@github.com:owner/repo.git
            if "github.com" not in remote_url:
                logger.error(f"Not a GitHub repository: {remote_url}")
                return None

            if remote_url.startswith("git@"):
                # git@github.com:owner/repo.git
                parts = remote_url.split(":")[-1].replace(".git", "").split("/")
            else:
                # https://github.com/owner/repo.git
                parts = remote_url.rstrip("/").replace(".git", "").split("/")[-2:]

            owner, repo_name = parts[0], parts[1]

            # Get repo object
            user = self.gh.get_user(owner)
            repo = user.get_repo(repo_name)

            logger.info(f"Detected repository: {owner}/{repo_name}")
            return repo

        except Exception as e:
            logger.error(f"Cannot detect repository: {e}")
            return None

    # ===== ISSUE OPERATIONS =====

    def create_issue(
        self,
        title: str,
        body: str = "",
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a GitHub issue.

        Args:
            title: Issue title
            body: Issue description (markdown supported)
            labels: List of label names (e.g., ["bug", "critical"])
            assignee: Username to assign to

        Returns:
            {
                "success": bool,
                "issue_number": int,
                "issue_url": str,
                "issue_id": int,
                "created_at": str
            }
        """
        if not self.repo:
            logger.error("No repository configured")
            return {"success": False, "error": "No repository"}

        logger.info(f"Creating issue: {title[:50]}...")

        try:
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=labels or [],
                assignee=assignee
            )

            logger.info(f"✓ Issue created: #{issue.number}")

            return {
                "success": True,
                "issue_number": issue.number,
                "issue_url": issue.html_url,
                "issue_id": issue.id,
                "created_at": issue.created_at.isoformat()
            }

        except Exception as e:
            logger.error(f"Issue creation failed: {e}")
            return {"success": False, "error": str(e)}

    def add_issue_comment(
        self,
        issue_number: int,
        comment: str
    ) -> Dict[str, Any]:
        """
        Add a comment to an issue.

        Args:
            issue_number: GitHub issue number
            comment: Comment text (markdown supported)

        Returns:
            {"success": bool, "comment_id": int, "comment_url": str}
        """
        if not self.repo:
            return {"success": False, "error": "No repository"}

        logger.info(f"Adding comment to issue #{issue_number}")

        try:
            issue = self.repo.get_issue(issue_number)
            comment_obj = issue.create_comment(comment)

            logger.info(f"✓ Comment added to issue #{issue_number}")

            return {
                "success": True,
                "comment_id": comment_obj.id,
                "comment_url": comment_obj.html_url
            }

        except Exception as e:
            logger.error(f"Comment failed: {e}")
            return {"success": False, "error": str(e)}

    def close_issue(self, issue_number: int, closing_comment: Optional[str] = None) -> Dict[str, Any]:
        """
        Close a GitHub issue.

        Args:
            issue_number: GitHub issue number
            closing_comment: Optional comment to add before closing

        Returns:
            {"success": bool, "closed_at": str}
        """
        if not self.repo:
            return {"success": False, "error": "No repository"}

        logger.info(f"Closing issue #{issue_number}")

        try:
            issue = self.repo.get_issue(issue_number)

            # Add closing comment if provided
            if closing_comment:
                comment_result = self.add_issue_comment(issue_number, closing_comment)
                if not comment_result.get("success"):
                    logger.warning(f"Could not add closing comment: {comment_result.get('error')}")

            # Close the issue
            issue.edit(state="closed")

            logger.info(f"✓ Issue #{issue_number} closed")

            return {
                "success": True,
                "issue_number": issue_number,
                "closed_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Issue closure failed: {e}")
            return {"success": False, "error": str(e)}

    # ===== PULL REQUEST OPERATIONS =====

    def create_pull_request(
        self,
        title: str,
        body: str = "",
        head_branch: str = None,
        base_branch: str = "main",
        labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a pull request.

        Args:
            title: PR title
            body: PR description (markdown)
            head_branch: Source branch
            base_branch: Target branch (default: main)
            labels: List of label names

        Returns:
            {
                "success": bool,
                "pr_number": int,
                "pr_url": str,
                "pr_id": int
            }
        """
        if not self.repo:
            return {"success": False, "error": "No repository"}

        if not head_branch:
            logger.error("head_branch required")
            return {"success": False, "error": "head_branch required"}

        logger.info(f"Creating PR: {title[:50]}...")

        try:
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch
            )

            # Add labels if provided
            if labels:
                try:
                    pr.add_to_labels(*labels)
                    logger.debug(f"Added labels to PR: {labels}")
                except Exception as e:
                    logger.warning(f"Could not add labels: {e}")

            logger.info(f"✓ PR created: #{pr.number}")

            return {
                "success": True,
                "pr_number": pr.number,
                "pr_url": pr.html_url,
                "pr_id": pr.id,
                "created_at": pr.created_at.isoformat()
            }

        except Exception as e:
            logger.error(f"PR creation failed: {e}")
            return {"success": False, "error": str(e)}

    def merge_pull_request(
        self,
        pr_number: int,
        commit_message: Optional[str] = None,
        delete_branch: bool = True
    ) -> Dict[str, Any]:
        """
        Merge a pull request.

        Args:
            pr_number: PR number
            commit_message: Custom merge commit message
            delete_branch: Delete source branch after merge

        Returns:
            {"success": bool, "merged": bool, "merge_commit_sha": str}
        """
        if not self.repo:
            return {"success": False, "error": "No repository"}

        logger.info(f"Merging PR #{pr_number}")

        try:
            pr = self.repo.get_pull(pr_number)

            # Check if mergeable
            if not pr.mergeable:
                logger.error(f"PR #{pr_number} has conflicts")
                return {"success": False, "error": "PR has merge conflicts"}

            # Merge the PR
            result = pr.merge(
                commit_message=commit_message or f"Merge pull request #{pr_number}",
                merge_method="squash"  # Squash commits
            )

            if result.merged:
                logger.info(f"✓ PR #{pr_number} merged")

                # Delete head branch if requested
                if delete_branch and pr.head.ref:
                    try:
                        ref = self.repo.get_git_ref(f"heads/{pr.head.ref}")
                        ref.delete()
                        logger.info(f"Deleted branch: {pr.head.ref}")
                    except Exception as e:
                        logger.warning(f"Could not delete branch: {e}")

                return {
                    "success": True,
                    "merged": True,
                    "merge_commit_sha": result.sha
                }
            else:
                logger.error(f"PR merge returned false")
                return {"success": False, "error": "Merge failed"}

        except Exception as e:
            logger.error(f"PR merge failed: {e}")
            return {"success": False, "error": str(e)}

    def add_pr_comment(self, pr_number: int, comment: str) -> Dict[str, Any]:
        """Add a comment to a pull request."""
        if not self.repo:
            return {"success": False, "error": "No repository"}

        logger.info(f"Adding comment to PR #{pr_number}")

        try:
            pr = self.repo.get_pull(pr_number)
            comment_obj = pr.create_issue_comment(comment)

            return {
                "success": True,
                "comment_id": comment_obj.id,
                "comment_url": comment_obj.html_url
            }

        except Exception as e:
            logger.error(f"PR comment failed: {e}")
            return {"success": False, "error": str(e)}

    # ===== LABEL OPERATIONS =====

    def get_available_labels(self) -> List[str]:
        """Get list of available labels in repository."""
        if not self.repo:
            return []

        try:
            labels = [label.name for label in self.repo.get_labels()]
            logger.debug(f"Available labels: {labels[:5]}...")
            return labels
        except Exception as e:
            logger.error(f"Could not fetch labels: {e}")
            return []

    # ===== CONVENIENCE METHODS =====

    def create_issue_and_pr(
        self,
        title: str,
        issue_body: str,
        pr_body: str,
        head_branch: str,
        labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create both issue and pull request.

        Returns:
            {
                "success": bool,
                "issue": {"number": int, "url": str},
                "pr": {"number": int, "url": str}
            }
        """
        logger.info(f"Creating issue and PR for: {title[:40]}...")

        # Create issue
        issue_result = self.create_issue(title, issue_body, labels)
        if not issue_result.get("success"):
            return issue_result

        issue_number = issue_result.get("issue_number")

        # Create PR
        pr_result = self.create_pull_request(title, pr_body, head_branch)
        if not pr_result.get("success"):
            logger.warning(f"PR creation failed: {pr_result.get('error')}")
            return {
                "success": False,
                "error": "PR creation failed",
                "issue": issue_result
            }

        return {
            "success": True,
            "issue": {
                "number": issue_number,
                "url": issue_result.get("issue_url")
            },
            "pr": {
                "number": pr_result.get("pr_number"),
                "url": pr_result.get("pr_url")
            }
        }
