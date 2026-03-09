#!/usr/bin/env python3
"""
Level 3 Step 7 - Auto Recommendations (with Ollama)

Uses local LLM to suggest improvements and best practices.
"""

import json
import sys
import os
import urllib.request
import urllib.error


def main():
    """Generate recommendations using Ollama LLM."""
    ollama_endpoint = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434/api/generate")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    # Get task type from args if provided
    task_type = "General"
    for arg in sys.argv[1:]:
        if not arg.startswith('--'):
            task_type = arg
            break

    # Use Ollama to suggest improvements
    prompt = f"""Suggest 3-5 best practice recommendations for: {task_type}

Respond ONLY with JSON (no markdown):
{{
  "recommendations": [
    "recommendation 1",
    "recommendation 2",
    ...
  ]
}}

JSON only:"""

    try:
        payload = {
            "model": ollama_model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.5
        }
        req = urllib.request.Request(
            ollama_endpoint,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            llm_response = result.get("response", "")

        # Parse JSON from response
        if "{" in llm_response:
            json_start = llm_response.index("{")
            json_end = llm_response.rindex("}") + 1
            llm_result = json.loads(llm_response[json_start:json_end])
            recommendations = llm_result.get("recommendations", [])
        else:
            recommendations = ["Code review recommended", "Add tests", "Document changes"]

    except Exception:
        # Fallback
        recommendations = ["Code review recommended", "Add tests", "Document changes"]

    output = {
        "recommendations": recommendations,
        "task_type": task_type,
        "status": "OK"
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
