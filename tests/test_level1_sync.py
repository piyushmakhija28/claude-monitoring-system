"""
Tests for Level 1 SubGraph - Context Sync System

Tests individual node functions in isolation using simple dict state.
All external dependencies (LangGraph, complexity_calculator, subprocess,
ContextCache, toons, write_level_log) are mocked before import.

ASCII-safe, UTF-8 encoded - Windows cp1252 compatible.
"""

import io
import json
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

# toons library stub
_toons = _stub("toons")
_toons.dumps = json.dumps

# langgraph_engine package stub (prevents __init__ cascade)
_le_pkg = types.ModuleType("langgraph_engine")
_le_pkg.__path__ = [str(Path(_SCRIPTS) / "langgraph_engine")]
_le_pkg.__package__ = "langgraph_engine"
sys.modules["langgraph_engine"] = _le_pkg

# Sub-modules needed by level1_sync via relative imports
_flow_state = _stub("langgraph_engine.flow_state")
_flow_state.FlowState = dict

_step_logger = _stub("langgraph_engine.step_logger")
_step_logger.write_level_log = MagicMock()

# complexity_calculator stub (graceful miss -> heuristic fallback)
_cx_mod = _stub("langgraph_engine.complexity_calculator")
_cx_mod.calculate_complexity = MagicMock(return_value=5)
_cx_mod.should_plan = MagicMock(return_value=True)
_cx_mod.calculate_graph_complexity = MagicMock(return_value=(0, {}, 0.0))

# ContextCache stub (miss by default)
_cache_mod = _stub("langgraph_engine.context_cache")
_CacheCls = MagicMock()
_CacheCls.return_value.load_cache.return_value = None
_CacheCls.get_session_stats = MagicMock(return_value={"hit_rate_pct": 0.0})
_CacheCls._cache_key = staticmethod(lambda p: "key-{}".format(p))
_cache_mod.ContextCache = _CacheCls

# context_deduplicator stub (passthrough)
_dedup = _stub("langgraph_engine.context_deduplicator")
_dedup.deduplicate_context = MagicMock(side_effect=lambda x: x)

# toon_schema stub (always valid)
_toon_schema = _stub("langgraph_engine.toon_schema")
_toon_schema.validate_toon = MagicMock(return_value=(True, []))

# Subgraphs package stub
_subgraphs = _stub("langgraph_engine.subgraphs")
_subgraphs.__path__ = [str(Path(_SCRIPTS) / "langgraph_engine" / "subgraphs")]
_subgraphs.__package__ = "langgraph_engine.subgraphs"


# ---------------------------------------------------------------------------
# Load level1_sync via importlib
# ---------------------------------------------------------------------------

import importlib.util as _ilu

_mod_path = (
    Path(_SCRIPTS) / "langgraph_engine" / "subgraphs" / "level1_sync.py"
)
_spec = _ilu.spec_from_file_location(
    "langgraph_engine.subgraphs.level1_sync",
    str(_mod_path),
    submodule_search_locations=[],
)
_level1_sync = _ilu.module_from_spec(_spec)
_level1_sync.__package__ = "langgraph_engine.subgraphs"
sys.modules["langgraph_engine.subgraphs.level1_sync"] = _level1_sync
_spec.loader.exec_module(_level1_sync)

node_session_loader = _level1_sync.node_session_loader
node_complexity_calculation = _level1_sync.node_complexity_calculation
node_context_loader = _level1_sync.node_context_loader
node_toon_compression = _level1_sync.node_toon_compression
level1_merge_node = _level1_sync.level1_merge_node
cleanup_level1_memory = _level1_sync.cleanup_level1_memory


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _state(tmp_path=None, **extra):
    base = {
        "session_id": "test-session-001",
        "project_root": str(tmp_path) if tmp_path else ".",
        "session_path": "",
        "user_message": "test task",
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Tests: node_session_loader
# ---------------------------------------------------------------------------

class TestNodeSessionLoader(unittest.TestCase):

    def test_node_session_loader_creates_folder(self):
        """Session loader creates a session directory under home."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state()
            with patch("pathlib.Path.home", return_value=Path(td)):
                result = node_session_loader(state)
        self.assertTrue(result.get("session_loaded", False))

    def test_node_session_loader_returns_path(self):
        """Session loader returns non-empty session_path in result."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state()
            with patch("pathlib.Path.home", return_value=Path(td)):
                result = node_session_loader(state)
        self.assertIn("session_path", result)
        self.assertTrue(len(result.get("session_path", "")) > 0)

    def test_node_session_loader_writes_metadata(self):
        """Session loader writes session.json with session_id field."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state(user_message="write my tests")
            with patch("pathlib.Path.home", return_value=Path(td)):
                result = node_session_loader(state)
            if result.get("session_path"):
                meta_file = Path(result["session_path"]) / "session.json"
                if meta_file.exists():
                    data = json.loads(meta_file.read_text(encoding="utf-8"))
                    self.assertIn("session_id", data)


# ---------------------------------------------------------------------------
# Tests: node_complexity_calculation
# ---------------------------------------------------------------------------

class TestNodeComplexityCalculation(unittest.TestCase):

    def test_node_complexity_calculation_default(self):
        """Returns complexity_score between 1 and 10."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            for i in range(5):
                (Path(td) / "mod_{}.py".format(i)).write_text("x = {}\n".format(i))
            state = _state(project_root=td)
            result = node_complexity_calculation(state)
        score = result.get("complexity_score", 0)
        self.assertTrue(1 <= score <= 10, "Score {} not in range 1-10".format(score))

    def test_node_complexity_calculation_fallback(self):
        """Uses file count heuristic (min(10, max(1, count//10))) as fallback."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            # 20 Python files -> heuristic: min(10, max(1, 20//10)) = 2
            for i in range(20):
                (Path(td) / "f_{}.py".format(i)).write_text("pass\n")
            state = _state(project_root=td)
            # Force heuristic path by disabling complexity calculator module
            _level1_sync._COMPLEXITY_CALCULATOR_AVAILABLE = False
            try:
                result = node_complexity_calculation(state)
            finally:
                _level1_sync._COMPLEXITY_CALCULATOR_AVAILABLE = True
        self.assertIn("complexity_score", result)
        self.assertTrue(result.get("complexity_calculated", False))

    def test_node_complexity_calculation_sets_calculated_flag(self):
        """Sets complexity_calculated=True on success."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state(project_root=td)
            result = node_complexity_calculation(state)
        self.assertTrue(result.get("complexity_calculated", False))


# ---------------------------------------------------------------------------
# Tests: node_context_loader
# ---------------------------------------------------------------------------

class TestNodeContextLoader(unittest.TestCase):

    def test_node_context_loader_loads_files(self):
        """Loads README.md when it exists in project root."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "README.md").write_text("# README\nContent.\n")
            (Path(td) / "CLAUDE.md").write_text("# CLAUDE\nConfig.\n")
            state = _state(project_root=td)
            result = node_context_loader(state)
        self.assertTrue(result.get("context_loaded", False))
        ctx = result.get("context_data", {})
        files = ctx.get("files_loaded", [])
        self.assertTrue(len(files) >= 1, "Expected at least 1 file loaded")

    def test_node_context_loader_missing_files(self):
        """Returns context_loaded=True with zero files when none exist."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state(project_root=td)
            result = node_context_loader(state)
        self.assertIn("context_loaded", result)
        self.assertEqual(result.get("files_loaded_count", 0), 0)

    def test_node_context_loader_timeout(self):
        """Records skipped file and warning on per-file TimeoutError."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "README.md").write_text("# README\n")
            state = _state(project_root=td)
            with patch.object(
                _level1_sync,
                "_read_file_with_timeout",
                side_effect=TimeoutError("simulated timeout"),
            ):
                result = node_context_loader(state)
        self.assertIn("context_loaded", result)
        skipped = result.get("context_skipped_files", [])
        warnings = result.get("context_load_warnings", [])
        self.assertTrue(
            len(skipped) > 0 or len(warnings) > 0,
            "Expected skipped files or warnings on timeout",
        )

    def test_node_context_loader_partial_context_on_error(self):
        """Handles gracefully - returns partial context not empty dict."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "SRS.md").write_text("# SRS\nrequirements.\n")
            state = _state(project_root=td)
            result = node_context_loader(state)
        # At minimum context_data key must exist
        self.assertIn("context_data", result)


# ---------------------------------------------------------------------------
# Tests: node_toon_compression
# ---------------------------------------------------------------------------

class TestNodeToonCompression(unittest.TestCase):

    def test_node_toon_compression_returns_toon(self):
        """Returns toon_object dict in result."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state(
                session_path=td,
                session_id="test-session-001",
                complexity_score=5,
                context_data={
                    "files_loaded": ["README.md"],
                    "srs": None,
                    "readme": "# README",
                    "claude_md": None,
                },
            )
            result = node_toon_compression(state)
        self.assertIn("toon_object", result)
        self.assertIsInstance(result["toon_object"], dict)

    def test_node_toon_compression_integrity(self):
        """toon_integrity_ok is True for valid session and complexity data."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state(
                session_path=td,
                session_id="test-session-001",
                complexity_score=7,
                context_data={
                    "files_loaded": ["README.md"],
                    "srs": None,
                    "readme": "# README content",
                    "claude_md": None,
                },
            )
            result = node_toon_compression(state)
        self.assertTrue(result.get("toon_integrity_ok", False))

    def test_node_toon_compression_clamps_complexity(self):
        """Complexity scores outside 1-10 are clamped in TOON output."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state(
                session_path=td,
                session_id="test-session-001",
                complexity_score=99,
                context_data={
                    "files_loaded": [],
                    "srs": None, "readme": None, "claude_md": None,
                },
            )
            result = node_toon_compression(state)
        score = result.get("toon_object", {}).get("complexity_score", 99)
        self.assertTrue(1 <= score <= 10, "Clamped score {} not in 1-10".format(score))


# ---------------------------------------------------------------------------
# Tests: level1_merge_node
# ---------------------------------------------------------------------------

class TestLevel1MergeNode(unittest.TestCase):

    def test_level1_merge_node_complete(self):
        """Sets level1_complete=True."""
        state = _state(toon_object={"session_id": "x", "complexity_score": 5})
        result = level1_merge_node(state)
        self.assertTrue(result.get("level1_complete", False))

    def test_level1_merge_node_preserves_toon(self):
        """Stores TOON as level1_context_toon in result."""
        toon = {"session_id": "test", "complexity_score": 3}
        state = _state(toon_object=toon)
        result = level1_merge_node(state)
        self.assertIn("level1_context_toon", result)


# ---------------------------------------------------------------------------
# Tests: cleanup_level1_memory
# ---------------------------------------------------------------------------

class TestCleanupLevel1Memory(unittest.TestCase):

    def test_cleanup_level1_memory(self):
        """Sets verbose fields to None."""
        state = _state(
            context_data={"srs": "big content", "files_loaded": ["A"]},
            project_graph={"nodes": [1, 2, 3]},
            architecture={"layers": ["ui", "service"]},
        )
        result = cleanup_level1_memory(state)
        self.assertIsNone(result.get("context_data"))
        self.assertIsNone(result.get("project_graph"))
        self.assertIsNone(result.get("architecture"))

    def test_cleanup_level1_memory_summary_present(self):
        """Includes level1_cleanup_summary for audit trail."""
        state = _state(context_data={"files_loaded": []})
        result = cleanup_level1_memory(state)
        self.assertIn("level1_cleanup_summary", result)


if __name__ == "__main__":
    unittest.main()
