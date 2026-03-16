"""Tests for Post-Tool Tracker MCP Server (src/mcp/post_tool_tracker_mcp_server.py).

Tests cover all 6 tools:
  track_tool_usage, increment_progress, clear_enforcement_flag,
  get_progress_status, get_tool_stats, check_commit_readiness

File system paths (PROGRESS_FILE, LOGS_PATH) are patched to tmp_path.
All results are parsed with json.loads(). ASCII-only, no emoji.
"""

import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import importlib.util

_MCP_DIR = Path(__file__).parent.parent / "src" / "mcp"


def _load_module(name, file_path):
    spec = importlib.util.spec_from_file_location(name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module("post_tool_tracker_mcp_server", _MCP_DIR / "post_tool_tracker_mcp_server.py")

track_tool_usage = _mod.track_tool_usage
increment_progress = _mod.increment_progress
clear_enforcement_flag = _mod.clear_enforcement_flag
get_progress_status = _mod.get_progress_status
get_tool_stats = _mod.get_tool_stats
check_commit_readiness = _mod.check_commit_readiness


def _parse(result: str) -> dict:
    """Parse JSON result from MCP tool."""
    return json.loads(result)


@pytest.fixture
def temp_tracker_dir(tmp_path):
    """Patch LOGS_PATH and PROGRESS_FILE to a temporary directory.

    Also patches CURRENT_SESSION_FILE and provides a helper to write
    a valid session-progress.json.
    """
    logs_path = tmp_path / "logs"
    logs_path.mkdir(parents=True)
    progress_file = logs_path / "session-progress.json"
    memory_path = tmp_path
    current_session_file = memory_path / ".current-session.json"

    with patch.object(_mod, "LOGS_PATH", logs_path), \
         patch.object(_mod, "PROGRESS_FILE", progress_file), \
         patch.object(_mod, "MEMORY_PATH", memory_path), \
         patch.object(_mod, "CURRENT_SESSION_FILE", current_session_file):
        yield {
            "tmp": tmp_path,
            "logs": logs_path,
            "progress_file": progress_file,
            "current_session_file": current_session_file,
        }


def _write_session(dirs, session_id="SESSION-TEST-001"):
    """Write a .current-session.json and initial session-progress.json."""
    dirs["current_session_file"].write_text(
        json.dumps({"current_session_id": session_id}), encoding="utf-8"
    )
    session_dir = dirs["logs"] / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_id


def _write_progress(dirs, state: dict):
    """Write a session-progress.json with the given state."""
    dirs["progress_file"].write_text(json.dumps(state, indent=2), encoding="utf-8")


# =============================================================================
# TOOL 1: TRACK TOOL USAGE
# =============================================================================

class TestTrackToolUsageBasic:
    """Basic tracking behavior for Write, Edit, Read."""

    def test_track_write_returns_success(self, temp_tracker_dir):
        """Write tool call is tracked and returns success."""
        _write_session(temp_tracker_dir)
        params = json.dumps({"file_path": "/a/b/c/myfile.py", "content": "line1\nline2\nline3"})
        result = _parse(track_tool_usage("Write", params))
        assert result["success"] is True
        assert result["tool"] == "Write"

    def test_track_write_increases_progress(self, temp_tracker_dir):
        """Write tool increments total_progress by Write delta (8)."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Write", json.dumps({"file_path": "/x/y/z.py"})))
        assert result["progress_delta"] == 8
        assert result["total_progress"] == 8

    def test_track_edit_increases_progress(self, temp_tracker_dir):
        """Edit tool increments total_progress by Edit delta (5)."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 10, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Edit", json.dumps({
            "file_path": "/a/b/c.py", "old_string": "foo", "new_string": "foobar"
        })))
        assert result["progress_delta"] == 5
        assert result["total_progress"] == 15

    def test_track_read_increases_progress_by_one(self, temp_tracker_dir):
        """Read tool increments total_progress by 1."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Read", json.dumps({"file_path": "/some/file.py"})))
        assert result["progress_delta"] == 1
        assert result["total_progress"] == 1

    def test_progress_capped_at_100(self, temp_tracker_dir):
        """total_progress never exceeds 100 regardless of accumulated deltas."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 98, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Write", json.dumps({"file_path": "/a/b/c.py"})))
        assert result["total_progress"] == 100

    def test_unknown_tool_yields_zero_delta(self, temp_tracker_dir):
        """A tool name not in PROGRESS_DELTA yields a delta of 0."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 5, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("UnknownTool", "{}"))
        assert result["progress_delta"] == 0
        assert result["total_progress"] == 5

    def test_result_includes_session_id(self, temp_tracker_dir):
        """Returned JSON includes session_id field."""
        session_id = _write_session(temp_tracker_dir, "SESSION-ABC-123")
        result = _parse(track_tool_usage("Read", "{}"))
        assert result["session_id"] == session_id

    def test_result_includes_context_estimate(self, temp_tracker_dir):
        """Returned JSON includes context_estimate_pct field."""
        _write_session(temp_tracker_dir)
        result = _parse(track_tool_usage("Read", "{}"))
        assert "context_estimate_pct" in result
        assert isinstance(result["context_estimate_pct"], int)


class TestTrackToolUsageErrorHandling:
    """Error handling in track_tool_usage."""

    def test_error_flag_suppresses_progress_delta(self, temp_tracker_dir):
        """When is_error=True the progress delta is 0."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 20, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Write", "{}", is_error=True))
        assert result["progress_delta"] == 0
        assert result["total_progress"] == 20

    def test_error_flag_increments_errors_seen(self, temp_tracker_dir):
        """When is_error=True errors_seen is incremented in persisted state."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 2
        })
        track_tool_usage("Bash", "{}", is_error=True)
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert saved["errors_seen"] == 3

    def test_invalid_json_tool_input_does_not_crash(self, temp_tracker_dir):
        """Malformed tool_input string is treated as empty params without error."""
        _write_session(temp_tracker_dir)
        result = _parse(track_tool_usage("Read", "NOT_VALID_JSON"))
        assert result["success"] is True

    def test_error_flag_write_does_not_track_modified_file(self, temp_tracker_dir):
        """A failed Write does not add a file to modified_files_since_commit."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        track_tool_usage("Write", json.dumps({"file_path": "/a/b/new.py"}), is_error=True)
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert saved["modified_files_since_commit"] == []


class TestTrackToolUsageProgressDelta:
    """Complexity-weighted progress delta calculation."""

    def test_high_complexity_halves_delta(self, temp_tracker_dir):
        """Complexity >= 8 halves the base delta (Write: 8 -> 4)."""
        session_id = _write_session(temp_tracker_dir)
        # Write a flow-trace.json indicating complexity 10
        session_dir = temp_tracker_dir["logs"] / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        trace = [{"final_decision": {"complexity": 10}}]
        (session_dir / "flow-trace.json").write_text(json.dumps(trace), encoding="utf-8")

        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Write", json.dumps({"file_path": "/a/b/c.py"})))
        assert result["progress_delta"] == 4  # 8 // 2

    def test_very_high_complexity_quarters_delta(self, temp_tracker_dir):
        """Complexity >= 15 quarters the base delta (Write: 8 -> 2)."""
        session_id = _write_session(temp_tracker_dir)
        session_dir = temp_tracker_dir["logs"] / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        trace = [{"final_decision": {"complexity": 15}}]
        (session_dir / "flow-trace.json").write_text(json.dumps(trace), encoding="utf-8")

        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Write", json.dumps({"file_path": "/a/b/c.py"})))
        assert result["progress_delta"] == 2  # 8 // 4

    def test_normal_complexity_uses_full_delta(self, temp_tracker_dir):
        """Complexity < 8 uses the unweighted base delta."""
        session_id = _write_session(temp_tracker_dir)
        session_dir = temp_tracker_dir["logs"] / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        trace = [{"final_decision": {"complexity": 4}}]
        (session_dir / "flow-trace.json").write_text(json.dumps(trace), encoding="utf-8")

        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Write", json.dumps({"file_path": "/a/b/c.py"})))
        assert result["progress_delta"] == 8  # unmodified

    def test_complexity_delta_minimum_is_one(self, temp_tracker_dir):
        """Complexity weighting never reduces a non-zero delta below 1."""
        session_id = _write_session(temp_tracker_dir)
        session_dir = temp_tracker_dir["logs"] / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        # Complexity 15, Read base delta=1 -> max(1, 1//4) = max(1,0) = 1
        trace = [{"final_decision": {"complexity": 15}}]
        (session_dir / "flow-trace.json").write_text(json.dumps(trace), encoding="utf-8")

        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Read", json.dumps({"file_path": "/a/b/c.py"})))
        assert result["progress_delta"] >= 1


class TestTrackToolUsageModifiedFiles:
    """Modified file tracking for Write and Edit tools."""

    def test_write_adds_file_to_modified_list(self, temp_tracker_dir):
        """Successful Write appends the file to modified_files_since_commit."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        track_tool_usage("Write", json.dumps({"file_path": "/a/b/c/target.py"}))
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert any("target.py" in f for f in saved["modified_files_since_commit"])

    def test_edit_adds_file_to_modified_list(self, temp_tracker_dir):
        """Successful Edit appends the file to modified_files_since_commit."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        track_tool_usage("Edit", json.dumps({
            "file_path": "/x/y/z/edit_me.py", "old_string": "a", "new_string": "b"
        }))
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert any("edit_me.py" in f for f in saved["modified_files_since_commit"])

    def test_same_file_not_duplicated_in_modified_list(self, temp_tracker_dir):
        """Writing the same file twice does not duplicate it in modified list."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        track_tool_usage("Write", json.dumps({"file_path": "/a/b/c/same.py"}))
        track_tool_usage("Write", json.dumps({"file_path": "/a/b/c/same.py"}))
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        count = sum(1 for f in saved["modified_files_since_commit"] if "same.py" in f)
        assert count == 1

    def test_read_does_not_add_to_modified_list(self, temp_tracker_dir):
        """Read tool does not modify the modified_files_since_commit list."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        track_tool_usage("Read", json.dumps({"file_path": "/a/b/c/read_only.py"}))
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert saved["modified_files_since_commit"] == []


class TestTrackToolUsageWarnings:
    """Warning generation for task update frequency and complexity enforcement."""

    def test_warns_when_too_many_calls_without_task_update(self, temp_tracker_dir):
        """Warning emitted after 5+ tool calls without a TaskUpdate."""
        session_id = _write_session(temp_tracker_dir)
        session_dir = temp_tracker_dir["logs"] / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        trace = [{"final_decision": {"complexity": 5}}]
        (session_dir / "flow-trace.json").write_text(json.dumps(trace), encoding="utf-8")

        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 6,  # already at 6
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Write", json.dumps({"file_path": "/a/b/c.py"})))
        assert len(result["warnings"]) > 0
        assert any("TaskUpdate" in w for w in result["warnings"])

    def test_no_warning_below_five_calls(self, temp_tracker_dir):
        """No warning when tools_since_last_update is 4 or fewer."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 4,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Write", json.dumps({"file_path": "/a/b/c.py"})))
        assert result["warnings"] == []

    def test_warns_when_complexity_high_and_no_tasks_created(self, temp_tracker_dir):
        """Warning when complexity >= 6 and tasks_created == 0 and editing."""
        session_id = _write_session(temp_tracker_dir)
        session_dir = temp_tracker_dir["logs"] / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        trace = [{"final_decision": {"complexity": 7}}]
        (session_dir / "flow-trace.json").write_text(json.dumps(trace), encoding="utf-8")

        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Write", json.dumps({"file_path": "/a/b/c.py"})))
        assert any("phased" in w.lower() or "complexity" in w.lower() for w in result["warnings"])

    def test_no_complexity_warning_when_tasks_exist(self, temp_tracker_dir):
        """No complexity-phase warning when tasks_created > 0."""
        session_id = _write_session(temp_tracker_dir)
        session_dir = temp_tracker_dir["logs"] / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        trace = [{"final_decision": {"complexity": 7}}]
        (session_dir / "flow-trace.json").write_text(json.dumps(trace), encoding="utf-8")

        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 2, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(track_tool_usage("Write", json.dumps({"file_path": "/a/b/c.py"})))
        complexity_warnings = [w for w in result["warnings"] if "phased" in w.lower()]
        assert complexity_warnings == []


class TestTrackToolUsageToolLogger:
    """Tool-tracker.jsonl logging behavior."""

    def test_write_logs_entry_to_jsonl(self, temp_tracker_dir):
        """Write tool call appends an entry to tool-tracker.jsonl."""
        session_id = _write_session(temp_tracker_dir)
        track_tool_usage("Write", json.dumps({"file_path": "/a/b/c/logged.py", "content": "x\ny\n"}))
        tracker_file = (
            temp_tracker_dir["logs"] / "sessions" / session_id / "tool-tracker.jsonl"
        )
        assert tracker_file.exists()
        lines = [l for l in tracker_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry["tool"] == "Write"

    def test_jsonl_entry_has_required_fields(self, temp_tracker_dir):
        """Each JSONL entry contains ts, tool, status, and progress_delta."""
        session_id = _write_session(temp_tracker_dir)
        track_tool_usage("Read", json.dumps({"file_path": "/a/b/c.py"}))
        tracker_file = (
            temp_tracker_dir["logs"] / "sessions" / session_id / "tool-tracker.jsonl"
        )
        entry = json.loads(tracker_file.read_text(encoding="utf-8").splitlines()[0])
        for field in ("ts", "tool", "status", "progress_delta"):
            assert field in entry

    def test_error_tool_status_is_error_in_jsonl(self, temp_tracker_dir):
        """When is_error=True the JSONL entry status field equals 'error'."""
        session_id = _write_session(temp_tracker_dir)
        track_tool_usage("Bash", json.dumps({"command": "ls"}), is_error=True)
        tracker_file = (
            temp_tracker_dir["logs"] / "sessions" / session_id / "tool-tracker.jsonl"
        )
        entry = json.loads(tracker_file.read_text(encoding="utf-8").splitlines()[0])
        assert entry["status"] == "error"

    def test_no_logging_when_session_id_missing(self, temp_tracker_dir):
        """No tool-tracker.jsonl is created when session_id is empty."""
        # Do not call _write_session so no current session exists
        track_tool_usage("Read", json.dumps({"file_path": "/a/b/c.py"}))
        sessions_dir = temp_tracker_dir["logs"] / "sessions"
        # Either no sessions directory or empty sessions directory
        if sessions_dir.exists():
            jsonl_files = list(sessions_dir.rglob("tool-tracker.jsonl"))
            assert jsonl_files == []

    def test_multiple_calls_append_multiple_lines(self, temp_tracker_dir):
        """Multiple track_tool_usage calls append separate lines to jsonl."""
        session_id = _write_session(temp_tracker_dir)
        track_tool_usage("Read", json.dumps({"file_path": "/a/b/c.py"}))
        track_tool_usage("Write", json.dumps({"file_path": "/a/b/d.py"}))
        track_tool_usage("Bash", json.dumps({"command": "pytest"}))
        tracker_file = (
            temp_tracker_dir["logs"] / "sessions" / session_id / "tool-tracker.jsonl"
        )
        lines = [l for l in tracker_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 3


# =============================================================================
# TOOL 2: INCREMENT PROGRESS
# =============================================================================

class TestIncrementProgress:
    """Tests for manual progress increment tool."""

    def test_increment_default_delta(self, temp_tracker_dir):
        """Default delta of 5 is applied when not specified."""
        _write_progress(temp_tracker_dir, {
            "total_progress": 10, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(increment_progress())
        assert result["success"] is True
        assert result["total_progress"] == 15
        assert result["delta"] == 5

    def test_increment_custom_delta(self, temp_tracker_dir):
        """Custom delta is applied correctly."""
        _write_progress(temp_tracker_dir, {
            "total_progress": 30, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(increment_progress(delta=15))
        assert result["total_progress"] == 45
        assert result["delta"] == 15

    def test_increment_caps_at_100(self, temp_tracker_dir):
        """Progress is capped at 100 even if delta exceeds remaining space."""
        _write_progress(temp_tracker_dir, {
            "total_progress": 95, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(increment_progress(delta=20))
        assert result["total_progress"] == 100

    def test_increment_persists_to_file(self, temp_tracker_dir):
        """Increment is persisted to the progress file."""
        _write_progress(temp_tracker_dir, {
            "total_progress": 40, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        increment_progress(delta=10, reason="phase completed")
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert saved["total_progress"] == 50

    def test_increment_reason_in_response(self, temp_tracker_dir):
        """The reason string is echoed back in the response."""
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        result = _parse(increment_progress(delta=5, reason="test reason"))
        assert result["reason"] == "test reason"

    def test_increment_from_zero_state(self, temp_tracker_dir):
        """Increment works when no progress file exists (empty initial state)."""
        result = _parse(increment_progress(delta=7))
        assert result["success"] is True
        assert result["total_progress"] == 7


# =============================================================================
# TOOL 3: CLEAR ENFORCEMENT FLAG
# =============================================================================

class TestClearEnforcementFlag:
    """Tests for clear_enforcement_flag tool."""

    def test_clear_existing_flag_new_location(self, temp_tracker_dir):
        """Clears flag file in the new sessions/flags location."""
        session_id = _write_session(temp_tracker_dir, "SESSION-FLAG-001")
        flags_dir = (
            temp_tracker_dir["logs"] / "sessions" / session_id / "flags"
        )
        flags_dir.mkdir(parents=True, exist_ok=True)
        flag_file = flags_dir / "task-breakdown-pending.json"
        flag_file.write_text(json.dumps({"pending": True}), encoding="utf-8")

        result = _parse(clear_enforcement_flag("task-breakdown-pending"))
        assert result["success"] is True
        assert result["cleared"] == "task-breakdown-pending"
        assert not flag_file.exists()

    def test_clear_nonexistent_flag_is_ok(self, temp_tracker_dir):
        """Clearing a flag that does not exist succeeds without error."""
        _write_session(temp_tracker_dir)
        result = _parse(clear_enforcement_flag("task-breakdown-pending"))
        assert result["success"] is True

    def test_clear_flag_returns_session_id(self, temp_tracker_dir):
        """Response includes the session_id field."""
        session_id = _write_session(temp_tracker_dir, "SESSION-ID-CLEAR")
        result = _parse(clear_enforcement_flag("skill-selection-pending"))
        assert result["session_id"] == session_id

    def test_clear_skill_selection_pending_flag(self, temp_tracker_dir):
        """Clears skill-selection-pending flag file."""
        session_id = _write_session(temp_tracker_dir, "SESSION-SKILL-001")
        flags_dir = (
            temp_tracker_dir["logs"] / "sessions" / session_id / "flags"
        )
        flags_dir.mkdir(parents=True, exist_ok=True)
        flag_file = flags_dir / "skill-selection-pending.json"
        flag_file.write_text("{}", encoding="utf-8")

        clear_enforcement_flag("skill-selection-pending")
        assert not flag_file.exists()

    def test_task_create_auto_clears_task_breakdown_flag(self, temp_tracker_dir):
        """TaskCreate tool call auto-clears task-breakdown-pending flag."""
        session_id = _write_session(temp_tracker_dir, "SESSION-AUTO-001")
        flags_dir = (
            temp_tracker_dir["logs"] / "sessions" / session_id / "flags"
        )
        flags_dir.mkdir(parents=True, exist_ok=True)
        flag_file = flags_dir / "task-breakdown-pending.json"
        flag_file.write_text("{}", encoding="utf-8")

        track_tool_usage("TaskCreate", json.dumps({"subject": "my task"}))
        assert not flag_file.exists()

    def test_skill_tool_auto_clears_skill_selection_flag(self, temp_tracker_dir):
        """Skill tool call auto-clears skill-selection-pending flag."""
        session_id = _write_session(temp_tracker_dir, "SESSION-AUTO-002")
        flags_dir = (
            temp_tracker_dir["logs"] / "sessions" / session_id / "flags"
        )
        flags_dir.mkdir(parents=True, exist_ok=True)
        flag_file = flags_dir / "skill-selection-pending.json"
        flag_file.write_text("{}", encoding="utf-8")

        track_tool_usage("Skill", json.dumps({"skill": "python-core"}))
        assert not flag_file.exists()


# =============================================================================
# TOOL 4: GET PROGRESS STATUS
# =============================================================================

class TestGetProgressStatus:
    """Tests for get_progress_status snapshot tool."""

    def test_status_returns_all_expected_fields(self, temp_tracker_dir):
        """Response contains all expected snapshot fields."""
        _write_progress(temp_tracker_dir, {
            "session_id": "SESSION-SNAP-001",
            "total_progress": 42,
            "tasks_created": 3,
            "tasks_completed": 1,
            "errors_seen": 2,
            "tool_counts": {"Read": 5, "Write": 2},
            "last_tool": "Write",
            "last_tool_at": "2026-03-16T10:00:00",
            "modified_files_since_commit": ["a/b/c.py"],
            "content_chars": 1000,
            "context_estimate_pct": 25,
            "tools_since_last_update": 3
        })
        result = _parse(get_progress_status())
        assert result["success"] is True
        assert result["total_progress"] == 42
        assert result["tasks_created"] == 3
        assert result["tasks_completed"] == 1
        assert result["errors_seen"] == 2
        assert result["tool_counts"] == {"Read": 5, "Write": 2}
        assert result["total_tool_calls"] == 7
        assert result["last_tool"] == "Write"
        assert result["modified_files"] == ["a/b/c.py"]
        assert result["context_estimate_pct"] == 25
        assert result["tools_since_last_update"] == 3
        assert result["session_id"] == "SESSION-SNAP-001"

    def test_status_empty_state_returns_defaults(self, temp_tracker_dir):
        """When no progress file exists, defaults are returned."""
        result = _parse(get_progress_status())
        assert result["success"] is True
        assert result["total_progress"] == 0
        assert result["tasks_created"] == 0
        assert result["errors_seen"] == 0
        assert result["modified_files"] == []
        assert result["total_tool_calls"] == 0

    def test_total_tool_calls_is_sum_of_counts(self, temp_tracker_dir):
        """total_tool_calls is computed as the sum of all tool_counts values."""
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tasks_created": 0, "tasks_completed": 0,
            "errors_seen": 0, "tool_counts": {"Read": 10, "Write": 5, "Bash": 3},
            "last_tool": "", "last_tool_at": "", "modified_files_since_commit": [],
            "content_chars": 0, "context_estimate_pct": 0, "tools_since_last_update": 0
        })
        result = _parse(get_progress_status())
        assert result["total_tool_calls"] == 18

    def test_status_returns_valid_json(self, temp_tracker_dir):
        """get_progress_status always returns valid parseable JSON."""
        raw = get_progress_status()
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)


# =============================================================================
# TOOL 5: GET TOOL STATS
# =============================================================================

class TestGetToolStats:
    """Tests for get_tool_stats tool."""

    def test_stats_no_session_returns_no_data_message(self, temp_tracker_dir):
        """When no session or tracker file exists, returns no-data message."""
        result = _parse(get_tool_stats())
        assert result["success"] is True
        assert result["entries"] == 0
        assert "No tool tracker data" in result.get("message", "")

    def test_stats_with_entries(self, temp_tracker_dir):
        """Stats are computed correctly from a non-empty tool-tracker.jsonl."""
        session_id = _write_session(temp_tracker_dir, "SESSION-STATS-001")
        session_dir = temp_tracker_dir["logs"] / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        tracker_file = session_dir / "tool-tracker.jsonl"

        entries = [
            {"ts": "2026-03-16T10:00:00", "tool": "Read", "status": "success",
             "progress_delta": 1, "file": "src/a.py"},
            {"ts": "2026-03-16T10:01:00", "tool": "Write", "status": "success",
             "progress_delta": 8, "file": "src/b.py"},
            {"ts": "2026-03-16T10:02:00", "tool": "Write", "status": "error",
             "progress_delta": 0, "file": "src/b.py"},
            {"ts": "2026-03-16T10:03:00", "tool": "Bash", "status": "success",
             "progress_delta": 3},
        ]
        tracker_file.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
        )

        result = _parse(get_tool_stats())
        assert result["success"] is True
        assert result["total_entries"] == 4
        assert result["by_tool"]["Read"] == 1
        assert result["by_tool"]["Write"] == 2
        assert result["by_tool"]["Bash"] == 1
        assert result["errors"] == 1

    def test_stats_files_modified_set(self, temp_tracker_dir):
        """files_modified contains unique file paths from Write and Edit entries."""
        session_id = _write_session(temp_tracker_dir, "SESSION-FILES-001")
        session_dir = temp_tracker_dir["logs"] / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        tracker_file = session_dir / "tool-tracker.jsonl"

        entries = [
            {"ts": "T1", "tool": "Write", "status": "success",
             "progress_delta": 8, "file": "src/a.py"},
            {"ts": "T2", "tool": "Write", "status": "success",
             "progress_delta": 8, "file": "src/a.py"},  # duplicate
            {"ts": "T3", "tool": "Edit", "status": "success",
             "progress_delta": 5, "file": "src/b.py"},
        ]
        tracker_file.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
        )

        result = _parse(get_tool_stats())
        assert result["files_modified_count"] == 2
        assert sorted(result["files_modified"]) == ["src/a.py", "src/b.py"]

    def test_stats_first_and_last_entry_timestamps(self, temp_tracker_dir):
        """first_entry and last_entry reflect the earliest and latest ts values."""
        session_id = _write_session(temp_tracker_dir, "SESSION-TS-001")
        session_dir = temp_tracker_dir["logs"] / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        tracker_file = session_dir / "tool-tracker.jsonl"

        entries = [
            {"ts": "2026-03-16T08:00:00", "tool": "Read", "status": "success",
             "progress_delta": 1},
            {"ts": "2026-03-16T09:00:00", "tool": "Write", "status": "success",
             "progress_delta": 8},
            {"ts": "2026-03-16T10:00:00", "tool": "Bash", "status": "success",
             "progress_delta": 3},
        ]
        tracker_file.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
        )

        result = _parse(get_tool_stats())
        assert result["first_entry"] == "2026-03-16T08:00:00"
        assert result["last_entry"] == "2026-03-16T10:00:00"

    def test_stats_skips_invalid_jsonl_lines(self, temp_tracker_dir):
        """Malformed lines in tool-tracker.jsonl are skipped without crashing."""
        session_id = _write_session(temp_tracker_dir, "SESSION-BAD-001")
        session_dir = temp_tracker_dir["logs"] / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        tracker_file = session_dir / "tool-tracker.jsonl"

        tracker_file.write_text(
            '{"ts":"T1","tool":"Read","status":"success","progress_delta":1}\n'
            'NOT VALID JSON\n'
            '{"ts":"T2","tool":"Bash","status":"success","progress_delta":3}\n',
            encoding="utf-8"
        )
        result = _parse(get_tool_stats())
        assert result["success"] is True
        assert result["total_entries"] == 2

    def test_stats_returns_valid_json(self, temp_tracker_dir):
        """get_tool_stats always returns valid parseable JSON."""
        raw = get_tool_stats()
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)


# =============================================================================
# TOOL 6: CHECK COMMIT READINESS
# =============================================================================

class TestCheckCommitReadiness:
    """Tests for check_commit_readiness tool."""

    def test_three_or_more_files_triggers_commit(self, temp_tracker_dir):
        """should_commit is True when 3 or more files have been modified."""
        _write_progress(temp_tracker_dir, {
            "total_progress": 10,
            "tasks_completed": 0,
            "modified_files_since_commit": ["a/b/c.py", "x/y/z.py", "src/main.py"],
            "tool_counts": {}, "last_tool": "", "last_tool_at": "",
            "content_chars": 0, "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "errors_seen": 0
        })
        result = _parse(check_commit_readiness())
        assert result["success"] is True
        assert result["should_commit"] is True
        assert "3+" in result["reason"]

    def test_progress_50_with_one_file_triggers_commit(self, temp_tracker_dir):
        """should_commit is True when progress >= 50 and at least one file modified."""
        _write_progress(temp_tracker_dir, {
            "total_progress": 55,
            "tasks_completed": 0,
            "modified_files_since_commit": ["src/main.py"],
            "tool_counts": {}, "last_tool": "", "last_tool_at": "",
            "content_chars": 0, "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "errors_seen": 0
        })
        result = _parse(check_commit_readiness())
        assert result["should_commit"] is True
        assert "50" in result["reason"]

    def test_task_completed_triggers_commit(self, temp_tracker_dir):
        """should_commit is True when tasks_completed > 0."""
        _write_progress(temp_tracker_dir, {
            "total_progress": 20,
            "tasks_completed": 1,
            "modified_files_since_commit": [],
            "tool_counts": {}, "last_tool": "", "last_tool_at": "",
            "content_chars": 0, "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "errors_seen": 0
        })
        result = _parse(check_commit_readiness())
        assert result["should_commit"] is True

    def test_insufficient_changes_no_commit(self, temp_tracker_dir):
        """should_commit is False when fewer than 3 files, progress < 50, no completed tasks."""
        _write_progress(temp_tracker_dir, {
            "total_progress": 20,
            "tasks_completed": 0,
            "modified_files_since_commit": ["a/b/c.py"],
            "tool_counts": {}, "last_tool": "", "last_tool_at": "",
            "content_chars": 0, "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "errors_seen": 0
        })
        result = _parse(check_commit_readiness())
        assert result["should_commit"] is False
        assert "Not enough" in result["reason"]

    def test_no_files_no_commit(self, temp_tracker_dir):
        """should_commit is False when no files have been modified."""
        _write_progress(temp_tracker_dir, {
            "total_progress": 60,
            "tasks_completed": 0,
            "modified_files_since_commit": [],
            "tool_counts": {}, "last_tool": "", "last_tool_at": "",
            "content_chars": 0, "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "errors_seen": 0
        })
        result = _parse(check_commit_readiness())
        assert result["should_commit"] is False

    def test_readiness_response_includes_modified_count(self, temp_tracker_dir):
        """Response includes modified_count that matches len(modified_files)."""
        _write_progress(temp_tracker_dir, {
            "total_progress": 10,
            "tasks_completed": 0,
            "modified_files_since_commit": ["a.py", "b.py"],
            "tool_counts": {}, "last_tool": "", "last_tool_at": "",
            "content_chars": 0, "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "errors_seen": 0
        })
        result = _parse(check_commit_readiness())
        assert result["modified_count"] == 2
        assert len(result["modified_files"]) == 2

    def test_readiness_empty_state_is_not_ready(self, temp_tracker_dir):
        """With no progress file, commit is not triggered."""
        result = _parse(check_commit_readiness())
        assert result["success"] is True
        assert result["should_commit"] is False

    def test_readiness_returns_valid_json(self, temp_tracker_dir):
        """check_commit_readiness always returns valid parseable JSON."""
        raw = check_commit_readiness()
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)


# =============================================================================
# TOOL COUNTS AND PERSISTENCE
# =============================================================================

class TestToolCountsPersistence:
    """Tests that tool_counts are properly accumulated and persisted."""

    def test_tool_counts_increment_on_each_call(self, temp_tracker_dir):
        """Successive calls to the same tool increment its count."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        track_tool_usage("Read", json.dumps({"file_path": "/a/b/c.py"}))
        track_tool_usage("Read", json.dumps({"file_path": "/a/b/d.py"}))
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert saved["tool_counts"].get("Read", 0) == 2

    def test_different_tools_each_tracked_separately(self, temp_tracker_dir):
        """Different tools accumulate counts independently."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        track_tool_usage("Read", json.dumps({"file_path": "/a.py"}))
        track_tool_usage("Write", json.dumps({"file_path": "/b.py"}))
        track_tool_usage("Bash", json.dumps({"command": "ls"}))
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert saved["tool_counts"]["Read"] == 1
        assert saved["tool_counts"]["Write"] == 1
        assert saved["tool_counts"]["Bash"] == 1

    def test_last_tool_is_updated(self, temp_tracker_dir):
        """last_tool field reflects the most recently tracked tool."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        track_tool_usage("Read", json.dumps({"file_path": "/a.py"}))
        track_tool_usage("Bash", json.dumps({"command": "pytest"}))
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert saved["last_tool"] == "Bash"


# =============================================================================
# TASK UPDATE FREQUENCY COUNTER
# =============================================================================

class TestTaskUpdateFrequency:
    """Tests that tools_since_last_update resets on TaskUpdate / TaskCreate."""

    def test_task_update_resets_counter(self, temp_tracker_dir):
        """TaskUpdate call resets tools_since_last_update to 0."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 4,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        track_tool_usage("TaskUpdate", json.dumps({"status": "in_progress"}))
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert saved["tools_since_last_update"] == 0

    def test_task_create_resets_counter(self, temp_tracker_dir):
        """TaskCreate call resets tools_since_last_update to 0."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 3,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        track_tool_usage("TaskCreate", json.dumps({"subject": "test task"}))
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert saved["tools_since_last_update"] == 0

    def test_other_tools_increment_counter(self, temp_tracker_dir):
        """Non-task tools increment tools_since_last_update by 1."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 2,
            "tasks_created": 0, "tasks_completed": 0, "errors_seen": 0
        })
        track_tool_usage("Read", json.dumps({"file_path": "/a.py"}))
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert saved["tools_since_last_update"] == 3

    def test_task_update_completed_increments_tasks_completed(self, temp_tracker_dir):
        """TaskUpdate with status=completed increments tasks_completed."""
        _write_session(temp_tracker_dir)
        _write_progress(temp_tracker_dir, {
            "total_progress": 0, "tool_counts": {}, "last_tool": "",
            "last_tool_at": "", "modified_files_since_commit": [], "content_chars": 0,
            "context_estimate_pct": 0, "tools_since_last_update": 0,
            "tasks_created": 1, "tasks_completed": 0, "errors_seen": 0
        })
        track_tool_usage("TaskUpdate", json.dumps({"status": "completed"}))
        saved = json.loads(temp_tracker_dir["progress_file"].read_text(encoding="utf-8"))
        assert saved["tasks_completed"] == 1


# =============================================================================
# JSON FORMAT VALIDATION
# =============================================================================

class TestJsonFormatConsistency:
    """Verify all 6 tools consistently return valid JSON with a success field."""

    def test_all_tools_return_valid_json(self, temp_tracker_dir):
        """Every tool call returns a parseable JSON dict."""
        _write_session(temp_tracker_dir)
        results = [
            track_tool_usage("Read", "{}"),
            increment_progress(),
            clear_enforcement_flag("task-breakdown-pending"),
            get_progress_status(),
            get_tool_stats(),
            check_commit_readiness(),
        ]
        for raw in results:
            parsed = json.loads(raw)
            assert isinstance(parsed, dict)

    def test_all_tools_have_success_field(self, temp_tracker_dir):
        """Every tool response contains a boolean 'success' field."""
        _write_session(temp_tracker_dir)
        results = [
            track_tool_usage("Read", "{}"),
            increment_progress(),
            clear_enforcement_flag("task-breakdown-pending"),
            get_progress_status(),
            get_tool_stats(),
            check_commit_readiness(),
        ]
        for raw in results:
            parsed = json.loads(raw)
            assert "success" in parsed
            assert isinstance(parsed["success"], bool)
