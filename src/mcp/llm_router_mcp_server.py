"""
LLM Router MCP Server - Intelligent routing without direct LLM invocation.

Replaces the routing and orchestration logic that was embedded in llm_mcp_server.py.
This server NEVER calls an LLM directly; it only returns routing decisions so the
caller can invoke the correct provider server.

Routing logic:
  complexity 1-3 or classification steps  -> try Ollama first
  complexity 4-6 or lightweight steps     -> try Ollama, fallback Anthropic
  complexity 7-10 or complex steps        -> Anthropic directly

Backend: config lookup only (no network calls, no SDK deps)
Transport: stdio

Tools (4):
  llm_route_request, llm_classify_step, llm_select_model, llm_git_commit_title
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# Ensure src/mcp/ is in path for base package imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP
from base.response import to_json
from base.decorators import mcp_tool_handler

mcp = FastMCP(
    "llm-router",
    instructions=(
        "Intelligent LLM routing - selects best provider based on task, "
        "complexity, and availability"
    ),
)

# ---------------------------------------------------------------------------
# Step classification table (copied from llm_mcp_server.py)
# ---------------------------------------------------------------------------

_STEP_CLASSIFICATION = {
    "step0_prompt_generation":   "complex_reasoning",
    "step1_plan_mode_decision":  "classification",
    "step2_plan_execution":      "complex_reasoning",
    "step3_task_analysis":       "lightweight_analysis",
    "step4_model_selection":     "complex_reasoning",
    "step5_skill_selection":     "lightweight_analysis",
    "step6_tool_optimization":   "no_llm",
    "step7_context_reading":     "complex_reasoning",
    "step8_progress_tracking":   "no_llm",
    "step9_git_commit":          "no_llm",
    "step10_github_pr":          "no_llm",
    "step11_github_issues":      "no_llm",
    "step12_parallel_execution": "no_llm",
    "step13_failure_prevention": "no_llm",
    # Level-3 v2 execution steps
    "step0_task_analysis":       "complex_reasoning",
    "step1_plan_decision":       "classification",
    "step2_plan_exec":           "complex_reasoning",
    "step3_breakdown":           "lightweight_analysis",
    "step4_toon_refinement":     "complex_reasoning",
    "step5_skill_agent":         "lightweight_analysis",
    "step6_skill_validation":    "no_llm",
    "step7_final_prompt":        "complex_reasoning",
    "step8_github_issue":        "no_llm",
    "step9_branch_creation":     "no_llm",
    "step10_implementation":     "complex_reasoning",
    "step11_pull_request":       "complex_reasoning",
    "step12_issue_closure":      "no_llm",
    "step13_documentation":      "lightweight_analysis",
    "step14_final_summary":      "lightweight_analysis",
}

# ---------------------------------------------------------------------------
# Model recommendations per step type (copied from llm_mcp_server.py)
# ---------------------------------------------------------------------------

_MODEL_RECOMMENDATIONS = {
    "classification": {
        "ollama_model": "qwen2.5:7b",
        "description":  "Fast classification - yes/no, type detection",
        "temperature":  0.1,
        "fallback_provider": "anthropic",
        "fallback_model":    "fast",
    },
    "lightweight_analysis": {
        "ollama_model": "qwen2.5:7b",
        "description":  "Quick analysis - skill selection, task classification",
        "temperature":  0.2,
        "fallback_provider": "anthropic",
        "fallback_model":    "fast",
    },
    "deep_local": {
        "ollama_model": "qwen2.5:14b",
        "description":  "Deep reasoning on local GPU (free)",
        "temperature":  0.3,
        "fallback_provider": "anthropic",
        "fallback_model":    "balanced",
    },
    "complex_reasoning": {
        "ollama_model": None,
        "description":  "Complex reasoning - requires cloud LLM",
        "temperature":  0.4,
        "fallback_provider": "anthropic",
        "fallback_model":    "deep",
    },
    "no_llm": {
        "ollama_model": None,
        "description":  "No LLM needed - deterministic step",
        "temperature":  0.0,
        "fallback_provider": None,
        "fallback_model":    None,
    },
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _classify_by_complexity(complexity: int) -> str:
    """Map a numeric complexity score (1-10) to a step type string."""
    if complexity <= 3:
        return "classification"
    if complexity <= 6:
        return "lightweight_analysis"
    if complexity <= 8:
        return "deep_local"
    return "complex_reasoning"


def _build_routing_decision(
    step_type: str,
    provider_override: Optional[str],
    rec: dict,
) -> dict:
    """Build a routing decision dict from classification results.

    Args:
        step_type: Classified step type key.
        provider_override: Explicit provider requested by the caller ('auto' == None).
        rec: Recommendation entry from _MODEL_RECOMMENDATIONS.

    Returns:
        Dict describing the routing decision.
    """
    if step_type == "no_llm":
        return {
            "provider":          None,
            "model":             None,
            "temperature":       0.0,
            "reasoning":         "No LLM required for this step type",
            "fallback_provider": None,
        }

    if provider_override and provider_override != "auto":
        # Caller explicitly chose a provider - honour it
        if provider_override == "ollama":
            model = rec["ollama_model"] or "qwen2.5:7b"
        elif provider_override == "openai":
            model = "gpt-4o-mini"
        else:
            model = rec["fallback_model"] or "fast"
        return {
            "provider":          provider_override,
            "model":             model,
            "temperature":       rec["temperature"],
            "reasoning":         f"Caller requested provider='{provider_override}'",
            "fallback_provider": rec["fallback_provider"],
        }

    # Auto routing
    if rec["ollama_model"] is not None:
        # Ollama-eligible step
        return {
            "provider":          "ollama",
            "model":             rec["ollama_model"],
            "temperature":       rec["temperature"],
            "reasoning":         (
                f"Ollama selected for {step_type} "
                f"(local, free, fast; model={rec['ollama_model']})"
            ),
            "fallback_provider": rec["fallback_provider"],
        }

    # Complex / cloud-only step
    return {
        "provider":          rec["fallback_provider"],
        "model":             rec["fallback_model"],
        "temperature":       rec["temperature"],
        "reasoning":         (
            f"Cloud provider '{rec['fallback_provider']}' selected "
            f"for {step_type} (Ollama not suitable)"
        ),
        "fallback_provider": None,
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
@mcp_tool_handler
def llm_route_request(
    prompt: str,
    provider: str = "auto",
    model_tier: str = "fast",
    step_name: str = "",
    complexity: int = 5,
    temperature: Optional[float] = None,
    json_mode: bool = False,
) -> str:
    """Return a routing decision for an LLM request without making any LLM call.

    This tool selects the best provider and model based on step classification
    and complexity. The caller is responsible for invoking the chosen provider.

    Routing strategy:
      - If provider is specified (not 'auto'), route directly to that provider.
      - Otherwise use step classification + complexity to pick Ollama or cloud.
      - complexity 1-3 or classification steps -> Ollama preferred
      - complexity 4-6 or lightweight steps   -> Ollama preferred, Anthropic fallback
      - complexity 7-10 or complex steps      -> Anthropic directly

    Args:
        prompt: The prompt that will be sent (used only for length estimation).
        provider: 'auto' to let the router decide, or explicit: 'ollama',
                  'anthropic', 'openai'.
        model_tier: Tier hint for cloud providers (fast/balanced/deep).
        step_name: Optional pipeline step name for step-aware classification.
        complexity: Task complexity 1-10 (used when step_name is not provided).
        temperature: Override temperature. None means use the recommended value.
        json_mode: Whether the caller intends to request JSON output.
    """
    # Classify the step
    if step_name:
        step_type = _STEP_CLASSIFICATION.get(step_name, "complex_reasoning")
    else:
        step_type = _classify_by_complexity(complexity)

    rec = _MODEL_RECOMMENDATIONS.get(step_type, _MODEL_RECOMMENDATIONS["complex_reasoning"])

    # Resolve temperature
    resolved_temp = temperature if temperature is not None else rec["temperature"]

    # Build routing decision
    decision = _build_routing_decision(
        step_type,
        None if provider == "auto" else provider,
        rec,
    )

    # Apply temperature override
    decision["temperature"] = resolved_temp

    # Estimate prompt length
    prompt_chars = len(prompt)
    estimated_input_tokens = max(1, prompt_chars // 4)

    return to_json({
        "success": True,
        "provider":          decision["provider"],
        "model":             decision["model"],
        "temperature":       decision["temperature"],
        "reasoning":         decision["reasoning"],
        "fallback_provider": decision["fallback_provider"],
        "step_type":         step_type,
        "step_name":         step_name,
        "complexity":        complexity,
        "json_mode":         json_mode,
        "estimated_input_tokens": estimated_input_tokens,
    })


@mcp.tool()
@mcp_tool_handler
def llm_classify_step(step_name: str) -> str:
    """Classify a pipeline step and return the recommended model configuration.

    Pure config lookup - no network calls, always fast.

    Args:
        step_name: Pipeline step name (e.g. 'step1_plan_mode_decision').
                   Returns 'complex_reasoning' for unrecognised step names.
    """
    step_type = _STEP_CLASSIFICATION.get(step_name, "complex_reasoning")
    rec = _MODEL_RECOMMENDATIONS.get(step_type, _MODEL_RECOMMENDATIONS["complex_reasoning"])

    return to_json({
        "success": True,
        "step_name":              step_name,
        "step_type":              step_type,
        "recommended_model":      rec["ollama_model"],
        "recommended_temperature": rec["temperature"],
        "fallback_provider":      rec["fallback_provider"],
        "fallback_model":         rec["fallback_model"],
        "description":            rec["description"],
        "needs_llm":              step_type != "no_llm",
    })


@mcp.tool()
@mcp_tool_handler
def llm_select_model(
    task_type: str = "",
    complexity: int = 5,
    step_name: str = "",
) -> str:
    """Select the best model and provider for a given task.

    Combines step classification (if step_name given) and complexity scoring
    to produce a concrete provider + model recommendation.

    Args:
        task_type: Human-readable task description (e.g. 'Implementation',
                   'Bug Fix', 'Refactor'). Used only for context in the response.
        complexity: Complexity score 1-10. Used when step_name is not provided.
        step_name: Optional pipeline step name for step-aware routing.
    """
    if step_name:
        step_type = _STEP_CLASSIFICATION.get(step_name, "complex_reasoning")
    else:
        step_type = _classify_by_complexity(complexity)

    rec = _MODEL_RECOMMENDATIONS.get(step_type, _MODEL_RECOMMENDATIONS["complex_reasoning"])

    if step_type == "no_llm":
        return to_json({
            "success": True,
            "selected_provider": None,
            "selected_model":    None,
            "temperature":       0.0,
            "step_type":         step_type,
            "reason":            "No LLM required for this step",
            "task_type":         task_type,
            "complexity":        complexity,
        })

    # Prefer Ollama when a local model is recommended
    if rec["ollama_model"] is not None:
        return to_json({
            "success": True,
            "selected_provider": "ollama",
            "selected_model":    rec["ollama_model"],
            "temperature":       rec["temperature"],
            "step_type":         step_type,
            "reason":            (
                f"Ollama model '{rec['ollama_model']}' preferred for "
                f"{step_type} (local, free, fast)"
            ),
            "fallback_provider": rec["fallback_provider"],
            "fallback_model":    rec["fallback_model"],
            "task_type":         task_type,
            "complexity":        complexity,
        })

    # Cloud-only step
    return to_json({
        "success": True,
        "selected_provider": rec["fallback_provider"],
        "selected_model":    rec["fallback_model"],
        "temperature":       rec["temperature"],
        "step_type":         step_type,
        "reason":            (
            f"Cloud provider '{rec['fallback_provider']}' required "
            f"for {step_type} (complexity={complexity})"
        ),
        "fallback_provider": None,
        "fallback_model":    None,
        "task_type":         task_type,
        "complexity":        complexity,
    })


@mcp.tool()
@mcp_tool_handler
def llm_git_commit_title(
    commit_type: Optional[str] = None,
    cwd: Optional[str] = None,
) -> str:
    """Generate a git commit title using the best available LLM provider.

    Reads the staged diff, builds a prompt, then attempts Ollama first
    (fast + free) and falls back to the Anthropic API on failure.

    Args:
        commit_type: Optional semantic prefix (feat, fix, refactor, docs, ...).
                     Applied to the generated title if not already present.
        cwd: Working directory for git commands. Defaults to the current directory.
    """
    # Collect staged diff
    try:
        stat_result = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        diff_result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except Exception as e:
        return to_json({"success": False, "error": f"git command failed: {e}"})

    stat_text = stat_result.stdout.strip() if stat_result.returncode == 0 else ""
    diff_text = diff_result.stdout[:3000]  if diff_result.returncode == 0 else ""

    if not stat_text and not diff_text:
        return to_json({"success": False, "error": "No staged changes found"})

    type_hint = f"Commit type: {commit_type}\n" if commit_type else ""
    type_rule  = (
        f"- Start with type prefix: {commit_type}:\n"
        if commit_type else
        "- Use conventional commit format: type: description\n"
    )

    prompt = (
        "Generate a git commit message for these changes.\n"
        f"{type_hint}\n"
        f"Changed files:\n{stat_text}\n\n"
        f"Diff (truncated):\n{diff_text}\n\n"
        "Rules:\n"
        "- Return ONLY the commit title (one line, under 72 chars)\n"
        f"{type_rule}"
        "- Focus on WHAT changed and WHY, not just file names\n"
        "- Be specific\n"
        "- No quotes, no explanation, just the commit title line\n"
    )

    response_text = None
    provider_used = None

    # --- Try Ollama first (fast, free) ---
    try:
        endpoint = os.getenv("OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
        payload = json.dumps({
            "model": "qwen2.5:7b",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{endpoint}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidate = data.get("response", "").strip()
            if candidate:
                response_text = candidate
                provider_used = "ollama"
    except Exception:
        pass  # Fall through to Anthropic

    # --- Fallback to Anthropic API ---
    if not response_text:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if api_key:
            try:
                payload = json.dumps({
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 128,
                    "messages": [{"role": "user", "content": prompt}],
                }).encode("utf-8")
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content_blocks = data.get("content", [])
                    if content_blocks:
                        candidate = content_blocks[0].get("text", "").strip()
                        if candidate:
                            response_text = candidate
                            provider_used = "anthropic"
            except Exception:
                pass

    if not response_text:
        return to_json({
            "success": False,
            "error": "All providers failed to generate a commit title",
        })

    # Clean up the title
    title = response_text.splitlines()[0].strip().strip('"').strip("'")
    if commit_type and not title.lower().startswith(commit_type.lower()):
        title = f"{commit_type}: {title}"
    if len(title) > 72:
        title = title[:69] + "..."

    return to_json({
        "success": True,
        "title":        title,
        "commit_type":  commit_type,
        "provider_used": provider_used,
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")
