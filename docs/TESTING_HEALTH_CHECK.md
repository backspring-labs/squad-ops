# Testing Dynamic Health Check Service

## Overview

The health-check service now dynamically discovers agents from the database instead of requiring static configuration. Agents report their metadata (display_name, role, version) via heartbeats, and the health-check service displays this information in real-time.

## Prerequisites

1. **Ollama running locally** (for agents that use LLM):
   ```bash
   ollama pull qwen2.5:3b-instruct
   ```

2. **Docker Compose infrastructure**:
   - PostgreSQL
   - RabbitMQ
   - Redis
   - Health-check service

## Step-by-Step Testing

### Step 1: Start Infrastructure Services

```bash
# Start core infrastructure
docker-compose up -d postgres rabbitmq redis health-check

# Wait for services to be healthy (30 seconds)
sleep 30

# Verify services are running
docker-compose ps
```

### Step 2: Verify Health-Check Service

```bash
# Check health-check service is running
curl http://localhost:8000/health

# Should return JSON with service status
```

**Expected Response:**
```json
{
  "status": "healthy",
  "version": "0.0.1",
  "services": {
    "postgres": "connected",
    "rabbitmq": "connected",
    "redis": "connected"
  }
}
```

### Step 3: Check Initial Agent Status (Should be Empty)

```bash
# Get agent status list (should be empty initially)
curl http://localhost:8000/api/agents

# Or open in browser
open http://localhost:8000/health
```

**Expected:** Empty list or only offline agents from database initialization.

### Step 4: Start an Agent (Data Agent Example)

```bash
# Build and start the Data agent
docker-compose up -d --build data

# Wait for agent to initialize (10-15 seconds)
sleep 15

# Check agent logs
docker-compose logs --tail=50 data
```

**Look for in logs:**
- "Memory providers initialized"
- "Data agent started successfully"
- "Sending heartbeat" messages

### Step 5: Verify Agent Appears in Health Check

```bash
# Check agent status via API
curl http://localhost:8000/api/agents | jq

# Or open dashboard in browser
open http://localhost:8000/health
```

**Expected Response:**
```json
[
  {
    "agent_name": "data",
    "display_name": "Data",
    "role": "data",
    "status": "online",
    "version": "0.0.1",
    "last_heartbeat": "2025-01-28T12:34:56Z"
  }
]
```

**Verify:**
- ✅ Agent appears in the list
- ✅ `display_name` is "Data" (not "data-agent")
- ✅ `role` is "data"
- ✅ `version` matches `config/version.py` (not "0.0.0")
- ✅ `status` is "online"

### Step 6: Test Dynamic Discovery (No Restart Required)

```bash
# Stop the agent
docker-compose stop data

# Wait a moment
sleep 5

# Check agent status (should show offline)
curl http://localhost:8000/api/agents | jq

# Start the agent again
docker-compose start data

# Wait for heartbeat
sleep 10

# Check agent status (should show online again)
curl http://localhost:8000/api/agents | jq
```

**Expected:** Agent status changes from "online" → "offline" → "online" without restarting health-check service.

### Step 7: Test Version Updates

```bash
# Check current version in database
docker exec squadops-postgres psql -U squadops -d squadops -c \
  "SELECT agent_name, version, display_name, role FROM agent_status WHERE agent_name='data';"

# The version should match config/version.py
cat config/version.py | grep SQUADOPS_VERSION
```

**Expected:** Version in database matches `SQUADOPS_VERSION` from `config/version.py`.

### Step 8: Test Multiple Agents

```bash
# Start additional agents
docker-compose up -d max neo

# Wait for heartbeats
sleep 15

# Check all agents
curl http://localhost:8000/api/agents | jq
```

**Expected:** All agents appear with correct `display_name`, `role`, and `version`.

## Browser Testing

### Open Health Check Dashboard

```bash
open http://localhost:8000/health
```

**What to verify:**
1. **Agent List Tab:**
   - All agents are listed
   - Display names are human-readable (e.g., "Data" not "data-agent")
   - Roles are shown correctly
   - Versions match `config/version.py`
   - Status updates in real-time (online/offline)

2. **Agent Console Tab:**
   - Can send messages to agents
   - Messages are delivered via RabbitMQ

3. **Services Tab:**
   - PostgreSQL, RabbitMQ, Redis show as connected

## API Endpoints

### Get All Agents
```bash
curl http://localhost:8000/api/agents
```

### Get Specific Agent
```bash
curl http://localhost:8000/api/agents/data
```

### Get Agent Status (Raw Database Query)
```bash
curl http://localhost:8000/api/agent-status
```

## Troubleshooting

### Agent Not Appearing

1. **Check agent logs:**
   ```bash
   docker-compose logs --tail=100 data
   ```

2. **Check RabbitMQ connection:**
   ```bash
   docker-compose logs rabbitmq | grep -i error
   ```

3. **Check database:**
   ```bash
   docker exec squadops-postgres psql -U squadops -d squadops -c \
     "SELECT * FROM agent_status WHERE agent_name='data';"
   ```

4. **Verify heartbeat is being sent:**
   - Look for "Sending heartbeat" in agent logs
   - Check RabbitMQ management UI: http://localhost:15672
   - Username: `squadops`, Password: `squadops123`

### Version Shows as 0.0.0

1. **Check volume mount:**
   ```bash
   docker-compose config | grep -A 5 health-check
   ```
   Should show volume mounts for `config/version.py` and `agents/instances/instances.yaml`

2. **Check version file exists:**
   ```bash
   docker exec squadops-health-check ls -la /app/config/version.py
   ```

3. **Check agent_info.json:**
   ```bash
   docker exec squadops-data cat /app/agent_info.json | jq
   ```

### Display Name or Role Missing

1. **Check agent_info.json:**
   ```bash
   docker exec squadops-data cat /app/agent_info.json
   ```
   Should have `display_name` and `role` fields.

2. **Check heartbeat payload:**
   - Look in agent logs for heartbeat messages
   - Should include `display_name` and `role`

3. **Check database schema:**
   ```bash
   docker exec squadops-postgres psql -U squadops -d squadops -c \
     "\d agent_status"
   ```
   Should show `display_name` and `role` columns.

## Success Criteria

- ✅ Health-check service starts without errors
- ✅ Agents appear in the dashboard automatically
- ✅ Agent metadata (display_name, role, version) is correct
- ✅ Agents can go online/offline without restarting health-check
- ✅ Version updates reflect in dashboard without restart
- ✅ Multiple agents are discovered and displayed correctly

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes (optional, clears database)
docker-compose down -v
```

