# ruff: noqa: F821
"""Level 3 v2 step node wrapper.

Extracted from level3_execution/subgraph.py for modularity.
Windows-safe: ASCII only.

CHANGE LOG (v1.13.0):
  Removed Steps 1, 3, 4 node wrappers -- collapsed into Step 0 template call.
  Step 0 now injects combined_complexity_score (1-25 from Level 1) and
  CallGraph analysis into the template context before the single LLM call.
  Step 0 output populates the fields that Steps 1,3,4,5,6,7 previously provided.
  Step 2 (plan execution) is retained as-is.
"""
import os
from pathlib import Path
from typing import Any, Dict

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

try:
    from ...flow_state import FlowState
except ImportError:
    FlowState = dict  # type: ignore[misc,assignment]

from ..helpers import call_streaming_script


def step0_task_analysis_node(state: FlowState) -> Dict[str, Any]:
    """Step 0 v2: prompt-gen-expert -> orchestrator-agent chain.

    Phase 1: calls prompt-gen-expert-caller (fast, captured stdout) to build
    an orchestration prompt enriched with combined_complexity_score and
    CallGraph risk data.

    Phase 2: calls orchestrator-agent-caller (long-running, stderr streamed
    live) with the orchestration prompt written to a temp file so the user
    sees real-time agent progress.

    Post-call: populates migration fields so Steps 8-14 receive correct data.
    """
    import json as _json
    import tempfile

    DEBUG = os.getenv("CLAUDE_DEBUG") == "1"

    # --- PRE-INJECTION A: combined_complexity_score from Level 1 (1-25 scale) ---
    # Do NOT re-compute; read directly from state. Scale is 1-25, not 1-10.
    complexity_score = state.get("combined_complexity_score", 5)

    # --- PRE-INJECTION B: CallGraph impact analysis ---
    call_graph_risk_level = "LOW"
    call_graph_danger_zones = []
    call_graph_affected_methods = []
    try:
        from ..call_graph_analyzer import analyze_impact_before_change

        project_root = state.get("project_root", ".")
        target_files = state.get("step0_target_files", [])
        task_desc = state.get("user_message", "")
        cg_result = analyze_impact_before_change(project_root, target_files, task_desc)
        if cg_result.get("call_graph_available"):
            call_graph_risk_level = cg_result.get("risk_level", "LOW")
            call_graph_danger_zones = cg_result.get("danger_zones", [])
            call_graph_affected_methods = cg_result.get("affected_methods", [])
            logger.info(
                "[v2] Step 0 CallGraph pre-injection: risk=%s danger_zones=%d affected=%d",
                call_graph_risk_level,
                len(call_graph_danger_zones),
                len(call_graph_affected_methods),
            )
    except Exception as _cg_exc:
        logger.debug("[v2] Step 0 CallGraph pre-injection skipped (fail-open): %s", _cg_exc)

    user_message = state.get("user_message", "") or os.environ.get("CURRENT_USER_MESSAGE", "")

    # --- PHASE 1: prompt-gen-expert-caller ---
    os.environ.setdefault("STEP0_PROMPT_GEN_TIMEOUT", "60")
    prompt_gen_args = [
        user_message,
        "--complexity=%s" % complexity_score,
        "--call-graph-risk=%s" % call_graph_risk_level,
        "--danger-zones=%s" % _json.dumps(call_graph_danger_zones),
        "--affected-methods=%s" % _json.dumps(call_graph_affected_methods),
    ]

    # call_execution_script does not have __func__; use it directly but override timeout via env
    _orig_timeout_env = os.environ.get("STEP0_PROMPT_GEN_TIMEOUT")
    try:
        # Re-import to avoid circular; helpers module already imported at top
        import importlib as _il

        _helpers_mod = _il.import_module("scripts.langgraph_engine.level3_execution.helpers")
        _call_execution_script = _helpers_mod.call_execution_script
    except Exception:
        from ..helpers import call_execution_script as _call_execution_script  # noqa: PLC0415

    prompt_gen_raw = _call_execution_script(
        "prompt-gen-expert-caller",
        prompt_gen_args,
        model_tier="fast",
    )

    orchestration_prompt = prompt_gen_raw.get("orchestration_prompt", "")
    if not orchestration_prompt:
        # Fallback: use user_message directly
        orchestration_prompt = user_message
        logger.warning("[v2] Step 0 prompt-gen-expert returned no orchestration_prompt; using raw task")
    else:
        logger.info("[v2] Step 0 prompt-gen-expert: orchestration_prompt length=%d", len(orchestration_prompt))

    # --- PHASE 2: orchestrator-agent-caller (streaming stderr) ---
    orch_result: Dict[str, Any] = {}
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as _tf:
            _tf.write(orchestration_prompt)
            _prompt_file = _tf.name

        if DEBUG:
            logger.debug("[v2] Step 0 orchestration prompt written to %s", _prompt_file)

        orch_args = [
            "--orchestration-prompt-file=%s" % _prompt_file,
            "--session-dir=%s" % state.get("session_dir", ""),
            "--project-root=%s" % state.get("project_root", "."),
        ]

        orch_result = call_streaming_script("orchestrator-agent-caller", orch_args)

        if not orch_result.get("success", True):
            logger.warning(
                "[v2] Step 0 orchestrator-agent-caller non-success: %s",
                orch_result.get("error", "unknown"),
            )
    except Exception as _orch_exc:
        logger.warning("[v2] Step 0 orchestrator-agent-caller failed (fail-open): %s", _orch_exc)
        orch_result = {"success": False, "error": str(_orch_exc)}
    finally:
        try:
            Path(_prompt_file).unlink(missing_ok=True)
        except Exception:
            pass

    # --- Build result from orchestrator output + migration fields ---
    result = _map_step0_v2_result_to_state(state, orchestration_prompt, orch_result)

    # Store the injected context for observability
    result["step0_call_graph_risk_level"] = call_graph_risk_level
    result["step0_call_graph_danger_zones_count"] = len(call_graph_danger_zones)
    result["step0_call_graph_affected_methods_count"] = len(call_graph_affected_methods)
    result["step0_complexity_injected"] = complexity_score
    result["orchestration_prompt"] = orchestration_prompt
    result["orchestrator_result"] = orch_result

    # Apply call graph complexity boost from orchestration_pre_analysis_node
    # (legacy boost path -- pre_analysis uses 1-10 scale boost on top of step0_complexity)
    try:
        graph_metrics = state.get("call_graph_metrics", {}) or {}
        boost = graph_metrics.get("complexity_boost", 0)
        if boost != 0 and graph_metrics.get("call_graph_available"):
            current = result.get("step0_complexity", 5)
            boosted = max(1, min(10, current + boost))
            if boosted != current:
                result["step0_complexity"] = boosted
                result["step0_complexity_boosted"] = True
                result["step0_complexity_boost_source"] = "call_graph"
                logger.info(
                    "[v2] Step 0 complexity adjusted by call graph: %d -> %d (boost=%+d)",
                    current,
                    boosted,
                    boost,
                )
    except Exception:
        pass  # Boost adjustment is best-effort

    return result


def _map_step0_v2_result_to_state(
    state: FlowState,
    orchestration_prompt: str,
    orch_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Map orchestrator-agent-caller output to FlowState migration fields.

    Populates all fields that Steps 1, 3, 4, 5, 6, 7 previously wrote so that
    Steps 8-14 continue to receive the correct state keys regardless of which
    orchestration path produced the data.

    Args:
        state: Current pipeline state (read-only reference for fallback values).
        orchestration_prompt: The prompt text produced by prompt-gen-expert-caller.
        orch_result: Parsed JSON dict returned by orchestrator-agent-caller.

    Returns:
        A flat dict of state updates ready to merge into FlowState.
    """
    result: Dict[str, Any] = {}

    # Core Step 0 fields
    result["step0_task_type"] = orch_result.get("task_type", "General Task")
    result["step0_complexity"] = orch_result.get("complexity", 5)
    result["step0_reasoning"] = orch_result.get("reasoning", "")
    raw_tasks = orch_result.get("tasks", {})
    result["step0_tasks"] = raw_tasks if isinstance(raw_tasks, dict) else {"count": 1, "tasks": []}
    result["step0_task_count"] = orch_result.get("task_count", 1)
    result["step0_error"] = orch_result.get("error") if not orch_result.get("success", True) else None

    # From Step 1: plan_required decision
    result.setdefault("step1_plan_required", orch_result.get("plan_required", False))

    # From Step 3: validated task list
    if isinstance(raw_tasks, dict):
        task_list = raw_tasks.get("tasks", [])
    else:
        task_list = []
    result.setdefault("step3_tasks_validated", task_list)

    # From Step 4: model selection
    result.setdefault("step4_model", orch_result.get("model_recommendation", "complex_reasoning"))

    # From Step 5: skill and agent selection
    result.setdefault("step5_skill", orch_result.get("selected_skill", ""))
    result.setdefault("step5_agent", orch_result.get("selected_agent", ""))
    result.setdefault("step5_skills", orch_result.get("skills", []))
    result.setdefault("step5_agents", orch_result.get("agents", []))
    result.setdefault("step5_skill_definition", orch_result.get("skill_definition", ""))
    result.setdefault("step5_agent_definition", orch_result.get("agent_definition", ""))

    # From Step 6: skill readiness (always True -- orchestrator already validated)
    result.setdefault("step6_skill_ready", True)
    result.setdefault("step6_agent_ready", True)
    result.setdefault("step6_validation_status", "OK")

    # From Step 7: execution prompt
    execution_prompt = orch_result.get("execution_prompt", "") or orchestration_prompt
    result.setdefault("step7_execution_prompt", execution_prompt)
    result.setdefault("step7_prompt_saved", bool(execution_prompt))

    # Write execution prompt to disk (what Step 7 used to do)
    try:
        session_dir = state.get("session_dir", "")
        if session_dir and execution_prompt:
            sp_file = Path(session_dir) / "system_prompt.txt"
            sp_file.parent.mkdir(parents=True, exist_ok=True)
            sp_file.write_text(execution_prompt, encoding="utf-8")
            result["step7_system_prompt_file"] = str(sp_file)
            result["step7_system_prompt_loaded"] = True
            logger.info("[v2] Step 0 wrote execution prompt to %s", sp_file)
    except Exception as _sp_exc:
        logger.debug("[v2] Step 0 prompt file write skipped: %s", _sp_exc)

    return result


def step2_plan_execution_node(state: FlowState) -> Dict[str, Any]:
    """Step 2: Plan Execution (conditional on Step 1) with full error handling.

    Retained: provides structural plan data consumed by Steps 10 and 11.
    Injects CallGraph impact analysis before planning so the planner
    considers ripple effects of proposed changes.
    """
    # --- CallGraph Impact Analysis (pre-plan) ---
    impact_data = {}
    try:
        from ..call_graph_analyzer import analyze_impact_before_change

        project_root = state.get("project_root", ".")
        target_files = state.get("step0_target_files", [])
        task_desc = state.get("user_message", "")
        impact_data = analyze_impact_before_change(project_root, target_files, task_desc)
        if impact_data.get("call_graph_available"):
            logger.info(
                "[v2] Step 2 CallGraph impact: risk=%s, affected=%d methods",
                impact_data.get("risk_level", "unknown"),
                len(impact_data.get("affected_methods", [])),
            )
    except Exception as e:
        logger.debug("[v2] Step 2 CallGraph analysis skipped: %s", e)

    result = _run_step(
        2,
        "Plan Execution",
        step2_plan_execution,
        state,
        fallback_result={
            "step2_plan_execution": {"error": "Step 2 failed", "phases": []},
            "step2_plan_status": "ERROR",
            "step2_phases": 0,
            "step2_total_estimated_steps": 0,
        },
    )

    # Merge impact analysis into result
    if impact_data.get("call_graph_available"):
        result["step2_impact_analysis"] = impact_data
        result["step2_graph_risk_level"] = impact_data.get("risk_level", "low")
        result["step2_affected_methods"] = [m.get("fqn", "") for m in impact_data.get("affected_methods", [])]

    # --- Plan Validation against CallGraph impact ---
    plan = result.get("step2_plan_execution", {})
    phases = plan.get("phases", [])

    if phases:
        try:
            impact = result.get("step2_impact_analysis", {}) or state.get("step2_impact_analysis", {})
            affected_methods = impact.get("affected_methods", [])
            danger_zones = impact.get("danger_zones", [])

            validation_issues = []

            # Check 1: Do plan phases cover all affected files?
            plan_files = set()
            for phase in phases:
                for task in phase.get("tasks", []):
                    if isinstance(task, dict):
                        plan_files.update(task.get("files", []))

            affected_files = set()
            for m in affected_methods:
                fqn = m.get("fqn", "") if isinstance(m, dict) else str(m)
                if "::" in fqn:
                    affected_files.add(fqn.split("::")[0])

            uncovered = affected_files - plan_files
            if uncovered:
                validation_issues.append(
                    "Plan does not cover %d affected files: %s" % (len(uncovered), ", ".join(sorted(uncovered)[:5]))
                )

            # Check 2: Are danger zone methods addressed in the plan?
            if danger_zones and not any("careful" in str(p).lower() or "test" in str(p).lower() for p in phases):
                validation_issues.append(
                    "%d danger zone methods found but plan has no testing/careful phase" % len(danger_zones)
                )

            result["step2_plan_validated"] = len(validation_issues) == 0
            result["step2_plan_validation_issues"] = validation_issues

            if validation_issues:
                logger.info(
                    "[v2] Step 2 plan validation: %d issues found: %s",
                    len(validation_issues),
                    "; ".join(validation_issues),
                )
            else:
                logger.info("[v2] Step 2 plan validation: PASSED")

        except Exception as e:
            logger.debug("[v2] Step 2 plan validation skipped: %s", e)
            result["step2_plan_validated"] = True  # Default to valid on error
            result["step2_plan_validation_issues"] = []

    # --- User Interaction: High-risk plan confirmation ---
    try:
        from ..user_interaction import generate_step2_questions

        questions = generate_step2_questions({**state, **result})
        if questions:
            result["step2_pending_questions"] = questions
    except Exception as e:
        logger.debug("[v2] Step 2 user interaction skipped: %s", e)

    return result


# REMOVED: step1_plan_mode_decision_node -- collapsed into Step 0 template (v1.13.0)
# REMOVED: step3_task_breakdown_node -- collapsed into Step 0 template (v1.13.0)
# REMOVED: step4_toon_refinement_node -- collapsed into Step 0 template (v1.13.0)
#
# These functions are intentionally absent. Their FlowState outputs are now populated
# by step0_task_analysis_node after the orchestration template LLM call.
# See: impact_map.md Section 2 (FlowState Field Audit) and Section 3 (Step 0 Spec).
