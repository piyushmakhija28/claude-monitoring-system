"""
Shared LLM Call Helper - Single entry point for all LLM calls in the pipeline.

Fallback chain: Ollama -> claude CLI (user's subscription)
All scripts should use this instead of direct urllib calls to Ollama.

Performance: Ollama health is checked ONCE at import time (3s timeout).
If Ollama is down, all calls go directly to Claude CLI — no per-call wait.

Model tiers:
  fast     -> haiku  (classification, JSON, yes/no, titles)
  balanced -> sonnet (skill selection, code review, synthesis)
  deep     -> opus  (planning, complex reasoning, architecture)

Temperature guidelines (based on research):
  0.0-0.1: JSON output, classification, code review
  0.2-0.3: Skill selection, title generation, structured output
  0.4:     Planning, complex reasoning
  0.7+:    Creative tasks (not used in pipeline)

Usage:
    from langgraph_engine.llm_call import llm_call
    response = llm_call(prompt, model="fast", temperature=0.1)
"""

import os
import sys
import json
import subprocess
import shutil
from typing import Optional

# Ollama config
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434/api/generate")
OLLAMA_MODEL_FAST = os.getenv("OLLAMA_MODEL_FAST", os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))
OLLAMA_MODEL_DEEP = os.getenv("OLLAMA_MODEL_DEEP", "qwen2.5:14b")

# ============================================================================
# OLLAMA HEALTH CHECK - Run ONCE at import time, not per call
# Saves 30s per LLM call when Ollama is down (4 calls = 120s saved)
# ============================================================================
_OLLAMA_AVAILABLE = False
try:
    import urllib.request
    # Extract base URL (scheme + host) from endpoint, append health check path
    from urllib.parse import urlparse
    _parsed = urlparse(OLLAMA_ENDPOINT)
    _health_url = f"{_parsed.scheme}://{_parsed.netloc}/api/tags"
    with urllib.request.urlopen(urllib.request.Request(_health_url), timeout=3) as _resp:
        _OLLAMA_AVAILABLE = _resp.status == 200
except Exception:
    pass

# Claude CLI model mapping
CLAUDE_MODEL_MAP = {
    "fast": "haiku",
    "balanced": "sonnet",
    "deep": "opus",
    # Legacy keys
    "fast_classification": "haiku",
    "complex_reasoning": "opus",
    "synthesis": "sonnet",
    "planning": "opus",
    "code_review": "sonnet",
}

# Default temperature per model tier (research-backed)
DEFAULT_TEMPERATURES = {
    "fast": 0.1,       # Classification, JSON, yes/no -> near-deterministic
    "balanced": 0.3,   # Skill selection, synthesis -> slight flexibility
    "deep": 0.4,       # Planning, complex reasoning -> quality exploration
    "fast_classification": 0.1,
    "complex_reasoning": 0.4,
    "synthesis": 0.2,
    "planning": 0.4,
    "code_review": 0.1,
}


def llm_call(
    prompt: str,
    model: str = "fast",
    temperature: Optional[float] = None,
    timeout: int = 120,
    json_mode: bool = False,
) -> Optional[str]:
    """Make an LLM call with automatic fallback chain.

    Args:
        prompt: The prompt text to send
        model: "fast" (haiku), "balanced" (sonnet), "deep" (opus)
        temperature: Override temp (default: auto per model tier)
        timeout: Max seconds to wait
        json_mode: If True, request JSON format from Ollama

    Returns:
        Response text string, or None if all backends failed.
    """
    # Auto-select temperature based on model tier if not specified
    if temperature is None:
        temperature = DEFAULT_TEMPERATURES.get(model, 0.3)

    # Try 1: Ollama (local, free) - skip entirely if health check failed at import
    if _OLLAMA_AVAILABLE:
        response = _call_ollama(prompt, model, temperature, timeout, json_mode)
        if response:
            return response

    # Try 2: claude CLI (user's subscription)
    response = _call_claude_cli(prompt, model, timeout)
    if response:
        return response

    return None


def _call_ollama(prompt, model, temperature, timeout, json_mode):
    """Try Ollama HTTP API."""
    import urllib.request
    import urllib.error

    ollama_model = OLLAMA_MODEL_DEEP if model in ("deep", "complex_reasoning", "planning") else OLLAMA_MODEL_FAST

    try:
        payload = {
            "model": ollama_model,
            "prompt": prompt,
            "stream": False,
            "temperature": temperature,
            "options": {"num_ctx": 16384, "num_predict": 2048},
        }
        if json_mode:
            payload["format"] = "json"

        req = urllib.request.Request(
            OLLAMA_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        # Cap Ollama timeout at 30s - if it takes longer, fall back to CLI
        with urllib.request.urlopen(req, timeout=min(timeout, 30)) as resp:
            result = json.loads(resp.read().decode())
            text = result.get("response", "").strip()
            if text:
                return text
    except Exception:
        pass

    return None


def _call_claude_cli(prompt, model, timeout):
    """Try claude CLI with user's subscription."""
    claude_path = shutil.which("claude")
    if not claude_path:
        return None

    cli_model = CLAUDE_MODEL_MAP.get(model, "haiku")

    # Truncate to avoid pipe/arg issues
    if len(prompt) > 10000:
        prompt = prompt[:10000] + "\n[truncated]"

    env = os.environ.copy()
    env["CLAUDE_WORKFLOW_RUNNING"] = "1"

    try:
        result = subprocess.run(
            [claude_path, "-p", "--model", cli_model, prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    return None


def generate_llm_commit_title(commit_type: str = None, cwd: str = None) -> Optional[str]:
    """Generate a meaningful commit title using LLM with staged diff context.

    Single source of truth for LLM-powered commit messages. Used by both
    git-auto-commit-policy.py and github_pr_workflow.py.

    Args:
        commit_type: Optional semantic type (feat, fix, refactor, etc.)
        cwd: Working directory for git commands (default: current dir)

    Returns:
        Commit title string (max 72 chars), or None if LLM unavailable.
    """
    try:
        stat_result = subprocess.run(
            ['git', 'diff', '--cached', '--stat'],
            capture_output=True, text=True, timeout=5, cwd=cwd
        )
        stat_text = stat_result.stdout.strip() if stat_result.returncode == 0 else ""

        diff_result = subprocess.run(
            ['git', 'diff', '--cached'],
            capture_output=True, text=True, timeout=5, cwd=cwd
        )
        diff_text = diff_result.stdout[:3000] if diff_result.returncode == 0 else ""

        if not stat_text and not diff_text:
            return None

        type_hint = f"Commit type: {commit_type}\n" if commit_type else ""
        type_rule = (f"- Start with type prefix: {commit_type}:\n" if commit_type
                     else "- Use conventional commit format: type: description\n")

        prompt = (
            f"Generate a git commit message for these changes.\n"
            f"{type_hint}\n"
            f"Changed files:\n{stat_text}\n\n"
            f"Diff (truncated):\n{diff_text}\n\n"
            f"Rules:\n"
            f"- Return ONLY the commit title (one line, under 72 chars)\n"
            f"{type_rule}"
            f"- Focus on WHAT changed and WHY, not just file names\n"
            f"- Be specific: 'fix stash detection using stdout+stderr' not 'fix issues'\n"
            f"- No quotes, no explanation, just the commit title line\n"
        )

        response = llm_call(prompt, model="fast", temperature=0.1, timeout=15)
        if not response:
            return None

        title = response.strip().splitlines()[0].strip().strip('"').strip("'")
        if commit_type and not title.lower().startswith(commit_type):
            title = f"{commit_type}: {title}"
        return title[:69] + "..." if len(title) > 72 else title

    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
