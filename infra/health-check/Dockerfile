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
COPY config ./config
COPY agents/instances ./agents/instances

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]
