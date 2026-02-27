# SquadOps Runtime API Container
#
# Multi-stage build following the same pattern as agents/Dockerfile.
# SIP-0048: Runtime API for task and cycle management.
#
# Usage:
#   docker build -t squadops-runtime-api -f src/squadops/api/runtime/Dockerfile .

# Stage 1: Build validation
FROM python:3.11-slim AS builder
WORKDIR /build

# Copy source for validation
COPY src/ ./src/
COPY adapters/ ./adapters/
COPY pyproject.toml ./

# Validate runtime main exists
RUN python -c "from pathlib import Path; assert Path('src/squadops/api/runtime/main.py').exists(), 'runtime/main.py not found'"


# Stage 2: Runtime image
FROM python:3.11-slim
WORKDIR /app
ENV SQUADOPS_BASE_PATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files FIRST (for better layer caching)
COPY pyproject.toml ./
COPY requirements.txt requirements-api.txt ./

# Install dependencies (this layer is cached when requirements don't change)
# BuildKit cache mount preserves pip download cache across builds
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-api.txt

# Copy source code (changes frequently, but doesn't invalidate deps layer)
COPY src/ ./src/
COPY adapters/ ./adapters/
COPY agents/instances/ ./agents/instances/
COPY config/ ./config/
COPY examples/ ./examples/
COPY infra/ ./infra/

# Install package in editable mode (fast - deps already installed)
RUN --mount=type=cache,target=/root/.cache/pip pip install -e .

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "squadops.api.runtime.main:app", "--host", "0.0.0.0", "--port", "8001"]
