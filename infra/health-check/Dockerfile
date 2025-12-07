FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY infra/health-check/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and config
COPY infra/health-check/main.py .
COPY infra/health-check/templates ./templates
COPY config ./config
COPY agents/instances ./agents/instances
COPY agents/utils ./agents/utils

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]
