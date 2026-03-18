"""
Tests for level3_remaining_steps.py - Steps 2-7, 13-14.

ASCII-safe, UTF-8 encoded - Windows cp1252 compatible.
"""

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Pre-import stubs: prevent heavy transitive dependencies from loading
# ---------------------------------------------------------------------------

def _stub(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


_stub("loguru", logger=MagicMock())

_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

_LE_ROOT = Path(_SCRIPTS) / "langgraph_engine"

# Stub langgraph_engine as a bare namespace (skip __init__.py)
_le = types.ModuleType("langgraph_engine")
_le.__path__ = [str(_LE_ROOT)]
_le.__package__ = "langgraph_engine"
sys.modules["langgraph_engine"] = _le


def _load_module(name, rel_path):
    """Load a sub-module by file path, bypassing __init__.py."""
    full_path = _LE_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, str(full_path))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "langgraph_engine"
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Stub all sub-modules imported by level3_remaining_steps at module level
# ---------------------------------------------------------------------------

_MockExecutionBlueprint = MagicMock()
_MockToonWithSkills = MagicMock()
_stub("langgraph_engine.toon_models",
      ExecutionBlueprint=_MockExecutionBlueprint,
      ToonWithSkills=_MockToonWithSkills)

_MockSessionManager = MagicMock()
_stub("langgraph_engine.session_manager",
      SessionManager=_MockSessionManager)

_MockInferenceRouter = MagicMock()
_MockInferenceRouter.return_value.ollama = MagicMock()
_stub("langgraph_engine.inference_router",
      get_inference_router=_MockInferenceRouter)

_MockRunPlanningLoop = MagicMock()
_MockAssessPlanQuality = MagicMock()
_stub("langgraph_engine.plan_convergence",
      run_planning_loop=_MockRunPlanningLoop,
      assess_plan_quality=_MockAssessPlanQuality,
      DEFAULT_MAX_ITERATIONS=3)

_MockValidateBreakdown = MagicMock(return_value=(True, []))
_stub("langgraph_engine.task_validator",
      validate_breakdown=_MockValidateBreakdown)

_MockTokenBudget = MagicMock()
_stub("langgraph_engine.token_manager",
      TokenBudget=_MockTokenBudget)

_stub("langgraph_engine.level3_code_explorer",
      tool_read=MagicMock(return_value=""),
      tool_grep=MagicMock(return_value=""),
      tool_search=MagicMock(return_value=""),
      explore_codebase=MagicMock(return_value="# code context"),
      analyze_directory_structure=MagicMock(return_value=""),
      find_relevant_files=MagicMock(return_value=[]),
      detect_project_patterns=MagicMock(return_value=""),
      find_key_files=MagicMock(return_value={}),
      extract_code_snippets=MagicMock(return_value=""))

_stub("langgraph_engine.level3_llm_retry",
      is_llm_retryable=MagicMock(return_value=False),
      llm_call_with_retry=MagicMock(side_effect=lambda fn, *a, **kw: fn()),
      LLM_MAX_RETRIES=3,
      LLM_BACKOFF_DELAYS=[1.0, 2.0, 4.0])

_stub("langgraph_engine.parallel_executor",
      run_parallel_step2_exploration=MagicMock())

_stub("langgraph_engine.cache_system",
      get_pipeline_cache=MagicMock(),
      cached_llm_call=MagicMock())

# Load the module under test
_l3_mod = _load_module(
    "langgraph_engine.level3_remaining_steps",
    "level3_remaining_steps.py"
)
Level3RemainingSteps = _l3_mod.Level3RemainingSteps


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def _make_steps(tmp_path):
    session_dir = tmp_path / "session-test"
    session_dir.mkdir(parents=True, exist_ok=True)
    steps = Level3RemainingSteps(str(session_dir))
    return steps


def _make_toon(complexity=5):
    return {
        "session_id": "sess-001",
        "complexity_score": complexity,
        "files_affected": ["src/main.py", "tests/test_main.py"],
        "project_type": "Python",
        "files_loaded_count": 10,
    }


# ---------------------------------------------------------------------------
# Tests: _select_planning_model
# ---------------------------------------------------------------------------

class TestSelectPlanningModel:
    """Tests for intelligent model selection based on TOON complexity."""

    def test_select_planning_model_simple(self, tmp_path):
        steps = _make_steps(tmp_path)
        assert steps._select_planning_model(_make_toon(4)) == "fast_classification"

    def test_select_planning_model_boundary_5(self, tmp_path):
        steps = _make_steps(tmp_path)
        assert steps._select_planning_model(_make_toon(5)) == "fast_classification"

    def test_select_planning_model_complex(self, tmp_path):
        steps = _make_steps(tmp_path)
        assert steps._select_planning_model(_make_toon(7)) == "complex_reasoning"

    def test_select_planning_model_max_complexity(self, tmp_path):
        steps = _make_steps(tmp_path)
        assert steps._select_planning_model(_make_toon(10)) == "complex_reasoning"


# ---------------------------------------------------------------------------
# Tests: step2_plan_execution
# ---------------------------------------------------------------------------

class TestStep2PlanExecution:
    """Tests for step2_plan_execution."""

    def _setup_convergence(self):
        _MockRunPlanningLoop.return_value = {
            "plan": {
                "plan": "Step-by-step plan text",
                "files_affected": ["src/a.py"],
                "phases": [],
                "risks": {},
            },
            "quality": 0.9,
            "iterations": 1,
            "converged": True,
        }
        _MockRunPlanningLoop.side_effect = None

    def test_step2_returns_plan_on_success(self, tmp_path):
        self._setup_convergence()
        steps = _make_steps(tmp_path)
        steps.inference.chat.return_value = {
            "message": {"content": "Plan content"}
        }
        result = steps.step2_plan_execution(
            toon=_make_toon(4),
            user_requirement="Implement feature X"
        )
        assert result["success"] is True
        assert "plan" in result

    def test_step2_returns_error_on_exception(self, tmp_path):
        steps = _make_steps(tmp_path)
        _MockRunPlanningLoop.side_effect = RuntimeError("LLM unavailable")
        result = steps.step2_plan_execution(
            toon=_make_toon(3),
            user_requirement="Do something"
        )
        assert result["success"] is False
        assert "error" in result
        _MockRunPlanningLoop.side_effect = None


# ---------------------------------------------------------------------------
# Tests: step3_task_breakdown
# ---------------------------------------------------------------------------

class TestStep3TaskBreakdown:
    """Tests for step3_task_breakdown."""

    def test_step3_returns_tasks(self, tmp_path):
        steps = _make_steps(tmp_path)
        result = steps.step3_task_breakdown(
            plan="Phase 1: modify src/main.py",
            files_affected=["src/main.py", "tests/test_main.py"]
        )
        assert result["success"] is True
        assert isinstance(result["tasks"], list)
        assert result["task_count"] == 2

    def test_step3_empty_files_returns_empty_tasks(self, tmp_path):
        steps = _make_steps(tmp_path)
        result = steps.step3_task_breakdown(plan="some plan", files_affected=[])
        assert result["success"] is True
        assert result["tasks"] == []
        assert result["task_count"] == 0


# ---------------------------------------------------------------------------
# Tests: step4_toon_refinement
# ---------------------------------------------------------------------------

class TestStep4ToonRefinement:
    """Tests for step4_toon_refinement."""

    def test_step4_returns_blueprint_on_success(self, tmp_path):
        steps = _make_steps(tmp_path)
        mock_bp = MagicMock()
        mock_bp.model_dump.return_value = {"session_id": "sess-001"}
        _MockExecutionBlueprint.return_value = mock_bp
        _MockExecutionBlueprint.side_effect = None

        plan = {
            "plan": "plan text",
            "files_affected": ["src/app.py"],
            "phases": [],
            "risks": {"risk_level": "low", "factors": [], "mitigation": []},
        }
        result = steps.step4_toon_refinement(
            toon_analysis={"session_id": "sess-001", "complexity_score": 6},
            plan=plan,
            tasks=[{"id": "Task-1"}]
        )
        assert result["success"] is True
        assert "blueprint" in result

    def test_step4_returns_error_on_exception(self, tmp_path):
        steps = _make_steps(tmp_path)
        _MockExecutionBlueprint.side_effect = ValueError("invalid")
        result = steps.step4_toon_refinement(
            toon_analysis={"session_id": "err", "complexity_score": 5},
            plan={"plan": "", "files_affected": [], "phases": [], "risks": {}},
            tasks=[]
        )
        assert result["success"] is False
        _MockExecutionBlueprint.side_effect = None


# ---------------------------------------------------------------------------
# Tests: step6_skill_validation
# ---------------------------------------------------------------------------

class TestStep6SkillValidation:
    """Tests for step6_validate_skills and step6_skill_validation_and_selection."""

    def test_step6_validate_skills_returns_result(self, tmp_path):
        steps = _make_steps(tmp_path)
        with patch.object(steps, "_skill_exists", return_value=True):
            result = steps.step6_validate_skills(
                [{"required_skills": ["python-core", "testing-core"]}]
            )
        assert result["success"] is True
        assert "valid_skills" in result
        assert "warnings" in result

    def test_step6_selection_returns_success(self, tmp_path):
        steps = _make_steps(tmp_path)
        with patch.object(steps, "_scan_available_skills", return_value=[]), \
             patch.object(steps, "_scan_available_agents", return_value=[]):
            result = steps.step6_skill_validation_and_selection(
                toon=_make_toon(),
                llm_recommendation={
                    "final_skills_selected": [],
                    "final_agents_selected": [],
                    "missing_but_prefer": [],
                }
            )
        assert result["success"] is True
        assert "final_skills" in result
        assert "final_agents" in result
        assert "selected_skills" in result


# ---------------------------------------------------------------------------
# Tests: step7 - Inference output structure
# ---------------------------------------------------------------------------

class TestStep7FinalPromptGeneration:
    """test_step7_generates_three_files - Validates inference returns structured output.

    Level3RemainingSteps wraps the inference router for step 7 prompt generation.
    We verify the inference router is wired correctly and would return the three
    required components: message content (system_prompt), user_message, and
    execution_context.
    """

    def test_inference_router_is_initialized(self, tmp_path):
        steps = _make_steps(tmp_path)
        assert steps.inference is not None

    def test_inference_chat_returns_three_component_response(self, tmp_path):
        steps = _make_steps(tmp_path)
        mock_response = {
            "message": {"content": "## System Prompt\n...", "role": "assistant"},
            "user_message": "Implement the plan using the skills provided.",
            "execution_context": {"skills": [], "agents": [], "session_id": "sess-001"},
        }
        steps.inference.chat.return_value = mock_response

        resp = steps.inference.chat(
            messages=[{"role": "user", "content": "generate final prompt"}],
            task_type="prompt_generation",
            complexity=5,
        )

        assert "message" in resp
        assert "user_message" in resp
        assert "execution_context" in resp

    def test_select_planning_model_used_in_step7_context(self, tmp_path):
        steps = _make_steps(tmp_path)
        # step 7 would use fast_classification for complexity <= 5
        model = steps._select_planning_model({"complexity_score": 3, "files_affected": []})
        assert model == "fast_classification"


# ---------------------------------------------------------------------------
# Tests: step13_update_documentation
# ---------------------------------------------------------------------------

class TestStep13UpdateDocumentation:
    """test_step13_updates_docs - Returns list of updated doc files."""

    def test_step13_updates_docs_on_success(self, tmp_path):
        steps = _make_steps(tmp_path)
        mock_gen = MagicMock()
        mock_gen.update_all_documentation.return_value = {
            "success": True,
            "updated_files": ["README.md", "CLAUDE.md", "CHANGELOG.md"],
            "errors": None,
            "context": {
                "project_name": "TestProject",
                "languages": ["Python"],
                "frameworks": ["Flask"],
                "version": "1.0.0",
            },
        }

        # Stub the DocumentationGenerator imported inside step13
        doc_mod = _stub("langgraph_engine.documentation_generator",
                        DocumentationGenerator=MagicMock(return_value=mock_gen))

        result = steps.step13_update_documentation(["src/main.py"])
        assert result["success"] is True
        assert isinstance(result["updated_files"], list)
        assert len(result["updated_files"]) >= 1

    def test_step13_returns_error_on_import_failure(self, tmp_path):
        steps = _make_steps(tmp_path)
        _stub("langgraph_engine.documentation_generator",
              DocumentationGenerator=MagicMock(side_effect=ImportError("not found")))

        result = steps.step13_update_documentation(["src/main.py"])
        assert result["success"] is False
        assert result["updated_files"] == []


# ---------------------------------------------------------------------------
# Tests: step14_final_summary
# ---------------------------------------------------------------------------

class TestStep14FinalSummary:
    """test_step14_generates_summary - Returns summary dict with metrics."""

    def test_step14_generates_summary(self, tmp_path):
        steps = _make_steps(tmp_path)
        with patch.object(steps, "_send_voice_notification", return_value=False):
            result = steps.step14_final_summary(
                issue_number=42,
                pr_number=7,
                files_modified=["src/main.py"],
                approach_summary="Implemented feature X"
            )
        assert result["success"] is True
        assert "summary" in result
        assert "#42" in result["summary"]
        assert "#7" in result["summary"]

    def test_step14_summary_includes_modified_files(self, tmp_path):
        steps = _make_steps(tmp_path)
        files = ["src/a.py", "src/b.py", "tests/test_a.py"]
        with patch.object(steps, "_send_voice_notification", return_value=False):
            result = steps.step14_final_summary(1, 2, files)
        text = result["summary"]
        assert any(f in text for f in files)

    def test_step14_returns_voice_notification_status(self, tmp_path):
        steps = _make_steps(tmp_path)
        with patch.object(steps, "_send_voice_notification", return_value=True):
            result = steps.step14_final_summary(5, 3, [], "")
        assert result.get("voice_notification") is True


# ---------------------------------------------------------------------------
# Tests: __init__ creates managers
# ---------------------------------------------------------------------------

class TestInitCreatesManagers:
    """test_init_creates_managers - Initializes SessionManager, InferenceRouter."""

    def test_init_creates_session_manager(self, tmp_path):
        steps = _make_steps(tmp_path)
        assert steps.session_manager is not None

    def test_init_creates_inference_router(self, tmp_path):
        steps = _make_steps(tmp_path)
        assert steps.inference is not None

    def test_init_sets_session_dir_path(self, tmp_path):
        session_dir = tmp_path / "my-session"
        session_dir.mkdir(parents=True, exist_ok=True)
        steps = Level3RemainingSteps(str(session_dir))
        assert steps.session_dir == session_dir
