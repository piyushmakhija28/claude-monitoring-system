#!/usr/bin/env python3
"""
Level 3 - Orchestrator Agent Caller

Reads a pre-built prompt from a temp file path (--orchestration-prompt-file),
calls the LLM, streams stderr progress, and writes JSON to stdout.

Invoked by: call_execution_script("orchestrator-agent-caller", args)
Output: JSON with keys: status, agent_output, llm_response, error (on failure)

Environment:
  STEP0_ORCHESTRATOR_TIMEOUT  max seconds to wait for LLM (default: 300)
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
DEBUG = os.getenv("CLAUDE_DEBUG") == "1"
_TIMEOUT = int(os.getenv("STEP0_ORCHESTRATOR_TIMEOUT", "300"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_args(argv):
    """Parse CLI arguments into a dict.

    Supported flags:
      --orchestration-prompt-file <path>   path to file containing full prompt text
      --task-description <str>             fallback if no prompt file provided
      --complexity-score <int>
    """
    args = {
        "orchestration_prompt_file": "",
        "task_description": "",
        "complexity_score": 5,
    }

    i = 1
    while i < len(argv):
        token = argv[i]
        if token == "--orchestration-prompt-file" and i + 1 < len(argv):
            args["orchestration_prompt_file"] = argv[i + 1]
            i += 2
        elif token == "--task-description" and i + 1 < len(argv):
            args["task_description"] = argv[i + 1]
            i += 2
        elif token == "--complexity-score" and i + 1 < len(argv):
            try:
                args["complexity_score"] = int(argv[i + 1])
            except ValueError:
                args["complexity_score"] = 5
            i += 2
        else:
            i += 1

    return args


def _load_prompt(args):
    """Load prompt text from file or fall back to task_description.

    Returns (prompt_text, error).
    """
    prompt_file = args.get("orchestration_prompt_file", "")
    if prompt_file:
        path = Path(prompt_file)
        if not path.exists():
            return None, "Prompt file not found: " + prompt_file
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            return text.strip(), None
        except Exception as exc:
            return None, "Failed to read prompt file: " + str(exc)

    # Fallback: use task_description as bare prompt
    task = args.get("task_description", "").strip()
    if task:
        return task, None

    return None, "No --orchestration-prompt-file and no --task-description provided"


def _call_llm(prompt):
    """Call shared llm_call with quality model. Returns (response_text, error)."""
    try:
        from langgraph_engine.llm_call import llm_call

        response = llm_call(prompt, model="quality", temperature=0.2)
        if response:
            return response, None
        return None, "llm_call returned empty response"
    except ImportError as exc:
        return None, "ImportError: " + str(exc)
    except Exception as exc:
        return None, "LLM call failed: " + str(exc)


def _parse_agent_output(llm_response):
    """Attempt to parse structured JSON from the LLM response."""
    if not llm_response:
        return None
    try:
        if "{" in llm_response:
            json_start = llm_response.index("{")
            json_end = llm_response.rindex("}") + 1
            return json.loads(llm_response[json_start:json_end])
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("[orchestrator-agent-caller] Starting", file=sys.stderr, flush=True)

    args = _parse_args(sys.argv)

    # Load prompt
    print("[orchestrator-agent-caller] Loading prompt", file=sys.stderr, flush=True)
    prompt, err = _load_prompt(args)
    if err:
        print(json.dumps({"status": "ERROR", "error": err}))
        return

    prompt_len = len(prompt)
    print(
        "[orchestrator-agent-caller] Prompt ready (" + str(prompt_len) + " chars)",
        file=sys.stderr,
        flush=True,
    )

    if DEBUG:
        preview = prompt[:200].replace("\n", " ")
        print("[orchestrator-agent-caller] Preview: " + preview, file=sys.stderr, flush=True)

    # Call LLM
    print("[orchestrator-agent-caller] Calling LLM (model=quality)", file=sys.stderr, flush=True)

    llm_response, err = _call_llm(prompt)

    if err:
        print("[orchestrator-agent-caller] LLM call failed: " + str(err), file=sys.stderr, flush=True)
        print(json.dumps({"status": "ERROR", "error": err}))
        return

    response_len = len(llm_response) if llm_response else 0
    print(
        "[orchestrator-agent-caller] LLM responded (" + str(response_len) + " chars)",
        file=sys.stderr,
        flush=True,
    )

    # Parse structured output
    agent_output = _parse_agent_output(llm_response)
    if agent_output:
        print("[orchestrator-agent-caller] Parsed agent output OK", file=sys.stderr, flush=True)
    else:
        print("[orchestrator-agent-caller] No structured JSON in response", file=sys.stderr, flush=True)

    result = {
        "status": "SUCCESS",
        "agent_output": agent_output,
        "llm_response": llm_response,
        "complexity_score": args["complexity_score"],
        "prompt_chars": prompt_len,
    }

    print(json.dumps(result, ensure_ascii=True))

    print("[orchestrator-agent-caller] Done", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
