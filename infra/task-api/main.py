from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncpg
import os
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

app = FastAPI(title="SquadOps Task Management API", version="1.0")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://squadops:squadops123@postgres:5432/squadops")

# Global connection pool
pool = None

@app.on_event("startup")
async def startup_event():
    global pool
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=10)

@app.on_event("shutdown")
async def shutdown_event():
    global pool
    if pool:
        await pool.close()

# Pydantic models
class ExecutionCycleCreate(BaseModel):
    ecid: str
    pid: str
    run_type: str
    title: str
    description: Optional[str] = None
    initiated_by: str

class ExecutionCycleUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

class TaskLogCreate(BaseModel):
    task_id: str
    ecid: str
    agent: str
    status: str
    priority: Optional[str] = "MEDIUM"
    description: Optional[str] = None
    dependencies: Optional[List[str]] = []
    delegated_by: Optional[str] = None
    delegated_to: Optional[str] = None

class TaskLogUpdate(BaseModel):
    status: Optional[str] = None
    end_time: Optional[datetime] = None
    artifacts: Optional[Dict[str, Any]] = None
    error_log: Optional[str] = None

# GET endpoints for querying tasks and execution cycles

@app.get("/api/v1/tasks/ec/{ecid}")
async def get_tasks_by_ecid(ecid: str):
    """Get all tasks for a specific execution cycle"""
    async with pool.acquire() as conn:
        tasks = await conn.fetch("""
            SELECT * FROM agent_task_log 
            WHERE ecid = $1 
            ORDER BY created_at ASC
        """, ecid)
    return [dict(task) for task in tasks]


@app.get("/api/v1/tasks/agent/{agent_name}")
async def get_tasks_by_agent(agent_name: str, ecid: Optional[str] = None, limit: int = 50):
    """Get recent tasks for a specific agent, optionally filtered by ECID"""
    async with pool.acquire() as conn:
        if ecid:
            tasks = await conn.fetch("""
                SELECT * FROM agent_task_log 
                WHERE agent = $1 AND ecid = $2
                ORDER BY created_at DESC 
                LIMIT $3
            """, agent_name, ecid, limit)
        else:
            tasks = await conn.fetch("""
                SELECT * FROM agent_task_log 
                WHERE agent = $1 
                ORDER BY created_at DESC 
                LIMIT $2
            """, agent_name, limit)
    return [dict(task) for task in tasks]

@app.get("/api/v1/tasks/status/{status}")
async def get_tasks_by_status(status: str):
    """Get tasks by status"""
    async with pool.acquire() as conn:
        tasks = await conn.fetch("""
            SELECT * FROM agent_task_log 
            WHERE status = $1 
            ORDER BY created_at DESC
        """, status)
    return [dict(task) for task in tasks]

@app.get("/api/v1/execution-cycles")
async def get_execution_cycles(run_type: Optional[str] = None):
    """Get execution cycles, optionally filtered by type"""
    async with pool.acquire() as conn:
        if run_type:
            cycles = await conn.fetch("""
                SELECT * FROM execution_cycle 
                WHERE run_type = $1 
                ORDER BY created_at DESC
            """, run_type)
        else:
            cycles = await conn.fetch("""
                SELECT * FROM execution_cycle 
                ORDER BY created_at DESC
            """)
    return [dict(cycle) for cycle in cycles]

@app.get("/api/v1/tasks/summary/{ecid}")
async def get_task_summary(ecid: str):
    """Get task summary for an execution cycle"""
    async with pool.acquire() as conn:
        summary = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_tasks,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'started') as in_progress,
                COUNT(*) FILTER (WHERE status = 'delegated') as delegated,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                AVG(duration) as avg_duration
            FROM agent_task_log 
            WHERE ecid = $1
        """, ecid)
    return dict(summary)

# POST/PUT endpoints for agents to create and update tasks

@app.post("/api/v1/execution-cycles")
async def create_execution_cycle(cycle: ExecutionCycleCreate):
    """Create a new execution cycle"""
    async with pool.acquire() as conn:
        try:
            now = datetime.utcnow()
            # Note: execution_cycle table only has created_at, not start_time
            # Use created_at as start_time for duration calculation
            await conn.execute("""
                INSERT INTO execution_cycle 
                (ecid, pid, run_type, title, description, initiated_by, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, cycle.ecid, cycle.pid, cycle.run_type, cycle.title, 
                cycle.description, cycle.initiated_by, now)
            return {"status": "created", "ecid": cycle.ecid}
        except asyncpg.exceptions.UniqueViolationError:
            raise HTTPException(status_code=409, detail=f"Execution cycle {cycle.ecid} already exists")

@app.put("/api/v1/execution-cycles/{ecid}")
async def update_execution_cycle(ecid: str, update: ExecutionCycleUpdate):
    """Update execution cycle status or notes"""
    
    updates = []
    params = []
    param_count = 1
    
    if update.status:
        updates.append(f"status = ${param_count}")
        params.append(update.status)
        param_count += 1
    
    if update.notes:
        updates.append(f"notes = ${param_count}")
        params.append(update.notes)
        param_count += 1
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    params.append(ecid)
    query = f"UPDATE execution_cycle SET {', '.join(updates)} WHERE ecid = ${param_count}"
    
    async with pool.acquire() as conn:
        result = await conn.execute(query, *params)
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail=f"Execution cycle {ecid} not found")
    
    return {"status": "updated", "ecid": ecid}

@app.post("/api/v1/execution-cycles/{ecid}/complete")
async def complete_execution_cycle(ecid: str, notes: Optional[str] = None):
    """Mark execution cycle as completed"""
    update = ExecutionCycleUpdate(status="completed", notes=notes)
    return await update_execution_cycle(ecid, update)

@app.post("/api/v1/execution-cycles/{ecid}/fail")
async def fail_execution_cycle(ecid: str, notes: str):
    """Mark execution cycle as failed"""
    update = ExecutionCycleUpdate(status="failed", notes=notes)
    return await update_execution_cycle(ecid, update)

@app.post("/api/v1/tasks/start")
async def start_task(task: TaskLogCreate):
    """Log task start"""
    async with pool.acquire() as conn:
        try:
            await conn.execute("""
                INSERT INTO agent_task_log 
                (task_id, ecid, agent, status, priority, description, start_time, 
                 dependencies, delegated_by, delegated_to, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """, task.task_id, task.ecid, task.agent, task.status, task.priority, 
                task.description, datetime.utcnow(), task.dependencies or [], 
                task.delegated_by, task.delegated_to, datetime.utcnow())
            return {"status": "started", "task_id": task.task_id}
        except asyncpg.exceptions.UniqueViolationError:
            raise HTTPException(status_code=409, detail=f"Task {task.task_id} already exists")

@app.put("/api/v1/tasks/{task_id}")
async def update_task(task_id: str, update: TaskLogUpdate):
    """Update task status, completion, or error"""
    
    # Build dynamic update query based on provided fields
    updates = []
    params = []
    param_count = 1
    
    if update.status:
        updates.append(f"status = ${param_count}")
        params.append(update.status)
        param_count += 1
    
    if update.end_time:
        updates.append(f"end_time = ${param_count}")
        params.append(update.end_time)
        param_count += 1
        updates.append("duration = end_time - start_time")
    
    if update.artifacts:
        updates.append(f"artifacts = ${param_count}")
        params.append(json.dumps(update.artifacts))
        param_count += 1
    
    if update.error_log:
        updates.append(f"error_log = ${param_count}")
        params.append(update.error_log)
        param_count += 1
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    params.append(task_id)
    query = f"UPDATE agent_task_log SET {', '.join(updates)} WHERE task_id = ${param_count}"
    
    async with pool.acquire() as conn:
        await conn.execute(query, *params)
    
    return {"status": "updated", "task_id": task_id}

class TaskCompleteRequest(BaseModel):
    task_id: str
    artifacts: Optional[Dict[str, Any]] = None

@app.post("/api/v1/tasks/complete")
async def complete_task(request: TaskCompleteRequest):
    """Mark task as completed with optional artifacts"""
    update = TaskLogUpdate(
        status="completed",
        end_time=datetime.utcnow(),
        artifacts=request.artifacts
    )
    return await update_task(request.task_id, update)

class TaskFailRequest(BaseModel):
    task_id: str
    error_log: str

@app.post("/api/v1/tasks/fail")
async def fail_task(request: TaskFailRequest):
    """Mark task as failed with error log"""
    update = TaskLogUpdate(
        status="failed",
        end_time=datetime.utcnow(),
        error_log=request.error_log
    )
    return await update_task(request.task_id, update)

# Task Status Management Endpoints (replaces direct task_status table writes)

class TaskStatusCreate(BaseModel):
    task_id: str
    agent_name: str
    status: str
    progress: float = 0.0
    eta: Optional[str] = None

class TaskStatusUpdate(BaseModel):
    status: Optional[str] = None
    progress: Optional[float] = None
    eta: Optional[str] = None

@app.post("/api/v1/task-status")
async def create_or_update_task_status(task_status: TaskStatusCreate):
    """Create or update task status (replaces direct task_status table writes)"""
    async with pool.acquire() as conn:
        try:
            await conn.execute("""
                INSERT INTO task_status 
                (task_id, agent_name, status, progress, eta, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (task_id) 
                DO UPDATE SET 
                    agent_name = $2,
                    status = $3,
                    progress = $4,
                    eta = $5,
                    updated_at = $6
            """, task_status.task_id, task_status.agent_name, task_status.status,
                task_status.progress, task_status.eta, datetime.utcnow())
            return {"status": "updated", "task_id": task_status.task_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update task status: {str(e)}")

@app.put("/api/v1/task-status/{task_id}")
async def update_task_status(task_id: str, update: TaskStatusUpdate):
    """Update task status fields"""
    updates = []
    params = []
    param_count = 1
    
    if update.status:
        updates.append(f"status = ${param_count}")
        params.append(update.status)
        param_count += 1
    
    if update.progress is not None:
        updates.append(f"progress = ${param_count}")
        params.append(update.progress)
        param_count += 1
    
    if update.eta:
        updates.append(f"eta = ${param_count}")
        params.append(update.eta)
        param_count += 1
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    updates.append(f"updated_at = ${param_count}")
    params.append(datetime.utcnow())
    param_count += 1
    
    params.append(task_id)
    query = f"UPDATE task_status SET {', '.join(updates)} WHERE task_id = ${param_count}"
    
    async with pool.acquire() as conn:
        result = await conn.execute(query, *params)
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail=f"Task status {task_id} not found")
    
    return {"status": "updated", "task_id": task_id}

@app.get("/api/v1/task-status/{task_id}")
async def get_task_status(task_id: str):
    """Get task status by task_id"""
    async with pool.acquire() as conn:
        status = await conn.fetchrow("""
            SELECT * FROM task_status 
            WHERE task_id = $1
        """, task_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Task status {task_id} not found")
        return dict(status)

# Agent Status Management Endpoints (replaces direct agent_status table writes)

class AgentStatusCreate(BaseModel):
    agent_name: str
    status: str
    current_task_id: Optional[str] = None
    version: Optional[str] = None
    tps: int = 0

class AgentStatusUpdate(BaseModel):
    status: Optional[str] = None
    current_task_id: Optional[str] = None
    version: Optional[str] = None
    tps: Optional[int] = None

@app.post("/api/v1/agent-status")
async def create_or_update_agent_status(agent_status: AgentStatusCreate):
    """Create or update agent status (replaces direct agent_status table writes for heartbeats)"""
    async with pool.acquire() as conn:
        try:
            await conn.execute("""
                INSERT INTO agent_status 
                (agent_name, status, last_heartbeat, current_task_id, version, tps, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (agent_name) 
                DO UPDATE SET 
                    status = $2,
                    last_heartbeat = $3,
                    current_task_id = $4,
                    version = $5,
                    tps = $6,
                    updated_at = $7
            """, agent_status.agent_name, agent_status.status, datetime.utcnow(),
                agent_status.current_task_id, agent_status.version, agent_status.tps,
                datetime.utcnow())
            return {"status": "updated", "agent_name": agent_status.agent_name}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update agent status: {str(e)}")

@app.put("/api/v1/agent-status/{agent_name}")
async def update_agent_status(agent_name: str, update: AgentStatusUpdate):
    """Update agent status fields"""
    updates = []
    params = []
    param_count = 1
    
    if update.status:
        updates.append(f"status = ${param_count}")
        params.append(update.status)
        param_count += 1
    
    if update.current_task_id is not None:
        updates.append(f"current_task_id = ${param_count}")
        params.append(update.current_task_id)
        param_count += 1
    
    if update.version:
        updates.append(f"version = ${param_count}")
        params.append(update.version)
        param_count += 1
    
    if update.tps is not None:
        updates.append(f"tps = ${param_count}")
        params.append(update.tps)
        param_count += 1
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    updates.append(f"last_heartbeat = ${param_count}")
    params.append(datetime.utcnow())
    param_count += 1
    updates.append(f"updated_at = ${param_count}")
    params.append(datetime.utcnow())
    param_count += 1
    
    params.append(agent_name)
    query = f"UPDATE agent_status SET {', '.join(updates)} WHERE agent_name = ${param_count}"
    
    async with pool.acquire() as conn:
        result = await conn.execute(query, *params)
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail=f"Agent status {agent_name} not found")
    
    return {"status": "updated", "agent_name": agent_name}

@app.get("/api/v1/agent-status/{agent_name}")
async def get_agent_status(agent_name: str):
    """Get agent status by agent_name"""
    async with pool.acquire() as conn:
        status = await conn.fetchrow("""
            SELECT * FROM agent_status 
            WHERE agent_name = $1
        """, agent_name)
        if not status:
            raise HTTPException(status_code=404, detail=f"Agent status {agent_name} not found")
        return dict(status)

# Execution Cycle Get by ECID (single cycle)

@app.get("/api/v1/execution-cycles/{ecid}")
async def get_execution_cycle(ecid: str):
    """Get a single execution cycle by ECID"""
    async with pool.acquire() as conn:
        cycle = await conn.fetchrow("""
            SELECT * FROM execution_cycle 
            WHERE ecid = $1
        """, ecid)
        if not cycle:
            raise HTTPException(status_code=404, detail=f"Execution cycle {ecid} not found")
        return dict(cycle)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "task-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
