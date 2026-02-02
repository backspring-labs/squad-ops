# SquadOps Health Check Service
#
# Multi-stage build following the same pattern as agents/Dockerfile.
# Installs squadops package via pip for proper imports.
#
# Usage:
#   docker build -t squadops-health-check -f src/squadops/api/Dockerfile .

# Stage 1: Build validation
FROM python:3.11-slim AS builder
WORKDIR /build

# Copy source for validation
COPY src/ ./src/
COPY adapters/ ./adapters/
COPY pyproject.toml ./

# Validate health_app exists
RUN python -c "from pathlib import Path; assert Path('src/squadops/api/health_app.py').exists(), 'health_app.py not found'"


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

# Copy package files and install
COPY pyproject.toml ./
COPY requirements.txt ./
COPY src/ ./src/
COPY adapters/ ./adapters/

# Install dependencies and package
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e .

# Copy agent instances configuration (for agent registry)
COPY agents/instances /app/agents/instances

# Copy templates
COPY src/squadops/api/templates /app/templates

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "squadops.api.health_app:app", "--host", "0.0.0.0", "--port", "8000"]
