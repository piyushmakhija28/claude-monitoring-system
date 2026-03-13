"""
Level 3 SubGraph v2 - Integrated 14-Step Execution Pipeline

Bridge module that wraps the WORKFLOW.md-compliant level3_execution.py functions
with proper orchestrator integration and logging.

All 14 steps implemented with:
- Proper logging via loguru
- Time tracking
- TOON object handling
- Session management
- LangGraph routing support
"""

import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

try:
    from langgraph.graph import StateGraph, START, END
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from ..flow_state import FlowState
from .level3_execution import (
    step0_task_analysis,
    step1_plan_mode_decision,
    step2_plan_execution,
    step3_task_breakdown_validation,
    step4_toon_refinement,
    step5_skill_agent_selection,
    step6_skill_validation_download,
    step7_final_prompt_generation,
    step8_github_issue_creation,
    step9_branch_creation,
    step10_implementation_execution,
    step11_pull_request_review,
    step12_issue_closure,
    step13_project_documentation_update,
    step14_final_summary_generation,
    route_after_step1_plan_decision,
    route_after_step11_review,
    level3_merge_node,
)


# ============================================================================
# BRIDGE NODE - Map Level 1 fields to Level 3 fields
# ============================================================================


def level3_init_node(state: FlowState) -> Dict[str, Any]:
    """Bridge: Map session_path (from Level 1) to session_dir (used by steps)."""
    session_path = state.get("session_path", "")
    session_id = state.get("session_id", "unknown")

    if not session_path:
        session_path = str(Path.home() / ".claude" / "logs" / "sessions" / session_id)

    return {
        "session_dir": session_path,
        "user_requirement": state.get("user_message", ""),
    }


# ============================================================================
# STEP WRAPPER NODES - Wrap core functions with logging and timing
# ============================================================================


def step0_task_analysis_node(state: FlowState) -> Dict[str, Any]:
    """Step 0: Task Analysis with logging."""
    logger.info("\n🔄 [STEP 0] Task Analysis")
    step_start = time.time()

    try:
        result = step0_task_analysis(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step0_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 0 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 0 failed: {e}")
        return {"step0_error": str(e)}


def step1_plan_mode_decision_node(state: FlowState) -> Dict[str, Any]:
    """Step 1: Plan Mode Decision with logging."""
    logger.info("\n🔄 [STEP 1] Plan Mode Decision")
    step_start = time.time()

    try:
        result = step1_plan_mode_decision(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step1_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 1 completed: plan_required={result.get('step1_plan_required')} ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 1 failed: {e}")
        return {"step1_error": str(e), "step1_plan_required": True}


def step2_plan_execution_node(state: FlowState) -> Dict[str, Any]:
    """Step 2: Plan Execution (conditional on Step 1)."""
    logger.info("\n🔄 [STEP 2] Plan Execution")
    step_start = time.time()

    try:
        result = step2_plan_execution(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step2_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 2 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 2 failed: {e}")
        return {"step2_error": str(e)}


def step3_task_breakdown_node(state: FlowState) -> Dict[str, Any]:
    """Step 3: Task Breakdown Validation."""
    logger.info("\n🔄 [STEP 3] Task Breakdown Validation")
    step_start = time.time()

    try:
        result = step3_task_breakdown_validation(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step3_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 3 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 3 failed: {e}")
        return {"step3_error": str(e)}


def step4_toon_refinement_node(state: FlowState) -> Dict[str, Any]:
    """Step 4: TOON Refinement."""
    logger.info("\n🔄 [STEP 4] TOON Refinement")
    step_start = time.time()

    try:
        result = step4_toon_refinement(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step4_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 4 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 4 failed: {e}")
        return {"step4_error": str(e)}


def step5_skill_selection_node(state: FlowState) -> Dict[str, Any]:
    """Step 5: Skill & Agent Selection."""
    logger.info("\n🔄 [STEP 5] Skill & Agent Selection")
    step_start = time.time()

    try:
        result = step5_skill_agent_selection(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step5_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 5 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 5 failed: {e}")
        return {"step5_error": str(e)}


def step6_skill_validation_node(state: FlowState) -> Dict[str, Any]:
    """Step 6: Skill Validation & Download."""
    logger.info("\n🔄 [STEP 6] Skill Validation & Download")
    step_start = time.time()

    try:
        result = step6_skill_validation_download(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step6_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 6 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 6 failed: {e}")
        return {"step6_error": str(e)}


def step7_final_prompt_node(state: FlowState) -> Dict[str, Any]:
    """Step 7: Final Prompt Generation."""
    logger.info("\n🔄 [STEP 7] Final Prompt Generation")
    step_start = time.time()

    try:
        result = step7_final_prompt_generation(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step7_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 7 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 7 failed: {e}")
        return {"step7_error": str(e)}


def step8_github_issue_node(state: FlowState) -> Dict[str, Any]:
    """Step 8: GitHub Issue Creation."""
    logger.info("\n🔄 [STEP 8] GitHub Issue Creation")
    step_start = time.time()

    try:
        result = step8_github_issue_creation(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step8_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 8 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 8 failed: {e}")
        return {"step8_error": str(e)}


def step9_branch_creation_node(state: FlowState) -> Dict[str, Any]:
    """Step 9: Branch Creation."""
    logger.info("\n🔄 [STEP 9] Branch Creation")
    step_start = time.time()

    try:
        result = step9_branch_creation(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step9_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 9 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 9 failed: {e}")
        return {"step9_error": str(e)}


def step10_implementation_note(state: FlowState) -> Dict[str, Any]:
    """Step 10: Implementation Execution."""
    logger.info("\n🔄 [STEP 10] Implementation Execution")
    step_start = time.time()

    try:
        result = step10_implementation_execution(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step10_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 10 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 10 failed: {e}")
        return {"step10_error": str(e)}


def step11_pull_request_node(state: FlowState) -> Dict[str, Any]:
    """Step 11: Pull Request & Code Review."""
    logger.info("\n🔄 [STEP 11] Pull Request & Code Review")
    step_start = time.time()

    try:
        result = step11_pull_request_review(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step11_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 11 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 11 failed: {e}")
        return {"step11_error": str(e)}


def step12_issue_closure_node(state: FlowState) -> Dict[str, Any]:
    """Step 12: Issue Closure."""
    logger.info("\n🔄 [STEP 12] Issue Closure")
    step_start = time.time()

    try:
        result = step12_issue_closure(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step12_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 12 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 12 failed: {e}")
        return {"step12_error": str(e)}


def step13_docs_update_node(state: FlowState) -> Dict[str, Any]:
    """Step 13: Documentation Update."""
    logger.info("\n🔄 [STEP 13] Documentation Update")
    step_start = time.time()

    try:
        result = step13_project_documentation_update(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step13_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 13 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 13 failed: {e}")
        return {"step13_error": str(e)}


def step14_final_summary_node(state: FlowState) -> Dict[str, Any]:
    """Step 14: Final Summary."""
    logger.info("\n🔄 [STEP 14] Final Summary")
    step_start = time.time()

    try:
        result = step14_final_summary_generation(state)
        execution_time_ms = (time.time() - step_start) * 1000
        result["step14_execution_time_ms"] = execution_time_ms
        logger.info(f"✓ Step 14 completed ({execution_time_ms:.0f}ms)")
        return result
    except Exception as e:
        logger.error(f"Step 14 failed: {e}")
        return {"step14_error": str(e)}


# ============================================================================
# ROUTING FUNCTIONS - Pass-through to core routing logic
# ============================================================================


def route_to_plan_or_breakdown(state: FlowState) -> str:
    """Route after Step 1 plan decision."""
    return route_after_step1_plan_decision(state)


def route_to_closure_or_retry(state: FlowState) -> str:
    """Route after Step 11 PR review."""
    return route_after_step11_review(state)


# ============================================================================
# MERGE NODE - Final status determination
# ============================================================================


# Just re-export the merge node from core
level3_v2_merge_node = level3_merge_node
