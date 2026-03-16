"""Tests for Pre-Tool Gate MCP Server (src/mcp/pre_tool_gate_mcp_server.py).

Covers all 8 tools:
  1. validate_tool_call
  2. check_task_breakdown
  3. check_skill_selected
  4. check_level_completion
  5. get_enforcer_state
  6. check_failure_patterns
  7. get_dynamic_skill_hint
  8. reset_enforcer_flags
"""

import json
import os
import tempfile
import pytest
from datetime import datetime, timedelta
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


_mod = _load_module("pre_tool_gate_mcp_server", _MCP_DIR / "pre_tool_gate_mcp_server.py")

validate_tool_call = _mod.validate_tool_call
check_task_breakdown = _mod.check_task_breakdown
check_skill_selected = _mod.check_skill_selected
check_level_completion = _mod.check_level_completion
get_enforcer_state = _mod.get_enforcer_state
check_failure_patterns = _mod.check_failure_patterns
get_dynamic_skill_hint = _mod.get_dynamic_skill_hint
reset_enforcer_flags = _mod.reset_enforcer_flags


def _parse(result: str) -> dict:
    """Parse JSON string returned by any MCP tool."""
    return json.loads(result)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def session_id():
    return "SESSION-TEST-001"


@pytest.fixture
def tmp_session(tmp_path, session_id):
    """Create the full session directory structure and patch module-level paths."""
    memory_path = tmp_path / "memory"
    logs_path = memory_path / "logs" / "sessions"
    session_dir = logs_path / session_id
    flags_dir = session_dir / "flags"
    flags_dir.mkdir(parents=True)

    current_session_file = memory_path / ".current-session.json"
    current_session_file.write_text(
        json.dumps({"current_session_id": session_id}), encoding="utf-8"
    )

    with patch.object(_mod, "MEMORY_PATH", memory_path), \
         patch.object(_mod, "FLAG_DIR", tmp_path), \
         patch.object(_mod, "CURRENT_SESSION_FILE", current_session_file), \
         patch.object(_mod, "LOGS_PATH", logs_path):
        yield {
            "memory_path": memory_path,
            "logs_path": logs_path,
            "session_dir": session_dir,
            "flags_dir": flags_dir,
            "session_id": session_id,
        }


def _write_flag(flags_dir: Path, flag_name: str, extra: dict = None, age_minutes: int = 0):
    """Write a flag JSON file into the flags directory."""
    created_at = datetime.now() - timedelta(minutes=age_minutes)
    data = {"created_at": created_at.isoformat()}
    if extra:
        data.update(extra)
    flag_file = flags_dir / f"{flag_name}.json"
    flag_file.write_text(json.dumps(data), encoding="utf-8")
    return flag_file


def _write_flow_trace(session_dir: Path, steps: list):
    """Write a flow-trace.json with the given pipeline steps."""
    trace = {"pipeline": [{"step": s} for s in steps]}
    trace_file = session_dir / "flow-trace.json"
    trace_file.write_text(json.dumps(trace), encoding="utf-8")
    return trace_file


# ===========================================================================
# TOOL 1: validate_tool_call
# ===========================================================================

class TestValidateToolCallAlwaysAllowed:
    """Always-allowed tools (Read, Grep, Glob, WebFetch, WebSearch, Task) skip all blocks."""

    @pytest.mark.parametrize("tool_name", ["Read", "Grep", "Glob", "WebFetch", "WebSearch", "Task"])
    def test_always_allowed_returns_allowed(self, tmp_session, tool_name):
        result = _parse(validate_tool_call(tool_name))
        assert result["allowed"] is True
        assert result["reason"] == "Tool is always allowed"

    def test_read_no_blocks_even_with_pending_flags(self, tmp_session):
        """Read is allowed even when task-breakdown-pending flag exists."""
        _write_flag(tmp_session["flags_dir"], "task-breakdown-pending")
        result = _parse(validate_tool_call("Read"))
        assert result["allowed"] is True

    def test_grep_no_blocks_even_with_checkpoint_pending(self, tmp_session):
        """Grep is allowed even when checkpoint-pending flag exists."""
        _write_flag(tmp_session["flags_dir"], "checkpoint-pending")
        result = _parse(validate_tool_call("Grep"))
        assert result["allowed"] is True


class TestValidateToolCallBlocked:
    """Write/Edit/NotebookEdit are blocked by policy flags."""

    def test_write_blocked_by_task_breakdown_pending(self, tmp_session):
        _write_flag(tmp_session["flags_dir"], "task-breakdown-pending")
        result = _parse(validate_tool_call("Write"))
        assert result["allowed"] is False
        assert "task breakdown pending" in result["reason"].lower() or \
               "task breakdown" in result["blocks"][0].lower()

    def test_edit_blocked_by_task_breakdown_pending(self, tmp_session):
        _write_flag(tmp_session["flags_dir"], "task-breakdown-pending")
        result = _parse(validate_tool_call("Edit"))
        assert result["allowed"] is False
        assert len(result["blocks"]) >= 1

    def test_notebook_edit_blocked_by_task_breakdown_pending(self, tmp_session):
        _write_flag(tmp_session["flags_dir"], "task-breakdown-pending")
        result = _parse(validate_tool_call("NotebookEdit"))
        assert result["allowed"] is False

    def test_write_blocked_by_checkpoint_pending(self, tmp_session):
        _write_flag(tmp_session["flags_dir"], "checkpoint-pending")
        result = _parse(validate_tool_call("Write"))
        assert result["allowed"] is False
        assert any("checkpoint" in b.lower() for b in result["blocks"])

    def test_write_blocked_by_skill_selection_pending(self, tmp_session):
        _write_flag(
            tmp_session["flags_dir"],
            "skill-selection-pending",
            extra={"required_skill": "python-core"}
        )
        result = _parse(validate_tool_call("Write"))
        assert result["allowed"] is False
        assert any("skill" in b.lower() for b in result["blocks"])

    def test_write_allowed_when_no_flags(self, tmp_session):
        result = _parse(validate_tool_call("Write"))
        assert result["allowed"] is True

    def test_write_allowed_with_expired_task_breakdown_flag(self, tmp_session):
        """Flag older than TTL_SECONDS (90 s) should not block."""
        # Write flag with age > FLAG_TTL_SECONDS (90 s). FLAG_TTL_SECONDS is in seconds,
        # but _check_flag_with_ttl compares age in seconds against ttl_seconds.
        # Write a flag aged 2 minutes = 120 seconds > 90 seconds TTL.
        _write_flag(tmp_session["flags_dir"], "task-breakdown-pending", age_minutes=2)
        result = _parse(validate_tool_call("Write"))
        assert result["allowed"] is True

    def test_write_blocked_by_level1_not_complete(self, tmp_session):
        """When flow-trace exists but Level 1 steps are absent, Write is blocked."""
        _write_flow_trace(tmp_session["session_dir"], ["LEVEL_2_STANDARDS"])
        result = _parse(validate_tool_call("Write"))
        assert result["allowed"] is False
        assert any("level 1" in b.lower() or "level1" in b.lower() for b in result["blocks"])

    def test_write_blocked_by_level2_not_complete(self, tmp_session):
        """Level 1 present but Level 2 absent -> blocked."""
        _write_flow_trace(
            tmp_session["session_dir"],
            ["LEVEL_1_CONTEXT", "LEVEL_1_SESSION"]
        )
        result = _parse(validate_tool_call("Write"))
        assert result["allowed"] is False
        assert any("level 2" in b.lower() or "level2" in b.lower() for b in result["blocks"])

    def test_write_allowed_with_complete_pipeline(self, tmp_session):
        """All pipeline steps present and no flags -> Write allowed."""
        _write_flow_trace(
            tmp_session["session_dir"],
            ["LEVEL_1_CONTEXT", "LEVEL_1_SESSION", "LEVEL_2_STANDARDS"]
        )
        result = _parse(validate_tool_call("Write"))
        assert result["allowed"] is True

    def test_result_contains_session_id(self, tmp_session, session_id):
        result = _parse(validate_tool_call("Write"))
        assert result["session_id"] == session_id

    def test_result_schema_for_blocked_tool(self, tmp_session):
        result = _parse(validate_tool_call("Write"))
        assert "allowed" in result
        assert "tool" in result
        assert "hints" in result
        assert "blocks" in result
        assert "checks_run" in result
        assert "reason" in result


class TestValidateToolCallBashWindowsBlocking:
    """Bash Windows command blocking (Check 7)."""

    def test_bash_blocked_on_win32_del_command(self, tmp_session):
        with patch.object(_mod.sys, "platform", "win32"):
            result = _parse(validate_tool_call("Bash", json.dumps({"command": "del myfile.txt"})))
            assert result["allowed"] is False
            assert any("del" in b.lower() or "windows" in b.lower() for b in result["blocks"])

    def test_bash_blocked_on_win32_copy_command(self, tmp_session):
        with patch.object(_mod.sys, "platform", "win32"):
            result = _parse(validate_tool_call("Bash", json.dumps({"command": "copy a.txt b.txt"})))
            assert result["allowed"] is False

    def test_bash_blocked_on_win32_xcopy(self, tmp_session):
        with patch.object(_mod.sys, "platform", "win32"):
            result = _parse(validate_tool_call("Bash", json.dumps({"command": "xcopy /s src dst"})))
            assert result["allowed"] is False

    def test_bash_allowed_on_linux(self, tmp_session):
        """del command should not be blocked on linux."""
        with patch.object(_mod.sys, "platform", "linux"):
            result = _parse(validate_tool_call("Bash", json.dumps({"command": "del myfile.txt"})))
            assert result["allowed"] is True

    def test_bash_unix_rm_not_blocked_on_win32(self, tmp_session):
        with patch.object(_mod.sys, "platform", "win32"):
            result = _parse(validate_tool_call("Bash", json.dumps({"command": "rm -rf /tmp/test"})))
            assert result["allowed"] is True


class TestValidateToolCallPythonUnicodeBlocking:
    """Python Unicode blocking (Check 8) - non-ASCII in .py files on Windows."""

    def test_write_py_with_emoji_blocked_on_win32(self, tmp_session):
        params = {
            "file_path": "/some/path/module.py",
            "content": "# This has a unicode char: \u2713"
        }
        with patch.object(_mod.sys, "platform", "win32"):
            result = _parse(validate_tool_call("Write", json.dumps(params)))
            assert result["allowed"] is False
            assert any("ascii" in b.lower() or "unicode" in b.lower() or "cp1252" in b.lower()
                       for b in result["blocks"])

    def test_edit_py_with_non_ascii_blocked_on_win32(self, tmp_session):
        params = {
            "file_path": "/some/path/utils.py",
            "new_string": "# \u00e9l\u00e8ve"
        }
        with patch.object(_mod.sys, "platform", "win32"):
            result = _parse(validate_tool_call("Edit", json.dumps(params)))
            assert result["allowed"] is False

    def test_write_py_ascii_only_allowed_on_win32(self, tmp_session):
        params = {
            "file_path": "/some/path/module.py",
            "content": "# Pure ASCII content only\nresult = 42\n"
        }
        with patch.object(_mod.sys, "platform", "win32"):
            result = _parse(validate_tool_call("Write", json.dumps(params)))
            assert result["allowed"] is True

    def test_write_non_py_file_with_unicode_allowed_on_win32(self, tmp_session):
        """Non-.py files are not checked for unicode."""
        params = {
            "file_path": "/some/path/readme.md",
            "content": "# \u2713 Done"
        }
        with patch.object(_mod.sys, "platform", "win32"):
            result = _parse(validate_tool_call("Write", json.dumps(params)))
            assert result["allowed"] is True

    def test_write_py_non_ascii_allowed_on_linux(self, tmp_session):
        params = {
            "file_path": "/some/path/module.py",
            "content": "# \u2713 Unicode"
        }
        with patch.object(_mod.sys, "platform", "linux"):
            result = _parse(validate_tool_call("Write", json.dumps(params)))
            assert result["allowed"] is True


class TestValidateToolCallHints:
    """Non-blocking optimization hints.

    Note: Grep and Read are in ALWAYS_ALLOWED so they return early before the
    hint block is reached in validate_tool_call. The hint logic is only active
    for tools NOT in ALWAYS_ALLOWED that pass through the full pipeline. The
    check_failure_patterns tool is the dedicated surface for Grep/Read hints.
    """

    def test_grep_always_allowed_returns_empty_hints(self, tmp_session):
        """Grep is in ALWAYS_ALLOWED - it returns before hint logic runs."""
        result = _parse(validate_tool_call("Grep", json.dumps({"pattern": "TODO"})))
        assert result["allowed"] is True
        assert result["hints"] == []

    def test_read_always_allowed_returns_empty_hints(self, tmp_session):
        """Read is in ALWAYS_ALLOWED - it returns before hint logic runs."""
        result = _parse(validate_tool_call("Read", json.dumps({"file_path": "/a/b.py"})))
        assert result["allowed"] is True
        assert result["hints"] == []

    def test_invalid_json_input_does_not_crash(self, tmp_session):
        result = _parse(validate_tool_call("Write", "not-json"))
        assert "allowed" in result


# ===========================================================================
# TOOL 2: check_task_breakdown
# ===========================================================================

class TestCheckTaskBreakdown:

    def test_no_flag_returns_not_pending(self, tmp_session):
        result = _parse(check_task_breakdown())
        assert result["success"] is True
        assert result["pending"] is False
        assert result["flag_data"] is None

    def test_active_flag_returns_pending(self, tmp_session):
        _write_flag(tmp_session["flags_dir"], "task-breakdown-pending")
        result = _parse(check_task_breakdown())
        assert result["success"] is True
        assert result["pending"] is True
        assert result["flag_data"] is not None

    def test_expired_flag_returns_not_pending(self, tmp_session):
        """Flag aged > 90 seconds (TTL) should be treated as not pending."""
        _write_flag(tmp_session["flags_dir"], "task-breakdown-pending", age_minutes=2)
        result = _parse(check_task_breakdown())
        assert result["success"] is True
        assert result["pending"] is False

    def test_result_contains_session_id(self, tmp_session, session_id):
        result = _parse(check_task_breakdown())
        assert result["session_id"] == session_id

    def test_result_contains_ttl_seconds(self, tmp_session):
        result = _parse(check_task_breakdown())
        assert result["ttl_seconds"] == _mod.FLAG_TTL_SECONDS

    def test_no_session_returns_not_pending(self, tmp_session):
        """Without a session ID, flag lookup returns nothing."""
        with patch.object(_mod, "_get_session_id", return_value=""):
            result = _parse(check_task_breakdown())
            assert result["success"] is True
            assert result["pending"] is False


# ===========================================================================
# TOOL 3: check_skill_selected
# ===========================================================================

class TestCheckSkillSelected:

    def test_no_flag_returns_not_pending(self, tmp_session):
        result = _parse(check_skill_selected())
        assert result["success"] is True
        assert result["pending"] is False
        assert result["required_skill"] == ""

    def test_active_flag_returns_pending_with_skill(self, tmp_session):
        _write_flag(
            tmp_session["flags_dir"],
            "skill-selection-pending",
            extra={"required_skill": "python-core", "required_type": "skill"}
        )
        result = _parse(check_skill_selected())
        assert result["success"] is True
        assert result["pending"] is True
        assert result["required_skill"] == "python-core"
        assert result["required_type"] == "skill"

    def test_expired_flag_returns_not_pending(self, tmp_session):
        _write_flag(tmp_session["flags_dir"], "skill-selection-pending", age_minutes=2)
        result = _parse(check_skill_selected())
        assert result["pending"] is False

    def test_result_contains_session_id(self, tmp_session, session_id):
        result = _parse(check_skill_selected())
        assert result["session_id"] == session_id

    def test_missing_required_skill_key_defaults_to_empty(self, tmp_session):
        _write_flag(tmp_session["flags_dir"], "skill-selection-pending")
        result = _parse(check_skill_selected())
        assert result["pending"] is True
        assert result["required_skill"] == ""


# ===========================================================================
# TOOL 4: check_level_completion
# ===========================================================================

class TestCheckLevelCompletion:

    def test_no_flow_trace_returns_fail_open(self, tmp_session):
        result = _parse(check_level_completion())
        assert result["success"] is True
        assert result["trace_found"] is False
        assert "fail-open" in result["message"].lower()

    def test_level1_complete_when_both_steps_present(self, tmp_session):
        _write_flow_trace(
            tmp_session["session_dir"],
            ["LEVEL_1_CONTEXT", "LEVEL_1_SESSION", "LEVEL_2_STANDARDS"]
        )
        result = _parse(check_level_completion("level1"))
        assert result["success"] is True
        assert result["trace_found"] is True
        assert result["level1_complete"] is True
        assert result["level1_context"] is True
        assert result["level1_session"] is True

    def test_level1_incomplete_when_only_context_present(self, tmp_session):
        _write_flow_trace(tmp_session["session_dir"], ["LEVEL_1_CONTEXT"])
        result = _parse(check_level_completion())
        assert result["level1_complete"] is False
        assert result["level1_session"] is False

    def test_level2_complete_when_standards_step_present(self, tmp_session):
        _write_flow_trace(
            tmp_session["session_dir"],
            ["LEVEL_1_CONTEXT", "LEVEL_1_SESSION", "LEVEL_2_STANDARDS"]
        )
        result = _parse(check_level_completion("level2"))
        assert result["level2_complete"] is True
        assert result["level2_standards"] is True

    def test_all_complete_when_all_steps_present(self, tmp_session):
        _write_flow_trace(
            tmp_session["session_dir"],
            ["LEVEL_1_CONTEXT", "LEVEL_1_SESSION", "LEVEL_2_STANDARDS"]
        )
        result = _parse(check_level_completion("all"))
        assert result["all_complete"] is True

    def test_all_incomplete_when_level2_missing(self, tmp_session):
        _write_flow_trace(
            tmp_session["session_dir"],
            ["LEVEL_1_CONTEXT", "LEVEL_1_SESSION"]
        )
        result = _parse(check_level_completion("all"))
        assert result["all_complete"] is False
        assert result["level2_complete"] is False

    def test_flow_trace_as_list_of_entries_uses_last(self, tmp_session):
        """flow-trace.json can be a list; the last entry is used."""
        entries = [
            {"pipeline": [{"step": "LEVEL_1_CONTEXT"}]},
            {"pipeline": [{"step": "LEVEL_1_CONTEXT"}, {"step": "LEVEL_1_SESSION"}, {"step": "LEVEL_2_STANDARDS"}]},
        ]
        trace_file = tmp_session["session_dir"] / "flow-trace.json"
        trace_file.write_text(json.dumps(entries), encoding="utf-8")
        result = _parse(check_level_completion())
        assert result["trace_found"] is True
        assert result["all_complete"] is True

    def test_result_contains_session_id(self, tmp_session, session_id):
        result = _parse(check_level_completion())
        assert result["session_id"] == session_id


# ===========================================================================
# TOOL 5: get_enforcer_state
# ===========================================================================

class TestGetEnforcerState:

    def test_clean_state_all_false(self, tmp_session):
        result = _parse(get_enforcer_state())
        assert result["success"] is True
        flags = result["flags"]
        assert flags["checkpoint_pending"] is False
        assert flags["task_breakdown_pending"] is False
        assert flags["skill_selection_pending"] is False
        assert flags["required_skill"] == ""

    def test_checkpoint_flag_reflected(self, tmp_session):
        _write_flag(tmp_session["flags_dir"], "checkpoint-pending")
        result = _parse(get_enforcer_state())
        assert result["flags"]["checkpoint_pending"] is True

    def test_task_breakdown_flag_reflected(self, tmp_session):
        _write_flag(tmp_session["flags_dir"], "task-breakdown-pending")
        result = _parse(get_enforcer_state())
        assert result["flags"]["task_breakdown_pending"] is True

    def test_skill_selection_flag_reflected_with_skill_name(self, tmp_session):
        _write_flag(
            tmp_session["flags_dir"],
            "skill-selection-pending",
            extra={"required_skill": "java-spring-boot-microservices"}
        )
        result = _parse(get_enforcer_state())
        assert result["flags"]["skill_selection_pending"] is True
        assert result["flags"]["required_skill"] == "java-spring-boot-microservices"

    def test_pipeline_trace_exists_reflected(self, tmp_session):
        _write_flow_trace(
            tmp_session["session_dir"],
            ["LEVEL_1_CONTEXT", "LEVEL_1_SESSION", "LEVEL_2_STANDARDS"]
        )
        result = _parse(get_enforcer_state())
        pipeline = result["pipeline"]
        assert pipeline["trace_exists"] is True
        assert pipeline["level1_complete"] is True
        assert pipeline["level2_complete"] is True

    def test_pipeline_no_trace(self, tmp_session):
        result = _parse(get_enforcer_state())
        pipeline = result["pipeline"]
        assert pipeline["trace_exists"] is False
        assert pipeline["level1_complete"] is False
        assert pipeline["level2_complete"] is False

    def test_blocked_tools_list_correct(self, tmp_session):
        result = _parse(get_enforcer_state())
        assert set(result["blocked_tools"]) == {"Edit", "NotebookEdit", "Write"}

    def test_always_allowed_list_present(self, tmp_session):
        result = _parse(get_enforcer_state())
        assert "Read" in result["always_allowed"]
        assert "Grep" in result["always_allowed"]

    def test_session_id_in_result(self, tmp_session, session_id):
        result = _parse(get_enforcer_state())
        assert result["session_id"] == session_id


# ===========================================================================
# TOOL 6: check_failure_patterns
# ===========================================================================

class TestCheckFailurePatterns:

    def test_edit_with_line_number_prefix_produces_warning(self, tmp_session):
        params = {"file_path": "/a/b.py", "old_string": "  42 def foo():"}
        result = _parse(check_failure_patterns("Edit", json.dumps(params)))
        assert result["success"] is True
        assert any("line number" in h.lower() for h in result["hints"])

    def test_edit_without_line_number_prefix_no_warning(self, tmp_session):
        params = {"file_path": "/a/b.py", "old_string": "def foo():"}
        result = _parse(check_failure_patterns("Edit", json.dumps(params)))
        assert not any("line number" in h.lower() for h in result["hints"])

    def test_edit_missing_file_path_produces_hint(self, tmp_session):
        params = {"old_string": "something"}
        result = _parse(check_failure_patterns("Edit", json.dumps(params)))
        assert any("file_path" in h.lower() for h in result["hints"])

    def test_bash_windows_del_suggests_rm_on_win32(self, tmp_session):
        params = {"command": "del myfile.txt"}
        with patch.object(_mod.sys, "platform", "win32"):
            result = _parse(check_failure_patterns("Bash", json.dumps(params)))
            assert any("rm" in h.lower() or "del" in h.lower() for h in result["hints"])

    def test_bash_windows_copy_suggests_cp_on_win32(self, tmp_session):
        params = {"command": "copy src.txt dst.txt"}
        with patch.object(_mod.sys, "platform", "win32"):
            result = _parse(check_failure_patterns("Bash", json.dumps(params)))
            assert any("cp" in h.lower() or "copy" in h.lower() for h in result["hints"])

    def test_bash_windows_cmd_on_linux_no_hint(self, tmp_session):
        params = {"command": "del myfile.txt"}
        with patch.object(_mod.sys, "platform", "linux"):
            result = _parse(check_failure_patterns("Bash", json.dumps(params)))
            assert result["success"] is True
            assert len(result["hints"]) == 0

    def test_grep_without_head_limit_produces_hint(self, tmp_session):
        params = {"pattern": "TODO"}
        result = _parse(check_failure_patterns("Grep", json.dumps(params)))
        assert any("head_limit" in h.lower() for h in result["hints"])

    def test_grep_with_head_limit_no_hint(self, tmp_session):
        params = {"pattern": "TODO", "head_limit": 10}
        result = _parse(check_failure_patterns("Grep", json.dumps(params)))
        assert not any("head_limit" in h.lower() for h in result["hints"])

    def test_read_without_limits_produces_hint(self, tmp_session):
        params = {"file_path": "/some/large/file.py"}
        result = _parse(check_failure_patterns("Read", json.dumps(params)))
        assert any("offset" in h.lower() or "limit" in h.lower() for h in result["hints"])

    def test_read_with_offset_no_hint(self, tmp_session):
        params = {"file_path": "/some/file.py", "offset": 100, "limit": 50}
        result = _parse(check_failure_patterns("Read", json.dumps(params)))
        assert not any("offset" in h.lower() for h in result["hints"])

    def test_unknown_tool_returns_no_hints(self, tmp_session):
        result = _parse(check_failure_patterns("UnknownTool", "{}"))
        assert result["success"] is True
        assert result["hints"] == []

    def test_invalid_json_input_does_not_crash(self, tmp_session):
        result = _parse(check_failure_patterns("Edit", "not-json"))
        assert result["success"] is True

    def test_result_schema(self, tmp_session):
        result = _parse(check_failure_patterns("Edit", "{}"))
        assert "success" in result
        assert "tool" in result
        assert "hints" in result
        assert "kb_loaded" in result
        assert "patterns_checked" in result

    def test_patterns_checked_count_matches_hints(self, tmp_session):
        params = {"old_string": "  10 something"}
        result = _parse(check_failure_patterns("Edit", json.dumps(params)))
        assert result["patterns_checked"] == len(result["hints"])


# ===========================================================================
# TOOL 7: get_dynamic_skill_hint
# ===========================================================================

class TestGetDynamicSkillHint:

    @pytest.mark.parametrize("file_path,expected_skill", [
        ("/project/src/Main.java", "java-spring-boot-microservices"),
        ("/project/app.py", "python-core"),
        ("/project/index.ts", "typescript-core"),
        ("/project/component.tsx", "react-core"),
        ("/project/app.js", "javascript-core"),
        ("/project/widget.jsx", "react-core"),
        ("/project/ContentView.swift", "swiftui-core"),
        ("/project/layout.xml", "android-xml-ui"),
        ("/project/styles.css", "css-core"),
        ("/project/main.scss", "css-core"),
        ("/project/index.html", "html5-core"),
        ("/project/schema.sql", "rdbms-core"),
        ("/project/docker-compose.yml", "docker"),
        ("/project/deployment.yaml", "kubernetes"),
        ("/project/main.tf", "kubernetes"),
        ("/project/data.json", "json-core"),
        ("/project/api.graphql", "graphql-core"),
        ("/project/Service.kt", "kotlin-core"),
    ])
    def test_extension_to_skill_mapping(self, file_path, expected_skill):
        result = _parse(get_dynamic_skill_hint(file_path))
        assert result["success"] is True
        assert result["suggested_skill"] == expected_skill
        assert result["has_suggestion"] is True

    def test_java_file_extension_is_case_insensitive(self):
        result = _parse(get_dynamic_skill_hint("/project/Main.JAVA"))
        assert result["success"] is True
        assert result["suggested_skill"] == "java-spring-boot-microservices"

    def test_py_extension_returns_python_core(self):
        result = _parse(get_dynamic_skill_hint("/project/app.py"))
        assert result["suggested_skill"] == "python-core"
        assert result["has_suggestion"] is True

    def test_markdown_file_has_no_suggestion(self):
        result = _parse(get_dynamic_skill_hint("/project/README.md"))
        assert result["success"] is True
        assert result["suggested_skill"] is None
        assert result["has_suggestion"] is False

    def test_unknown_extension_has_no_suggestion(self):
        result = _parse(get_dynamic_skill_hint("/project/file.xyz"))
        assert result["success"] is True
        assert result["suggested_skill"] is None
        assert result["has_suggestion"] is False

    def test_dockerfile_special_case(self):
        result = _parse(get_dynamic_skill_hint("/project/Dockerfile"))
        assert result["suggested_skill"] == "docker"
        assert result["has_suggestion"] is True

    def test_dockerfile_with_suffix(self):
        result = _parse(get_dynamic_skill_hint("/project/api.dockerfile"))
        assert result["suggested_skill"] == "docker"

    def test_jenkinsfile_special_case(self):
        result = _parse(get_dynamic_skill_hint("/project/Jenkinsfile"))
        assert result["suggested_skill"] == "jenkins-pipeline"
        assert result["has_suggestion"] is True

    def test_result_contains_file_and_extension(self):
        result = _parse(get_dynamic_skill_hint("/project/app.py"))
        assert result["file"] == "/project/app.py"
        assert result["extension"] == ".py"

    def test_no_extension_file_has_no_suggestion(self):
        result = _parse(get_dynamic_skill_hint("/project/Makefile"))
        assert result["success"] is True
        assert result["has_suggestion"] is False


# ===========================================================================
# TOOL 8: reset_enforcer_flags
# ===========================================================================

class TestResetEnforcerFlags:

    def test_reset_all_clears_all_three_flags(self, tmp_session):
        flags_dir = tmp_session["flags_dir"]
        _write_flag(flags_dir, "task-breakdown-pending")
        _write_flag(flags_dir, "skill-selection-pending")
        _write_flag(flags_dir, "checkpoint-pending")

        result = _parse(reset_enforcer_flags("all"))
        assert result["success"] is True
        assert set(result["cleared"]) == {
            "task-breakdown-pending", "skill-selection-pending", "checkpoint-pending"
        }
        assert result["count"] == 3

    def test_reset_single_flag_only_clears_that_flag(self, tmp_session):
        flags_dir = tmp_session["flags_dir"]
        _write_flag(flags_dir, "task-breakdown-pending")
        _write_flag(flags_dir, "skill-selection-pending")

        result = _parse(reset_enforcer_flags("task-breakdown-pending"))
        assert result["success"] is True
        assert "task-breakdown-pending" in result["cleared"]
        # skill-selection-pending should still exist
        assert (flags_dir / "skill-selection-pending.json").exists()

    def test_reset_when_no_flags_returns_empty_cleared(self, tmp_session):
        result = _parse(reset_enforcer_flags("all"))
        assert result["success"] is True
        assert result["cleared"] == []
        assert result["count"] == 0

    def test_reset_without_session_returns_error(self, tmp_session):
        with patch.object(_mod, "_get_session_id", return_value=""):
            result = _parse(reset_enforcer_flags("all"))
            assert result["success"] is False
            assert "session" in result["error"].lower()

    def test_reset_cleans_up_flag_files(self, tmp_session):
        flags_dir = tmp_session["flags_dir"]
        flag_file = _write_flag(flags_dir, "task-breakdown-pending")
        assert flag_file.exists()

        reset_enforcer_flags("task-breakdown-pending")
        assert not flag_file.exists()

    def test_reset_clears_legacy_flag_location(self, tmp_session, session_id):
        """Legacy flags in FLAG_DIR (e.g., ~/.claude) are also cleared."""
        legacy_file = tmp_path_for_legacy = Path(tmp_session["memory_path"]).parent
        # FLAG_DIR is patched to tmp_path (parent of memory_path)
        flag_dir_patch = Path(tmp_session["memory_path"]).parent
        legacy_flag = flag_dir_patch / f".task-breakdown-pending-{session_id}.json"
        legacy_flag.write_text(
            json.dumps({"created_at": datetime.now().isoformat()}), encoding="utf-8"
        )

        result = _parse(reset_enforcer_flags("task-breakdown-pending"))
        assert result["success"] is True
        assert not legacy_flag.exists()

    def test_reset_result_contains_session_id(self, tmp_session, session_id):
        result = _parse(reset_enforcer_flags("all"))
        assert result["session_id"] == session_id

    def test_reset_checkpoint_pending_only(self, tmp_session):
        _write_flag(tmp_session["flags_dir"], "checkpoint-pending")
        _write_flag(tmp_session["flags_dir"], "task-breakdown-pending")

        result = _parse(reset_enforcer_flags("checkpoint-pending"))
        assert result["success"] is True
        assert "checkpoint-pending" in result["cleared"]
        assert (tmp_session["flags_dir"] / "task-breakdown-pending.json").exists()


# ===========================================================================
# Internal helpers (unit tests for private functions)
# ===========================================================================

class TestInternalHelpers:
    """Test internal helper functions for correctness."""

    def test_get_session_id_from_current_session_file(self, tmp_session, session_id):
        result = _mod._get_session_id()
        assert result == session_id

    def test_get_session_id_returns_empty_when_file_missing(self, tmp_path):
        with patch.object(_mod, "CURRENT_SESSION_FILE", tmp_path / "nonexistent.json"), \
             patch.object(_mod, "MEMORY_PATH", tmp_path):
            result = _mod._get_session_id()
            assert result == ""

    def test_find_flag_returns_none_for_unknown_flag(self, tmp_session, session_id):
        result = _mod._find_flag("nonexistent-flag", session_id)
        assert result is None

    def test_find_flag_auto_expires_old_flag(self, tmp_session, session_id):
        """Flags older than CHECKPOINT_MAX_AGE_MINUTES (60 min) are auto-expired."""
        _write_flag(tmp_session["flags_dir"], "checkpoint-pending", age_minutes=61)
        result = _mod._find_flag("checkpoint-pending", session_id)
        assert result is None

    def test_find_flag_returns_data_for_fresh_flag(self, tmp_session, session_id):
        _write_flag(tmp_session["flags_dir"], "checkpoint-pending")
        result = _mod._find_flag("checkpoint-pending", session_id)
        assert result is not None
        assert "created_at" in result

    def test_pipeline_step_present_detects_step(self):
        trace = {"pipeline": [{"step": "LEVEL_1_CONTEXT"}, {"step": "LEVEL_2_STANDARDS"}]}
        assert _mod._pipeline_step_present(trace, "LEVEL_1_CONTEXT") is True
        assert _mod._pipeline_step_present(trace, "LEVEL_1_SESSION") is False

    def test_pipeline_step_present_empty_trace(self):
        assert _mod._pipeline_step_present({}, "LEVEL_1_CONTEXT") is False
        assert _mod._pipeline_step_present(None, "LEVEL_1_CONTEXT") is False

    def test_json_serializes_dict(self):
        data = {"key": "value", "num": 42}
        result = _mod._json(data)
        parsed = json.loads(result)
        assert parsed == data
