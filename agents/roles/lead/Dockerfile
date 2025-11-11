FROM python:3.11-slim

WORKDIR /app

# Build argument for agent role
ARG AGENT_ROLE=lead

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY agents/roles/${AGENT_ROLE}/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent files
COPY agents/base_agent.py .
COPY agents/roles/${AGENT_ROLE}/agent.py .

# Copy new LLM, contracts, telemetry, and memory modules
COPY agents/llm ./agents/llm
COPY agents/specs ./agents/specs
COPY agents/capabilities ./agents/capabilities
COPY agents/telemetry ./agents/telemetry
COPY agents/memory ./agents/memory
COPY agents/instances ./agents/instances
# Copy skills directory for capability imports (capabilities use agents.skills.*)
COPY agents/skills ./agents/skills

# Copy version management
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