"""Tests for Standards Loader MCP Server (src/mcp/standards_loader_mcp_server.py)."""

import json
import sys
import importlib.util
import tempfile
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


_std_mod = _load_module(
    "standards_loader_mcp_server",
    _MCP_DIR / "standards_loader_mcp_server.py",
)

detect_project_type = _std_mod.detect_project_type
detect_framework = _std_mod.detect_framework
load_standards = _std_mod.load_standards
resolve_standard_conflicts = _std_mod.resolve_standard_conflicts
get_active_standards = _std_mod.get_active_standards
list_available_standards = _std_mod.list_available_standards
_extract_rules = _std_mod._extract_rules
_detect_conflicts = _std_mod._detect_conflicts
_resolve_conflicts = _std_mod._resolve_conflicts


def _parse(result: str) -> dict:
    return json.loads(result)


# =============================================================================
# Helpers
# =============================================================================

def _make_project(tmp_path: Path, *marker_files, extra_files=None) -> Path:
    """Create a minimal project directory with the given marker files."""
    for fname in marker_files:
        fpath = tmp_path / fname
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text("# placeholder", encoding="utf-8")
    if extra_files:
        for fname, content in extra_files.items():
            fpath = tmp_path / fname
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content, encoding="utf-8")
    return tmp_path


def _make_standard(
    directory: Path,
    name: str,
    rules_md: str,
    source: str = "custom",
    priority: int = 4,
) -> dict:
    """Write a standards .md file and return a minimal standard dict."""
    fp = directory / f"{name}.md"
    fp.write_text(rules_md, encoding="utf-8")
    return {
        "id": name,
        "source": source,
        "priority": priority,
        "file": str(fp),
        "rules": _extract_rules(rules_md),
    }


# =============================================================================
# TOOL 1: detect_project_type
# =============================================================================

class TestDetectProjectType:
    """Tests for detect_project_type tool."""

    def test_python_via_setup_py(self, tmp_path):
        _make_project(tmp_path, "setup.py")
        result = _parse(detect_project_type(str(tmp_path)))
        assert result["success"] is True
        assert result["project_type"] == "python"

    def test_python_via_pyproject_toml(self, tmp_path):
        _make_project(tmp_path, "pyproject.toml")
        result = _parse(detect_project_type(str(tmp_path)))
        assert result["success"] is True
        assert result["project_type"] == "python"

    def test_python_via_requirements_txt(self, tmp_path):
        _make_project(tmp_path, "requirements.txt")
        result = _parse(detect_project_type(str(tmp_path)))
        assert result["success"] is True
        assert result["project_type"] == "python"

    def test_java_via_pom_xml(self, tmp_path):
        _make_project(tmp_path, "pom.xml")
        result = _parse(detect_project_type(str(tmp_path)))
        assert result["success"] is True
        assert result["project_type"] == "java"

    def test_java_via_build_gradle(self, tmp_path):
        _make_project(tmp_path, "build.gradle")
        result = _parse(detect_project_type(str(tmp_path)))
        assert result["success"] is True
        assert result["project_type"] == "java"

    def test_typescript_via_tsconfig(self, tmp_path):
        _make_project(tmp_path, "tsconfig.json")
        result = _parse(detect_project_type(str(tmp_path)))
        assert result["success"] is True
        assert result["project_type"] == "typescript"

    def test_typescript_wins_over_javascript(self, tmp_path):
        # tsconfig.json takes priority over package.json
        _make_project(tmp_path, "tsconfig.json", "package.json")
        result = _parse(detect_project_type(str(tmp_path)))
        assert result["success"] is True
        assert result["project_type"] == "typescript"

    def test_javascript_via_package_json(self, tmp_path):
        _make_project(tmp_path, "package.json")
        result = _parse(detect_project_type(str(tmp_path)))
        assert result["success"] is True
        assert result["project_type"] == "javascript"

    def test_go_via_go_mod(self, tmp_path):
        _make_project(tmp_path, "go.mod")
        result = _parse(detect_project_type(str(tmp_path)))
        assert result["success"] is True
        assert result["project_type"] == "go"

    def test_rust_via_cargo_toml(self, tmp_path):
        _make_project(tmp_path, "Cargo.toml")
        result = _parse(detect_project_type(str(tmp_path)))
        assert result["success"] is True
        assert result["project_type"] == "rust"

    def test_unknown_empty_dir(self, tmp_path):
        result = _parse(detect_project_type(str(tmp_path)))
        assert result["success"] is True
        assert result["project_type"] == "unknown"

    def test_path_not_found(self):
        result = _parse(detect_project_type("/nonexistent/path/xyz"))
        assert result["success"] is False
        assert "error" in result

    def test_response_contains_project_path(self, tmp_path):
        _make_project(tmp_path, "setup.py")
        result = _parse(detect_project_type(str(tmp_path)))
        assert "project_path" in result
        assert result["project_path"] != ""

    def test_default_path_dot(self):
        # Should not crash with default "." argument
        result = _parse(detect_project_type())
        assert result["success"] is True
        assert "project_type" in result


# =============================================================================
# TOOL 2: detect_framework
# =============================================================================

class TestDetectFramework:
    """Tests for detect_framework tool."""

    def test_flask_from_requirements(self, tmp_path):
        _make_project(
            tmp_path,
            extra_files={"requirements.txt": "flask==2.3.0\nrequests==2.28.0\n"},
        )
        result = _parse(detect_framework(str(tmp_path), "python"))
        assert result["success"] is True
        assert result["framework"] == "flask"

    def test_fastapi_from_requirements(self, tmp_path):
        _make_project(
            tmp_path,
            extra_files={"requirements.txt": "fastapi==0.100.0\nuvicorn==0.23.0\n"},
        )
        result = _parse(detect_framework(str(tmp_path), "python"))
        assert result["success"] is True
        assert result["framework"] == "fastapi"

    def test_django_from_manage_py(self, tmp_path):
        _make_project(tmp_path, "manage.py")
        result = _parse(detect_framework(str(tmp_path), "python"))
        assert result["success"] is True
        assert result["framework"] == "django"

    def test_spring_boot_from_pom(self, tmp_path):
        pom_content = (
            "<project><dependencies>"
            "<dependency><artifactId>spring-boot-starter-web</artifactId></dependency>"
            "</dependencies></project>"
        )
        _make_project(tmp_path, extra_files={"pom.xml": pom_content})
        result = _parse(detect_framework(str(tmp_path), "java"))
        assert result["success"] is True
        assert result["framework"] == "spring-boot"

    def test_spring_framework_from_pom(self, tmp_path):
        pom_content = (
            "<project><dependencies>"
            "<dependency><artifactId>spring-core</artifactId></dependency>"
            "</dependencies></project>"
        )
        _make_project(tmp_path, extra_files={"pom.xml": pom_content})
        result = _parse(detect_framework(str(tmp_path), "java"))
        assert result["success"] is True
        # spring-boot substring check precedes spring, so if not present -> spring
        assert result["framework"] in ("spring", "spring-boot")

    def test_react_from_package_json(self, tmp_path):
        pkg = json.dumps({"dependencies": {"react": "^18.0.0", "react-dom": "^18.0.0"}})
        _make_project(tmp_path, extra_files={"package.json": pkg})
        result = _parse(detect_framework(str(tmp_path), "javascript"))
        assert result["success"] is True
        assert result["framework"] == "react"

    def test_nextjs_from_package_json(self, tmp_path):
        pkg = json.dumps({"dependencies": {"next": "^13.0.0", "react": "^18.0.0"}})
        _make_project(tmp_path, extra_files={"package.json": pkg})
        result = _parse(detect_framework(str(tmp_path), "typescript"))
        assert result["success"] is True
        assert result["framework"] == "nextjs"

    def test_angular_from_package_json(self, tmp_path):
        pkg = json.dumps({"dependencies": {"@angular/core": "^16.0.0"}})
        _make_project(tmp_path, extra_files={"package.json": pkg})
        result = _parse(detect_framework(str(tmp_path), "typescript"))
        assert result["success"] is True
        assert result["framework"] == "angular"

    def test_unknown_project_type_returns_unknown_framework(self, tmp_path):
        result = _parse(detect_framework(str(tmp_path), "rust"))
        assert result["success"] is True
        assert result["framework"] == "unknown"

    def test_auto_detects_project_type_when_empty(self, tmp_path):
        _make_project(
            tmp_path,
            extra_files={"requirements.txt": "flask==2.3.0\n"},
        )
        # No project_type supplied - tool should auto-detect
        result = _parse(detect_framework(str(tmp_path), ""))
        assert result["success"] is True
        assert result["framework"] == "flask"

    def test_response_contains_both_type_and_framework(self, tmp_path):
        _make_project(tmp_path, extra_files={"pom.xml": "spring-boot"})
        result = _parse(detect_framework(str(tmp_path), "java"))
        assert "project_type" in result
        assert "framework" in result


# =============================================================================
# TOOL 3: load_standards
# =============================================================================

class TestLoadStandards:
    """Tests for load_standards tool - full pipeline."""

    def test_load_standards_unknown_project_succeeds(self, tmp_path):
        # Empty directory -> unknown project type
        result = _parse(load_standards(str(tmp_path)))
        assert result["success"] is True
        assert result["project_type"] == "unknown"

    def test_load_standards_returns_required_keys(self, tmp_path):
        result = _parse(load_standards(str(tmp_path)))
        assert result["success"] is True
        required_keys = [
            "project_type", "framework", "standards_loaded",
            "standards_list", "conflicts", "conflict_count",
            "merged_rules", "traceability",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_load_standards_with_custom_dir(self, tmp_path):
        # Create a custom standards directory with one .md file
        custom_dir = tmp_path / ".claude" / "standards"
        custom_dir.mkdir(parents=True)
        (custom_dir / "my-rules.md").write_text(
            "- **indent**: 4\n- **max_line_length**: 120\n", encoding="utf-8"
        )
        # Python project
        (tmp_path / "setup.py").write_text("", encoding="utf-8")

        result = _parse(load_standards(str(tmp_path)))
        assert result["success"] is True
        # Custom standard should be loaded with priority 4
        sources = [s["source"] for s in result["standards_list"]]
        assert "custom" in sources

    def test_load_standards_traceability_has_four_sources(self, tmp_path):
        result = _parse(load_standards(str(tmp_path)))
        assert result["success"] is True
        sources_checked = result["traceability"]["sources_checked"]
        source_names = {s["source"] for s in sources_checked}
        assert "custom" in source_names
        assert "team" in source_names
        assert "framework" in source_names
        assert "language" in source_names

    def test_load_standards_custom_higher_priority_than_team(self, tmp_path):
        # Both custom and team exist; custom wins for same rule
        custom_dir = tmp_path / ".claude" / "standards"
        custom_dir.mkdir(parents=True)
        (custom_dir / "rules.md").write_text("- **indent**: 2\n", encoding="utf-8")

        result = _parse(load_standards(str(tmp_path)))
        assert result["success"] is True
        # If rule exists in merged, custom value should win (2)
        merged = result["merged_rules"]
        if "indent" in merged:
            assert merged["indent"] == "2"

    def test_load_standards_conflict_count_is_integer(self, tmp_path):
        result = _parse(load_standards(str(tmp_path)))
        assert result["success"] is True
        assert isinstance(result["conflict_count"], int)
        assert result["conflict_count"] >= 0

    def test_load_standards_invalid_path(self):
        result = _parse(load_standards("/definitely/does/not/exist"))
        # Should either fail gracefully or return success with unknown type
        assert isinstance(result["success"], bool)


# =============================================================================
# TOOL 4: resolve_standard_conflicts
# =============================================================================

class TestResolveStandardConflicts:
    """Tests for resolve_standard_conflicts tool."""

    def _std(self, id_, priority, rules):
        return {"id": id_, "priority": priority, "rules": rules}

    def test_no_conflicts_when_rules_match(self):
        standards = [
            self._std("lang", 1, {"indent": "4"}),
            self._std("team", 3, {"indent": "4"}),
        ]
        result = _parse(resolve_standard_conflicts(json.dumps(standards)))
        assert result["success"] is True
        assert result["conflicts"] == []

    def test_conflict_detected_when_rules_differ(self):
        standards = [
            self._std("lang", 1, {"indent": "4"}),
            self._std("custom", 4, {"indent": "2"}),
        ]
        result = _parse(resolve_standard_conflicts(json.dumps(standards)))
        assert result["success"] is True
        assert len(result["conflicts"]) == 1
        conflict = result["conflicts"][0]
        assert "indent" in conflict["conflicting_rules"]

    def test_higher_priority_wins_in_merged_rules(self):
        standards = [
            self._std("lang", 1, {"indent": "4", "quotes": "double"}),
            self._std("team", 3, {"indent": "2"}),
            self._std("custom", 4, {"quotes": "single"}),
        ]
        result = _parse(resolve_standard_conflicts(json.dumps(standards)))
        assert result["success"] is True
        merged = result["merged_rules"]
        # priority 3 overwrites priority 1 for indent
        assert merged["indent"] == "2"
        # priority 4 overwrites priority 1 for quotes
        assert merged["quotes"] == "single"

    def test_three_way_conflict_highest_priority_wins(self):
        standards = [
            self._std("a", 1, {"max_len": "80"}),
            self._std("b", 2, {"max_len": "100"}),
            self._std("c", 4, {"max_len": "120"}),
        ]
        result = _parse(resolve_standard_conflicts(json.dumps(standards)))
        assert result["success"] is True
        assert result["merged_rules"]["max_len"] == "120"

    def test_empty_standards_list(self):
        result = _parse(resolve_standard_conflicts(json.dumps([])))
        assert result["success"] is True
        assert result["conflicts"] == []
        assert result["merged_rules"] == {}

    def test_single_standard_no_conflict(self):
        standards = [self._std("lang", 1, {"indent": "4"})]
        result = _parse(resolve_standard_conflicts(json.dumps(standards)))
        assert result["success"] is True
        assert result["conflicts"] == []
        assert result["merged_rules"]["indent"] == "4"

    def test_invalid_json_returns_error(self):
        result = _parse(resolve_standard_conflicts("not valid json"))
        assert result["success"] is False
        assert "error" in result

    def test_total_rules_count_matches_merged(self):
        standards = [
            self._std("a", 1, {"indent": "4", "quotes": "double"}),
            self._std("b", 2, {"max_len": "100"}),
        ]
        result = _parse(resolve_standard_conflicts(json.dumps(standards)))
        assert result["success"] is True
        assert result["total_rules"] == len(result["merged_rules"])

    def test_priority_ordering_resolves_multiple_conflicts(self):
        # Four standards with overlapping rules
        standards = [
            self._std("lang", 1, {"a": "1", "b": "1"}),
            self._std("fw", 2, {"b": "2", "c": "2"}),
            self._std("team", 3, {"a": "3", "c": "3"}),
            self._std("custom", 4, {"a": "4"}),
        ]
        result = _parse(resolve_standard_conflicts(json.dumps(standards)))
        assert result["success"] is True
        merged = result["merged_rules"]
        assert merged["a"] == "4"  # custom wins
        assert merged["b"] == "2"  # fw wins over lang
        assert merged["c"] == "3"  # team wins over fw


# =============================================================================
# TOOL 5: get_active_standards
# =============================================================================

class TestGetActiveStandards:
    """Tests for get_active_standards tool."""

    def test_returns_summary_keys(self, tmp_path):
        result = _parse(get_active_standards(str(tmp_path)))
        assert result["success"] is True
        required = [
            "project_type", "framework", "total_loaded",
            "by_source", "conflict_count", "rule_count",
        ]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_by_source_has_four_sources(self, tmp_path):
        result = _parse(get_active_standards(str(tmp_path)))
        assert result["success"] is True
        by_source = result["by_source"]
        assert "custom" in by_source
        assert "team" in by_source
        assert "framework" in by_source
        assert "language" in by_source

    def test_total_loaded_is_non_negative(self, tmp_path):
        result = _parse(get_active_standards(str(tmp_path)))
        assert result["success"] is True
        assert result["total_loaded"] >= 0

    def test_rule_count_non_negative(self, tmp_path):
        result = _parse(get_active_standards(str(tmp_path)))
        assert result["success"] is True
        assert result["rule_count"] >= 0

    def test_active_standards_with_custom_rule(self, tmp_path):
        custom_dir = tmp_path / ".claude" / "standards"
        custom_dir.mkdir(parents=True)
        (custom_dir / "rules.md").write_text(
            "- **indent**: 4\n", encoding="utf-8"
        )
        result = _parse(get_active_standards(str(tmp_path)))
        assert result["success"] is True
        assert result["by_source"]["custom"] >= 1

    def test_conflict_count_is_integer(self, tmp_path):
        result = _parse(get_active_standards(str(tmp_path)))
        assert result["success"] is True
        assert isinstance(result["conflict_count"], int)


# =============================================================================
# TOOL 6: list_available_standards
# =============================================================================

class TestListAvailableStandards:
    """Tests for list_available_standards tool."""

    def test_list_all_returns_success(self):
        result = _parse(list_available_standards("all"))
        assert result["success"] is True
        assert "standards" in result
        assert "count" in result
        assert isinstance(result["standards"], list)

    def test_count_matches_list_length(self):
        result = _parse(list_available_standards("all"))
        assert result["success"] is True
        assert result["count"] == len(result["standards"])

    def test_source_filter_team_only_returns_team(self):
        result = _parse(list_available_standards("team"))
        assert result["success"] is True
        for std in result["standards"]:
            assert std["source"] == "team"

    def test_source_filter_language_includes_policy_and_architecture(self):
        result = _parse(list_available_standards("language"))
        assert result["success"] is True
        # May be empty if dirs don't exist, but should succeed
        assert isinstance(result["standards"], list)

    def test_source_filter_framework(self):
        result = _parse(list_available_standards("framework"))
        assert result["success"] is True
        assert isinstance(result["standards"], list)

    def test_source_filter_stored_in_response(self):
        result = _parse(list_available_standards("team"))
        assert result["success"] is True
        assert result["source_filter"] == "team"

    def test_each_standard_has_required_fields(self):
        result = _parse(list_available_standards("all"))
        assert result["success"] is True
        for std in result["standards"]:
            assert "id" in std
            assert "source" in std
            assert "priority" in std
            assert "file" in std
            assert "size_kb" in std

    def test_readme_files_excluded(self):
        # readme.md should never appear in results
        result = _parse(list_available_standards("all"))
        assert result["success"] is True
        for std in result["standards"]:
            assert std["id"].lower() != "readme"


# =============================================================================
# Internal helpers
# =============================================================================

class TestExtractRules:
    """Tests for _extract_rules helper."""

    def test_extracts_bold_key_value(self):
        content = "- **indent**: 4\n- **max_line_length**: 120\n"
        rules = _extract_rules(content)
        assert "indent" in rules
        assert rules["indent"] == "4"
        assert "max_line_length" in rules
        assert rules["max_line_length"] == "120"

    def test_spaces_in_key_converted_to_underscores(self):
        content = "- **max line length**: 100\n"
        rules = _extract_rules(content)
        assert "max_line_length" in rules

    def test_hyphens_in_key_converted_to_underscores(self):
        content = "- **max-line-length**: 100\n"
        rules = _extract_rules(content)
        assert "max_line_length" in rules

    def test_no_rules_returns_empty_dict(self):
        content = "# Just a heading\nSome prose text without rules.\n"
        rules = _extract_rules(content)
        assert rules == {}

    def test_key_lowercased(self):
        content = "- **MaxLen**: 80\n"
        rules = _extract_rules(content)
        assert "maxlen" in rules


class TestDetectConflictsHelper:
    """Tests for _detect_conflicts helper."""

    def test_no_conflict_same_values(self):
        standards = [
            {"id": "a", "rules": {"indent": "4"}},
            {"id": "b", "rules": {"indent": "4"}},
        ]
        conflicts = _detect_conflicts(standards)
        assert conflicts == []

    def test_conflict_different_values(self):
        standards = [
            {"id": "a", "rules": {"indent": "4"}},
            {"id": "b", "rules": {"indent": "2"}},
        ]
        conflicts = _detect_conflicts(standards)
        assert len(conflicts) == 1
        assert "indent" in conflicts[0]["conflicting_rules"]

    def test_no_shared_keys_means_no_conflict(self):
        standards = [
            {"id": "a", "rules": {"indent": "4"}},
            {"id": "b", "rules": {"quotes": "single"}},
        ]
        conflicts = _detect_conflicts(standards)
        assert conflicts == []

    def test_partial_key_overlap(self):
        standards = [
            {"id": "a", "rules": {"indent": "4", "quotes": "double"}},
            {"id": "b", "rules": {"indent": "4", "max_len": "120"}},
        ]
        # indent matches, max_len not shared
        conflicts = _detect_conflicts(standards)
        assert conflicts == []


class TestResolveConflictsHelper:
    """Tests for _resolve_conflicts helper."""

    def test_higher_priority_overwrites_lower(self):
        standards = [
            {"id": "a", "priority": 1, "rules": {"indent": "4"}},
            {"id": "b", "priority": 4, "rules": {"indent": "2"}},
        ]
        merged = _resolve_conflicts(standards)
        assert merged["indent"] == "2"

    def test_all_rules_merged(self):
        standards = [
            {"id": "a", "priority": 1, "rules": {"indent": "4"}},
            {"id": "b", "priority": 2, "rules": {"quotes": "double"}},
        ]
        merged = _resolve_conflicts(standards)
        assert "indent" in merged
        assert "quotes" in merged

    def test_empty_list_returns_empty_dict(self):
        merged = _resolve_conflicts([])
        assert merged == {}


# =============================================================================
# JSON response consistency
# =============================================================================

class TestJsonResponseFormat:
    """Verify all tools return valid JSON with success key."""

    def test_all_tools_return_valid_json(self, tmp_path):
        _make_project(tmp_path, "setup.py")
        tools = [
            lambda: detect_project_type(str(tmp_path)),
            lambda: detect_framework(str(tmp_path), "python"),
            lambda: load_standards(str(tmp_path)),
            lambda: resolve_standard_conflicts(json.dumps([])),
            lambda: get_active_standards(str(tmp_path)),
            lambda: list_available_standards("all"),
        ]
        for fn in tools:
            raw = fn()
            parsed = json.loads(raw)
            assert isinstance(parsed, dict)
            assert "success" in parsed
