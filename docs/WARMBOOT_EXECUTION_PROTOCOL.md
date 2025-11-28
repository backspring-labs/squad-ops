# WarmBoot Execution & Monitoring Protocol

## Overview

This document provides a comprehensive guide for submitting and monitoring WarmBoot executions in SquadOps. WarmBoot is the agent-managed development workflow where AI agents (Max, Neo, etc.) collaborate to build, deploy, and manage applications autonomously.

## Quick Start

### 1. Submit a WarmBoot Request

**Option A: Web Form (Recommended)**
```bash
# Open the WarmBoot request form in your browser
open http://localhost:8000/warmboot/form
```

**Option B: API Endpoint**
```bash
curl -X POST http://localhost:8000/warmboot/submit \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "run-128",
    "application": "HelloSquad",
    "request_type": "from-scratch",
    "agents": ["max", "neo"],
    "priority": "HIGH",
    "description": "Build HelloSquad application from scratch",
    "requirements": null,
    "prd_path": "warm-boot/prd/PRD-001-HelloSquad.md"
  }'
```

### 2. Monitor Execution

**Real-time Log Monitoring:**
```bash
# Terminal 1: Max (Lead Agent) logs
docker-compose logs -f max | grep -E "(task|delegation|governance)"

# Terminal 2: Neo (Dev Agent) logs
docker-compose logs -f neo | grep -E "(task|design|build|deploy)"

# Terminal 3: Task API logs
docker-compose logs -f task-api
```

**Status Check:**
```bash
# Get WarmBoot status via API
curl http://localhost:8000/warmboot/status/run-128 | python3 -m json.tool
```

---

## WarmBoot Request Parameters

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `run_id` | string | Unique run identifier | `run-128`, `feature-auth`, `bug-fix-001` |
| `application` | string | Application name | `HelloSquad`, `SquadOps-Framework` |
| `request_type` | string | Build type | `from-scratch`, `feature-update`, `bug-fix`, `refactor`, `deployment`, `testing` |
| `agents` | array | List of agent IDs to involve | `["max", "neo"]` |
| `priority` | string | Task priority | `HIGH`, `MEDIUM`, `LOW` |
| `description` | string | Task description | `Build HelloSquad application from scratch` |

### Optional Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `requirements` | string | Additional technical requirements | `Use Docker, PostgreSQL backend` |
| `prd_path` | string | Path to PRD file | `warm-boot/prd/PRD-001-HelloSquad.md` |

### Request Types

1. **`from-scratch`** - Archive previous version, build new application
2. **`feature-update`** - Add features to existing application
3. **`bug-fix`** - Fix bugs in existing application
4. **`refactor`** - Improve existing code without changing functionality
5. **`deployment`** - Deploy existing application
6. **`testing`** - Test existing application

---

## API Endpoints

### 1. Submit WarmBoot Request

**Endpoint:** `POST /warmboot/submit`

**Request Body:**
```json
{
  "run_id": "run-128",
  "application": "HelloSquad",
  "request_type": "from-scratch",
  "agents": ["max", "neo"],
  "priority": "HIGH",
  "description": "Build HelloSquad application from scratch",
  "requirements": null,
  "prd_path": "warm-boot/prd/PRD-001-HelloSquad.md"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "WarmBoot request run-128 submitted successfully",
  "run_id": "run-128",
  "agents_notified": ["max", "neo"],
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### 2. Get WarmBoot Status

**Endpoint:** `GET /warmboot/status/{run_id}`

**Response:**
```json
{
  "run_id": "run-128",
  "status": "in_progress",
  "task_statuses": [
    {
      "task_id": "ECID-WB-128-main",
      "agent_name": "max",
      "status": "completed",
      "progress": 100.0
    },
    {
      "task_id": "ECID-WB-128-design",
      "agent_name": "neo",
      "status": "in_progress",
      "progress": 50.0
    }
  ],
  "timestamp": "2025-01-15T10:35:00Z"
}
```

### 3. Get Next Run ID

**Endpoint:** `GET /warmboot/next-run-id`

**Response:**
```json
{
  "run_id": "run-128"
}
```

### 4. Get Available PRDs

**Endpoint:** `GET /warmboot/prds`

**Response:**
```json
[
  {
    "file_path": "warm-boot/prd/PRD-001-HelloSquad.md",
    "title": "HelloSquad",
    "pid": "PID-001",
    "description": "Simple web application for testing"
  }
]
```

### 5. Get Agent Status

**Endpoint:** `GET /warmboot/agents`

**Response:**
```json
[
  {
    "agent": "Max",
    "status": "online",
    "role": "Task Lead"
  },
  {
    "agent": "Neo",
    "status": "online",
    "role": "Developer"
  }
]
```

### 6. Get Agent Messages

**Endpoint:** `GET /warmboot/messages?since=2025-01-15T10:30:00Z`

**Response:**
```json
[
  {
    "timestamp": "2025-01-15T10:30:05Z",
    "sender": "warmboot-orchestrator",
    "recipient": "max",
    "message_type": "WARMBOOT_REQUEST",
    "content": "WarmBoot request run-128 submitted"
  },
  {
    "timestamp": "2025-01-15T10:30:10Z",
    "sender": "max",
    "recipient": "neo",
    "message_type": "TASK_ASSIGNMENT",
    "content": "Task: design_manifest for HelloSquad"
  }
]
```

---

## Execution Flow

### 1. Submission Phase

1. **User submits WarmBoot request** via web form or API
2. **Health Check service** receives request and validates parameters
3. **ECID generated** for the execution cycle: `ECID-WB-{run_number}`
4. **Message sent to Max** via RabbitMQ queue `max_tasks`
5. **WarmBoot run recorded** in database (`warmboot_runs` table)

### 2. Max Processing Phase

1. **Max receives governance task** from RabbitMQ
2. **Max reads PRD** from `warm-boot/prd/` directory
3. **Max analyzes requirements** and creates project plan
4. **Max creates tasks** for other agents (Neo, EVE, etc.)
5. **Max delegates tasks** via RabbitMQ to appropriate agents

### 3. Agent Execution Phase

1. **Neo receives task delegation** from Max
2. **Neo acknowledges** task receipt
3. **Neo executes tasks**:
   - `design_manifest` - Generate application manifest
   - `build` - Build application files
   - `deploy` - Deploy application via Docker
4. **Neo updates task status** via Task API
5. **Neo sends completion events** back to Max

### 4. Completion Phase

1. **Max receives completion events** from agents
2. **Max generates wrap-up** document with telemetry
3. **WarmBoot run marked complete** in database
4. **Run summary created** in `warm-boot/runs/run-XXX/`

---

## Monitoring Protocol

### Real-time Log Monitoring

#### Max (Lead Agent) - Task Creation & Delegation

```bash
# Watch Max's logs for task creation and delegation
docker-compose logs -f max | grep -E "(task|delegation|governance|process_task)"
```

**Key events to look for:**
- `"max processing governance task"` - Max received the WarmBoot request
- `"max approved.*for delegation"` - Max approved and delegated tasks
- `"max received task acknowledgment"` - Neo confirmed receiving tasks
- `"max received task.*completed"` - Tasks completed successfully

#### Neo (Dev Agent) - Task Execution

```bash
# Watch Neo's logs for task execution
docker-compose logs -f neo | grep -E "(task|delegation|design_manifest|build|deploy|completed)"
```

**Key events to look for:**
- `"neo received task delegation"` - Neo received task from Max
- `"neo marked task.*as in_progress"` - Neo started working
- `"neo.*design_manifest"` - Manifest generation
- `"neo.*build"` - Build process
- `"neo.*deploy"` - Deployment process
- `"neo.*task.*completed"` - Task completion

#### Task API - Task Lifecycle Tracking

```bash
# Monitor Task API for task status updates
docker-compose logs -f task-api | grep -E "(task|POST|PUT|GET.*tasks)"
```

**Key events:**
- `POST /api/v1/tasks` - Task created
- `PUT /api/v1/tasks/{task_id}` - Task status updated
- `POST /api/v1/tasks/complete` - Task marked complete
- HTTP status codes (200 = success, 404 = task not found, 500 = error)

### Database Monitoring

#### Task Status Database

```bash
# Check task status in database
docker exec squadops-postgres psql -U squadops -d squadops -c \
  "SELECT task_id, agent_name, status, progress, updated_at 
   FROM task_status 
   WHERE task_id LIKE 'run-128%' 
   ORDER BY updated_at DESC;"
```

**Expected status flow:**
- `pending` → `in_progress` → `completed`
- `status = "completed"` with `progress = 100.0`

#### Execution Cycles

```bash
# Check execution cycle status
docker exec squadops-postgres psql -U squadops -d squadops -c \
  "SELECT ecid, status, created_at, updated_at 
   FROM execution_cycles 
   WHERE ecid LIKE 'ECID-WB-128%'
   ORDER BY created_at DESC;"
```

### RabbitMQ Monitoring

#### Check Queue Status

```bash
# Check queue message counts
docker exec squadops-rabbitmq rabbitmqctl list_queues name messages consumers
```

**Expected queues:**
- `max_tasks` - Tasks for Max (should process quickly)
- `neo_tasks` - Tasks for Neo (should have messages during execution)

#### RabbitMQ Management UI

```bash
# Open RabbitMQ management UI
open http://localhost:15672
# Login: squadops / squadops123
# Check queues: max_tasks, neo_tasks
```

### Web Form Live Monitoring

The WarmBoot form includes a live agent communication feed that shows:
- Real-time message passing between agents
- Task assignments and acknowledgments
- Progress updates and completion events
- Message types with icons and timestamps

**Access:** `http://localhost:8000/warmboot/form`

---

## Verification Checklist

### Task Handoff Verification

✅ **Max receives task:**
```bash
docker-compose logs max | grep "processing governance task"
```

✅ **Max creates tasks and delegates:**
```bash
docker-compose logs max | grep -E "(approved|delegation_target|send_message.*neo)"
```

✅ **Neo receives delegation:**
```bash
docker-compose logs neo | grep "received task delegation"
```

✅ **Neo acknowledges:**
```bash
docker-compose logs neo | grep "task_acknowledgment"
```

✅ **Max receives acknowledgment:**
```bash
docker-compose logs max | grep "received task acknowledgment"
```

### Task Completion Verification

✅ **Tasks marked complete in API:**
```bash
docker-compose logs task-api | grep "task.*complete"
```

✅ **Task status in database = "completed":**
```bash
docker exec squadops-postgres psql -U squadops -d squadops -c \
  "SELECT COUNT(*) FROM task_status WHERE status = 'completed' AND task_id LIKE 'run-128%';"
```

✅ **Neo logs completion:**
```bash
docker-compose logs neo | grep -E "(task.*completed|log_task_completion)"
```

✅ **All expected tasks completed:**
- `archive` (if from-scratch)
- `design_manifest`
- `build`
- `deploy`

---

## Common Issues & Troubleshooting

### ❌ Task Never Delegated

**Symptom:** Max processes task but Neo never receives it

**Check:**
```bash
docker-compose logs max | grep -E "(delegation|send_message)"
docker-compose logs neo | grep "received task"
```

**Solution:** Check RabbitMQ connection and queue configuration

### ❌ Task Stuck in "in_progress"

**Symptom:** Task status never reaches "completed"

**Check:**
```bash
# Check Neo logs for errors
docker-compose logs neo | grep -i error

# Check task status
docker exec squadops-postgres psql -U squadops -d squadops -c \
  "SELECT * FROM task_status WHERE status = 'in_progress';"
```

**Solution:** Review Neo logs for errors, check Docker container status

### ❌ RabbitMQ Messages Not Delivered

**Symptom:** Tasks queued but not consumed

**Check:**
```bash
docker exec squadops-rabbitmq rabbitmqctl list_queues name messages consumers
```

**Solution:** Verify agent containers are running and connected to RabbitMQ

### ❌ Task API Errors

**Symptom:** 500 errors in Task API logs

**Check:**
```bash
docker-compose logs task-api | grep -E "(ERROR|500|exception)"
```

**Solution:** Check database connection, verify Task API configuration

---

## Best Practices

### 1. Run ID Management

- Use sequential run IDs: `run-128`, `run-129`, etc.
- Get next run ID via API: `GET /warmboot/next-run-id`
- Web form auto-generates run IDs

### 2. PRD Selection

- Place PRDs in `warm-boot/prd/` directory
- Use format: `PRD-###-{AppName}.md`
- Link PRD to PID in `process_registry.md`

### 3. Agent Selection

- **Max** is always required (lead agent)
- **Neo** is required for development tasks
- **EVE** for QA and security tasks
- Check agent status before submission: `GET /warmboot/agents`

### 4. Request Type Selection

- **from-scratch**: New application, archives previous version
- **feature-update**: Add features to existing application
- **bug-fix**: Fix bugs in existing application
- **refactor**: Improve code without changing functionality
- **deployment**: Deploy existing application
- **testing**: Test existing application

### 5. Monitoring Strategy

- **Start with agent logs** (Max, Neo) for real-time visibility
- **Check Task API logs** for status updates
- **Query database** for persistent state
- **Use web form live feed** for message flow visibility
- **Monitor RabbitMQ** for message queue health

---

## Related Documentation

- **`MONITOR_WARMBOOT_LOGS.md`** - Detailed log monitoring guide
- **`docs/Agent_Managed_WarmBoot.md`** - Agent-managed workflow overview
- **`docs/SIPs/SIP-020-Health-Check-WarmBoot-Enhancement.md`** - WarmBoot UI implementation
- **`docs/ideas/WarmBoot_Management_Protocol.md`** - WarmBoot management protocol
- **`warm-boot/README.md`** - WarmBoot directory structure and usage

---

## Summary

The WarmBoot execution and monitoring protocol provides:

1. **Easy Submission** - Web form or API for submitting WarmBoot requests
2. **Real-time Monitoring** - Agent logs, Task API, database queries
3. **Status Tracking** - Task status, progress, completion verification
4. **Message Visibility** - Live agent communication feed
5. **Troubleshooting** - Common issues and solutions

**Key Workflow:**
1. Submit request → 2. Max processes → 3. Agents execute → 4. Monitor progress → 5. Verify completion

**Primary Monitoring:**
- Agent container logs (Max, Neo)
- Task API logs
- Database queries
- Web form live feed

