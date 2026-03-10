"""
Git Operations - Subprocess-based Git CLI wrapper for Level 3 automation.

Provides:
- Branch creation and switching
- Commit operations with proper messages
- Push to remote
- PR-related Git operations
- Status and diff tracking

Uses: Git CLI (via subprocess) - NOT GitPython
"""

import subprocess
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from loguru import logger


class GitOperations:
    """Manages Git operations via CLI for Level 3 execution."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)
        self.repo_path.mkdir(parents=True, exist_ok=True)

        # Verify git is available
        if not self._is_git_available():
            raise RuntimeError("Git CLI not found. Install git and ensure it's in PATH")

        # Get current repo info
        self.origin_url = self._get_origin_url()
        self.current_branch = self._get_current_branch()

        logger.info(f"Git operations initialized at {self.repo_path}")
        logger.info(f"Current branch: {self.current_branch}")
        logger.info(f"Remote origin: {self.origin_url}")

    def _is_git_available(self) -> bool:
        """Check if git CLI is available."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _run_git(self, args: List[str], check: bool = True) -> Dict[str, Any]:
        """
        Run a git command and return output.

        Args:
            args: Git command arguments (e.g., ["branch", "-v"])
            check: Raise exception on non-zero exit

        Returns:
            {"returncode": int, "stdout": str, "stderr": str}
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=30,
                encoding='utf-8',
                errors='replace'
            )

            if check and result.returncode != 0:
                logger.error(f"Git error: {result.stderr}")
                return {
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "success": False
                }

            return {
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "success": result.returncode == 0
            }

        except subprocess.TimeoutExpired:
            logger.error("Git command timeout")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            logger.error(f"Git execution error: {e}")
            return {"success": False, "error": str(e)}

    def _get_origin_url(self) -> Optional[str]:
        """Get remote origin URL."""
        result = self._run_git(["remote", "get-url", "origin"], check=False)
        return result.get("stdout") if result.get("success") else None

    def _get_current_branch(self) -> str:
        """Get currently checked out branch."""
        result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
        return result.get("stdout", "unknown") if result.get("success") else "unknown"

    # ===== BRANCH OPERATIONS =====

    def create_branch(self, branch_name: str, from_branch: str = "main") -> Dict[str, Any]:
        """
        Create a new branch from specified base.

        Args:
            branch_name: Name for new branch (e.g., "issue-42-fix-dashboard")
            from_branch: Base branch to create from (default: main)

        Returns:
            {"success": bool, "branch": str, "message": str}
        """
        logger.info(f"Creating branch: {branch_name} from {from_branch}")

        try:
            # First, ensure we have latest from origin
            logger.debug(f"Fetching latest from origin...")
            self._run_git(["fetch", "origin"], check=False)

            # Switch to base branch
            logger.debug(f"Checking out {from_branch}...")
            result = self._run_git(["checkout", from_branch], check=False)
            if not result.get("success"):
                return {
                    "success": False,
                    "error": f"Cannot checkout {from_branch}: {result.get('stderr')}"
                }

            # Pull latest
            logger.debug(f"Pulling latest from {from_branch}...")
            self._run_git(["pull", "origin", from_branch], check=False)

            # Create new branch
            logger.debug(f"Creating branch {branch_name}...")
            result = self._run_git(["checkout", "-b", branch_name], check=False)
            if not result.get("success"):
                return {
                    "success": False,
                    "error": f"Cannot create branch: {result.get('stderr')}"
                }

            # Push to remote
            logger.debug(f"Pushing {branch_name} to origin...")
            result = self._run_git(["push", "-u", "origin", branch_name], check=False)
            if not result.get("success"):
                # Non-critical error, branch exists locally
                logger.warning(f"Push error (branch may exist): {result.get('stderr')}")

            logger.info(f"✓ Branch created: {branch_name}")
            return {
                "success": True,
                "branch": branch_name,
                "message": f"Created and pushed {branch_name}"
            }

        except Exception as e:
            logger.error(f"Branch creation failed: {e}")
            return {"success": False, "error": str(e)}

    def switch_branch(self, branch_name: str) -> Dict[str, Any]:
        """Switch to existing branch."""
        logger.info(f"Switching to branch: {branch_name}")
        result = self._run_git(["checkout", branch_name], check=False)

        if result.get("success"):
            logger.info(f"✓ Switched to {branch_name}")
            return {"success": True, "branch": branch_name}
        else:
            logger.error(f"Cannot switch to {branch_name}: {result.get('stderr')}")
            return {"success": False, "error": result.get("stderr")}

    def list_branches(self) -> List[str]:
        """List all local branches."""
        result = self._run_git(["branch", "-v"], check=False)
        if result.get("success"):
            branches = [line.split()[0].lstrip("*").strip() for line in result.get("stdout", "").split("\n") if line]
            return branches
        return []

    # ===== COMMIT OPERATIONS =====

    def stage_files(self, files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Stage files for commit.

        Args:
            files: List of file paths to stage. If None, stages all changes.

        Returns:
            {"success": bool, "staged_count": int}
        """
        try:
            if files is None or len(files) == 0:
                # Stage all changes
                logger.debug("Staging all changes...")
                result = self._run_git(["add", "-A"], check=False)
            else:
                # Stage specific files
                logger.debug(f"Staging {len(files)} files...")
                result = self._run_git(["add"] + files, check=False)

            if result.get("success"):
                logger.info(f"✓ Files staged")
                return {"success": True, "staged_count": len(files or ["all"])}
            else:
                logger.error(f"Staging failed: {result.get('stderr')}")
                return {"success": False, "error": result.get("stderr")}

        except Exception as e:
            logger.error(f"Staging error: {e}")
            return {"success": False, "error": str(e)}

    def commit(self, message: str, files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Create a commit with message.

        Args:
            message: Commit message (can be multi-line)
            files: Specific files to commit (stages all if None)

        Returns:
            {"success": bool, "commit_hash": str, "message": str}
        """
        logger.info(f"Creating commit: {message[:50]}...")

        try:
            # Stage files first
            stage_result = self.stage_files(files)
            if not stage_result.get("success"):
                return {"success": False, "error": "Staging failed"}

            # Check if there are changes to commit
            status = self._run_git(["status", "--porcelain"], check=False)
            if not status.get("stdout"):
                logger.info("No changes to commit")
                return {"success": True, "message": "No changes"}

            # Create commit
            result = self._run_git(["commit", "-m", message], check=False)

            if result.get("success"):
                # Get commit hash
                hash_result = self._run_git(["rev-parse", "HEAD"], check=False)
                commit_hash = hash_result.get("stdout", "unknown")[:7] if hash_result.get("success") else "unknown"

                logger.info(f"✓ Commit created: {commit_hash}")
                return {
                    "success": True,
                    "commit_hash": commit_hash,
                    "message": message
                }
            else:
                logger.error(f"Commit failed: {result.get('stderr')}")
                return {"success": False, "error": result.get("stderr")}

        except Exception as e:
            logger.error(f"Commit error: {e}")
            return {"success": False, "error": str(e)}

    # ===== PUSH OPERATIONS =====

    def push_to_remote(self, branch: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """
        Push branch to remote.

        Args:
            branch: Branch to push (current if None)
            force: Force push (use with caution)

        Returns:
            {"success": bool, "branch": str}
        """
        if not branch:
            branch = self.current_branch

        logger.info(f"Pushing to origin/{branch}")

        try:
            cmd = ["push", "origin", branch]
            if force:
                cmd.insert(2, "-f")

            result = self._run_git(cmd, check=False)

            if result.get("success"):
                logger.info(f"✓ Pushed to origin/{branch}")
                return {"success": True, "branch": branch}
            else:
                logger.error(f"Push failed: {result.get('stderr')}")
                return {"success": False, "error": result.get("stderr")}

        except Exception as e:
            logger.error(f"Push error: {e}")
            return {"success": False, "error": str(e)}

    # ===== STATUS & DIFF =====

    def get_status(self) -> Dict[str, Any]:
        """Get repository status."""
        result = self._run_git(["status", "-s"], check=False)

        if result.get("success"):
            lines = [line for line in result.get("stdout", "").split("\n") if line]
            return {
                "success": True,
                "changes": len(lines),
                "files": lines
            }
        return {"success": False}

    def get_diff(self, from_branch: Optional[str] = None) -> Dict[str, Any]:
        """Get diff from another branch."""
        try:
            if from_branch:
                cmd = ["diff", from_branch, "HEAD", "--stat"]
            else:
                cmd = ["diff", "--stat"]

            result = self._run_git(cmd, check=False)

            if result.get("success"):
                return {
                    "success": True,
                    "diff_summary": result.get("stdout")
                }
            return {"success": False}

        except Exception as e:
            logger.error(f"Diff error: {e}")
            return {"success": False, "error": str(e)}

    # ===== CONVENIENCE METHODS =====

    def create_and_commit(
        self,
        branch_name: str,
        commit_message: str,
        files: Optional[List[str]] = None,
        from_branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Complete workflow: create branch, commit changes, push.

        Returns:
            {"success": bool, "branch": str, "commit": str}
        """
        logger.info(f"Complete workflow: branch={branch_name}, commit={commit_message[:30]}...")

        # Create branch
        branch_result = self.create_branch(branch_name, from_branch)
        if not branch_result.get("success"):
            return branch_result

        # Commit changes
        commit_result = self.commit(commit_message, files)
        if not commit_result.get("success"):
            logger.error(f"Commit failed: {commit_result.get('error')}")
            return {"success": False, "error": "Commit failed"}

        # Push
        push_result = self.push_to_remote(branch_name)
        if not push_result.get("success"):
            logger.warning(f"Push failed: {push_result.get('error')}")

        return {
            "success": True,
            "branch": branch_name,
            "commit": commit_result.get("commit_hash"),
            "pushed": push_result.get("success", False)
        }
