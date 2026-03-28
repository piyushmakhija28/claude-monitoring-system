# Runbook: LLM Provider Failure

**Severity:** High
**Component:** llm_mcp_server.py, LLM hybrid inference layer
**Provider Chain:** Anthropic -> OpenAI -> Ollama (qwen2.5:7b) -> NPU

---

## Overview

The pipeline uses a GPU-first, cost-aware fallback chain across four LLM
providers. When the primary provider fails, the engine automatically tries the
next in sequence. This runbook covers diagnosis and manual recovery for each
provider.

Fallback chain (in priority order):

```
1. Anthropic (Claude API)     -- remote, pay-per-token
2. OpenAI (GPT-4o / GPT-4)   -- remote, pay-per-token
3. Ollama (qwen2.5:7b)        -- local GPU inference
4. NPU (on-device inference)  -- local, lowest latency
```

---

## Symptom

Pipeline logs show provider errors:

```
[llm_provider] Anthropic call failed: 529 Overloaded
[llm_provider] Falling back to openai
[llm_provider] OpenAI call failed: APIConnectionError
[llm_provider] Falling back to ollama
[llm_provider] All providers exhausted - no response available
```

Or the pipeline stalls at a step with no LLM response and no error (silent
timeout).

---

## Provider 1: Anthropic

### Diagnosis

```bash
# Test API key and connectivity
curl -s -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-haiku-20240307","max_tokens":10,"messages":[{"role":"user","content":"ping"}]}'
```

Expected: JSON with `content` field.

Common failures:

| Error | Cause | Fix |
|-------|-------|-----|
| 401 Unauthorized | Invalid or expired API key | Rotate key in `.env`, update `ANTHROPIC_API_KEY` |
| 529 Overloaded | Anthropic capacity | Wait and retry, or skip to OpenAI (see Step 3) |
| 429 Rate Limited | Too many requests | Implement exponential backoff; reduce concurrent steps |
| SSL error | Corporate proxy / firewall | Set `HTTPS_PROXY` or whitelist `api.anthropic.com` |

### Check API key in environment

```bash
python -c "import os; k = os.getenv('ANTHROPIC_API_KEY', ''); print('Set:', bool(k), '| Length:', len(k))"
```

Expected: `Set: True | Length: 108` (Claude API keys are ~108 chars).

---

## Provider 2: OpenAI

### Diagnosis

```bash
# Test connectivity
curl -s https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | python -c "import sys,json; d=json.load(sys.stdin); print('Models:', len(d.get('data', [])))"
```

Expected: `Models: <N>` where N > 0.

Common failures:

| Error | Cause | Fix |
|-------|-------|-----|
| 401 | Invalid API key | Rotate key in `.env`, update `OPENAI_API_KEY` |
| 429 | Quota exceeded | Check billing on platform.openai.com |
| 503 | OpenAI outage | Check https://status.openai.com |
| Timeout | Network issue | Check proxy settings or try `OPENAI_BASE_URL` override |

---

## Provider 3: Ollama (Local GPU)

### Diagnosis

```bash
# Check Ollama process
curl -s http://localhost:11434/api/tags | python -c "import sys,json; d=json.load(sys.stdin); [print(m['name']) for m in d.get('models',[])]"
```

Expected: `qwen2.5:7b` in the list.

If Ollama is not running:

```bash
# Start Ollama (Windows)
ollama serve &

# Pull the model if missing
ollama pull qwen2.5:7b
```

Common failures:

| Error | Cause | Fix |
|-------|-------|-----|
| Connection refused :11434 | Ollama not running | `ollama serve` |
| Model not found | Model not pulled | `ollama pull qwen2.5:7b` |
| Out of VRAM | GPU memory exhausted | Use `--gpu-layers 0` for CPU fallback or reduce batch size |
| Slow response (>60s) | CPU inference | Check GPU utilization with `nvidia-smi` |

### Change Ollama endpoint

```bash
# In .env
OLLAMA_ENDPOINT=http://localhost:11434
```

---

## Provider 4: NPU (On-Device)

### Diagnosis

NPU inference requires hardware support (Intel NPU, Apple Neural Engine, or
Qualcomm NPU). Check availability:

```bash
python -c "
try:
    import openvino as ov
    core = ov.Core()
    print('Available devices:', core.available_devices)
except ImportError:
    print('OpenVINO not installed')
"
```

Expected: `Available devices: ['CPU', 'GPU', 'NPU']` or similar.

Common failures:

| Error | Cause | Fix |
|-------|-------|-----|
| Device NPU not found | Hardware not present | Fall back to CPU mode |
| Driver error | NPU driver outdated | Update Intel NPU driver |
| Model not compiled | Model not converted for NPU | Run NPU compilation step |

---

## Force a Specific Provider

To bypass the fallback chain and force a specific provider for debugging:

```bash
# Force Anthropic
export FORCE_LLM_PROVIDER=anthropic

# Force Ollama
export FORCE_LLM_PROVIDER=ollama

# Force OpenAI
export FORCE_LLM_PROVIDER=openai

# Force NPU
export FORCE_LLM_PROVIDER=npu

python scripts/3-level-flow.py --task "your task"
```

After debugging, unset the override to restore automatic fallback:

```bash
unset FORCE_LLM_PROVIDER
```

---

## All Providers Exhausted

If the fallback chain is fully exhausted (all four providers fail):

1. Check network connectivity: `curl -s https://api.anthropic.com/health`
2. Confirm at least one local provider (Ollama or NPU) is operational.
3. Check `.env` for missing keys:
   ```bash
   python -c "
   import os
   for k in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'OLLAMA_ENDPOINT']:
       v = os.getenv(k, '')
       print(k, ':', 'SET' if v else 'MISSING')
   "
   ```
4. Run `python src/mcp/llm_mcp_server.py --health` to get per-provider status.
5. If all remote providers are down, ensure Ollama is running with the required
   model and re-run the pipeline.

---

## Recovery

After restoring any provider:

```bash
# Verify the provider chain is healthy
python -c "
import sys; sys.path.insert(0, 'src/mcp')
from llm_mcp_server import check_provider_health
import asyncio
results = asyncio.run(check_provider_health())
for provider, status in results.items():
    print(provider, ':', status)
"
```

Then re-run the failed pipeline step from the last checkpoint.
