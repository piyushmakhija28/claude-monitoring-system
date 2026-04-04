#!/usr/bin/env python3
"""
Level 3 - Prompt Generation Expert Caller

Reads CLI args, loads the orchestration system prompt template,
fills the 7 placeholders, calls the LLM, and writes JSON to stdout.

Invoked by: call_execution_script("prompt-gen-expert-caller", args)
Output: JSON with keys: status, prompt, llm_response, error (on failure)
"""

import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap (shared llm_call module lives 4 dirs up)
# ---------------------------------------------------------------------------
_ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_ENGINE_ROOT))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_TEMPLATE_FILE = _TEMPLATES_DIR / "orchestration_system_prompt.txt"

DEBUG = os.getenv("CLAUDE_DEBUG") == "1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_args(argv):
    """Parse CLI arguments into a dict.

    Supported flags:
      --task-description <str>
      --complexity-score <int>
      --call-graph-json <json-string>
      --runtime-context-json <json-string>
    """
    args = {
        "task_description": "",
        "complexity_score": 5,
        "call_graph_json": "{}",
        "runtime_context_json": "{}",
    }

    i = 1
    while i < len(argv):
        token = argv[i]
        if token == "--task-description" and i + 1 < len(argv):
            args["task_description"] = argv[i + 1]
            i += 2
        elif token == "--complexity-score" and i + 1 < len(argv):
            try:
                args["complexity_score"] = int(argv[i + 1])
            except ValueError:
                args["complexity_score"] = 5
            i += 2
        elif token == "--call-graph-json" and i + 1 < len(argv):
            args["call_graph_json"] = argv[i + 1]
            i += 2
        elif token == "--runtime-context-json" and i + 1 < len(argv):
            args["runtime_context_json"] = argv[i + 1]
            i += 2
        else:
            i += 1

    return args


def _load_template():
    """Load orchestration_system_prompt.txt. Returns (text, error)."""
    if not _TEMPLATE_FILE.exists():
        return None, "Template file not found: " + str(_TEMPLATE_FILE)
    try:
        content = _TEMPLATE_FILE.read_text(encoding="utf-8", errors="replace")
        return content, None
    except Exception as exc:
        return None, "Failed to read template: " + str(exc)


def _build_filled_prompt(template, args):
    """Fill the 7 placeholders in the template with runtime values."""
    call_graph = {}
    try:
        call_graph = json.loads(args["call_graph_json"]) if args["call_graph_json"] else {}
    except (json.JSONDecodeError, TypeError):
        call_graph = {}

    runtime_context = {}
    try:
        runtime_context = json.loads(args["runtime_context_json"]) if args["runtime_context_json"] else {}
    except (json.JSONDecodeError, TypeError):
        runtime_context = {}

    risk_level = call_graph.get("risk_level", "unknown")
    danger_zones = call_graph.get("danger_zones", [])
    affected_methods = call_graph.get("affected_methods", [])
    hot_nodes = call_graph.get("hot_nodes", [])

    danger_zones_str = ", ".join(danger_zones) if danger_zones else "none"
    affected_str = ", ".join(affected_methods[:10]) if affected_methods else "none"
    hot_nodes_str = ", ".join(hot_nodes[:10]) if hot_nodes else "none"

    runtime_block = json.dumps(runtime_context, indent=2, ensure_ascii=True)

    complexity = args["complexity_score"]
    if complexity <= 3:
        tier = "low"
    elif complexity <= 7:
        tier = "medium"
    else:
        tier = "high"
    complexity_display = str(complexity) + "/10 (" + tier + ")"

    filled = template
    filled = filled.replace("{user_requirements}", args["task_description"])
    filled = filled.replace("{runtime_context_json_block}", runtime_block)
    filled = filled.replace("{complexity_score_display}", complexity_display)
    filled = filled.replace("{codebase_risk_level}", str(risk_level))
    filled = filled.replace("{codebase_danger_zones}", danger_zones_str)
    filled = filled.replace("{codebase_affected_methods}", affected_str)
    filled = filled.replace("{codebase_hot_nodes}", hot_nodes_str)

    return filled


def _call_llm(prompt):
    """Call shared llm_call. Returns (response_text, error)."""
    try:
        from langgraph_engine.llm_call import llm_call

        response = llm_call(prompt, model="balanced", temperature=0.2)
        if response:
            return response, None
        return None, "llm_call returned empty response"
    except ImportError as exc:
        return None, "ImportError: " + str(exc)
    except Exception as exc:
        return None, "LLM call failed: " + str(exc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if DEBUG:
        print("[prompt-gen-expert-caller] Starting", file=sys.stderr, flush=True)

    args = _parse_args(sys.argv)

    if not args["task_description"]:
        print(json.dumps({"status": "ERROR", "error": "No --task-description provided"}))
        return

    # Load template
    template, err = _load_template()
    if err:
        print(json.dumps({"status": "ERROR", "error": err}))
        return

    if DEBUG:
        print("[prompt-gen-expert-caller] Template loaded", file=sys.stderr, flush=True)

    # Fill placeholders
    filled_prompt = _build_filled_prompt(template, args)

    if DEBUG:
        print("[prompt-gen-expert-caller] Calling LLM", file=sys.stderr, flush=True)

    # Call LLM
    llm_response, err = _call_llm(filled_prompt)
    if err:
        print(json.dumps({"status": "ERROR", "error": err, "prompt": filled_prompt[:500]}))
        return

    if DEBUG:
        print("[prompt-gen-expert-caller] LLM responded", file=sys.stderr, flush=True)

    # Try to parse LLM response as JSON (it should be per template instructions)
    parsed_plan = None
    try:
        if "{" in llm_response:
            json_start = llm_response.index("{")
            json_end = llm_response.rindex("}") + 1
            parsed_plan = json.loads(llm_response[json_start:json_end])
    except Exception:
        parsed_plan = None

    result = {
        "status": "SUCCESS",
        "prompt": filled_prompt,
        "llm_response": llm_response,
        "parsed_plan": parsed_plan,
        "complexity_score": args["complexity_score"],
    }

    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
