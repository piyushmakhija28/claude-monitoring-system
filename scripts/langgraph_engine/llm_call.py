"""
Shared LLM Call Helper - Single entry point for all LLM calls in the pipeline.

Fallback chain: Ollama -> Claude API SDK -> claude CLI
All scripts should use this instead of direct urllib calls to Ollama.

Usage:
    from langgraph_engine.llm_call import llm_call
    response_text = llm_call(prompt, model="fast")  # returns string or None
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

# Claude CLI model map (same as OllamaService)
CLAUDE_MODEL_MAP = {
    "fast": "haiku",
    "deep": "opus",
    "balanced": "sonnet",
    "fast_classification": "haiku",
    "complex_reasoning": "opus",
    "synthesis": "sonnet",
}


def llm_call(
    prompt: str,
    model: str = "fast",
    temperature: float = 0.3,
    timeout: int = 120,
    json_mode: bool = False,
) -> Optional[str]:
    """Make an LLM call with automatic fallback chain.

    Args:
        prompt: The prompt text to send
        model: "fast" (haiku/7b), "deep" (opus/14b), "balanced" (sonnet)
        temperature: 0-1
        timeout: Max seconds to wait
        json_mode: If True, request JSON format from Ollama

    Returns:
        Response text string, or None if all backends failed.
    """
    # Try 1: Ollama
    response = _call_ollama(prompt, model, temperature, timeout, json_mode)
    if response:
        return response

    # Try 2: claude CLI
    response = _call_claude_cli(prompt, model, timeout)
    if response:
        return response

    return None


def _call_ollama(prompt, model, temperature, timeout, json_mode):
    """Try Ollama HTTP API."""
    import urllib.request
    import urllib.error

    ollama_model = OLLAMA_MODEL_DEEP if model in ("deep", "complex_reasoning") else OLLAMA_MODEL_FAST

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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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

    # Truncate prompt to avoid issues
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
