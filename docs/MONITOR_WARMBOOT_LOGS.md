# Monitoring WarmBoot Task Handoff & Completion

## Quick Start - Key Logs to Monitor

When running a WarmBoot smoke test, monitor these logs in order of importance:

### 1. Agent Container Logs (Real-time task processing)

**Max (Lead Agent) - Task Creation & Delegation:**
```bash
# Watch Max's logs for task creation and delegation
docker-compose logs -f max | grep -E "(task|delegation|governance|process_task)"
```

**Key events to look for:**
- `"max processing governance task"` - Max received the WarmBoot request
- `"max approved.*for delegation"` - Max approved and delegated tasks
- `"max received task acknowledgment"` - Neo confirmed receiving tasks
- `"max received task.*completed"` - Tasks completed successfully

**Neo (Dev Agent) - Task Execution:**
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

### 2. Task API Logs (Task lifecycle tracking)

```bash
# Monitor Task API for task status updates
docker-compose logs -f task-api | grep -E "(task|POST|PUT|GET.*tasks)"
```

**Key events:**
- `POST /api/v1/tasks` - Task created
- `PUT /api/v1/tasks/{task_id}` - Task status updated
- `POST /api/v1/tasks/complete` - Task marked complete
- HTTP status codes (200 = success, 404 = task not found, 500 = error)

### 3. Task Status Database (Persistent task tracking)

**Query task status directly:**
```bash
# Check task status in database
docker exec squadops-postgres psql -U squadops -d squadops -c \
  "SELECT task_id, agent_name, status, progress, updated_at 
   FROM task_status 
   WHERE task_id LIKE 'run-%' 
   ORDER BY updated_at DESC 
   LIMIT 10;"
```

**Expected status flow:**
- `pending` → `in_progress` → `completed`
- `status = "completed"` with `progress = 100.0`

**Check execution cycles:**
```bash
# Check execution cycle status
docker exec squadops-postgres psql -U squadops -d squadops -c \
  "SELECT ecid, status, created_at, updated_at 
   FROM execution_cycles 
   ORDER BY created_at DESC 
   LIMIT 5;"
```

### 4. RabbitMQ (Inter-agent communication)

**Check RabbitMQ queues:**
```bash
# View RabbitMQ management UI
# Open: http://localhost:15672
# Login: squadops / squadops123
# Check queues: max_tasks, neo_tasks
```

**Or via command line:**
```bash
# Check queue message counts
docker exec squadops-rabbitmq rabbitmqctl list_queues name messages
```

**Expected queues:**
- `max_tasks` - Tasks for Max (should process quickly)
- `neo_tasks` - Tasks for Neo (should have messages during execution)

### 5. Full Agent Logs (Complete picture)

**All agent activity:**
```bash
# Watch both agents simultaneously
docker-compose logs -f max neo
```

**Or individually:**
```bash
# Max only (tail last 100 lines, then follow)
docker-compose logs --tail=100 -f max

# Neo only
docker-compose logs --tail=100 -f neo
```

## Verification Checklist

### Task Handoff Verification:
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

### Task Completion Verification:
✅ **Tasks marked complete in API:**
```bash
docker-compose logs task-api | grep "task.*complete"
```

✅ **Task status in database = "completed":**
```bash
docker exec squadops-postgres psql -U squadops -d squadops -c \
  "SELECT COUNT(*) FROM task_status WHERE status = 'completed' AND task_id LIKE 'run-%';"
```

✅ **Neo logs completion:**
```bash
docker-compose logs neo | grep -E "(task.*completed|log_task_completion)"
```

✅ **All expected tasks completed:**
- archive
- design_manifest
- build
- deploy

## Real-time Monitoring Script

Save this as `monitor_warmboot.sh`:

```bash
#!/bin/bash
# Monitor WarmBoot execution in real-time

RUN_ID=${1:-"run-XXX"}

echo "🔍 Monitoring WarmBoot: $RUN_ID"
echo "=================================="
echo ""

# Terminal 1: Max logs
echo "📊 Terminal 1 - Max (Lead):"
echo "docker-compose logs -f max | grep -E '(task|delegation)'"
echo ""

# Terminal 2: Neo logs  
echo "📊 Terminal 2 - Neo (Dev):"
echo "docker-compose logs -f neo | grep -E '(task|design|build|deploy)'"
echo ""

# Terminal 3: Task API
echo "📊 Terminal 3 - Task API:"
echo "docker-compose logs -f task-api"
echo ""

# Check task status
echo "📊 Current Task Status:"
docker exec squadops-postgres psql -U squadops -d squadops -c \
  "SELECT task_id, agent_name, status, progress 
   FROM task_status 
   WHERE task_id LIKE '${RUN_ID}%' 
   ORDER BY updated_at DESC;"

# Watch in real-time
watch -n 5 "docker exec squadops-postgres psql -U squadops -d squadops -t -c \
  \"SELECT task_id, status, progress FROM task_status WHERE task_id LIKE '${RUN_ID}%' ORDER BY updated_at DESC;\""
```

## Common Issues to Watch For

### ❌ Task Never Delegated
**Symptom:** Max processes task but Neo never receives it
**Check:**
```bash
docker-compose logs max | grep -E "(delegation|send_message)"
docker-compose logs neo | grep "received task"
```

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

### ❌ RabbitMQ Messages Not Delivered
**Symptom:** Tasks queued but not consumed
**Check:**
```bash
docker exec squadops-rabbitmq rabbitmqctl list_queues name messages consumers
```

### ❌ Task API Errors
**Symptom:** 500 errors in Task API logs
**Check:**
```bash
docker-compose logs task-api | grep -E "(ERROR|500|exception)"
```

## Status Endpoint (Quick Check)

```bash
# Get WarmBoot status via API
curl -s "http://localhost:8000/warmboot/status/run-XXX" | python3 -m json.tool

# Expected response:
# {
#   "run_id": "run-XXX",
#   "status": "completed",
#   "task_statuses": [
#     {"task_id": "...", "agent_name": "max", "status": "completed", ...},
#     {"task_id": "...", "agent_name": "neo", "status": "completed", ...}
#   ]
# }
```

