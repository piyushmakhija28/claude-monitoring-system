"""Tests for Token Optimization MCP Server (src/mcp/token_optimization_mcp_server.py)."""

import json
import sys
import importlib.util
import pytest
from pathlib import Path
from unittest.mock import patch

_MCP_DIR = Path(__file__).parent.parent / "src" / "mcp"


def _load_module(name, file_path):
    spec = importlib.util.spec_from_file_location(name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_tok_mod = _load_module(
    "token_optimization_mcp_server",
    _MCP_DIR / "token_optimization_mcp_server.py",
)

optimize_tool_call = _tok_mod.optimize_tool_call
ast_navigate_code = _tok_mod.ast_navigate_code
smart_read_analyze = _tok_mod.smart_read_analyze
deduplicate_context = _tok_mod.deduplicate_context
dedup_estimate = _tok_mod.dedup_estimate
context_budget_status = _tok_mod.context_budget_status
CONTEXT_BUDGET_BYTES = _tok_mod.CONTEXT_BUDGET_BYTES
MEMORY_PATH = _tok_mod.MEMORY_PATH


def _parse(result: str) -> dict:
    return json.loads(result)


# =============================================================================
# Helpers
# =============================================================================

def _make_text_file(path: Path, lines: int, content_per_line: str = "x" * 60) -> Path:
    """Create a text file with a fixed number of lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(content_per_line for _ in range(lines)),
        encoding="utf-8"
    )
    return path


def _make_python_file(path: Path, src: str) -> Path:
    """Write Python source to a .py file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(src, encoding="utf-8")
    return path


# =============================================================================
# TOOL 1: optimize_tool_call
# =============================================================================

class TestOptimizeToolCallRead:
    """Tests for optimize_tool_call with Read tool."""

    def test_read_large_file_gets_auto_limit(self, tmp_path):
        large_file = tmp_path / "large.txt"
        _make_text_file(large_file, 600)
        params = json.dumps({"file_path": str(large_file)})
        result = _parse(optimize_tool_call("Read", params))
        assert result["success"] is True
        optimized = result["optimized_params"]
        # Large file (>500 lines) without offset/limit -> auto-limited
        assert "limit" in optimized
        assert optimized["limit"] <= 200

    def test_read_small_file_not_modified(self, tmp_path):
        small_file = tmp_path / "small.txt"
        _make_text_file(small_file, 50)
        params = json.dumps({"file_path": str(small_file)})
        result = _parse(optimize_tool_call("Read", params))
        assert result["success"] is True
        # Small files (<= 200 lines) need no limit injection
        optimized = result["optimized_params"]
        assert optimized.get("limit") is None or optimized.get("limit", 51) > 50

    def test_read_with_existing_offset_and_limit_not_overridden(self, tmp_path):
        large_file = tmp_path / "large.txt"
        _make_text_file(large_file, 700)
        params = json.dumps({
            "file_path": str(large_file),
            "offset": 100,
            "limit": 50,
        })
        result = _parse(optimize_tool_call("Read", params))
        assert result["success"] is True
        optimized = result["optimized_params"]
        assert optimized["offset"] == 100
        assert optimized["limit"] == 50

    def test_read_nonexistent_file_still_succeeds(self, tmp_path):
        params = json.dumps({"file_path": str(tmp_path / "ghost.txt")})
        result = _parse(optimize_tool_call("Read", params))
        assert result["success"] is True

    def test_read_code_file_suggests_ast_navigation(self, tmp_path):
        py_file = tmp_path / "large_code.py"
        _make_text_file(py_file, 400)
        params = json.dumps({"file_path": str(py_file)})
        result = _parse(optimize_tool_call("Read", params))
        assert result["success"] is True
        all_suggestions = " ".join(result["suggestions"])
        assert "ast" in all_suggestions.lower() or "navigate" in all_suggestions.lower()

    def test_read_token_savings_positive_for_large_file(self, tmp_path):
        large_file = tmp_path / "huge.txt"
        _make_text_file(large_file, 1000)
        params = json.dumps({"file_path": str(large_file)})
        result = _parse(optimize_tool_call("Read", params))
        assert result["success"] is True
        assert result["token_savings_estimate"] > 0


class TestOptimizeToolCallGrep:
    """Tests for optimize_tool_call with Grep tool."""

    def test_grep_no_head_limit_gets_default_100(self):
        params = json.dumps({"pattern": "def main"})
        result = _parse(optimize_tool_call("Grep", params))
        assert result["success"] is True
        optimized = result["optimized_params"]
        assert optimized["head_limit"] == 100

    def test_grep_no_output_mode_gets_files_with_matches(self):
        params = json.dumps({"pattern": "def main"})
        result = _parse(optimize_tool_call("Grep", params))
        assert result["success"] is True
        optimized = result["optimized_params"]
        assert optimized["output_mode"] == "files_with_matches"

    def test_grep_existing_head_limit_preserved(self):
        params = json.dumps({"pattern": "TODO", "head_limit": 50})
        result = _parse(optimize_tool_call("Grep", params))
        assert result["success"] is True
        optimized = result["optimized_params"]
        assert optimized["head_limit"] == 50

    def test_grep_broad_pattern_generates_suggestion(self):
        params = json.dumps({"pattern": "a"})
        result = _parse(optimize_tool_call("Grep", params))
        assert result["success"] is True
        all_suggestions = " ".join(result["suggestions"]).lower()
        assert "broad" in all_suggestions or "specific" in all_suggestions

    def test_grep_savings_positive_when_no_head_limit(self):
        params = json.dumps({"pattern": "import"})
        result = _parse(optimize_tool_call("Grep", params))
        assert result["success"] is True
        assert result["token_savings_estimate"] > 0

    def test_grep_was_optimized_true_when_params_changed(self):
        params = json.dumps({"pattern": "class"})
        result = _parse(optimize_tool_call("Grep", params))
        assert result["success"] is True
        assert result["was_optimized"] is True


class TestOptimizeToolCallEdit:
    """Tests for optimize_tool_call with Edit tool."""

    def test_edit_unique_old_string_no_warning(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("def foo():\n    pass\n\ndef bar():\n    return 1\n", encoding="utf-8")
        params = json.dumps({
            "file_path": str(target),
            "old_string": "def foo():\n    pass",
            "new_string": "def foo():\n    return 42",
        })
        result = _parse(optimize_tool_call("Edit", params))
        assert result["success"] is True
        # No duplication warning
        warnings = [s for s in result["suggestions"] if "appears" in s and "times" in s]
        assert len(warnings) == 0

    def test_edit_duplicate_old_string_warns(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text(
            "def foo():\n    pass\n\ndef foo():\n    pass\n",
            encoding="utf-8"
        )
        params = json.dumps({
            "file_path": str(target),
            "old_string": "def foo():\n    pass",
            "new_string": "def foo():\n    return 1",
        })
        result = _parse(optimize_tool_call("Edit", params))
        assert result["success"] is True
        all_suggestions = " ".join(result["suggestions"])
        assert "times" in all_suggestions or "Edit will fail" in all_suggestions

    def test_edit_old_string_not_found_warns(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("class Foo:\n    pass\n", encoding="utf-8")
        params = json.dumps({
            "file_path": str(target),
            "old_string": "class Bar:\n    pass",
            "new_string": "class Bar:\n    return 1",
        })
        result = _parse(optimize_tool_call("Edit", params))
        assert result["success"] is True
        all_suggestions = " ".join(result["suggestions"]).lower()
        assert "not found" in all_suggestions

    def test_edit_nonexistent_file_no_crash(self, tmp_path):
        params = json.dumps({
            "file_path": str(tmp_path / "ghost.py"),
            "old_string": "foo",
            "new_string": "bar",
        })
        result = _parse(optimize_tool_call("Edit", params))
        assert result["success"] is True


class TestOptimizeToolCallGeneral:
    """General tests for optimize_tool_call."""

    def test_invalid_params_json_handled(self):
        result = _parse(optimize_tool_call("Read", "not valid json"))
        assert result["success"] is True  # Falls back to empty params

    def test_unknown_tool_returns_unmodified_params(self):
        params = json.dumps({"key": "value"})
        result = _parse(optimize_tool_call("UnknownTool", params))
        assert result["success"] is True
        # No crash, params passed through
        assert result["original_params"] == {"key": "value"}

    def test_response_always_has_required_keys(self):
        params = json.dumps({"pattern": "hello"})
        result = _parse(optimize_tool_call("Grep", params))
        required = [
            "success", "tool", "original_params", "optimized_params",
            "suggestions", "token_savings_estimate", "was_optimized"
        ]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_glob_broad_pattern_generates_suggestion(self):
        params = json.dumps({"pattern": "**/*"})
        result = _parse(optimize_tool_call("Glob", params))
        assert result["success"] is True
        # Should suggest adding file extension filter
        all_suggestions = " ".join(result["suggestions"]).lower()
        assert "broad" in all_suggestions or "extension" in all_suggestions or \
               "restrict" in all_suggestions

    def test_bash_find_command_suggests_tree_pattern(self):
        params = json.dumps({"command": "find . -type f -name '*.py'"})
        result = _parse(optimize_tool_call("Bash", params))
        assert result["success"] is True
        all_suggestions = " ".join(result["suggestions"]).lower()
        assert "tree" in all_suggestions or "maxdepth" in all_suggestions or \
               "find" in all_suggestions


# =============================================================================
# TOOL 2: ast_navigate_code
# =============================================================================

class TestAstNavigateCode:
    """Tests for ast_navigate_code tool."""

    def test_python_file_parsed_successfully(self, tmp_path):
        py_src = (
            "import os\nfrom pathlib import Path\n\n"
            "class MyClass:\n    def method_a(self):\n        pass\n\n"
            "def top_level_func():\n    return 42\n"
        )
        py_file = tmp_path / "sample.py"
        _make_python_file(py_file, py_src)
        result = _parse(ast_navigate_code(str(py_file)))
        assert result["success"] is True
        assert result["language"] == "python"

    def test_python_classes_detected(self, tmp_path):
        py_src = "class Alpha:\n    pass\n\nclass Beta:\n    pass\n"
        py_file = tmp_path / "classes.py"
        _make_python_file(py_file, py_src)
        result = _parse(ast_navigate_code(str(py_file)))
        assert result["success"] is True
        class_names = [c["name"] for c in result.get("classes", [])]
        assert "Alpha" in class_names
        assert "Beta" in class_names

    def test_python_top_level_functions_detected(self, tmp_path):
        py_src = "def func_a():\n    pass\n\ndef func_b():\n    return 1\n"
        py_file = tmp_path / "funcs.py"
        _make_python_file(py_file, py_src)
        result = _parse(ast_navigate_code(str(py_file)))
        assert result["success"] is True
        func_names = [f["name"] for f in result.get("functions", [])]
        assert "func_a" in func_names
        assert "func_b" in func_names

    def test_python_imports_detected(self, tmp_path):
        py_src = "import os\nimport sys\nfrom pathlib import Path\n\nx = 1\n"
        py_file = tmp_path / "imports.py"
        _make_python_file(py_file, py_src)
        result = _parse(ast_navigate_code(str(py_file)))
        assert result["success"] is True
        imports = result.get("imports", [])
        assert "os" in imports or "sys" in imports or "pathlib" in imports

    def test_python_show_methods_includes_class_methods(self, tmp_path):
        py_src = (
            "class MyClass:\n"
            "    def method_x(self):\n        pass\n"
            "    def method_y(self):\n        return 1\n"
        )
        py_file = tmp_path / "with_methods.py"
        _make_python_file(py_file, py_src)
        result = _parse(ast_navigate_code(str(py_file), show_methods=True))
        assert result["success"] is True
        classes = result.get("classes", [])
        assert len(classes) > 0
        methods = classes[0].get("methods", [])
        assert "method_x" in methods
        assert "method_y" in methods

    def test_python_syntax_error_handled(self, tmp_path):
        bad_src = "def broken_func(\n    # missing closing paren"
        py_file = tmp_path / "broken.py"
        _make_python_file(py_file, bad_src)
        result = _parse(ast_navigate_code(str(py_file)))
        # Should either fail gracefully or return with error in classes/functions
        assert isinstance(result, dict)

    def test_nonexistent_file_returns_error(self, tmp_path):
        result = _parse(ast_navigate_code(str(tmp_path / "ghost.py")))
        assert result["success"] is False
        assert "error" in result

    def test_unsupported_extension_returns_error(self, tmp_path):
        txt_file = tmp_path / "file.txt"
        txt_file.write_text("just some text", encoding="utf-8")
        result = _parse(ast_navigate_code(str(txt_file)))
        assert result["success"] is False
        assert "error" in result

    def test_result_contains_tokens_saved_estimate(self, tmp_path):
        py_src = "x = 1\ny = 2\n"
        py_file = tmp_path / "tiny.py"
        _make_python_file(py_file, py_src)
        result = _parse(ast_navigate_code(str(py_file)))
        assert result["success"] is True
        assert "tokens_saved_estimate" in result
        assert result["tokens_saved_estimate"] >= 0

    def test_result_contains_total_lines(self, tmp_path):
        py_src = "a = 1\nb = 2\nc = 3\n"
        py_file = tmp_path / "count.py"
        _make_python_file(py_file, py_src)
        result = _parse(ast_navigate_code(str(py_file)))
        assert result["success"] is True
        assert "total_lines" in result
        assert result["total_lines"] >= 3


# =============================================================================
# TOOL 3: smart_read_analyze
# =============================================================================

class TestSmartReadAnalyze:
    """Tests for smart_read_analyze tool."""

    def test_small_file_strategy(self, tmp_path):
        small_file = tmp_path / "small.txt"
        _make_text_file(small_file, 50)
        result = _parse(smart_read_analyze(str(small_file)))
        assert result["success"] is True
        assert result["strategy"]["type"] == "small"

    def test_medium_file_strategy(self, tmp_path):
        medium_file = tmp_path / "medium.txt"
        _make_text_file(medium_file, 300)
        result = _parse(smart_read_analyze(str(medium_file)))
        assert result["success"] is True
        assert result["strategy"]["type"] == "medium"

    def test_large_file_strategy(self, tmp_path):
        large_file = tmp_path / "large.txt"
        _make_text_file(large_file, 1000)
        result = _parse(smart_read_analyze(str(large_file)))
        assert result["success"] is True
        assert result["strategy"]["type"] == "large"

    def test_very_large_file_strategy(self, tmp_path):
        very_large_file = tmp_path / "very_large.txt"
        _make_text_file(very_large_file, 2500)
        result = _parse(smart_read_analyze(str(very_large_file)))
        assert result["success"] is True
        assert result["strategy"]["type"] == "very_large"

    def test_nonexistent_file_returns_error(self, tmp_path):
        result = _parse(smart_read_analyze(str(tmp_path / "ghost.txt")))
        assert result["success"] is False
        assert "error" in result

    def test_result_contains_file_metadata(self, tmp_path):
        f = tmp_path / "meta.txt"
        _make_text_file(f, 10)
        result = _parse(smart_read_analyze(str(f)))
        assert result["success"] is True
        assert "size_bytes" in result
        assert "size_kb" in result
        assert "lines" in result
        assert "estimated_tokens" in result

    def test_large_file_strategy_has_offset_and_limit_params(self, tmp_path):
        large_file = tmp_path / "large.txt"
        _make_text_file(large_file, 1000)
        result = _parse(smart_read_analyze(str(large_file)))
        assert result["success"] is True
        params = result["strategy"].get("params", {})
        assert "offset" in params
        assert "limit" in params

    def test_small_file_strategy_params_empty(self, tmp_path):
        small_file = tmp_path / "small.txt"
        _make_text_file(small_file, 20)
        result = _parse(smart_read_analyze(str(small_file)))
        assert result["success"] is True
        # Small file -> no restrictive params needed
        params = result["strategy"].get("params", {})
        assert params == {}

    def test_estimated_tokens_proportional_to_line_count(self, tmp_path):
        f = tmp_path / "proportional.txt"
        _make_text_file(f, 100)
        result = _parse(smart_read_analyze(str(f)))
        assert result["success"] is True
        assert result["estimated_tokens"] == result["lines"] * 80


# =============================================================================
# TOOL 4: deduplicate_context
# =============================================================================

class TestDeduplicateContext:
    """Tests for deduplicate_context tool."""

    def _make_ctx(self, srs="", readme="", claude_md=""):
        return json.dumps({"srs": srs, "readme": readme, "claude_md": claude_md})

    def test_less_than_two_docs_skips_dedup(self):
        ctx = json.dumps({"srs": "some content here"})
        result = _parse(deduplicate_context(ctx))
        assert result["success"] is True
        assert result["dedup_applied"] is False

    def test_no_duplicates_below_threshold_skips(self):
        # Completely different content - no duplication savings
        ctx = self._make_ctx(
            srs="The quick brown fox jumps over the lazy dog.\n",
            readme="All work and no play makes Jack a dull boy.\n",
        )
        result = _parse(deduplicate_context(ctx))
        assert result["success"] is True
        # savings_ratio should be low and dedup skipped
        assert result["savings_ratio"] < 0.20 or result["dedup_applied"] is False

    def test_high_duplication_above_threshold_applies_dedup(self):
        # Both docs have >20% identical content
        shared_lines = "\n".join(f"common line {i}" for i in range(50))
        unique_srs = "\n".join(f"unique srs line {i}" for i in range(5))
        unique_readme = "\n".join(f"unique readme line {i}" for i in range(5))

        ctx = self._make_ctx(
            srs=shared_lines + "\n" + unique_srs,
            readme=shared_lines + "\n" + unique_readme,
        )
        result = _parse(deduplicate_context(ctx))
        assert result["success"] is True
        assert result["dedup_applied"] is True
        assert result["savings_ratio"] >= 0.20

    def test_dedup_applied_returns_deduped_contexts(self):
        shared = "\n".join(f"line {i}" for i in range(100))
        ctx = self._make_ctx(srs=shared, readme=shared)
        result = _parse(deduplicate_context(ctx))
        assert result["success"] is True
        if result["dedup_applied"]:
            assert "deduped_contexts" in result
            assert isinstance(result["deduped_contexts"], dict)

    def test_invalid_json_returns_error(self):
        result = _parse(deduplicate_context("not valid json {{{"))
        assert result["success"] is False
        assert "error" in result

    def test_savings_ratio_between_zero_and_one(self):
        shared = "\n".join(f"shared {i}" for i in range(50))
        ctx = self._make_ctx(srs=shared, readme=shared)
        result = _parse(deduplicate_context(ctx))
        assert result["success"] is True
        assert 0.0 <= result["savings_ratio"] <= 1.0

    def test_original_bytes_tracked(self):
        ctx = self._make_ctx(srs="content A", readme="content B")
        result = _parse(deduplicate_context(ctx))
        assert result["success"] is True
        assert "original_bytes" in result
        assert result["original_bytes"] > 0

    def test_empty_strings_skipped(self):
        ctx = self._make_ctx(srs="", readme="some content here and more")
        result = _parse(deduplicate_context(ctx))
        assert result["success"] is True
        # Only one non-empty doc -> skip
        assert result["dedup_applied"] is False


# =============================================================================
# TOOL 5: dedup_estimate
# =============================================================================

class TestDedupEstimate:
    """Tests for dedup_estimate tool."""

    def _make_ctx(self, srs="", readme="", claude_md=""):
        return json.dumps({"srs": srs, "readme": readme, "claude_md": claude_md})

    def test_less_than_two_docs_returns_zero_ratio(self):
        ctx = json.dumps({"srs": "some content here"})
        result = _parse(dedup_estimate(ctx))
        assert result["success"] is True
        assert result["savings_ratio"] == 0

    def test_identical_docs_high_savings(self):
        repeated = "\n".join(f"line {i}" for i in range(100))
        ctx = self._make_ctx(srs=repeated, readme=repeated)
        result = _parse(dedup_estimate(ctx))
        assert result["success"] is True
        assert result["savings_ratio"] > 0

    def test_unique_docs_low_savings(self):
        ctx = self._make_ctx(
            srs="The quick brown fox.\n",
            readme="All different content here.\n",
        )
        result = _parse(dedup_estimate(ctx))
        assert result["success"] is True
        assert result["savings_ratio"] < 1.0

    def test_would_apply_true_when_above_threshold(self):
        shared = "\n".join(f"line {i}" for i in range(100))
        ctx = self._make_ctx(srs=shared, readme=shared)
        result = _parse(dedup_estimate(ctx))
        assert result["success"] is True
        if result["savings_ratio"] >= 0.20:
            assert result["would_apply"] is True

    def test_would_apply_false_when_below_threshold(self):
        ctx = self._make_ctx(
            srs="unique line one here\n",
            readme="completely different line two\n",
        )
        result = _parse(dedup_estimate(ctx))
        assert result["success"] is True
        if result["savings_ratio"] < 0.20:
            assert result["would_apply"] is False

    def test_invalid_json_returns_error(self):
        result = _parse(dedup_estimate("bad json }{"))
        assert result["success"] is False
        assert "error" in result

    def test_original_bytes_and_estimated_new_bytes_in_response(self):
        ctx = self._make_ctx(srs="aaa bbb ccc", readme="ddd eee fff")
        result = _parse(dedup_estimate(ctx))
        assert result["success"] is True
        assert "original_bytes" in result
        assert "estimated_new_bytes" in result

    def test_savings_pct_formatted_as_string(self):
        ctx = self._make_ctx(srs="line1\nline2\n", readme="line1\nline3\n")
        result = _parse(dedup_estimate(ctx))
        assert result["success"] is True
        assert "savings_pct" in result
        assert "%" in result["savings_pct"]

    def test_estimate_does_not_modify_context(self):
        original_content = "important line\n" * 50
        ctx = self._make_ctx(srs=original_content, readme=original_content)
        # estimate should be read-only
        result = _parse(dedup_estimate(ctx))
        assert result["success"] is True
        # No deduped_contexts key - this is estimation only
        assert "deduped_contexts" not in result


# =============================================================================
# TOOL 6: context_budget_status
# =============================================================================

class TestContextBudgetStatus:
    """Tests for context_budget_status tool."""

    def test_returns_success(self, tmp_path):
        with patch.object(_tok_mod, "MEMORY_PATH", tmp_path):
            result = _parse(context_budget_status())
        assert result["success"] is True

    def test_required_keys_present(self, tmp_path):
        with patch.object(_tok_mod, "MEMORY_PATH", tmp_path):
            result = _parse(context_budget_status())
        required = [
            "total_bytes", "total_kb", "budget_kb",
            "usage_pct", "file_count", "alert", "recommendation"
        ]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_empty_memory_dir_zero_usage(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        with patch.object(_tok_mod, "MEMORY_PATH", memory_dir):
            result = _parse(context_budget_status())
        assert result["success"] is True
        assert result["total_bytes"] == 0
        assert result["file_count"] == 0
        assert result["usage_pct"] == 0.0

    def test_missing_memory_dir_zero_usage(self, tmp_path):
        missing_dir = tmp_path / "no_memory"
        with patch.object(_tok_mod, "MEMORY_PATH", missing_dir):
            result = _parse(context_budget_status())
        assert result["success"] is True
        assert result["total_bytes"] == 0

    def test_alert_false_when_below_85_percent(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        # Write a small file well below 85% of 200KB budget
        (memory_dir / "small.txt").write_text("x" * 100, encoding="utf-8")
        with patch.object(_tok_mod, "MEMORY_PATH", memory_dir):
            result = _parse(context_budget_status())
        assert result["success"] is True
        assert result["alert"] is False

    def test_alert_true_when_at_or_above_85_percent(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        # Write file that exceeds 85% of 200KB (> 170KB)
        large_content = "x" * (175 * 1024)
        (memory_dir / "big.txt").write_text(large_content, encoding="utf-8")
        with patch.object(_tok_mod, "MEMORY_PATH", memory_dir):
            result = _parse(context_budget_status())
        assert result["success"] is True
        assert result["alert"] is True

    def test_budget_kb_matches_constant(self, tmp_path):
        with patch.object(_tok_mod, "MEMORY_PATH", tmp_path):
            result = _parse(context_budget_status())
        assert result["success"] is True
        expected_budget_kb = round(CONTEXT_BUDGET_BYTES / 1024, 2)
        assert result["budget_kb"] == expected_budget_kb

    def test_file_count_matches_actual_files(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        for i in range(3):
            (memory_dir / f"file{i}.txt").write_text("content", encoding="utf-8")
        with patch.object(_tok_mod, "MEMORY_PATH", memory_dir):
            result = _parse(context_budget_status())
        assert result["success"] is True
        assert result["file_count"] == 3

    def test_recommendation_contains_archive_when_alerted(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "huge.txt").write_text("x" * (175 * 1024), encoding="utf-8")
        with patch.object(_tok_mod, "MEMORY_PATH", memory_dir):
            result = _parse(context_budget_status())
        assert result["success"] is True
        if result["alert"]:
            assert "archive" in result["recommendation"].lower() or \
                   "free" in result["recommendation"].lower()

    def test_usage_pct_calculated_correctly(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        # Write exactly 50KB worth of content
        content = "x" * (50 * 1024)
        (memory_dir / "half.txt").write_text(content, encoding="utf-8")
        with patch.object(_tok_mod, "MEMORY_PATH", memory_dir):
            result = _parse(context_budget_status())
        assert result["success"] is True
        # 50KB / 200KB = 25%
        assert 20.0 <= result["usage_pct"] <= 30.0


# =============================================================================
# JSON response consistency
# =============================================================================

class TestJsonResponseFormat:
    """Verify all tools return valid JSON with success key."""

    def test_all_tools_return_valid_json(self, tmp_path):
        py_src = "def hello():\n    pass\n"
        py_file = tmp_path / "sample.py"
        _make_python_file(py_file, py_src)

        small_file = tmp_path / "small.txt"
        _make_text_file(small_file, 10)

        ctx = json.dumps({"srs": "content a", "readme": "content b"})

        with patch.object(_tok_mod, "MEMORY_PATH", tmp_path):
            tools = [
                lambda: optimize_tool_call("Read", json.dumps({"file_path": str(small_file)})),
                lambda: optimize_tool_call("Grep", json.dumps({"pattern": "def"})),
                lambda: ast_navigate_code(str(py_file)),
                lambda: smart_read_analyze(str(small_file)),
                lambda: deduplicate_context(ctx),
                lambda: dedup_estimate(ctx),
                context_budget_status,
            ]
            for fn in tools:
                raw = fn()
                parsed = json.loads(raw)
                assert isinstance(parsed, dict), f"Expected dict, got {type(parsed)}"
                assert "success" in parsed, f"Missing 'success' key in: {parsed}"
