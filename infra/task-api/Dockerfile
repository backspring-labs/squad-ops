FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY infra/task-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy task-api files
COPY infra/task-api/main.py .
COPY infra/task-api/deps.py .

# Copy agents/tasks directory (adapter framework)
COPY agents/tasks ./agents/tasks

# Copy config directory (for unified_config)
COPY config ./config

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

