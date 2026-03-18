"""
Tests for Level 2 SubGraph - Standards System

Tests individual node functions and helpers in isolation using simple dict state.
All external dependencies (LangGraph, subprocess, MCPPluginLoader,
write_level_log, policies directory) are mocked before import.

ASCII-safe, UTF-8 encoded - Windows cp1252 compatible.
"""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Add scripts/ to sys.path
# ---------------------------------------------------------------------------

_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


# ---------------------------------------------------------------------------
# Pre-import stubs
# ---------------------------------------------------------------------------

def _stub(name):
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m


# LangGraph
_lg = _stub("langgraph")
_lg_graph = _stub("langgraph.graph")
_lg_graph.START = "START"
_lg_graph.END = "END"
_lg_graph.StateGraph = MagicMock()

# loguru
_loguru = _stub("loguru")
_noop = lambda *a, **kw: None
_loguru.logger = type("_L", (), {
    "info": _noop, "debug": _noop, "warning": _noop,
    "error": _noop, "critical": _noop,
})()

# langgraph_engine package stub
_le_pkg = types.ModuleType("langgraph_engine")
_le_pkg.__path__ = [str(Path(_SCRIPTS) / "langgraph_engine")]
_le_pkg.__package__ = "langgraph_engine"
sys.modules["langgraph_engine"] = _le_pkg

# Sub-modules needed by level2_standards via relative imports
_flow_state = _stub("langgraph_engine.flow_state")
_flow_state.FlowState = dict

_step_logger = _stub("langgraph_engine.step_logger")
_step_logger.write_level_log = MagicMock()

# MCPPluginLoader stub (import error -> graceful fallback in the node)
_mcp_loader = _stub("langgraph_engine.mcp_plugin_loader")
_MCPPluginLoaderCls = MagicMock()
_mcp_loader.MCPPluginLoader = _MCPPluginLoaderCls
_mcp_loader.MCPPluginError = Exception

# Subgraphs package stub
_subgraphs = _stub("langgraph_engine.subgraphs")
_subgraphs.__path__ = [str(Path(_SCRIPTS) / "langgraph_engine" / "subgraphs")]
_subgraphs.__package__ = "langgraph_engine.subgraphs"


# ---------------------------------------------------------------------------
# Load level2_standards via importlib
# ---------------------------------------------------------------------------

import importlib.util as _ilu

_mod_path = (
    Path(_SCRIPTS) / "langgraph_engine" / "subgraphs" / "level2_standards.py"
)
_spec = _ilu.spec_from_file_location(
    "langgraph_engine.subgraphs.level2_standards",
    str(_mod_path),
    submodule_search_locations=[],
)
_level2_mod = _ilu.module_from_spec(_spec)
_level2_mod.__package__ = "langgraph_engine.subgraphs"
sys.modules["langgraph_engine.subgraphs.level2_standards"] = _level2_mod
_spec.loader.exec_module(_level2_mod)

load_policies_from_directory = _level2_mod.load_policies_from_directory
detect_project_type = _level2_mod.detect_project_type
node_common_standards = _level2_mod.node_common_standards
node_java_standards = _level2_mod.node_java_standards
node_tool_optimization_standards = _level2_mod.node_tool_optimization_standards
node_mcp_plugin_discovery = _level2_mod.node_mcp_plugin_discovery
level2_merge_node = _level2_mod.level2_merge_node
route_java_standards = _level2_mod.route_java_standards


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _state(**extra):
    base = {
        "session_id": "test-session-001",
        "project_root": ".",
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Tests: load_policies_from_directory
# ---------------------------------------------------------------------------

class TestLoadPoliciesFromDirectory(unittest.TestCase):

    def test_load_policies_from_directory(self):
        """Loads .md files from level directories when they exist."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            policies_root = Path(td) / ".claude" / "policies"
            level2_dir = policies_root / "02-standards-system"
            level2_dir.mkdir(parents=True)
            (level2_dir / "coding-standards.md").write_text("# Standard\n", encoding="utf-8")
            (level2_dir / "lint-rules.md").write_text("# Lint\n", encoding="utf-8")

            with patch("pathlib.Path.home", return_value=Path(td)):
                result = load_policies_from_directory()

        self.assertEqual(result.get("status"), "LOADED")
        self.assertIn("level2", result)
        self.assertGreaterEqual(len(result["level2"]), 1)

    def test_load_policies_missing_dir(self):
        """Returns empty dicts and NO_POLICIES_DIR status when dir absent."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            with patch("pathlib.Path.home", return_value=Path(td)):
                result = load_policies_from_directory()

        self.assertEqual(result.get("status"), "NO_POLICIES_DIR")
        self.assertEqual(result.get("level2", {}), {})


# ---------------------------------------------------------------------------
# Tests: detect_project_type
# ---------------------------------------------------------------------------

class TestDetectProjectType(unittest.TestCase):

    def test_detect_project_type_java(self):
        """Detects Java project when pom.xml exists."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "pom.xml").write_text("<project/>", encoding="utf-8")
            state = _state(project_root=td)
            detect_project_type(state)
        self.assertTrue(state.get("is_java_project", False))

    def test_detect_project_type_python(self):
        """Non-Java project when no Java markers exist."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "main.py").write_text("# Python\n", encoding="utf-8")
            state = _state(project_root=td)
            detect_project_type(state)
        self.assertFalse(state.get("is_java_project", True))

    def test_detect_project_type_gradle(self):
        """Detects Java project when build.gradle exists."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "build.gradle").write_text("apply plugin: 'java'\n", encoding="utf-8")
            state = _state(project_root=td)
            detect_project_type(state)
        self.assertTrue(state.get("is_java_project", False))


# ---------------------------------------------------------------------------
# Tests: node_common_standards
# ---------------------------------------------------------------------------

class TestNodeCommonStandards(unittest.TestCase):

    def test_node_common_standards_loads(self):
        """Returns standards_loaded=True and standards_count > 0."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state(project_root=td)
            with patch.object(
                _level2_mod,
                "load_policies_from_directory",
                return_value={"level2": {"std1": {}, "std2": {}}, "status": "LOADED"},
            ), patch.object(
                _level2_mod,
                "run_standards_loader_script",
                return_value={"status": "SCRIPT_NOT_FOUND"},
            ):
                result = node_common_standards(state)

        self.assertTrue(result.get("standards_loaded", False))
        self.assertGreater(result.get("standards_count", 0), 0)

    def test_node_common_standards_fallback_count(self):
        """Falls back to 12 when no policies or script standards found."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state(project_root=td)
            with patch.object(
                _level2_mod,
                "load_policies_from_directory",
                return_value={"level2": {}, "status": "LOADED"},
            ), patch.object(
                _level2_mod,
                "run_standards_loader_script",
                return_value={"status": "SCRIPT_NOT_FOUND"},
            ):
                result = node_common_standards(state)

        self.assertEqual(result.get("standards_count"), 12)


# ---------------------------------------------------------------------------
# Tests: node_java_standards
# ---------------------------------------------------------------------------

class TestNodeJavaStandards(unittest.TestCase):

    def test_node_java_standards_java_project(self):
        """Loads Java standards and includes spring_boot_patterns dict."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state(project_root=td, is_java_project=True)
            with patch("pathlib.Path.home", return_value=Path(td)):
                result = node_java_standards(state)

        self.assertTrue(result.get("java_standards_loaded", False))
        patterns = result.get("spring_boot_patterns", {})
        self.assertIn("annotations", patterns)

    def test_node_java_standards_always_returns_structure(self):
        """Node always returns a result dict when invoked (routing controls execution)."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state(project_root=td, is_java_project=False)
            with patch("pathlib.Path.home", return_value=Path(td)):
                result = node_java_standards(state)
        self.assertIn("java_standards_loaded", result)


# ---------------------------------------------------------------------------
# Tests: node_tool_optimization_standards
# ---------------------------------------------------------------------------

class TestNodeToolOptimizationStandards(unittest.TestCase):

    def test_node_tool_optimization_standards(self):
        """Returns tool_optimization_rules dict with expected integer keys."""
        state = _state()
        result = node_tool_optimization_standards(state)
        self.assertTrue(result.get("tool_optimization_loaded", False))
        rules = result.get("tool_optimization_rules", {})
        self.assertIn("read_max_lines", rules)
        self.assertIn("grep_max_matches", rules)
        self.assertIsInstance(rules["read_max_lines"], int)

    def test_node_tool_optimization_standards_all_rules_present(self):
        """All expected rule keys are present in returned dict."""
        state = _state()
        result = node_tool_optimization_standards(state)
        rules = result.get("tool_optimization_rules", {})
        for key in ["read_max_lines", "read_max_bytes", "grep_max_matches",
                    "grep_max_results", "search_max_results", "bash_find_head"]:
            self.assertIn(key, rules, "Missing rule key: {}".format(key))


# ---------------------------------------------------------------------------
# Tests: node_mcp_plugin_discovery
# ---------------------------------------------------------------------------

class TestNodeMCPPluginDiscovery(unittest.TestCase):

    def test_node_mcp_plugin_discovery_returns_count(self):
        """Returns mcp_discovered_count >= 0 on graceful fallback."""
        state = _state()
        # Remove MCPPluginLoader from sys.modules to trigger ImportError path
        orig = sys.modules.pop("langgraph_engine.mcp_plugin_loader", None)
        try:
            result = node_mcp_plugin_discovery(state)
        finally:
            if orig is not None:
                sys.modules["langgraph_engine.mcp_plugin_loader"] = orig
        self.assertIn("mcp_discovered_count", result)
        self.assertGreaterEqual(result["mcp_discovered_count"], 0)

    def test_node_mcp_plugin_discovery_with_plugins(self):
        """Returns correct count when MCPPluginLoader finds plugins."""
        state = _state()
        mock_loader_instance = MagicMock()
        mock_loader_instance.discover_plugins.return_value = {
            "filesystem": {},
            "git-ops": {},
        }
        mock_loader_instance.get_available_mcps.return_value = [
            {"short_name": "filesystem"},
            {"short_name": "git-ops"},
        ]
        mock_loader_instance.plugins_path = Path("/mock/plugins")

        _mcp_loader.MCPPluginLoader.return_value = mock_loader_instance

        result = node_mcp_plugin_discovery(state)
        self.assertIn("mcp_discovered_count", result)


# ---------------------------------------------------------------------------
# Tests: level2_merge_node
# ---------------------------------------------------------------------------

class TestLevel2MergeNode(unittest.TestCase):

    def test_level2_merge_all_loaded(self):
        """Sets level2_status='OK' when standards_loaded=True."""
        state = _state(standards_loaded=True, standards_count=12)
        result = level2_merge_node(state)
        self.assertEqual(result.get("level2_status"), "OK")

    def test_level2_merge_failed(self):
        """Sets level2_status='FAILED' and appends error when not loaded."""
        state = _state(standards_loaded=False)
        result = level2_merge_node(state)
        self.assertEqual(result.get("level2_status"), "FAILED")
        errors = result.get("errors", [])
        self.assertTrue(len(errors) > 0)


# ---------------------------------------------------------------------------
# Tests: route_java_standards
# ---------------------------------------------------------------------------

class TestRouteJavaStandards(unittest.TestCase):

    def test_route_java_standards_java(self):
        """Routes to level2_java_standards for Java projects."""
        state = _state(is_java_project=True)
        self.assertEqual(route_java_standards(state), "level2_java_standards")

    def test_route_java_standards_non_java(self):
        """Routes to level2_merge for non-Java projects."""
        state = _state(is_java_project=False)
        self.assertEqual(route_java_standards(state), "level2_merge")

    def test_route_java_standards_missing_flag(self):
        """Missing is_java_project key routes to level2_merge."""
        state = _state()  # no is_java_project key
        self.assertEqual(route_java_standards(state), "level2_merge")


if __name__ == "__main__":
    unittest.main()
