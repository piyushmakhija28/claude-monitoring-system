#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI-Based Task Type Detector using Trybonsai API

Instead of fragile keyword matching, use frontier AI models to intelligently
classify user prompts into task types.

REPLACES: Keyword-based detect_task_type() in prompt-generation-policy.py

Supported Models (via Trybonsai):
- Claude Sonnet/Opus
- GPT-5
- Grok
- Gemini
- Qwen
- GLM

Usage:
  python ai-task-type-detector.py --detect "user prompt here"
  python ai-task-type-detector.py --api-key YOUR_KEY

Environment:
  Set TRYBONSAI_API_KEY for authentication
"""

import sys
import json
import os
from pathlib import Path
from typing import Dict, Optional
import urllib.request
import urllib.error

# Task types we support
SUPPORTED_TASK_TYPES = [
    "Design",              # UI/UX, interface, layout, styling
    "API Creation",        # REST endpoints, microservices, CRUD
    "Authentication",      # Login, JWT, OAuth, security
    "Authorization",       # Roles, permissions, access control
    "Database",            # Tables, schemas, entities, queries
    "Configuration",       # Setup, settings, environment
    "Bug Fix",             # Errors, issues, patches
    "Refactoring",         # Code quality, improvements, optimization
    "Security",            # Encryption, vulnerabilities, hardening
    "Testing",             # Unit tests, integration tests, QA
    "Documentation",       # README, comments, guides
    "General Task"         # Default fallback
]

class AiTaskTypeDetector:
    """
    Intelligent task type detection using Trybonsai API.

    Instead of keyword matching, send the user's prompt to a frontier LLM
    and ask it to classify the task. Much more robust and handles varied
    natural language inputs.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Trybonsai API key.

        Reads from (in priority order):
        1. api_key parameter (passed directly)
        2. TRYBONSAI_API_KEY environment variable
        3. ~/.claude/trybonsai.conf file
        """
        self.api_key = api_key

        # Try environment variable
        if not self.api_key:
            self.api_key = os.getenv("TRYBONSAI_API_KEY")

        # Try config file
        if not self.api_key:
            config_file = Path.home() / ".claude" / "trybonsai.conf"
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Remove BOM if present
                        if content.startswith('\ufeff'):
                            content = content[1:]
                        # Parse lines
                        for line in content.split('\n'):
                            line = line.strip()
                            if line.startswith("TRYBONSAI_API_KEY="):
                                self.api_key = line.split("=", 1)[1].strip()
                                break
                except Exception:
                    pass

        if not self.api_key:
            raise ValueError(
                "TRYBONSAI_API_KEY not found. Set it using one of:\n"
                "  1. export TRYBONSAI_API_KEY=\"your-key\" (environment variable)\n"
                "  2. Create ~/.claude/trybonsai.conf with: TRYBONSAI_API_KEY=your-key\n"
                "  3. Pass --api-key parameter: python ... --api-key \"your-key\""
            )

        # Trybonsai API endpoint using Anthropic message format
        # Correct endpoint: go.trybons.ai/v1/messages (not api.trybons.ai/v1/chat/completions)
        self.api_endpoint = "https://go.trybons.ai/v1/messages"

        # System prompt for classification
        self.system_prompt = """You are a task classifier. Analyze the user's request and determine the task type.

Return a JSON object with exactly these fields:
{
  "task_type": "one of: Design, API Creation, Authentication, Authorization, Database, Configuration, Bug Fix, Refactoring, Security, Testing, Documentation, General Task",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}

Be precise. Examples:
- "redesign the login form" → Design (high confidence)
- "create user endpoint" → API Creation
- "fix database timeout error" → Bug Fix
- "add encryption to passwords" → Security
- "what's the best practice?" → General Task

Return ONLY the JSON object, no other text."""

    def detect(self, user_message: str) -> Dict:
        """
        Detect task type using Trybonsai API (NO FALLBACK).

        API-FIRST approach:
        - Call Trybonsai API
        - Return AI classification
        - Fail explicitly if API unavailable (don't use broken keywords)
        - User upgrades to paid API if free tier insufficient

        Args:
            user_message: User's prompt/request

        Returns:
            Dict with keys: task_type, confidence, reasoning

        Raises:
            Exception: If API call fails (no silent fallback)
        """
        # Call Trybonsai API (this will raise if API fails)
        response = self._call_api(user_message)

        # Parse and return response
        result = self._parse_response(response)

        return result

    def _call_api(self, user_message: str) -> str:
        """Call Trybonsai API and return response (Anthropic message format)."""

        # Request payload using Anthropic's message format
        payload = {
            "model": "anthropic/claude-sonnet-4.5",  # From techdeveloper scheduler config
            "system": self.system_prompt,  # Anthropic uses 'system' field separately
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            "temperature": 0.2,  # Low temp for consistent classification
            "max_tokens": 200
        }

        # HTTP request headers (Anthropic API format used by Trybonsai)
        headers = {
            "x-api-key": self.api_key,  # Anthropic uses x-api-key, not Bearer token
            "anthropic-version": "2023-06-01",  # Required Anthropic API version
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"  # Bypass Cloudflare
        }

        request = urllib.request.Request(
            self.api_endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read().decode('utf-8')
                return body
        except urllib.error.HTTPError as e:
            raise Exception(f"API HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(f"API connection failed: {e.reason}")

    def _parse_response(self, response_text: str) -> Dict:
        """Parse Trybonsai API response (Anthropic message format)."""
        try:
            response_json = json.loads(response_text)

            # Extract content from Anthropic response format
            # Anthropic returns: {"content": [{"type": "text", "text": "..."}], ...}
            if "content" not in response_json:
                raise ValueError("Invalid response format: missing 'content' field")

            # Get the text content
            content_blocks = response_json.get("content", [])
            if not content_blocks or content_blocks[0].get("type") != "text":
                raise ValueError("Invalid response format: no text content")

            content = content_blocks[0].get("text", "").strip()

            # Parse the JSON from content
            classification = json.loads(content)

            # Validate task type
            task_type = classification.get("task_type", "General Task")
            if task_type not in SUPPORTED_TASK_TYPES:
                task_type = "General Task"

            return {
                "task_type": task_type,
                "confidence": float(classification.get("confidence", 0.5)),
                "reasoning": classification.get("reasoning", "")
            }
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            raise ValueError(f"Failed to parse API response: {str(e)}")

    @staticmethod
    def is_available() -> bool:
        """Check if Trybonsai API is available."""
        return bool(os.getenv("TRYBONSAI_API_KEY"))


def main():
    """CLI interface for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="AI Task Type Detector")
    parser.add_argument("--detect", type=str, help="Detect task type for prompt")
    parser.add_argument("--api-key", type=str, help="Trybonsai API key")
    parser.add_argument("--test", action="store_true", help="Run test cases")

    args = parser.parse_args()

    # Initialize detector
    try:
        detector = AiTaskTypeDetector(api_key=args.api_key)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.test:
        # Test cases
        test_prompts = [
            "redesign the login page",
            "create a REST API for users",
            "fix the database timeout issue",
            "add JWT authentication",
            "improve code performance",
            "write unit tests for auth service",
            "what's the best way to learn Python?"
        ]

        print("=" * 80)
        print("AI TASK TYPE DETECTOR - TEST CASES")
        print("=" * 80)

        for prompt in test_prompts:
            result = detector.detect(prompt)
            print(f"\nPrompt: {prompt}")
            print(f"  Task Type: {result['task_type']}")
            print(f"  Confidence: {result['confidence']:.1%}")
            print(f"  Reasoning: {result['reasoning']}")

    elif args.detect:
        result = detector.detect(args.detect)
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
