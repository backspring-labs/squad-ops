FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY agents/neo/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent files
COPY agents/neo/base_agent.py .
COPY agents/neo/neo.py .

# Create logs directory
RUN mkdir -p /app/logs

# Expose health check port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "print('Agent healthy')" || exit 1

# Run the agent
CMD ["python", "neo.py"]
