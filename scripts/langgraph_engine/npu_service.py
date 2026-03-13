"""
Intel AI Boost NPU Service - Local inference on Neural Processing Unit

Provides interface to Intel AI Boost NPU for:
- Step 1: Plan mode decision (super fast classification)
- Step 3: Task breakdown (lightweight reasoning)
- Step 5: Skill selection (pattern matching)

Configuration:
- Endpoint: C:\Users\techd\Downloads\intel-ai\npu\llama-cli-npu.exe
- Models: DeepSeek-R1-Distill-Qwen-1.5B (fastest), Llama-3.2-3B, DeepSeek-7B
- Speed: 2-3x faster than GPU for simple tasks
- Latency: <500ms for classification tasks
"""

import subprocess
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from loguru import logger


class NPUService:
    """Manages Intel AI Boost NPU inference for fast local LLM."""

    def __init__(self, npu_path: str = "C:/Users/techd/Downloads/intel-ai/npu"):
        """
        Initialize NPU service.

        Args:
            npu_path: Path to NPU executable directory
        """
        self.npu_path = Path(npu_path)
        self.cli_exe = self.npu_path / "llama-cli-npu.exe"
        self.models_path = self.npu_path.parent / "models" / "npu"

        # Validate NPU setup
        if not self.cli_exe.exists():
            raise RuntimeError(
                f"NPU CLI not found at {self.cli_exe}. "
                f"Install Intel AI Boost from C:\\Users\\techd\\Downloads\\intel-ai"
            )

        if not self.models_path.exists():
            raise RuntimeError(f"NPU models directory not found at {self.models_path}")

        # Model routing - fast models for NPU
        self.models = {
            "fast_classification": "DeepSeek-R1-Distill-Qwen-1.5B-Q6_K.gguf",  # Fastest
            "medium_reasoning": "Llama-3.2-3B-Instruct-Q6_K.gguf",  # Medium
            "deep_reasoning": "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",  # Best quality but slower
        }

        # Available models on disk
        self.available_models = self._check_available_models()

        logger.info(f"✓ NPU service initialized at {self.npu_path}")
        logger.info(f"  Available models: {len(self.available_models)}")
        logger.info(f"  Models: {', '.join([m.stem for m in self.available_models])}")

    def _check_available_models(self) -> List[Path]:
        """Check which GGUF models are available locally."""
        try:
            models = list(self.models_path.glob("*.gguf"))
            return sorted(models)
        except Exception as e:
            logger.error(f"Error checking NPU models: {e}")
            return []

    def _get_model_path(self, model_type: str = "fast_classification") -> Optional[Path]:
        """Get full path to a model file."""
        model_file = self.models.get(model_type, self.models["fast_classification"])
        model_path = self.models_path / model_file

        if not model_path.exists():
            logger.warning(
                f"Model {model_file} not found. Available: "
                f"{[m.name for m in self.available_models]}"
            )
            # Fallback to first available model
            if self.available_models:
                return self.available_models[0]
            return None

        return model_path

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "fast_classification",
        temperature: float = 0.3,
        max_tokens: int = 200,
    ) -> Dict[str, Any]:
        """
        Run inference on NPU using llama-cli.

        Args:
            messages: Chat messages (role, content)
            model: Model type (fast_classification, medium_reasoning, deep_reasoning)
            temperature: Generation temperature (0-1)
            max_tokens: Max response tokens

        Returns:
            Dict with 'message' containing response content
        """
        try:
            # Build prompt from messages
            prompt = ""
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    prompt += f"System: {content}\n"
                elif role == "user":
                    prompt += f"User: {content}\n"
                elif role == "assistant":
                    prompt += f"Assistant: {content}\n"

            prompt += "Assistant:"

            # Get model path
            model_path = self._get_model_path(model)
            if not model_path:
                return {"error": "No models available"}

            logger.debug(f"NPU inference: {model_path.name} (tokens: {max_tokens})")

            # Run NPU inference
            cmd = [
                str(self.cli_exe),
                "-m",
                str(model_path),
                "-n",
                str(max_tokens),
                "--temp",
                str(temperature),
                "--prompt",
                prompt,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 min timeout
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0:
                error_msg = f"NPU inference failed: {result.stderr}"
                logger.error(error_msg)
                return {"error": error_msg}

            # Parse output
            output = result.stdout.strip()
            response_text = output.split("Assistant:")[-1].strip() if "Assistant:" in output else output

            logger.debug(f"NPU response: {len(response_text)} chars")

            return {
                "message": {
                    "content": response_text,
                    "role": "assistant",
                },
                "model": model_path.name,
                "done": True,
                "source": "npu",
            }

        except subprocess.TimeoutExpired:
            logger.error("NPU inference timeout (120s)")
            return {"error": "NPU inference timeout"}
        except Exception as e:
            logger.error(f"NPU inference error: {e}")
            return {"error": str(e)}

    def step1_plan_mode_decision(self, toon: Dict[str, Any], user_requirement: str) -> Dict[str, Any]:
        """Fast plan decision on NPU."""
        prompt = f"""Analyze project TOON and user requirement.
Determine if PLAN MODE is required (complexity {toon.get('complexity_score', 0)}/10).

Respond with ONLY valid JSON:
{{"plan_required": true/false, "reasoning": "brief", "risk_level": "low/medium/high"}}"""

        response = self.chat(
            messages=[{"role": "user", "content": prompt}],
            model="fast_classification",
            max_tokens=100,
        )

        if "error" in response:
            logger.error(f"Step 1 plan decision failed: {response['error']}")
            return {
                "plan_required": True,
                "reasoning": "NPU error, defaulting to plan mode",
                "risk_level": "medium",
            }

        try:
            content = response.get("message", {}).get("content", "{}")
            result = json.loads(content)
            return result
        except json.JSONDecodeError:
            logger.warning(f"Step 1 JSON parse error: {content}")
            return {
                "plan_required": True,
                "reasoning": "JSON parse error, defaulting to plan mode",
                "risk_level": "medium",
            }

    def step3_task_breakdown(self, plan: str, complexity: int) -> Dict[str, Any]:
        """Break plan into tasks on NPU."""
        prompt = f"""Break this plan into structured tasks (complexity {complexity}/10):
{plan[:500]}

Return tasks as JSON array: [{{"id": "Task-1", "description": "...", "files": [...]}}, ...]"""

        response = self.chat(
            messages=[{"role": "user", "content": prompt}],
            model="fast_classification" if complexity < 6 else "medium_reasoning",
            max_tokens=300,
        )

        if "error" in response:
            return {"success": False, "error": response["error"]}

        try:
            content = response.get("message", {}).get("content", "[]")
            tasks = json.loads(content)
            return {"success": True, "tasks": tasks}
        except json.JSONDecodeError:
            return {"success": False, "error": "Failed to parse task breakdown"}


def get_npu_service(npu_path: str = "C:/Users/techd/Downloads/intel-ai/npu") -> Optional[NPUService]:
    """Get or create singleton NPU service instance."""
    try:
        if not hasattr(get_npu_service, "_instance"):
            get_npu_service._instance = NPUService(npu_path)
        return get_npu_service._instance
    except Exception as e:
        logger.warning(f"NPU service not available: {e}")
        return None
