"""
Inference Configuration - GPU vs NPU routing and model setup

Supports Intel AI setup with GPU (Ollama) and NPU (Intel AI Boost)
"""

import os
from pathlib import Path
from typing import Literal


class InferenceConfig:
    """Configuration for inference backends."""

    # ============================================================================
    # INFERENCE MODE - Choose between GPU, NPU, or Auto routing
    # ============================================================================

    # Mode options: "auto" | "gpu_only" | "npu_only"
    # - "auto": Smart routing (fast tasks→NPU, complex tasks→GPU)
    # - "gpu_only": Use only Ollama GPU
    # - "npu_only": Use only Intel AI Boost NPU
    INFERENCE_MODE: Literal["auto", "gpu_only", "npu_only"] = os.getenv(
        "INFERENCE_MODE", "auto"
    )

    # ============================================================================
    # GPU SETUP (Ollama with Intel Arc)
    # ============================================================================

    GPU_ENABLED = True
    GPU_ENDPOINT = "http://127.0.0.1:11434"
    GPU_MODELS_PATH = "C:\\Users\\techd\\Downloads\\intel-ai\\models\\gpu"
    GPU_EXECUTABLE = "C:\\Users\\techd\\Downloads\\intel-ai\\gpu\\ollama.exe"

    # GPU startup command (Windows)
    GPU_STARTUP_COMMAND = (
        'start "Ollama GPU Server" cmd /k '
        '"cd /d C:\\Users\\techd\\Downloads\\intel-ai\\gpu && '
        "set OLLAMA_NUM_GPU=33 && "
        "set ZES_ENABLE_SYSMAN=1 && "
        "set SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS=1 && "
        "set SYCL_CACHE_PERSISTENT=1 && "
        "set ONEAPI_DEVICE_SELECTOR=level_zero:0 && "
        "set OLLAMA_KEEP_ALIVE=10m && "
        "set OLLAMA_NUM_PARALLEL=1 && "
        "set OLLAMA_HOST=127.0.0.1:11434 && "
        "ollama.exe serve"
        '"'
    )

    # Available GPU models (from GPU mode)
    GPU_MODELS = {
        "fast_classification": "qwen2.5:7b",  # For fast tasks
        "complex_reasoning": "granite4:3b",   # For complex reasoning
        "synthesis": "qwen2.5:7b",            # For prompt generation
    }

    # ============================================================================
    # NPU SETUP (Intel AI Boost - llama-cli-npu)
    # ============================================================================

    NPU_ENABLED = True
    NPU_PATH = "C:\\Users\\techd\\Downloads\\intel-ai\\npu"
    NPU_CLI_EXE = "C:\\Users\\techd\\Downloads\\intel-ai\\npu\\llama-cli-npu.exe"
    NPU_MODELS_PATH = "C:\\Users\\techd\\Downloads\\intel-ai\\models\\npu"

    # Available NPU models (GGUF format)
    NPU_MODELS = {
        "fast_classification": "DeepSeek-R1-Distill-Qwen-1.5B-Q6_K.gguf",  # 1.46GB, fastest
        "medium_reasoning": "Llama-3.2-3B-Instruct-Q6_K.gguf",             # 2.64GB
        "deep_reasoning": "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",       # 4.68GB, best quality
    }

    # ============================================================================
    # ROUTING STRATEGY - Which tasks go to which backend
    # ============================================================================

    TASK_ROUTING = {
        # Fast tasks → NPU (2-3x faster)
        "classification": "npu",
        "plan_decision": "npu",
        "simple_analysis": "npu",
        "pattern_matching": "npu",
        "task_breakdown": "npu",

        # Complex tasks → GPU (better quality)
        "reasoning": "gpu",
        "planning": "gpu",
        "synthesis": "gpu",
        "skill_selection": "gpu",
        "code_generation": "gpu",

        # Complexity-based routing
        "auto": "npu_if_complexity_<=5_else_gpu",
    }

    # ============================================================================
    # PERFORMANCE TARGETS
    # ============================================================================

    # NPU performance expectations
    NPU_TARGET_LATENCY_MS = 500  # NPU should respond in <500ms
    NPU_TARGET_THROUGHPUT = 50   # Tokens per second

    # GPU performance expectations
    GPU_TARGET_LATENCY_MS = 1000  # GPU slightly slower but better quality
    GPU_TARGET_THROUGHPUT = 30    # Tokens per second

    # ============================================================================
    # FALLBACK STRATEGY
    # ============================================================================

    # If NPU fails, fallback to GPU
    # If GPU fails, fallback to NPU
    # If both fail, use Claude API (if configured via ANTHROPIC_KEY)
    AUTO_FALLBACK = True

    # ============================================================================
    # STARTUP HELPERS
    # ============================================================================

    @staticmethod
    def get_gpu_startup_instruction() -> str:
        """Get instruction for starting GPU."""
        return (
            "GPU (Ollama with Intel Arc) not running.\n"
            "To start:\n"
            "  1. Open Command Prompt\n"
            "  2. cd C:\\Users\\techd\\Downloads\\intel-ai\\gpu\n"
            "  3. Set environment variables:\n"
            "     set OLLAMA_NUM_GPU=33\n"
            "     set ZES_ENABLE_SYSMAN=1\n"
            "     set SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS=1\n"
            "     set SYCL_CACHE_PERSISTENT=1\n"
            "     set ONEAPI_DEVICE_SELECTOR=level_zero:0\n"
            "     set OLLAMA_KEEP_ALIVE=10m\n"
            "     set OLLAMA_NUM_PARALLEL=1\n"
            "     set OLLAMA_HOST=127.0.0.1:11434\n"
            "  4. ollama.exe serve\n"
        )

    @staticmethod
    def get_npu_startup_instruction() -> str:
        """Get instruction for starting NPU."""
        return (
            "NPU (Intel AI Boost) not available.\n"
            "Required files:\n"
            "  - C:\\Users\\techd\\Downloads\\intel-ai\\npu\\llama-cli-npu.exe\n"
            "  - Models in C:\\Users\\techd\\Downloads\\intel-ai\\models\\npu\\\n"
            "\n"
            "If not installed, download Intel AI setup from:\n"
            "  https://github.com/intel-analytics/ipex-llm/releases\n"
        )

    @staticmethod
    def validate_setup() -> dict:
        """Validate GPU and NPU setup."""
        results = {
            "gpu_ready": False,
            "npu_ready": False,
            "errors": [],
        }

        # Check GPU
        gpu_exe = Path(InferenceConfig.GPU_EXECUTABLE)
        gpu_models = Path(InferenceConfig.GPU_MODELS_PATH)

        if gpu_exe.exists() and gpu_models.exists():
            results["gpu_ready"] = True
        else:
            if not gpu_exe.exists():
                results["errors"].append(f"GPU exe not found: {gpu_exe}")
            if not gpu_models.exists():
                results["errors"].append(f"GPU models not found: {gpu_models}")

        # Check NPU
        npu_cli = Path(InferenceConfig.NPU_CLI_EXE)
        npu_models = Path(InferenceConfig.NPU_MODELS_PATH)

        if npu_cli.exists() and npu_models.exists():
            results["npu_ready"] = True
        else:
            if not npu_cli.exists():
                results["errors"].append(f"NPU CLI not found: {npu_cli}")
            if not npu_models.exists():
                results["errors"].append(f"NPU models not found: {npu_models}")

        return results
