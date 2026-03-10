#!/usr/bin/env python3
"""
Wrapper for 3-level-flow.py that sets environment variables on Windows.

On Windows, the hook syntax VAR=value python script.py doesn't work.
This wrapper handles env vars properly and passes stdin to the main script.
"""
import os
import sys
import subprocess

# Set environment variables
os.environ["OLLAMA_MODEL"] = "qwen2.5:7b"
os.environ["OLLAMA_ENDPOINT"] = "http://localhost:11434/api/generate"

# Use quick version for hooks (Level -1 only, fast)
# Full 3-level execution happens during actual prompt processing
script_path = os.path.join(os.path.dirname(__file__), "3-level-flow-quick.py")

try:
    # Run the main script with no stdin (hook doesn't have proper stdin)
    # This prevents script from hanging waiting for user message
    result = subprocess.run(
        [sys.executable, script_path],
        stdin=subprocess.DEVNULL,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    sys.exit(result.returncode)
except Exception as e:
    print(f"[ERROR] 3-level-flow wrapper failed: {e}", file=sys.stderr)
    sys.exit(1)
