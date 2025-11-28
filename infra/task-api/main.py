from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import asyncpg
import os
from typing import List, Optional, Dict, Any
from datetime import datetime

import sys
from pathlib import Path

# Add parent directory to path to allow importing deps
sys.path.insert(0, str(Path(__file__).parent))

from agents.tasks.base_adapter import TaskAdapterBase
from agents.tasks.models import TaskCreate, TaskState, TaskFilters, FlowCreate, FlowUpdate, FlowState
from agents.tasks.errors import (
    TaskAdapterError,
    TaskNotFoundError,
    TaskConflictError,
)
from deps import get_tasks_adapter_dep

app = FastAPI(title="SquadOps Task Management API", version="1.0")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://squadops:squadops123@postgres:5432/squadops")

# Global connection pool (for memory endpoints only)
pool = None

@app.on_event("startup")
async def startup_event():
    global pool
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=10)
    
    # Initialize tasks adapter
    try:
        from agents.tasks.registry import get_tasks_adapter
        adapter = await get_tasks_adapter()
        await adapter.initialize()
    except Exception as e:
        # Log error but don't fail startup - adapter will be initialized on first use
        import logging
        logging.error(f"Failed to initialize tasks adapter during startup: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    global pool
    if pool:
        await pool.close()
    
    # Shutdown tasks adapter
    try:
        from agents.tasks.registry import get_tasks_adapter
        adapter = await get_tasks_adapter()
        await adapter.shutdown()
    except Exception as e:
        # Log error but continue shutdown
        import logging
        logging.error(f"Error during tasks adapter shutdown: {e}")

# Pydantic models (for backward compatibility with existing API clients)
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

class TaskCompleteRequest(BaseModel):
    task_id: str
    artifacts: Optional[Dict[str, Any]] = None

class TaskFailRequest(BaseModel):
    task_id: str
    error_log: str

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

# Helper functions to convert between DTOs and legacy formats
def task_to_dict(task) -> dict:
    """Convert Task DTO to legacy dict format"""
    result = {
        "task_id": task.task_id,
        "pid": task.pid,
        "ecid": task.ecid,
        "agent": task.agent,
        "phase": task.phase,
        "status": task.status,
        "priority": task.priority,
        "description": task.description,
        "start_time": task.start_time.isoformat() if task.start_time else None,
        "end_time": task.end_time.isoformat() if task.end_time else None,
        "duration": task.duration,
        "dependencies": task.dependencies,
        "error_log": task.error_log,
        "delegated_by": task.delegated_by,
        "delegated_to": task.delegated_to,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }
    # Convert artifacts to dict format
    if task.artifacts:
        result["artifacts"] = [a.dict() if hasattr(a, 'dict') else a for a in task.artifacts]
    else:
        result["artifacts"] = None
    return result

def flow_to_dict(flow) -> dict:
    """Convert FlowRun DTO to legacy dict format"""
    return {
        "ecid": flow.ecid,
        "pid": flow.pid,
        "run_type": flow.run_type,
        "title": flow.title,
        "description": flow.description,
        "created_at": flow.created_at.isoformat() if flow.created_at else None,
        "initiated_by": flow.initiated_by,
        "status": flow.status,
        "notes": flow.notes,
    }

def handle_adapter_error(e: Exception) -> HTTPException:
    """Map TaskAdapterError to appropriate HTTPException"""
    if isinstance(e, TaskNotFoundError):
        return HTTPException(status_code=404, detail=str(e))
    elif isinstance(e, TaskConflictError):
        return HTTPException(status_code=409, detail=str(e))
    elif isinstance(e, TaskAdapterError):
        return HTTPException(status_code=500, detail=str(e))
    else:
        return HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# GET endpoints for querying tasks and execution cycles

@app.get("/api/v1/tasks/ec/{ecid}")
async def get_tasks_by_ecid(ecid: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Get all tasks for a specific execution cycle"""
    try:
        tasks = await adapter.list_tasks_for_ecid(ecid)
        return [task_to_dict(task) for task in tasks]
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

@app.get("/api/v1/tasks/agent/{agent_name}")
async def get_tasks_by_agent(
    agent_name: str, 
    ecid: Optional[str] = None, 
    limit: int = 50,
    adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Get recent tasks for a specific agent, optionally filtered by ECID"""
    try:
        filters = TaskFilters(agent=agent_name, ecid=ecid, limit=limit)
        tasks = await adapter.list_tasks(filters)
        return [task_to_dict(task) for task in tasks]
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

@app.get("/api/v1/tasks/status/{status}")
async def get_tasks_by_status(status: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Get tasks by status"""
    try:
        filters = TaskFilters(status=status)
        tasks = await adapter.list_tasks(filters)
        return [task_to_dict(task) for task in tasks]
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

@app.get("/api/v1/execution-cycles")
async def get_execution_cycles(run_type: Optional[str] = None, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Get execution cycles, optionally filtered by type"""
    try:
        flows = await adapter.list_flows(run_type)
        return [flow_to_dict(flow) for flow in flows]
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

@app.get("/api/v1/tasks/summary/{ecid}")
async def get_task_summary(ecid: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Get task summary for an execution cycle"""
    try:
        summary = await adapter.get_task_summary(ecid)
        # Convert TaskSummary DTO to dict for backward compatibility
        return summary.dict()
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

# POST/PUT endpoints for agents to create and update tasks

@app.post("/api/v1/execution-cycles")
async def create_execution_cycle(cycle: ExecutionCycleCreate, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Create a new execution cycle"""
    try:
        flow = await adapter.create_flow(
            cycle.ecid,
            cycle.pid,
            meta={
                "run_type": cycle.run_type,
                "title": cycle.title,
                "description": cycle.description,
                "initiated_by": cycle.initiated_by,
            }
        )
        return {"status": "created", "ecid": cycle.ecid}
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

@app.put("/api/v1/execution-cycles/{ecid}")
async def update_execution_cycle(
    ecid: str, 
    update: ExecutionCycleUpdate,
    adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Update execution cycle status or notes"""
    if not update.status and not update.notes:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    try:
        # Determine state from status
        state = FlowState.ACTIVE
        if update.status == "completed":
            state = FlowState.COMPLETED
        elif update.status == "failed":
            state = FlowState.FAILED
        
        flow = await adapter.update_flow(
            ecid,
            state,
            meta={
                "status": update.status,
                "notes": update.notes,
            }
        )
        return {"status": "updated", "ecid": ecid}
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

@app.post("/api/v1/execution-cycles/{ecid}/complete")
async def complete_execution_cycle(ecid: str, notes: Optional[str] = None, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Mark execution cycle as completed"""
    update = ExecutionCycleUpdate(status="completed", notes=notes)
    return await update_execution_cycle(ecid, update, adapter)

@app.post("/api/v1/execution-cycles/{ecid}/fail")
async def fail_execution_cycle(ecid: str, notes: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Mark execution cycle as failed"""
    update = ExecutionCycleUpdate(status="failed", notes=notes)
    return await update_execution_cycle(ecid, update, adapter)

@app.post("/api/v1/tasks/start")
async def start_task(task: TaskLogCreate, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Log task start"""
    try:
        task_create = TaskCreate(
            task_id=task.task_id,
            ecid=task.ecid,
            agent=task.agent,
            status=task.status,
            priority=task.priority,
            description=task.description,
            dependencies=task.dependencies or [],
            delegated_by=task.delegated_by,
            delegated_to=task.delegated_to,
        )
        await adapter.create_task(task_create)
        return {"status": "started", "task_id": task.task_id}
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

@app.put("/api/v1/tasks/{task_id}")
async def update_task(
    task_id: str, 
    update: TaskLogUpdate,
    adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Update task status, completion, or error"""
    if not update.status and not update.end_time and not update.artifacts and not update.error_log:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    try:
        # Determine state from status
        state = TaskState.STARTED
        if update.status:
            try:
                state = TaskState(update.status)
            except ValueError:
                state = TaskState.STARTED  # Default if status doesn't match enum
        
        meta = {}
        if update.end_time:
            meta["end_time"] = update.end_time
        if update.artifacts:
            meta["artifacts"] = update.artifacts
        if update.error_log:
            meta["error_log"] = update.error_log
        
        await adapter.update_task_state(task_id, state, meta)
        return {"status": "updated", "task_id": task_id}
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

@app.post("/api/v1/tasks/complete")
async def complete_task(request: TaskCompleteRequest, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Mark task as completed with optional artifacts"""
    update = TaskLogUpdate(
        status="completed",
        end_time=datetime.utcnow(),
        artifacts=request.artifacts
    )
    return await update_task(request.task_id, update, adapter)

@app.post("/api/v1/tasks/fail")
async def fail_task(request: TaskFailRequest, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Mark task as failed with error log"""
    update = TaskLogUpdate(
        status="failed",
        end_time=datetime.utcnow(),
        error_log=request.error_log
    )
    return await update_task(request.task_id, update, adapter)

# Task Status Management Endpoints

@app.post("/api/v1/task-status")
async def create_or_update_task_status(
    task_status: TaskStatusCreate,
    adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Create or update task status (replaces direct task_status table writes)"""
    try:
        result = await adapter.update_task_status(
            task_status.task_id,
            task_status.status,
            task_status.progress,
            task_status.eta,
            task_status.agent_name
        )
        return {"status": "updated", "task_id": task_status.task_id}
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

@app.put("/api/v1/task-status/{task_id}")
async def update_task_status_endpoint(
    task_id: str, 
    update: TaskStatusUpdate,
    adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Update task status fields"""
    if not update.status and update.progress is None and not update.eta:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    try:
        # Get existing status to preserve agent_name
        existing = await adapter.get_task_status(task_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Task status {task_id} not found")
        
        status = update.status or existing.get("status", "")
        progress = update.progress if update.progress is not None else existing.get("progress", 0.0)
        eta = update.eta or existing.get("eta")
        agent_name = existing.get("agent_name", "")
        
        await adapter.update_task_status(task_id, status, progress, eta, agent_name)
        return {"status": "updated", "task_id": task_id}
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

@app.get("/api/v1/task-status/{task_id}")
async def get_task_status_endpoint(task_id: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Get task status by task_id"""
    try:
        status = await adapter.get_task_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Task status {task_id} not found")
        return status
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

@app.get("/api/v1/execution-cycles/{ecid}")
async def get_execution_cycle(ecid: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Get a single execution cycle by ECID"""
    try:
        flow = await adapter.get_flow(ecid)
        if not flow:
            raise HTTPException(status_code=404, detail=f"Execution cycle {ecid} not found")
        return flow_to_dict(flow)
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "task-api"}

# Memory Promotion Endpoints (SIP-042) - unchanged, uses separate pool

class MemoryPromoteRequest(BaseModel):
    memory_id: str
    validator: str
    agent_name: str
    auto_promote: bool = False

@app.post("/api/v1/memory/promote")
async def promote_memory(request: MemoryPromoteRequest):
    """Promote a memory from Mem0 to Squad Memory Pool"""
    try:
        from agents.memory.mem0_adapter import Mem0Adapter
        from agents.memory.sql_adapter import SqlAdapter
        from agents.memory.promotion import PromotionService
        
        # Initialize adapters
        mem0_adapter = Mem0Adapter(request.agent_name)
        sql_adapter = SqlAdapter(pool)
        
        # Create promotion service
        promotion_service = PromotionService(mem0_adapter, sql_adapter, pool)
        
        # Promote memory
        promoted_id = await promotion_service.promote_memory(
            request.memory_id,
            request.validator,
            request.agent_name,
            request.auto_promote
        )
        
        if promoted_id:
            return {"status": "promoted", "memory_id": promoted_id, "original_id": request.memory_id}
        else:
            raise HTTPException(status_code=400, detail="Memory promotion failed or criteria not met")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to promote memory: {str(e)}") from e

@app.get("/api/v1/memory/promoted")
async def get_promoted_memories(agent: Optional[str] = None, 
                               pid: Optional[str] = None,
                               ecid: Optional[str] = None,
                               limit: int = 50):
    """Get promoted memories from Squad Memory Pool"""
    try:
        from agents.memory.sql_adapter import SqlAdapter
        
        sql_adapter = SqlAdapter(pool)
        
        kwargs = {'status': 'validated'}
        if agent:
            kwargs['agent'] = agent
        if pid:
            kwargs['pid'] = pid
        if ecid:
            kwargs['ecid'] = ecid
        
        memories = await sql_adapter.get("", k=limit, **kwargs)
        return {"memories": memories, "count": len(memories)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve promoted memories: {str(e)}") from e

@app.get("/api/v1/memory/{mem_id}")
async def get_memory(mem_id: str):
    """Get memory details by ID"""
    try:
        from agents.memory.sql_adapter import SqlAdapter
        
        sql_adapter = SqlAdapter(pool)
        
        # Try to get from Squad Memory Pool first
        memories = await sql_adapter.get("", k=1, mem_ids=[mem_id])
        
        if memories:
            return memories[0]
        else:
            raise HTTPException(status_code=404, detail=f"Memory {mem_id} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memory: {str(e)}") from e

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
