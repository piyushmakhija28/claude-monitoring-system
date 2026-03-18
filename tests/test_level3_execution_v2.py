"""
Tests for Level 3 SubGraph v2 - Execution Pipeline Wrapper

Tests _run_step wrapper, level3_init_node, individual step nodes,
retry logic for step 8, and _build_retry_history_context.

All external dependencies (LangGraph, RAG layer, CheckpointManager,
MetricsCollector, ErrorLogger, level3_execution step functions,
loguru, subprocess) are mocked before import.

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

# langgraph_engine package stub (prevents __init__ cascade)
_le_pkg = types.ModuleType("langgraph_engine")
_le_pkg.__path__ = [str(Path(_SCRIPTS) / "langgraph_engine")]
_le_pkg.__package__ = "langgraph_engine"
sys.modules["langgraph_engine"] = _le_pkg

# flow_state
_flow_state = _stub("langgraph_engine.flow_state")
_flow_state.FlowState = dict

# step_logger
_step_logger = _stub("langgraph_engine.step_logger")
_step_logger.write_level_log = MagicMock()
_step_logger._summarize_result = MagicMock(return_value={})

# rag_integration stub (RAG miss by default)
_rag = _stub("langgraph_engine.rag_integration")
_rag.rag_store_after_node = MagicMock()
_rag.rag_lookup_before_llm = MagicMock(return_value=None)
_rag.get_rag_layer = MagicMock(return_value=None)

# Infrastructure module stubs
_cp_mod = _stub("langgraph_engine.checkpoint_manager")
_cp_mod.CheckpointManager = MagicMock()

_metrics_mod = _stub("langgraph_engine.metrics_collector")
_metrics_mod.MetricsCollector = MagicMock()

_el_mod = _stub("langgraph_engine.error_logger")
_el_mod.ErrorLogger = MagicMock()

_bm_mod = _stub("langgraph_engine.backup_manager")
_bm_mod.BackupManager = MagicMock()

_tw_mod = _stub("langgraph_engine.timeout_wrapper")
_tw_mod.STEP_TIMEOUTS = {}
_tw_mod.StepTimeout = None

_rh_mod = _stub("langgraph_engine.recovery_handler")
_rh_mod.RecoveryHandler = MagicMock()
_rh_mod._register_globals = MagicMock()

# Subgraphs package stub
_subgraphs = _stub("langgraph_engine.subgraphs")
_subgraphs.__path__ = [str(Path(_SCRIPTS) / "langgraph_engine" / "subgraphs")]
_subgraphs.__package__ = "langgraph_engine.subgraphs"

# level3_execution stub - all step functions return empty dicts
_exec_mod = _stub("langgraph_engine.subgraphs.level3_execution")
for _step_fn in [
    "step0_task_analysis", "step1_plan_mode_decision", "step2_plan_execution",
    "step3_task_breakdown_validation", "step4_toon_refinement",
    "step5_skill_agent_selection", "step6_skill_validation_download",
    "step7_final_prompt_generation", "step8_github_issue_creation",
    "step9_branch_creation", "step10_implementation_execution",
    "step11_pull_request_review", "step12_issue_closure",
    "step13_project_documentation_update", "step14_final_summary_generation",
    "route_after_step1_plan_decision", "route_after_step11_review",
    "level3_merge_node",
]:
    setattr(_exec_mod, _step_fn, MagicMock(return_value={}))


# ---------------------------------------------------------------------------
# Load level3_execution_v2 via importlib
# ---------------------------------------------------------------------------

import importlib.util as _ilu

_mod_path = (
    Path(_SCRIPTS) / "langgraph_engine" / "subgraphs" / "level3_execution_v2.py"
)
_spec = _ilu.spec_from_file_location(
    "langgraph_engine.subgraphs.level3_execution_v2",
    str(_mod_path),
    submodule_search_locations=[],
)
_v2_mod = _ilu.module_from_spec(_spec)
_v2_mod.__package__ = "langgraph_engine.subgraphs"
sys.modules["langgraph_engine.subgraphs.level3_execution_v2"] = _v2_mod
_spec.loader.exec_module(_v2_mod)

_run_step = _v2_mod._run_step
_build_retry_history_context = _v2_mod._build_retry_history_context
level3_init_node = _v2_mod.level3_init_node
step0_task_analysis_node = _v2_mod.step0_task_analysis_node
step8_github_issue_node = _v2_mod.step8_github_issue_node
_infra_cache = _v2_mod._infra_cache


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _state(**extra):
    base = {
        "session_id": "test-session-v2-001",
        "session_path": "",
        "session_dir": "",
        "user_message": "implement login feature",
        "project_root": ".",
    }
    base.update(extra)
    return base


def _clear_infra_cache():
    _infra_cache.clear()


# ---------------------------------------------------------------------------
# Tests: _run_step wrapper
# ---------------------------------------------------------------------------

class TestRunStep(unittest.TestCase):

    def setUp(self):
        _clear_infra_cache()
        _rag.rag_lookup_before_llm.return_value = None

    def test_run_step_success(self):
        """Returns step result dict on successful execution."""
        def _ok_step(state):
            return {"step99_done": True}

        result = _run_step(99, "Test Step", _ok_step, _state())
        self.assertTrue(result.get("step99_done", False))

    def test_run_step_with_fallback(self):
        """Returns fallback_result when step_fn raises an exception."""
        def _failing_step(state):
            raise RuntimeError("simulated failure")

        fallback = {"step99_error": "fallback_value"}
        result = _run_step(99, "Test Step", _failing_step, _state(), fallback_result=fallback)
        self.assertIn("step99_error", result)

    def test_run_step_timeout(self):
        """Returns fallback when StepTimeout.run returns timed_out=True."""
        mock_timeout_cls = MagicMock()
        mock_timeout_cls.return_value.run.return_value = {
            "timed_out": True,
            "step99_error": "timeout",
        }

        with patch.object(
            _v2_mod, "_get_timeout_wrapper",
            return_value=({99: 1}, mock_timeout_cls),
        ):
            result = _run_step(
                99, "Test Step",
                lambda st: {"step99_result": True},
                _state(),
                fallback_result={},
            )
        self.assertIn("step99_error", result)

    def test_run_step_rag_hit(self):
        """Returns RAG cached result when rag_hit=True."""
        _rag.rag_lookup_before_llm.return_value = {
            "rag_hit": True,
            "decision": {"step0_task_type": "BugFix", "step0_complexity": 3},
            "confidence": 0.95,
        }

        called = []

        def _step(st):
            called.append(True)
            return {"step0_task_type": "NewFeature"}

        result = _run_step(0, "Task Analysis", _step, _state())
        # RAG cached value should be returned
        self.assertEqual(result.get("step0_task_type"), "BugFix")
        self.assertFalse(called, "Step fn should NOT be called on RAG hit")

    def test_run_step_rag_miss(self):
        """Falls through to step function on RAG miss."""
        _rag.rag_lookup_before_llm.return_value = None
        called = []

        def _step(st):
            called.append(True)
            return {"step0_task_type": "NewFeature"}

        result = _run_step(0, "Task Analysis", _step, _state())
        self.assertTrue(called, "Step fn SHOULD be called on RAG miss")
        self.assertEqual(result.get("step0_task_type"), "NewFeature")

    def test_run_step_checkpoint_saved(self):
        """Checkpoint is saved after a successful step."""
        mock_cp = MagicMock()

        def _step(st):
            return {"step99_done": True}

        with patch.object(_v2_mod, "_get_checkpoint_manager", return_value=mock_cp):
            _clear_infra_cache()
            _run_step(99, "Test Step", _step, _state())

        mock_cp.save_checkpoint.assert_called()

    def test_run_step_metrics_recorded(self):
        """Metrics recorded for each step execution."""
        mock_metrics = MagicMock()

        def _step(st):
            return {"step99_done": True}

        with patch.object(_v2_mod, "_get_metrics_collector", return_value=mock_metrics):
            _clear_infra_cache()
            _run_step(99, "Test Step", _step, _state())

        mock_metrics.record_step.assert_called()


# ---------------------------------------------------------------------------
# Tests: level3_init_node
# ---------------------------------------------------------------------------

class TestLevel3InitNode(unittest.TestCase):

    def setUp(self):
        _clear_infra_cache()

    def test_level3_init_node(self):
        """Maps session_path to session_dir."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state = _state(session_path=td, session_id="test-session-v2-001")
            result = level3_init_node(state)
        self.assertIn("session_dir", result)
        self.assertEqual(result["session_dir"], td)

    def test_level3_init_node_user_requirement(self):
        """Sets user_requirement from user_message."""
        state = _state(session_path=".", user_message="implement payment gateway")
        result = level3_init_node(state)
        self.assertEqual(result.get("user_requirement"), "implement payment gateway")

    def test_level3_init_node_empty_session_path(self):
        """Constructs session_dir from session_id when session_path is empty."""
        state = _state(session_path="", session_id="test-session-v2-001")
        with patch("pathlib.Path.mkdir", MagicMock()):
            result = level3_init_node(state)
        self.assertIn("session_dir", result)
        self.assertIn("test-session-v2-001", result["session_dir"])


# ---------------------------------------------------------------------------
# Tests: step0_task_analysis_node
# ---------------------------------------------------------------------------

class TestStep0TaskAnalysisNode(unittest.TestCase):

    def setUp(self):
        _clear_infra_cache()
        _rag.rag_lookup_before_llm.return_value = None

    def test_step0_node_returns_task_analysis(self):
        """Returns step0_task_type and step0_complexity on success."""
        _exec_mod.step0_task_analysis.return_value = {
            "step0_task_type": "BugFix",
            "step0_complexity": 4,
            "step0_reasoning": "Small isolated fix",
            "step0_tasks": {"count": 1, "tasks": []},
            "step0_task_count": 1,
        }
        result = step0_task_analysis_node(_state())
        self.assertIn("step0_task_type", result)
        self.assertIn("step0_complexity", result)

    def test_step0_node_fallback(self):
        """Returns default complexity=5 when step0 raises exception."""
        _exec_mod.step0_task_analysis.side_effect = RuntimeError("LLM down")
        result = step0_task_analysis_node(_state())
        self.assertEqual(result.get("step0_complexity"), 5)
        _exec_mod.step0_task_analysis.side_effect = None


# ---------------------------------------------------------------------------
# Tests: step8_github_issue_node - network retry
# ---------------------------------------------------------------------------

class TestStep8NetworkRetry(unittest.TestCase):

    def setUp(self):
        _clear_infra_cache()
        _rag.rag_lookup_before_llm.return_value = None
        _exec_mod.step8_github_issue_creation.side_effect = None

    def tearDown(self):
        _exec_mod.step8_github_issue_creation.side_effect = None

    def test_step8_network_retry(self):
        """Step 8 returns fallback after retrying RequestException 3 times."""
        try:
            import requests
        except ImportError:
            self.skipTest("requests not installed")

        _exec_mod.step8_github_issue_creation.side_effect = (
            requests.RequestException("connection refused")
        )

        with patch("time.sleep", MagicMock()):
            result = step8_github_issue_node(_state())

        self.assertFalse(result.get("step8_issue_created", True))

    def test_step8_no_retry_on_non_network_error(self):
        """Non-network exceptions in step 8 are not retried."""
        try:
            import requests
        except ImportError:
            self.skipTest("requests not installed")

        _exec_mod.step8_github_issue_creation.side_effect = ValueError("bad token")

        result = step8_github_issue_node(_state())
        # Fallback ensures step8_issue_created is present
        self.assertIn("step8_issue_created", result)


# ---------------------------------------------------------------------------
# Tests: _build_retry_history_context
# ---------------------------------------------------------------------------

class TestBuildRetryHistoryContext(unittest.TestCase):

    def test_build_retry_history_context_first_attempt(self):
        """Returns empty string on first attempt (retry_count=0)."""
        result = _build_retry_history_context(_state(step11_retry_count=0))
        self.assertEqual(result, "")

    def test_build_retry_history_context_on_retry(self):
        """Returns formatted string with history sections on retry."""
        state = _state(
            step11_retry_count=1,
            step11_retry_messages=["Fixed null pointer in UserService"],
            step11_review_issues=["Missing test coverage", "Unused import"],
        )
        result = _build_retry_history_context(state)
        self.assertIn("RETRY HISTORY", result)
        self.assertIn("CURRENT ISSUES", result)
        self.assertIn("Fixed null pointer", result)

    def test_build_retry_history_context_final_attempt(self):
        """Shows FINAL ATTEMPT warning when no retries remain."""
        state = _state(
            step11_retry_count=3,
            step11_retry_messages=["Attempt 1", "Attempt 2", "Attempt 3"],
            step11_review_issues=["Still broken"],
        )
        result = _build_retry_history_context(state)
        self.assertIn("FINAL ATTEMPT", result)

    def test_build_retry_history_context_truncates_issues(self):
        """Truncates review_issues list to first 10 items."""
        state = _state(
            step11_retry_count=1,
            step11_retry_messages=["Fix 1"],
            step11_review_issues=["issue-{}".format(i) for i in range(15)],
        )
        result = _build_retry_history_context(state)
        self.assertIn("and 5 more", result)


if __name__ == "__main__":
    unittest.main()
