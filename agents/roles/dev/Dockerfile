FROM python:3.11-slim

WORKDIR /app
# Build argument for agent role
ARG AGENT_ROLE=dev


# Install system dependencies including Docker CLI
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    gnupg \
    lsb-release \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY agents/roles/${AGENT_ROLE}/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent files
COPY agents/base_agent.py .
COPY agents/roles/${AGENT_ROLE}/agent.py .
COPY agents/roles/${AGENT_ROLE}/app_builder.py .
COPY agents/roles/${AGENT_ROLE}/docker_manager.py .
COPY agents/roles/${AGENT_ROLE}/version_manager.py .
COPY agents/roles/${AGENT_ROLE}/file_manager.py .
COPY agents/roles/${AGENT_ROLE}/prompts ./prompts
COPY agents/llm ./agents/llm
COPY agents/contracts ./agents/contracts
COPY config ./config

# Create logs directory
RUN mkdir -p /app/logs

# Expose health check port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "print('Agent healthy')" || exit 1

# Run the agent
CMD ["python", "agent.py"]
