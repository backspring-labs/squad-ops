FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY infra/runtime-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy runtime-api files (SIP-0048: renamed from task-api)
COPY infra/runtime-api/main.py .
COPY infra/runtime-api/deps.py .

# Copy agents/tasks directory (adapter framework)
COPY agents/tasks ./agents/tasks

# Copy agents/utils directory (for path_resolver)
COPY agents/utils ./agents/utils

# Copy config directory (for unified_config)
COPY config ./config

# Copy infra directory (for config loader and secrets management)
COPY infra/ ./infra/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

