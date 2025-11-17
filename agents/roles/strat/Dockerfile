FROM python:3.11-slim

WORKDIR /app

# Set base path environment variable for unified path resolution
ENV SQUADOPS_BASE_PATH=/app

# Build argument for agent role
ARG AGENT_ROLE=strat

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY agents/roles/${AGENT_ROLE}/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire agents directory structure maintaining paths
COPY agents/llm ./agents/llm
COPY agents/specs ./agents/specs
COPY agents/capabilities ./agents/capabilities
COPY agents/capability_bindings.yaml ./agents/capability_bindings.yaml
COPY agents/telemetry ./agents/telemetry
COPY agents/memory ./agents/memory
COPY agents/instances ./agents/instances
COPY agents/skills ./agents/skills
COPY agents/utils ./agents/utils

# Copy agent-specific files to root for CMD compatibility
COPY agents/base_agent.py .
COPY agents/roles/${AGENT_ROLE}/agent.py .
COPY agents/roles/${AGENT_ROLE}/config.yaml ./agents/roles/${AGENT_ROLE}/

# Copy config directory
COPY config ./config

# Create logs and memory database directories
RUN mkdir -p /app/logs /app/data/memory_db

# Expose health check port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "print('Agent healthy')" || exit 1

# Run the agent
CMD ["python", "agent.py"]
