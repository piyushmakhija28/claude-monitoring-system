"""
Tests for Level3DocumentationManager - Circular SDLC Documentation Cycle.

Tests the READ (Step 0) and WRITE (Step 13) phases of documentation management.
"""

import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.langgraph_engine.level3_documentation_manager import (
    Level3DocumentationManager,
)


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory."""
    return tmp_path


@pytest.fixture
def manager(tmp_project):
    """Create a manager for the tmp project."""
    return Level3DocumentationManager(
        project_root=str(tmp_project),
        session_dir=str(tmp_project / "sessions"),
    )


@pytest.fixture
def existing_project(tmp_project):
    """Create a project with existing docs."""
    (tmp_project / "README.md").write_text(
        "# My Project\n\n**Last Updated:** 2026-01-01\n\nA test project.\n",
        encoding="utf-8",
    )
    (tmp_project / "CLAUDE.md").write_text(
        "# My Project - Claude Context\n\n## Overview\n\nTest project.\n",
        encoding="utf-8",
    )
    (tmp_project / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.0.0] - 2026-01-01\n\n### Added\n\n- Initial release\n",
        encoding="utf-8",
    )
    return tmp_project


class TestDetectProjectDocs:
    """Tests for detect_project_docs() - Step 0 read phase."""

    def test_detect_docs_fresh_project(self, manager, tmp_project):
        """Empty directory -> is_fresh_project=True."""
        result = manager.detect_project_docs()

        assert result["is_fresh_project"] is True
        assert result["srs_exists"] is False
        assert result["readme_exists"] is False
        assert result["claude_md_exists"] is False
        assert result["docs_found"] == []

    def test_detect_docs_existing_project(self, tmp_project):
        """Directory with README -> is_fresh_project=False."""
        (tmp_project / "README.md").write_text("# Hello", encoding="utf-8")
        mgr = Level3DocumentationManager(project_root=str(tmp_project))

        result = mgr.detect_project_docs()

        assert result["is_fresh_project"] is False
        assert result["readme_exists"] is True
        assert "README.md" in result["docs_found"]

    def test_detect_docs_all_present(self, existing_project):
        """All docs present -> correct flags."""
        (existing_project / "SRS.md").write_text("# SRS", encoding="utf-8")
        mgr = Level3DocumentationManager(project_root=str(existing_project))

        result = mgr.detect_project_docs()

        assert result["is_fresh_project"] is False
        assert result["srs_exists"] is True
        assert result["readme_exists"] is True
        assert result["claude_md_exists"] is True
        assert result["changelog_exists"] is True
        assert len(result["docs_found"]) == 4

    def test_detect_docs_alternate_srs_name(self, tmp_project):
        """System_Requirement_Analysis.md also counts as SRS."""
        (tmp_project / "System_Requirement_Analysis.md").write_text(
            "# SRS", encoding="utf-8"
        )
        mgr = Level3DocumentationManager(project_root=str(tmp_project))

        result = mgr.detect_project_docs()

        assert result["srs_exists"] is True
        assert result["is_fresh_project"] is False

    def test_partial_docs(self, tmp_project):
        """Only README exists -> is_fresh_project=False, only README in found."""
        (tmp_project / "README.md").write_text("# Test", encoding="utf-8")
        mgr = Level3DocumentationManager(project_root=str(tmp_project))

        result = mgr.detect_project_docs()

        assert result["is_fresh_project"] is False
        assert result["readme_exists"] is True
        assert result["claude_md_exists"] is False
        assert result["srs_exists"] is False
        assert result["docs_found"] == ["README.md"]


class TestSummarizeExistingDocs:
    """Tests for summarize_existing_docs() - Step 0 context injection."""

    def test_summarize_existing_docs(self, manager):
        """Returns truncated summaries from context_data."""
        context = {
            "readme_content": "A" * 1000,
            "srs_content": "B" * 800,
            "claude_md_content": "C" * 600,
        }

        result = manager.summarize_existing_docs(context)

        assert "readme" in result
        assert len(result["readme"]) == 500
        assert "srs" in result
        assert len(result["srs"]) == 500
        assert "claude_md" in result
        assert len(result["claude_md"]) == 500

    def test_summarize_empty_context(self, manager):
        """Empty context -> empty summaries."""
        result = manager.summarize_existing_docs({})
        assert result == {}

    def test_summarize_short_content(self, manager):
        """Short content is not truncated."""
        context = {"readme": "Short readme content here"}
        result = manager.summarize_existing_docs(context)
        assert result["readme"] == "Short readme content here"


class TestCreateAllDocs:
    """Tests for create_all_docs() - Step 13 fresh project."""

    def test_create_all_docs(self, manager, tmp_project):
        """Creates SRS, README, CLAUDE.md, CHANGELOG for fresh project."""
        state = {
            "project_root": str(tmp_project),
            "step10_modified_files": ["src/main.py"],
        }

        result = manager.create_all_docs(state)

        assert result["step13_documentation_status"] == "CREATED"
        assert len(result["step13_docs_created"]) > 0
        # DocumentationGenerator should have created files
        assert (tmp_project / "README.md").exists() or len(result["step13_docs_created"]) > 0


class TestUpdateExistingDocs:
    """Tests for update_existing_docs() - Step 13 existing project."""

    def test_update_existing_docs(self, existing_project):
        """Updates CLAUDE.md and CHANGELOG for existing project."""
        mgr = Level3DocumentationManager(
            project_root=str(existing_project),
            session_dir=str(existing_project / "sessions"),
        )
        state = {
            "project_root": str(existing_project),
            "step0_task_type": "Bug Fix",
            "step0_complexity": 4,
            "step5_skill": "python-core",
            "step5_agent": "",
            "session_id": "test-session-001",
            "step10_modified_files": ["src/fix.py"],
            "user_message": "Fix the login bug",
        }

        result = mgr.update_existing_docs(state)

        assert result["step13_documentation_status"] == "UPDATED"
        assert "CLAUDE.md" in result["step13_updated_files"]
        assert "CHANGELOG.md" in result["step13_updated_files"]

        # Verify CLAUDE.md has the insight
        claude_content = (existing_project / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Bug Fix" in claude_content
        assert "python-core" in claude_content

        # Verify CHANGELOG has entry
        changelog_content = (existing_project / "CHANGELOG.md").read_text(encoding="utf-8")
        assert "Fix the login bug" in changelog_content

    def test_update_feature_updates_srs(self, existing_project):
        """Feature tasks also update SRS if it exists."""
        (existing_project / "SRS.md").write_text(
            "# SRS\n\n## Functional Requirements\n\n## Non-Functional Requirements\n",
            encoding="utf-8",
        )
        mgr = Level3DocumentationManager(project_root=str(existing_project))
        state = {
            "step0_task_type": "Feature",
            "step0_complexity": 6,
            "session_id": "test-002",
            "user_message": "Add user dashboard",
            "step10_modified_files": [],
        }

        result = mgr.update_existing_docs(state)

        assert "SRS.md" in result["step13_updated_files"]
        srs_content = (existing_project / "SRS.md").read_text(encoding="utf-8")
        assert "Add user dashboard" in srs_content

    def test_update_high_complexity_updates_readme(self, existing_project):
        """High complexity (>=7) also updates README."""
        mgr = Level3DocumentationManager(project_root=str(existing_project))
        state = {
            "step0_task_type": "Enhancement",
            "step0_complexity": 8,
            "session_id": "test-003",
            "user_message": "Major architecture overhaul",
            "step10_modified_files": ["src/core.py"],
        }

        result = mgr.update_existing_docs(state)

        assert "README.md" in result["step13_updated_files"]

    def test_update_low_complexity_skips_readme(self, existing_project):
        """Low complexity (<7) does NOT update README."""
        mgr = Level3DocumentationManager(project_root=str(existing_project))
        state = {
            "step0_task_type": "Bug Fix",
            "step0_complexity": 3,
            "session_id": "test-004",
            "user_message": "Fix typo",
            "step10_modified_files": [],
        }

        result = mgr.update_existing_docs(state)

        assert "README.md" not in result["step13_updated_files"]

    def test_idempotent_claude_md_update(self, existing_project):
        """Same session_id does not duplicate insight in CLAUDE.md."""
        mgr = Level3DocumentationManager(project_root=str(existing_project))
        state = {
            "step0_task_type": "Fix",
            "step0_complexity": 3,
            "session_id": "test-005",
            "user_message": "Fix bug",
            "step10_modified_files": [],
        }

        mgr.update_existing_docs(state)
        mgr.update_existing_docs(state)

        claude_content = (existing_project / "CLAUDE.md").read_text(encoding="utf-8")
        count = claude_content.count("execution-insight-test-005")
        assert count == 1


class TestGracefulFailure:
    """Tests for error handling."""

    def test_graceful_failure_detect(self):
        """detect_project_docs on nonexistent path returns safe dict (no crash)."""
        mgr = Level3DocumentationManager(
            project_root="/nonexistent/path/that/does/not/exist"
        )
        result = mgr.detect_project_docs()

        # Should not raise, should return a valid dict with expected keys
        assert isinstance(result, dict)
        assert "srs_exists" in result
        assert "readme_exists" in result
        assert "claude_md_exists" in result
        assert "is_fresh_project" in result

    def test_graceful_failure_update(self):
        """update_existing_docs on bad path returns error status."""
        mgr = Level3DocumentationManager(
            project_root="/nonexistent/path/that/does/not/exist"
        )
        state = {
            "step0_task_type": "Fix",
            "step0_complexity": 3,
            "session_id": "err-001",
            "user_message": "test",
        }

        result = mgr.update_existing_docs(state)

        # Should return with updated_files (possibly empty) and status
        assert isinstance(result, dict)
        assert "step13_documentation_status" in result
