"""
Anthropic Claude API MCP Server - Focused direct access to Claude models.

Provides direct Anthropic API calls via urllib (no SDK dependency).
Anthropic-only: no Ollama, no OpenAI, no provider chain.

Backend: urllib.request (no anthropic SDK required)
Transport: stdio

Tools (4):
  anthropic_generate, anthropic_health_check,
  anthropic_list_models, anthropic_estimate_cost
"""

import json
import os
import sys
import time
from pathlib import Path

# Ensure src/mcp/ is in path for base package imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP
from base.response import to_json
from base.decorators import mcp_tool_handler

# ---------------------------------------------------------------------------
# Server definition
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "anthropic-provider",
    instructions="Anthropic Claude API - direct access to Claude models",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"

# Model tier -> actual model ID
_MODEL_TIERS = {
    "fast": "claude-haiku-4-5-20251001",
    "balanced": "claude-sonnet-4-6-20250514",
    "deep": "claude-opus-4-6-20250514",
}

# Per 1M tokens: (input_cost, output_cost) in USD
_MODEL_PRICING = {
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-sonnet-4-6-20250514": (3.00, 15.00),
    "claude-opus-4-6-20250514": (15.00, 75.00),
}

# Model metadata for anthropic_list_models
_MODEL_CATALOG = [
    {
        "id": "claude-haiku-4-5-20251001",
        "tier": "fast",
        "description": "Fastest, most compact Claude model. Best for classification, "
                       "JSON extraction, titles, and high-volume tasks.",
        "context_window": 200000,
    },
    {
        "id": "claude-sonnet-4-6-20250514",
        "tier": "balanced",
        "description": "Balanced intelligence and speed. Best for code generation, "
                       "synthesis, analysis, and most production tasks.",
        "context_window": 200000,
    },
    {
        "id": "claude-opus-4-6-20250514",
        "tier": "deep",
        "description": "Most capable Claude model. Best for complex reasoning, "
                       "architecture decisions, and nuanced analysis.",
        "context_window": 200000,
    },
]

# Health check cache (60s TTL)
_health_cache = {"timestamp": 0.0, "result": None}
_HEALTH_CACHE_TTL = 60


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_model(model: str) -> str:
    """Resolve a tier name or model ID to an actual Anthropic model ID.

    Accepts either a tier alias ('fast', 'balanced', 'deep') or a direct
    model ID (e.g. 'claude-haiku-4-5-20251001').

    Args:
        model: Tier alias or full model ID string.

    Returns:
        Resolved Anthropic model ID string.
    """
    return _MODEL_TIERS.get(model, model)


def _get_api_key() -> str:
    """Return the Anthropic API key from the environment.

    Returns:
        API key string, or empty string if not set.
    """
    return os.getenv("ANTHROPIC_API_KEY", "")


def _call_anthropic(
    prompt: str,
    model_id: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
    system_prompt: str,
) -> dict:
    """Execute a single POST to the Anthropic Messages API via urllib.

    Args:
        prompt: User message content.
        model_id: Resolved Anthropic model ID.
        temperature: Sampling temperature (0.0 - 1.0).
        max_tokens: Maximum tokens in the response.
        timeout: HTTP request timeout in seconds.
        system_prompt: Optional system prompt string.

    Returns:
        dict with keys: response (str), usage (dict), latency_ms (int).

    Raises:
        RuntimeError: On HTTP error or API-level error response.
        ValueError: If ANTHROPIC_API_KEY is not set.
    """
    import urllib.request
    import urllib.error

    api_key = _get_api_key()
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    payload = {
        "model": model_id,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        payload["system"] = system_prompt

    encoded = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _ANTHROPIC_API_URL,
        data=encoded,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        },
        method="POST",
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = round((time.time() - t0) * 1000)
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        latency_ms = round((time.time() - t0) * 1000)
        try:
            err_body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            err_body = {}
        api_err = err_body.get("error", {})
        raise RuntimeError(
            f"Anthropic API HTTP {exc.code}: "
            f"{api_err.get('message', exc.reason)}"
        ) from exc

    # Extract text from content blocks
    content = body.get("content", [])
    text = ""
    for block in content:
        if block.get("type") == "text":
            text += block.get("text", "")

    usage = body.get("usage", {})
    return {
        "response": text.strip(),
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        },
        "latency_ms": latency_ms,
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
@mcp_tool_handler
def anthropic_generate(
    prompt: str,
    model: str = "claude-haiku-4-5-20251001",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    timeout: int = 120,
    system_prompt: str = "",
    json_mode: bool = False,
) -> str:
    """Call the Anthropic Claude API directly.

    Accepts either a model tier alias ('fast', 'balanced', 'deep') or a full
    Anthropic model ID. Requires ANTHROPIC_API_KEY environment variable.

    Model tier aliases:
      fast     -> claude-haiku-4-5-20251001  (fast, cheap)
      balanced -> claude-sonnet-4-6-20250514 (best balance)
      deep     -> claude-opus-4-6-20250514   (most capable)

    Args:
        prompt: User message to send to the model.
        model: Tier alias or full Anthropic model ID (default: haiku).
        temperature: Sampling temperature 0.0-1.0 (default: 0.3).
        max_tokens: Maximum output tokens (default: 4096).
        timeout: Request timeout in seconds (default: 120).
        system_prompt: Optional system-level instructions.
        json_mode: If True, appends JSON-only instruction to the prompt.

    Returns:
        JSON string with: success, response, model, temperature,
        usage (input_tokens, output_tokens), latency_ms.
    """
    api_key = _get_api_key()
    if not api_key:
        return to_json({"success": False, "error": "ANTHROPIC_API_KEY not set"})

    model_id = _resolve_model(model)

    actual_prompt = prompt
    if json_mode:
        actual_prompt = (
            prompt
            + "\n\nIMPORTANT: Return ONLY valid JSON. No explanation or markdown."
        )

    result = _call_anthropic(
        prompt=actual_prompt,
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        system_prompt=system_prompt,
    )

    return to_json({
        "success": True,
        "response": result["response"],
        "model": model_id,
        "temperature": temperature,
        "usage": result["usage"],
        "latency_ms": result["latency_ms"],
    })


@mcp.tool()
@mcp_tool_handler
def anthropic_health_check() -> str:
    """Check Anthropic API availability with a minimal probe request.

    Sends a 1-token request to verify API key validity and connectivity.
    Result is cached for 60 seconds to avoid repeated slow checks.

    Returns:
        JSON string with: success, available, has_api_key, latency_ms.
        Cached responses include from_cache=true and cache_age_s.
    """
    now = time.time()

    # Return cached result if still fresh
    if _health_cache["result"] is not None:
        age = now - _health_cache["timestamp"]
        if age < _HEALTH_CACHE_TTL:
            cached = json.loads(_health_cache["result"])
            cached["from_cache"] = True
            cached["cache_age_s"] = round(age, 1)
            return to_json(cached)

    api_key = _get_api_key()
    if not api_key:
        result = {
            "success": True,
            "available": False,
            "has_api_key": False,
            "latency_ms": 0,
            "from_cache": False,
        }
        _health_cache["timestamp"] = now
        _health_cache["result"] = to_json(result)
        return to_json(result)

    import urllib.request
    import urllib.error

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }).encode("utf-8")

    req = urllib.request.Request(
        _ANTHROPIC_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        },
        method="POST",
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10):
            latency_ms = round((time.time() - t0) * 1000)
            result = {
                "success": True,
                "available": True,
                "has_api_key": True,
                "latency_ms": latency_ms,
                "from_cache": False,
            }
    except urllib.error.HTTPError as exc:
        latency_ms = round((time.time() - t0) * 1000)
        if exc.code == 401:
            result = {
                "success": True,
                "available": False,
                "has_api_key": True,
                "error": "Invalid API key (401)",
                "latency_ms": latency_ms,
                "from_cache": False,
            }
        else:
            # Any other HTTP error means the endpoint is reachable
            result = {
                "success": True,
                "available": True,
                "has_api_key": True,
                "latency_ms": latency_ms,
                "from_cache": False,
            }
    except Exception as exc:
        latency_ms = round((time.time() - t0) * 1000)
        result = {
            "success": True,
            "available": False,
            "has_api_key": True,
            "error": str(exc)[:120],
            "latency_ms": latency_ms,
            "from_cache": False,
        }

    _health_cache["timestamp"] = time.time()
    _health_cache["result"] = to_json(result)
    return to_json(result)


@mcp.tool()
@mcp_tool_handler
def anthropic_list_models() -> str:
    """Return available Anthropic Claude model tiers with descriptions.

    No API call is made; returns a static catalog of supported models
    with tier names, model IDs, context windows, and descriptions.

    Returns:
        JSON string with: success, models (list of model objects).
    """
    return to_json({
        "success": True,
        "models": _MODEL_CATALOG,
        "tiers": {
            "fast": _MODEL_TIERS["fast"],
            "balanced": _MODEL_TIERS["balanced"],
            "deep": _MODEL_TIERS["deep"],
        },
    })


@mcp.tool()
@mcp_tool_handler
def anthropic_estimate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "claude-haiku-4-5-20251001",
) -> str:
    """Estimate the API cost for a given number of tokens.

    Accepts either a tier alias ('fast', 'balanced', 'deep') or a full
    Anthropic model ID. Pricing is per 1M tokens (USD).

    Pricing (USD per 1M tokens):
      haiku:  $0.80 input / $4.00 output
      sonnet: $3.00 input / $15.00 output
      opus:   $15.00 input / $75.00 output

    Args:
        input_tokens: Number of input (prompt) tokens.
        output_tokens: Number of output (completion) tokens.
        model: Tier alias or full Anthropic model ID (default: haiku).

    Returns:
        JSON string with: success, model, input_cost, output_cost,
        total_cost (all in USD, rounded to 6 decimal places).
    """
    model_id = _resolve_model(model)
    pricing = _MODEL_PRICING.get(model_id)

    if pricing is None:
        # Unknown model - try to fall back to haiku as a safe default
        model_id = _MODEL_TIERS["fast"]
        pricing = _MODEL_PRICING[model_id]
        unknown_model = model
    else:
        unknown_model = None

    input_rate, output_rate = pricing
    input_cost = round((input_tokens / 1_000_000) * input_rate, 6)
    output_cost = round((output_tokens / 1_000_000) * output_rate, 6)
    total_cost = round(input_cost + output_cost, 6)

    result = {
        "success": True,
        "model": model_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "currency": "USD",
        "pricing_per_1m": {
            "input": input_rate,
            "output": output_rate,
        },
    }
    if unknown_model:
        result["warning"] = (
            f"Unknown model '{unknown_model}'; cost estimated using haiku pricing."
        )

    return to_json(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
