# SquadOps Sandbox Service Container (SIP-0102 — Ephemeral Application Sandbox)
#
# The only component that holds the container-runtime socket (§4.3). Runs the
# narrow authenticated API over the sandbox service core.
#
# Usage:
#   docker build -t squadops-sandbox-service -f src/squadops/sandbox/Dockerfile .

FROM python:3.11-slim
WORKDIR /app
ENV SQUADOPS_BASE_PATH=/app

RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI only (the daemon is the host's, reached via the mounted socket).
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker

# Copy dependency files FIRST (for better layer caching)
COPY pyproject.toml ./
COPY requirements/ ./requirements/

RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements/api.lock

# Cache-bust: when SOURCE_HASH changes, Docker invalidates this layer and below
ARG SOURCE_HASH=unknown

COPY src/ ./src/
COPY adapters/ ./adapters/
COPY config/ ./config/

RUN --mount=type=cache,target=/root/.cache/pip pip install -e .

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

CMD ["uvicorn", "--factory", "squadops.sandbox.main:build_app", "--host", "0.0.0.0", "--port", "8002"]
