"""
Ollama Provider MCP Server - Focused local Ollama inference via FastMCP.

Pure Ollama-only server. No Anthropic, no OpenAI, no llm_call.py dependency.
All HTTP via stdlib urllib.request only.

Transport: stdio

Tools (5):
  ollama_generate, ollama_list_models, ollama_health_check,
  ollama_discover_local_models, ollama_pull_model
"""

import json
import os
import sys
from pathlib import Path

# Ensure src/mcp/ is in path for base package imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP
from base.response import to_json
from base.decorators import mcp_tool_handler

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "ollama-provider",
    instructions="Local Ollama GPU inference - model management, generation, health",
)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _ollama_endpoint() -> str:
    """Return the configured Ollama base URL (no trailing slash)."""
    return os.getenv("OLLAMA_ENDPOINT", "http://127.0.0.1:11434").rstrip("/")


# ---------------------------------------------------------------------------
# Health check cache (30s TTL)
# ---------------------------------------------------------------------------

_health_cache: dict = {"timestamp": 0.0, "result": None}
_HEALTH_CACHE_TTL = 30  # seconds


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
@mcp_tool_handler
def ollama_generate(
    prompt: str,
    model: str = "qwen2.5:7b",
    temperature: float = 0.3,
    timeout: int = 30,
    json_mode: bool = False,
) -> str:
    """Generate text via direct HTTP call to the local Ollama API.

    No fallback chain. Fails explicitly when Ollama is unavailable.

    Args:
        prompt: The prompt text to send.
        model: Ollama model name (default: qwen2.5:7b).
        temperature: Sampling temperature 0.0-1.0 (default: 0.3).
        timeout: HTTP request timeout in seconds (default: 30).
        json_mode: If True, append a JSON-only instruction to the prompt.

    Returns:
        JSON string with keys: success, response, model, temperature, latency_ms.
    """
    import time
    import urllib.request
    import urllib.error

    try:
        endpoint = _ollama_endpoint()

        actual_prompt = prompt
        if json_mode:
            actual_prompt = (
                prompt
                + "\n\nIMPORTANT: Return ONLY valid JSON. No explanation or markdown."
            )

        payload = json.dumps({
            "model": model,
            "prompt": actual_prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{endpoint}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = round((time.time() - start) * 1000)
            data = json.loads(resp.read().decode("utf-8"))

        response_text = data.get("response", "")
        if not response_text.strip():
            return to_json({
                "success": False,
                "error": "Ollama returned an empty response",
                "model": model,
            })

        return to_json({
            "success": True,
            "response": response_text,
            "model": model,
            "temperature": temperature,
            "latency_ms": latency_ms,
        })

    except urllib.error.URLError as exc:
        return to_json({
            "success": False,
            "error": f"Ollama unreachable: {exc.reason}",
            "endpoint": _ollama_endpoint(),
        })
    except Exception as exc:
        return to_json({"success": False, "error": str(exc)})


@mcp.tool()
@mcp_tool_handler
def ollama_list_models() -> str:
    """List all models currently available in the local Ollama instance.

    Calls GET /api/tags on the configured Ollama endpoint.

    Returns:
        JSON string with keys: success, models (list of {name, size_gb, modified}),
        total.
    """
    import urllib.request
    import urllib.error

    try:
        endpoint = _ollama_endpoint()
        req = urllib.request.Request(
            f"{endpoint}/api/tags",
            method="GET",
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        models = []
        for m in data.get("models", []):
            size_bytes = m.get("size", 0)
            models.append({
                "name": m.get("name", ""),
                "size_gb": round(size_bytes / (1024 ** 3), 2),
                "modified": m.get("modified_at", ""),
            })

        return to_json({
            "success": True,
            "models": models,
            "total": len(models),
        })

    except urllib.error.URLError as exc:
        return to_json({
            "success": False,
            "error": f"Ollama unreachable: {exc.reason}",
            "endpoint": _ollama_endpoint(),
        })
    except Exception as exc:
        return to_json({"success": False, "error": str(exc)})


@mcp.tool()
@mcp_tool_handler
def ollama_health_check() -> str:
    """Quick availability probe to the configured Ollama endpoint.

    Result is cached for 30 seconds to avoid hammering the endpoint on
    repeated calls (e.g., pipeline health checks before each step).

    Returns:
        JSON string with keys: success, available, latency_ms, endpoint,
        model_count, from_cache.
    """
    import time
    import urllib.request
    import urllib.error

    now = time.time()
    cache_age = now - _health_cache["timestamp"]

    # Serve cached result if still fresh
    if _health_cache["result"] is not None and cache_age < _HEALTH_CACHE_TTL:
        cached = dict(json.loads(_health_cache["result"]))
        cached["from_cache"] = True
        cached["cache_age_s"] = round(cache_age, 1)
        return to_json(cached)

    endpoint = _ollama_endpoint()
    try:
        req = urllib.request.Request(
            f"{endpoint}/api/tags",
            method="GET",
        )

        start = time.time()
        with urllib.request.urlopen(req, timeout=5) as resp:
            latency_ms = round((time.time() - start) * 1000)
            data = json.loads(resp.read().decode("utf-8"))

        model_count = len(data.get("models", []))

        result = {
            "success": True,
            "available": True,
            "latency_ms": latency_ms,
            "endpoint": endpoint,
            "model_count": model_count,
            "from_cache": False,
        }

    except urllib.error.URLError as exc:
        result = {
            "success": True,  # The tool itself succeeded; Ollama is just down
            "available": False,
            "latency_ms": None,
            "endpoint": endpoint,
            "model_count": 0,
            "error": f"Ollama unreachable: {exc.reason}",
            "from_cache": False,
        }
    except Exception as exc:
        result = {
            "success": True,
            "available": False,
            "latency_ms": None,
            "endpoint": endpoint,
            "model_count": 0,
            "error": str(exc),
            "from_cache": False,
        }

    # Update cache
    _health_cache["timestamp"] = time.time()
    _health_cache["result"] = json.dumps(result)

    return to_json(result)


@mcp.tool()
@mcp_tool_handler
def ollama_discover_local_models() -> str:
    """Discover local model files and Ollama-registered models.

    Scans:
    - Ollama API (/api/tags) for registered models.
    - ~/.ollama/models/ for any files present in the Ollama model store.
    - Directory specified by INTEL_AI_MODELS_PATH env var for .gguf files.

    Returns:
        JSON string with keys: success, ollama_models (list), local_gguf_files
        (list), total.
    """
    import urllib.request
    import urllib.error

    endpoint = _ollama_endpoint()
    ollama_models = []
    local_gguf_files = []

    # --- Ollama API models ---
    try:
        req = urllib.request.Request(
            f"{endpoint}/api/tags",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        for m in data.get("models", []):
            size_bytes = m.get("size", 0)
            ollama_models.append({
                "name": m.get("name", ""),
                "size_gb": round(size_bytes / (1024 ** 3), 2),
                "modified": m.get("modified_at", ""),
                "source": "ollama_api",
            })
    except Exception:
        # Ollama not running is non-fatal for discovery
        pass

    # --- Local .gguf files ---
    search_dirs = [
        Path.home() / ".ollama" / "models",
        Path(os.getenv("INTEL_AI_MODELS_PATH", str(Path.home() / "intel-ai" / "models"))),
    ]

    seen_paths: set = set()
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for gguf_file in search_dir.rglob("*.gguf"):
            path_str = str(gguf_file)
            if path_str in seen_paths:
                continue
            seen_paths.add(path_str)
            try:
                size_gb = round(gguf_file.stat().st_size / (1024 ** 3), 2)
            except OSError:
                size_gb = 0.0
            local_gguf_files.append({
                "name": gguf_file.stem,
                "path": path_str,
                "size_gb": size_gb,
                "source": "local_gguf",
            })

    total = len(ollama_models) + len(local_gguf_files)

    return to_json({
        "success": True,
        "ollama_models": ollama_models,
        "local_gguf_files": local_gguf_files,
        "total": total,
    })


@mcp.tool()
@mcp_tool_handler
def ollama_pull_model(model_name: str) -> str:
    """Pull a model from the Ollama registry to the local instance.

    Sends a POST to /api/pull. The Ollama daemon streams progress but this
    tool waits for completion and returns a summary status. Use a generous
    timeout for large models (multi-GB downloads).

    Args:
        model_name: The Ollama model identifier, e.g. 'qwen2.5:7b' or
            'llama3:8b-instruct'.

    Returns:
        JSON string with keys: success, model, status.
    """
    import urllib.request
    import urllib.error

    if not model_name or not model_name.strip():
        return to_json({
            "success": False,
            "error": "model_name must not be empty",
        })

    model_name = model_name.strip()
    endpoint = _ollama_endpoint()

    try:
        payload = json.dumps({
            "name": model_name,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{endpoint}/api/pull",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        # Large models can take many minutes; use a long timeout
        with urllib.request.urlopen(req, timeout=600) as resp:
            raw = resp.read().decode("utf-8")

        # Ollama may return multiple JSON objects on separate lines when not
        # streaming. Parse the last non-empty line to get the final status.
        status = "unknown"
        for line in reversed(raw.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                status = obj.get("status", "unknown")
            except json.JSONDecodeError:
                pass
            break

        return to_json({
            "success": True,
            "model": model_name,
            "status": status,
        })

    except urllib.error.URLError as exc:
        return to_json({
            "success": False,
            "error": f"Ollama unreachable: {exc.reason}",
            "model": model_name,
            "endpoint": endpoint,
        })
    except Exception as exc:
        return to_json({
            "success": False,
            "error": str(exc),
            "model": model_name,
        })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
