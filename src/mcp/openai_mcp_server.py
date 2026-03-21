"""
OpenAI Provider MCP Server - Direct access to GPT models via OpenAI API.

Provides focused OpenAI-only tooling: generate text, check health, list models,
and estimate costs. Uses urllib.request only (no SDK dependency).

Backend: OpenAI REST API (urllib.request)
Transport: stdio

Tools (4):
  openai_generate, openai_health_check, openai_list_models, openai_estimate_cost
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Ensure src/mcp/ is in path for base package imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP
from base.response import to_json
from base.decorators import mcp_tool_handler

mcp = FastMCP("openai-provider", instructions="OpenAI API - direct access to GPT models")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OPENAI_API_BASE = "https://api.openai.com/v1"

# Model tier mapping
_MODEL_TIERS = {
    "fast":     "gpt-4o-mini",
    "balanced": "gpt-4o",
    "deep":     "gpt-4o",
}

# Pricing per 1M tokens (input, output) in USD
_MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.15,   "output": 0.60},
    "gpt-4o":      {"input": 2.50,   "output": 10.00},
}

# Static model catalog returned by openai_list_models
_STATIC_MODELS = [
    {"id": "gpt-4o-mini",    "tier": "fast",     "description": "Fast, cheap GPT-4 class model"},
    {"id": "gpt-4o",         "tier": "balanced", "description": "Full GPT-4o - balanced power and speed"},
    {"id": "gpt-4o",         "tier": "deep",     "description": "GPT-4o used for deep/complex tasks"},
    {"id": "gpt-3.5-turbo",  "tier": "legacy",   "description": "Legacy GPT-3.5, lowest cost"},
]

# Health check cache (60 s TTL)
_health_cache = {"timestamp": 0.0, "result": None}
_HEALTH_CACHE_TTL = 60


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    """Return OPENAI_API_KEY from environment."""
    return os.getenv("OPENAI_API_KEY", "")


def _resolve_model(model: str) -> str:
    """Resolve a tier alias or pass through a literal model name."""
    return _MODEL_TIERS.get(model, model)


def _openai_post(endpoint: str, payload: dict, timeout: int, api_key: str) -> dict:
    """Send a POST request to the OpenAI API and return the decoded JSON response.

    Args:
        endpoint: Path segment after /v1 (e.g. 'chat/completions').
        payload: Request body dictionary.
        timeout: Socket timeout in seconds.
        api_key: OpenAI API key for Authorization header.

    Returns:
        Decoded JSON response as a dict.

    Raises:
        urllib.error.HTTPError: On non-2xx HTTP response.
        Exception: On any other network or decode error.
    """
    url = f"{_OPENAI_API_BASE}/{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
@mcp_tool_handler
def openai_generate(
    prompt: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    timeout: int = 120,
    system_prompt: str = "",
    json_mode: bool = False,
) -> str:
    """Generate text using the OpenAI Chat Completions API.

    Supports all GPT-4o and GPT-4o-mini models via the standard chat
    completions endpoint. Accepts tier aliases (fast/balanced/deep) or
    literal model names.

    Args:
        prompt: User message to send.
        model: Model name or tier alias. Tier aliases: fast=gpt-4o-mini,
               balanced=gpt-4o, deep=gpt-4o. Literal names are passed through.
        temperature: Sampling temperature (0.0-2.0). Default 0.3.
        max_tokens: Maximum tokens in the completion. Default 4096.
        timeout: HTTP timeout in seconds. Default 120.
        system_prompt: Optional system message prepended to the conversation.
        json_mode: If True, set response_format to json_object and append a
                   JSON reminder to the prompt.
    """
    api_key = _get_api_key()
    if not api_key:
        return to_json({
            "success": False,
            "error": "OPENAI_API_KEY environment variable is not set",
            "has_api_key": False,
        })

    resolved_model = _resolve_model(model)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    actual_prompt = prompt
    if json_mode:
        actual_prompt = prompt + "\n\nIMPORTANT: Return ONLY valid JSON. No explanation or markdown."

    messages.append({"role": "user", "content": actual_prompt})

    payload = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    start = time.time()
    try:
        data = _openai_post("chat/completions", payload, timeout, api_key)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        return to_json({
            "success": False,
            "error": f"OpenAI API HTTP {e.code}: {body}",
            "status_code": e.code,
        })

    latency_ms = round((time.time() - start) * 1000)

    choice = data.get("choices", [{}])[0]
    response_text = choice.get("message", {}).get("content", "")
    usage = data.get("usage", {})

    return to_json({
        "success": True,
        "response": response_text,
        "model": resolved_model,
        "latency_ms": latency_ms,
        "usage": {
            "input_tokens":  usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens":  usage.get("total_tokens", 0),
        },
    })


@mcp.tool()
@mcp_tool_handler
def openai_health_check(force_refresh: bool = False) -> str:
    """Check OpenAI API availability with a lightweight probe.

    Sends a minimal chat completions request (1 token) to verify that the
    API key is valid and the endpoint is reachable. Results are cached for
    60 seconds to avoid repeated network calls.

    Args:
        force_refresh: If True, bypass the 60-second cache.
    """
    global _health_cache

    now = time.time()
    if not force_refresh and _health_cache["result"] is not None:
        age = now - _health_cache["timestamp"]
        if age < _HEALTH_CACHE_TTL:
            cached = json.loads(_health_cache["result"])
            cached["from_cache"] = True
            cached["cache_age_s"] = round(age, 1)
            return to_json(cached)

    api_key = _get_api_key()
    has_api_key = bool(api_key)

    if not has_api_key:
        result = {
            "success": True,
            "available": False,
            "has_api_key": False,
            "status": "no_api_key",
            "latency_ms": 0,
            "from_cache": False,
        }
        _health_cache["timestamp"] = now
        _health_cache["result"] = to_json(result)
        return to_json(result)

    start = time.time()
    try:
        _openai_post(
            "chat/completions",
            {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
                "temperature": 0,
            },
            timeout=5,
            api_key=api_key,
        )
        latency_ms = round((time.time() - start) * 1000)
        result = {
            "success": True,
            "available": True,
            "has_api_key": True,
            "status": "healthy",
            "latency_ms": latency_ms,
            "from_cache": False,
        }
    except urllib.error.HTTPError as e:
        latency_ms = round((time.time() - start) * 1000)
        if e.code == 401:
            status = "invalid_api_key"
            available = False
        elif e.code in (429, 503):
            status = "rate_limited_or_unavailable"
            available = False
        else:
            # Any other HTTP error still means the endpoint is reachable
            status = f"http_error_{e.code}"
            available = True
        result = {
            "success": True,
            "available": available,
            "has_api_key": True,
            "status": status,
            "latency_ms": latency_ms,
            "from_cache": False,
        }
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000)
        result = {
            "success": True,
            "available": False,
            "has_api_key": True,
            "status": "unreachable",
            "error": str(e)[:120],
            "latency_ms": latency_ms,
            "from_cache": False,
        }

    _health_cache["timestamp"] = now
    _health_cache["result"] = to_json(result)
    return to_json(result)


@mcp.tool()
@mcp_tool_handler
def openai_list_models() -> str:
    """List available OpenAI models with tier classification.

    Returns the static model catalog. Does not make a live API call so it
    always succeeds regardless of API key or network connectivity.
    """
    return to_json({
        "success": True,
        "models": _STATIC_MODELS,
        "tier_aliases": _MODEL_TIERS,
        "total": len(_STATIC_MODELS),
        "note": "Static catalog - tiers fast/balanced/deep map to specific model IDs",
    })


@mcp.tool()
@mcp_tool_handler
def openai_estimate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "gpt-4o-mini",
) -> str:
    """Estimate the USD cost of an OpenAI API call.

    Uses published pricing per 1M tokens. Accepts tier aliases (fast/balanced/deep)
    or literal model names.

    Pricing (USD per 1M tokens):
      gpt-4o-mini: input=$0.15, output=$0.60
      gpt-4o:      input=$2.50, output=$10.00

    Args:
        input_tokens: Number of prompt/input tokens.
        output_tokens: Number of completion/output tokens.
        model: Model name or tier alias (fast/balanced/deep).
    """
    resolved_model = _resolve_model(model)

    pricing = _MODEL_PRICING.get(resolved_model)
    if pricing is None:
        # Fall back to gpt-4o pricing for unknown models
        pricing = _MODEL_PRICING["gpt-4o"]
        note = f"Unknown model '{resolved_model}'; using gpt-4o pricing as estimate"
    else:
        note = None

    input_cost  = (input_tokens  / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total_cost  = input_cost + output_cost

    result = {
        "success": True,
        "model": resolved_model,
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd":  round(input_cost,  8),
        "output_cost_usd": round(output_cost, 8),
        "total_cost_usd":  round(total_cost,  8),
        "pricing_per_1m": {
            "input_usd":  pricing["input"],
            "output_usd": pricing["output"],
        },
    }
    if note:
        result["note"] = note

    return to_json(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")
