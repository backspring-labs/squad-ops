# Stage 1: Build agent package
FROM python:3.11-slim as builder
WORKDIR /build

# Install build dependencies
RUN pip install --no-cache-dir pyyaml

# Copy source code
COPY agents/ ./agents/
COPY scripts/dev/build_agent.py ./scripts/
COPY config/ ./config/

# Build agent package
ARG AGENT_ROLE=data
ARG GIT_COMMIT
RUN GIT_COMMIT=${GIT_COMMIT} python scripts/build_agent.py ${AGENT_ROLE}

# Stage 2: Runtime image
FROM python:3.11-slim
WORKDIR /app
ENV SQUADOPS_BASE_PATH=/app

# Build argument for agent role (needed for COPY path)
ARG AGENT_ROLE=data
# Build hash for Docker label (can be passed from CI/CD or will default to "unknown")
ARG BUILD_HASH=unknown

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy assembled agent package
COPY --from=builder /build/dist/agents/${AGENT_ROLE}/ ./

# Set Docker label for build hash
LABEL squadops.build_hash="${BUILD_HASH}"

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create required directories
RUN mkdir -p /app/logs /app/data/memory_db

# Expose health check port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "print('Agent healthy')" || exit 1

# Run the agent
CMD ["python", "agent.py"]
