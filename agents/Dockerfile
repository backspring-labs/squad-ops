# SquadOps Agent Container
#
# Unified Dockerfile for all agent roles using ports & adapters architecture.
# Role is specified via AGENT_ROLE build arg.
#
# Stage 1: Validate build configuration
# Stage 2: Runtime image with installed squadops package
#
# Usage:
#   docker build --build-arg AGENT_ROLE=lead -t squadops-lead -f agents/Dockerfile .
#   docker build --build-arg AGENT_ROLE=dev -t squadops-dev -f agents/Dockerfile .
#

# Stage 1: Build validation
FROM python:3.11-slim AS builder
WORKDIR /build

# Install build dependencies
RUN --mount=type=cache,target=/root/.cache/pip pip install pyyaml

# Copy source code
COPY src/ ./src/
COPY adapters/ ./adapters/
COPY scripts/dev/build_agent.py ./scripts/build_agent.py

# Validate agent build (new architecture mode)
ARG AGENT_ROLE=lead
ARG GIT_COMMIT
RUN python scripts/build_agent.py ${AGENT_ROLE}


# Stage 2: Runtime image
FROM python:3.11-slim
WORKDIR /app
ENV SQUADOPS_BASE_PATH=/app

# Build arguments
ARG AGENT_ROLE=lead
ARG BUILD_HASH=unknown
ARG GIT_COMMIT=unknown

# Labels for traceability
LABEL squadops.build_hash="${BUILD_HASH}"
LABEL squadops.git_commit="${GIT_COMMIT}"
LABEL squadops.role="${AGENT_ROLE}"

# Set runtime environment
ENV SQUADOPS_AGENT_ROLE=${AGENT_ROLE}

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files FIRST (for better layer caching)
COPY pyproject.toml ./
COPY requirements-agent.lock ./

# Install dependencies (this layer is cached when requirements don't change)
# BuildKit cache mount preserves pip download cache across builds
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-agent.lock

# Copy agent configuration (instances for role-specific config + per-role extras)
COPY agents/instances/ ./agents/instances/

# Install per-role extras (e.g., pytest for QA agent)
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ -f "agents/instances/${AGENT_ROLE}/requirements.txt" ]; then \
      pip install -r "agents/instances/${AGENT_ROLE}/requirements.txt"; \
    fi

# Cache-bust: when SOURCE_HASH changes, Docker invalidates this layer and below
ARG SOURCE_HASH=unknown

# Copy source code (changes frequently, but doesn't invalidate deps layer)
COPY src/ ./src/
COPY adapters/ ./adapters/

# Install package in editable mode (fast - just creates .egg-info)
RUN --mount=type=cache,target=/root/.cache/pip pip install -e .

# Create required directories
RUN mkdir -p /app/logs /app/data/memory_db

# Expose health check port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "from squadops.agents.entrypoint import AgentRunner; print('Agent healthy')" || exit 1

# Run the agent entry point
CMD ["python", "-m", "squadops.agents.entrypoint"]
