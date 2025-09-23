FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn==0.24.0 \
    asyncpg==0.29.0 \
    redis==5.0.1 \
    pika==1.3.2 \
    aiohttp==3.9.1

# Copy application code and config
COPY infra/health-check/main.py .
COPY config ./config

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]
