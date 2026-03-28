# Deployment Guide

**Project:** Claude Workflow Engine
**Version:** 1.6.1
**Last Updated:** 2026-03-27

---

## Prerequisites

| Requirement | Minimum Version | Notes |
|-------------|-----------------|-------|
| Python | 3.8 | 3.11 recommended |
| pip | 23.0 | `pip install --upgrade pip` |
| Git | 2.40 | Required for GitPython |
| Docker | 24.0 | Optional (local dev only) |
| Docker Compose | 2.20 | Optional (local dev only) |
| NVIDIA GPU driver | 525+ | Optional (Ollama GPU inference) |
| Ollama | 0.1.30 | Optional (local LLM fallback) |

---

## First-Time Setup

### 1. Clone and enter the repository

```bash
git clone https://github.com/techdeveloper-org/claude-workflow-engine.git
cd claude-workflow-engine
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Create environment file

```bash
cp .env.example .env
```

Edit `.env` and fill in all required values (see Environment Variables section).

### 5. Verify Qdrant storage directory

```bash
mkdir -p .qdrant_data
python -c "from qdrant_client import QdrantClient; c = QdrantClient(path='.qdrant_data'); print('Qdrant OK')"
```

### 6. Download the embedding model

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2'); print('Model OK')"
```

The model (~90 MB) is cached in `~/.cache/huggingface/` after first download.

### 7. Run the test suite

```bash
pytest tests/ -q --tb=short
```

All tests should pass before running the pipeline.

### 8. Run the pipeline

```bash
# Hook mode (Steps 0-9 only — prompt generation and GitHub issue creation)
python scripts/3-level-flow.py --task "add user profile endpoint"

# Full mode (all 15 steps including implementation, PR, and closure)
CLAUDE_HOOK_MODE=0 python scripts/3-level-flow.py --task "fix authentication bug"
```

---

## Docker Compose (Local Development)

A `docker-compose.yml` is provided for local development with Qdrant running
as a sidecar service.

```bash
# Start services
docker compose up -d

# Run the pipeline inside the container
docker compose exec app python scripts/3-level-flow.py --task "your task"

# Stop services
docker compose down
```

The compose file mounts the project directory as a volume so code changes take
effect immediately without rebuilding the image.

---

## Kubernetes Deployment

### Minimum cluster requirements

- Kubernetes 1.27+
- 2 CPU cores, 4 GB RAM per pod
- Persistent volume (1 GB) for Qdrant data

### Deployment manifest structure

```
k8s/
+-- namespace.yaml          # claude-workflow-engine namespace
+-- configmap.yaml          # Non-secret env vars
+-- secret.yaml             # API keys (use Sealed Secrets or Vault in production)
+-- deployment.yaml         # Main application pod
+-- service.yaml            # ClusterIP for health/metrics endpoints
+-- pvc.yaml                # PersistentVolumeClaim for .qdrant_data
+-- hpa.yaml                # HorizontalPodAutoscaler (optional)
```

### Apply the manifests

```bash
# Create namespace and apply all resources
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/

# Verify pods are running
kubectl -n claude-workflow-engine get pods

# Check liveness probe
kubectl -n claude-workflow-engine exec -it deploy/workflow-engine -- curl localhost:8000/health
```

### Liveness and readiness probes

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 15
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /readiness
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  failureThreshold: 3
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes* | — | Claude API key. Required if Anthropic is the primary provider. |
| `OPENAI_API_KEY` | No | — | OpenAI API key. Used as second fallback. |
| `GITHUB_TOKEN` | Yes | — | GitHub personal access token (repo + issues scope). |
| `OLLAMA_ENDPOINT` | No | `http://localhost:11434` | Ollama server URL for local LLM inference. |
| `CLAUDE_HOOK_MODE` | No | `1` | `1` = Hook mode (Steps 0-9). `0` = Full mode (Steps 0-14). |
| `CLAUDE_DEBUG` | No | `0` | `1` = verbose debug logging. |
| `ENABLE_JIRA` | No | `0` | `1` = enable Jira issue tracking (Steps 8, 9, 11, 12). |
| `ENABLE_JENKINS` | No | `0` | `1` = enable Jenkins build validation (Step 11). |
| `ENABLE_SONARQUBE` | No | `0` | `1` = enable SonarQube scan after implementation (Step 10). |
| `ENABLE_FIGMA` | No | `0` | `1` = enable Figma design extraction (Steps 3, 7, 11). |
| `ENABLE_CI` | No | `false` | `true` = trigger GitHub Actions CI on PR creation. |
| `JIRA_BASE_URL` | No* | — | Required when `ENABLE_JIRA=1`. e.g. `https://org.atlassian.net` |
| `JIRA_API_TOKEN` | No* | — | Required when `ENABLE_JIRA=1`. |
| `JIRA_USER_EMAIL` | No* | — | Required when `ENABLE_JIRA=1`. |
| `FIGMA_TOKEN` | No* | — | Required when `ENABLE_FIGMA=1`. |
| `SONARQUBE_URL` | No* | — | Required when `ENABLE_SONARQUBE=1`. |
| `SONARQUBE_TOKEN` | No* | — | Required when `ENABLE_SONARQUBE=1`. |
| `FORCE_LLM_PROVIDER` | No | — | Force a specific provider: `anthropic`, `openai`, `ollama`, `npu`. |
| `FORCE_GRAPH_REBUILD` | No | — | `1` = always rebuild call graph regardless of stale flag. |

*Required only when the corresponding integration is enabled.

---

## Upgrading

### Minor version upgrade (e.g., 1.6.0 -> 1.6.1)

```bash
git pull origin main
pip install -r requirements.txt --upgrade
pytest tests/ -q
```

No migration steps needed for patch versions.

### Major version upgrade

1. Read `CHANGELOG.md` for breaking changes.
2. Back up `.qdrant_data/` before upgrading (schema migrations may be needed).
3. Run the upgrade:
   ```bash
   git pull origin main
   pip install -r requirements.txt --upgrade
   ```
4. Run the migration script if provided:
   ```bash
   python scripts/migrate.py --from 1.5.0 --to 1.6.0
   ```
5. Run the full test suite:
   ```bash
   pytest tests/ -v
   ```

### Rollback

```bash
git checkout v1.5.0
pip install -r requirements.txt
```

Restore `.qdrant_data/` from backup if the schema changed.
