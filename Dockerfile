# =============================================================================
# Claude Workflow Engine - Dockerfile
# Version: 1.6.1
# Description: LangGraph orchestration pipeline with RAG
# Base: python:3.10-slim (multi-stage build)
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: dependency installer
# Installing dependencies in a separate stage keeps the final image lean
# and enables layer caching: requirements.txt changes less often than code.
# -----------------------------------------------------------------------------
FROM python:3.10-slim AS deps

# Install OS-level build dependencies required by some Python packages
# (e.g., sentence-transformers, TTS, psutil)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only the requirements file first.
# Docker caches this layer; it is only invalidated when requirements.txt changes.
COPY requirements.txt .

# Install all Python dependencies into a non-root prefix for easy copying
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: final runtime image
# Copies the pre-installed packages from the deps stage.
# No build tools are present in the final image (smaller attack surface).
# -----------------------------------------------------------------------------
FROM python:3.10-slim AS runtime

LABEL org.opencontainers.image.title="Claude Workflow Engine" \
      org.opencontainers.image.description="LangGraph 3-level orchestration pipeline with RAG" \
      org.opencontainers.image.version="1.6.1" \
      org.opencontainers.image.source="https://github.com/techdeveloper-org/claude-workflow-engine"

# Install minimal runtime OS libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --no-create-home --shell /bin/bash appuser

WORKDIR /app

# Copy pre-installed Python packages from the deps stage
COPY --from=deps /install /usr/local

# Copy application source code.
# .dockerignore excludes .env, .git, __pycache__, venv, docs, etc.
COPY --chown=appuser:appgroup . .

# Switch to non-root user
USER appuser

# Expose health and metrics ports
EXPOSE 8080
EXPOSE 9090

# Health check: HTTP GET /health on the lightweight health server.
# The server is started only when ENABLE_HEALTH_SERVER=1.
# Falls back to a process-level check when the server is not running.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8080/health || exit 1

# Entrypoint: always use the pipeline entry point
ENTRYPOINT ["python", "scripts/3-level-flow.py"]

# Default command: use TASK env var when provided, otherwise show help.
# Override at runtime: docker run -e TASK="add login feature" image:tag
CMD ["--help"]
