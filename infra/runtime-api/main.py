import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

# Add parent directory to path to allow importing deps
sys.path.insert(0, str(Path(__file__).parent))

from deps import (
    get_tasks_adapter_dep,  # SIP-0048: dependency function (kept same name for compatibility)
)

from agents.tasks.base_adapter import TaskAdapterBase
from agents.tasks.errors import (
    TaskAdapterError,
    TaskConflictError,
    TaskNotFoundError,
)
from agents.tasks.models import FlowState, TaskCreate, TaskFilters, TaskState

# Initialize centralized configuration
from config.unified_config import get_config

app = FastAPI(
    title="SquadOps Runtime API", version="1.0"
)  # SIP-0048: renamed from Task Management API

# Get PostgreSQL URL from centralized config system
config = get_config()
POSTGRES_URL = config.get_postgres_url()

# Global connection pool (for memory endpoints only)
pool = None

# Global RabbitMQ connection and channel (for task publishing)
rabbitmq_connection = None
rabbitmq_channel = None


@app.on_event("startup")
async def startup_event():
    global pool, rabbitmq_connection, rabbitmq_channel
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=10)

    # Initialize RabbitMQ connection (persistent, like agents do)
    import logging

    logger = logging.getLogger(__name__)
    try:
        import aio_pika

        rabbitmq_url = config.get_rabbitmq_url()
        print("[STARTUP] Attempting to connect to RabbitMQ...", flush=True)
        global rabbitmq_connection, rabbitmq_channel  # Ensure we're modifying globals
        rabbitmq_connection = await aio_pika.connect_robust(rabbitmq_url)
        rabbitmq_channel = await rabbitmq_connection.channel()
        print(
            f"[STARTUP] ✅ RabbitMQ connection established during startup (connection={rabbitmq_connection is not None}, channel={rabbitmq_channel is not None})",
            flush=True,
        )
        logger.info("RabbitMQ connection established during startup")
    except Exception as e:
        # Log error but don't fail startup - connection will be retried on first use
        print(f"[STARTUP] ❌ Failed to initialize RabbitMQ connection: {e}", flush=True)
        logger.error(f"Failed to initialize RabbitMQ connection during startup: {e}", exc_info=True)

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
    global pool, rabbitmq_connection
    if pool:
        await pool.close()
    if rabbitmq_connection:
        await rabbitmq_connection.close()

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
    cycle_id: str  # SIP-0048: renamed from ecid
    pid: str
    project_id: str | None = None  # SIP-0047
    run_type: str
    title: str
    description: str | None = None
    initiated_by: str


class ExecutionCycleUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


class TaskLogCreate(BaseModel):
    """ACI v0.8: Task creation request with required lineage fields"""

    task_id: str
    cycle_id: str  # SIP-0048: renamed from ecid
    agent: str  # Kept for backward compatibility
    agent_id: str | None = None  # SIP-0048: Agent identifier (use agent_id, not role normalization)
    task_name: str | None = None  # Optional human-readable label
    task_type: str  # Required standardized taxonomy/behavior category (ACI)
    inputs: dict[str, Any] = Field(default_factory=dict)  # Required structured task inputs (ACI)
    status: str
    priority: str | None = "MEDIUM"
    description: str | None = None
    pid: str | None = None  # SIP-0048: Process identifier
    dependencies: list[str] | None = []
    delegated_by: str | None = None
    delegated_to: str | None = None

    # ACI Lineage fields (required, will be generated if not provided)
    project_id: str | None = None
    pulse_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None


class TaskLogUpdate(BaseModel):
    status: str | None = None
    end_time: datetime | None = None
    artifacts: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None  # SIP-0048: Task metrics as JSON
    error_log: str | None = None
    dependencies: list[str] | None = None  # SIP-0048: Allow updating dependencies


class TaskCompleteRequest(BaseModel):
    task_id: str
    artifacts: dict[str, Any] | None = None


class TaskFailRequest(BaseModel):
    task_id: str
    error_log: str


class TaskStatusCreate(BaseModel):
    task_id: str
    agent_name: str
    status: str
    progress: float = 0.0
    eta: str | None = None


class TaskStatusUpdate(BaseModel):
    status: str | None = None
    progress: float | None = None
    eta: str | None = None


# Helper functions to convert between DTOs and legacy formats
def task_to_dict(task) -> dict:
    """Convert Task DTO to legacy dict format"""
    result = {
        "task_id": task.task_id,
        "pid": task.pid,
        "cycle_id": task.cycle_id,  # SIP-0048: renamed from ecid
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
        result["artifacts"] = [a.dict() if hasattr(a, "dict") else a for a in task.artifacts]
    else:
        result["artifacts"] = None
    return result


def flow_to_dict(flow) -> dict:
    """Convert FlowRun DTO to legacy dict format"""
    return {
        "cycle_id": flow.cycle_id,  # SIP-0048: renamed from ecid
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


@app.get("/api/v1/tasks/ec/{cycle_id}")  # SIP-0048: renamed from ecid
async def get_tasks_by_cycle_id(
    cycle_id: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):  # SIP-0048: renamed from get_tasks_by_ecid
    """Get all tasks for a specific execution cycle"""
    try:
        tasks = await adapter.list_tasks_for_cycle_id(
            cycle_id
        )  # SIP-0048: renamed from list_tasks_for_ecid
        return [task_to_dict(task) for task in tasks]
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


@app.get("/api/v1/tasks/agent/{agent_name}")
async def get_tasks_by_agent(
    agent_name: str,
    cycle_id: str | None = None,  # SIP-0048: renamed from ecid
    limit: int = 50,
    adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep),
):
    """Get recent tasks for a specific agent, optionally filtered by cycle_id (SIP-0048: renamed from ECID)"""
    try:
        filters = TaskFilters(
            agent=agent_name, cycle_id=cycle_id, limit=limit
        )  # SIP-0048: renamed from ecid
        tasks = await adapter.list_tasks(filters)
        return [task_to_dict(task) for task in tasks]
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


@app.get("/api/v1/tasks/status/{status}")
async def get_tasks_by_status(
    status: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Get tasks by status"""
    try:
        filters = TaskFilters(status=status)
        tasks = await adapter.list_tasks(filters)
        return [task_to_dict(task) for task in tasks]
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


@app.get("/api/v1/execution-cycles")
async def get_execution_cycles(
    run_type: str | None = None, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Get execution cycles, optionally filtered by type"""
    try:
        flows = await adapter.list_flows(run_type)
        return [flow_to_dict(flow) for flow in flows]
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


@app.get("/api/v1/tasks/summary/{cycle_id}")  # SIP-0048: renamed from ecid
async def get_task_summary(
    cycle_id: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):  # SIP-0048: renamed from ecid
    """Get task summary for an execution cycle (SIP-0048: uses cycle_id)"""
    try:
        summary = await adapter.get_task_summary(cycle_id)  # SIP-0048: renamed from ecid
        # Convert TaskSummary DTO to dict for backward compatibility
        return summary.dict()
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


# POST/PUT endpoints for agents to create and update tasks


@app.post("/api/v1/execution-cycles")
async def create_execution_cycle(
    cycle: ExecutionCycleCreate, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Create a new execution cycle (SIP-0048: uses cycle_id)"""
    try:
        await adapter.create_flow(
            cycle.cycle_id,  # SIP-0048: renamed from ecid
            cycle.pid,
            meta={
                "project_id": cycle.project_id,  # SIP-0047
                "run_type": cycle.run_type,
                "title": cycle.title,
                "description": cycle.description,
                "initiated_by": cycle.initiated_by,
            },
        )
        return {"status": "created", "cycle_id": cycle.cycle_id}  # SIP-0048: renamed from ecid
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


@app.put("/api/v1/execution-cycles/{cycle_id}")  # SIP-0048: renamed from ecid
async def update_execution_cycle(
    cycle_id: str,  # SIP-0048: renamed from ecid
    update: ExecutionCycleUpdate,
    adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep),
):
    """Update execution cycle status or notes (SIP-0048: uses cycle_id)"""
    if not update.status and not update.notes:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        # Determine state from status
        state = FlowState.ACTIVE
        if update.status == "completed":
            state = FlowState.COMPLETED
        elif update.status == "failed":
            state = FlowState.FAILED

        await adapter.update_flow(
            cycle_id,  # SIP-0048: renamed from ecid
            state,
            meta={
                "status": update.status,
                "notes": update.notes,
            },
        )
        return {"status": "updated", "cycle_id": cycle_id}  # SIP-0048: renamed from ecid
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


@app.post("/api/v1/execution-cycles/{cycle_id}/complete")  # SIP-0048: renamed from ecid
async def complete_execution_cycle(
    cycle_id: str,
    notes: str | None = None,
    adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep),
):  # SIP-0048: renamed from ecid
    """Mark execution cycle as completed (SIP-0048: uses cycle_id)"""
    update = ExecutionCycleUpdate(status="completed", notes=notes)
    return await update_execution_cycle(cycle_id, update, adapter)


@app.post("/api/v1/execution-cycles/{cycle_id}/fail")  # SIP-0048: renamed from ecid
async def fail_execution_cycle(
    cycle_id: str, notes: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):  # SIP-0048: renamed from ecid
    """Mark execution cycle as failed (SIP-0048: uses cycle_id)"""
    update = ExecutionCycleUpdate(status="failed", notes=notes)
    return await update_execution_cycle(cycle_id, update, adapter)


@app.post("/api/v1/tasks/start")
async def start_task(
    task: TaskLogCreate, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """
    Create task with ACI TaskEnvelope contract.

    Returns fully populated TaskEnvelope (not legacy task dict).
    All lineage fields are required in request or generated via LineageGenerator.
    """
    try:
        from agents.utils.lineage_generator import LineageGenerator

        # Generate missing lineage fields
        lineage = LineageGenerator.ensure_lineage_fields(
            cycle_id=task.cycle_id,
            task_id=task.task_id,
            correlation_id=task.correlation_id,
            causation_id=task.causation_id,
            trace_id=task.trace_id,
            span_id=task.span_id,
            tracing_enabled=False,  # Placeholder mode for v0.8
        )

        # Get project_id from cycle if not provided
        if not task.project_id:
            # Try to get from cycle
            flow = await adapter.get_flow(task.cycle_id)
            if flow and flow.project_id:
                project_id = flow.project_id
            else:
                project_id = "project-placeholder"  # Fallback
        else:
            project_id = task.project_id

        # Get pulse_id or generate placeholder
        pulse_id = task.pulse_id or f"pulse-placeholder-{task.task_id}"

        # Create TaskCreate with all lineage fields
        task_create = TaskCreate(
            task_id=task.task_id,
            cycle_id=task.cycle_id,
            agent=task.agent,
            agent_id=task.agent_id or task.agent,
            task_name=task.task_name,
            task_type=task.task_type,
            inputs=task.inputs,
            status=task.status,
            priority=task.priority,
            description=task.description,
            pid=task.pid,
            dependencies=task.dependencies or [],
            delegated_by=task.delegated_by,
            delegated_to=task.delegated_to,
            project_id=project_id,
            pulse_id=pulse_id,
            correlation_id=lineage["correlation_id"],
            causation_id=lineage["causation_id"],
            trace_id=lineage["trace_id"],
            span_id=lineage["span_id"],
        )

        # Create task via adapter (stores in DB with lineage fields)
        created_task = await adapter.create_task(task_create)

        # Construct TaskEnvelope
        from agents.tasks.models import TaskEnvelope

        envelope = TaskEnvelope(
            task_id=created_task.task_id,
            agent_id=created_task.agent_id or created_task.agent,
            cycle_id=created_task.cycle_id,
            pulse_id=pulse_id,
            project_id=project_id,
            task_type=task.task_type,
            inputs=task.inputs,
            correlation_id=lineage["correlation_id"],
            causation_id=lineage["causation_id"],
            trace_id=lineage["trace_id"],
            span_id=lineage["span_id"],
            priority=created_task.priority,
            metadata={
                "task_name": created_task.task_name,
                "phase": created_task.phase,
                "description": created_task.description,
            },
            task_name=created_task.task_name,
        )

        # Publish TaskEnvelope to RabbitMQ for agent consumption
        # Use persistent channel established at startup (like agents do)
        try:
            from agents.utils.task_envelope import send_envelope_to_agent_queue

            global rabbitmq_channel

            # Ensure channel is available (fallback to creating connection if startup failed)
            if rabbitmq_channel is None:
                import logging

                import aio_pika

                logger = logging.getLogger(__name__)
                logger.warning("RabbitMQ channel not available, creating temporary connection")
                rabbitmq_url = config.get_rabbitmq_url()
                connection = await aio_pika.connect_robust(rabbitmq_url)
                try:
                    channel = await connection.channel()
                    await send_envelope_to_agent_queue(channel, envelope.agent_id, envelope)
                finally:
                    await connection.close()
            else:
                await send_envelope_to_agent_queue(rabbitmq_channel, envelope.agent_id, envelope)
        except Exception as e:
            # Log error but don't fail task creation - task is already in DB
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to publish task {envelope.task_id} to RabbitMQ: {e}")

        return envelope.model_dump()
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


@app.put("/api/v1/tasks/{task_id}")
async def update_task(
    task_id: str, update: TaskLogUpdate, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Update task status, completion, or error"""
    if (
        not update.status
        and not update.end_time
        and not update.artifacts
        and not update.error_log
        and not update.metrics
        and not update.dependencies
    ):
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
        if update.metrics:  # SIP-0048: new field
            meta["metrics"] = update.metrics
        if update.dependencies:  # SIP-0048: allow updating dependencies
            meta["dependencies"] = update.dependencies
        if update.error_log:
            meta["error_log"] = update.error_log

        await adapter.update_task_state(task_id, state, meta)
        return {"status": "updated", "task_id": task_id}
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}") from e


@app.post("/api/v1/tasks/complete")
async def complete_task(
    request: TaskCompleteRequest, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Mark task as completed with optional artifacts"""
    update = TaskLogUpdate(
        status="completed", end_time=datetime.utcnow(), artifacts=request.artifacts
    )
    return await update_task(request.task_id, update, adapter)


@app.post("/api/v1/tasks/fail")
async def fail_task(
    request: TaskFailRequest, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Mark task as failed with error log"""
    update = TaskLogUpdate(status="failed", end_time=datetime.utcnow(), error_log=request.error_log)
    return await update_task(request.task_id, update, adapter)


# Task Status Management Endpoints


@app.post("/api/v1/task-status")
async def create_or_update_task_status(
    task_status: TaskStatusCreate, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Create or update task status (replaces direct task_status table writes)"""
    try:
        await adapter.update_task_status(
            task_status.task_id,
            task_status.status,
            task_status.progress,
            task_status.eta,
            task_status.agent_name,
        )
        return {"status": "updated", "task_id": task_status.task_id}
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


@app.put("/api/v1/task-status/{task_id}")
async def update_task_status_endpoint(
    task_id: str,
    update: TaskStatusUpdate,
    adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep),
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
async def get_task_status_endpoint(
    task_id: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Get task status by task_id"""
    try:
        status = await adapter.get_task_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Task status {task_id} not found")
        return status
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


@app.get("/api/v1/execution-cycles/{cycle_id}")  # SIP-0048: renamed from ecid
async def get_execution_cycle(
    cycle_id: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):  # SIP-0048: renamed from ecid
    """Get a single execution cycle by cycle_id (SIP-0048: renamed from ECID)"""
    try:
        flow = await adapter.get_flow(cycle_id)  # SIP-0048: renamed from ecid
        if not flow:
            raise HTTPException(
                status_code=404, detail=f"Execution cycle {cycle_id} not found"
            )  # SIP-0048: renamed from ecid
        return flow_to_dict(flow)
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "runtime-api"}  # SIP-0048: renamed from task-api


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

        from agents.memory.promotion import PromotionService
        from agents.memory.sql_adapter import SqlAdapter

        # Initialize adapters
        mem0_adapter = Mem0Adapter(request.agent_name)
        sql_adapter = SqlAdapter(pool)

        # Create promotion service
        promotion_service = PromotionService(mem0_adapter, sql_adapter, pool)

        # Promote memory
        promoted_id = await promotion_service.promote_memory(
            request.memory_id, request.validator, request.agent_name, request.auto_promote
        )

        if promoted_id:
            return {
                "status": "promoted",
                "memory_id": promoted_id,
                "original_id": request.memory_id,
            }
        else:
            raise HTTPException(
                status_code=400, detail="Memory promotion failed or criteria not met"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to promote memory: {str(e)}") from e


@app.get("/api/v1/memory/promoted")
async def get_promoted_memories(
    agent: str | None = None,
    pid: str | None = None,
    cycle_id: str | None = None,  # SIP-0048: renamed from ecid
    limit: int = 50,
):
    """Get promoted memories from Squad Memory Pool (SIP-0048: uses cycle_id)"""
    try:
        from agents.memory.sql_adapter import SqlAdapter

        sql_adapter = SqlAdapter(pool)

        kwargs = {"status": "validated"}
        if agent:
            kwargs["agent"] = agent
        if pid:
            kwargs["pid"] = pid
        if cycle_id:  # SIP-0048: renamed from ecid
            kwargs["cycle_id"] = cycle_id  # SIP-0048: renamed from ecid

        memories = await sql_adapter.get("", k=limit, **kwargs)
        return {"memories": memories, "count": len(memories)}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve promoted memories: {str(e)}"
        ) from e


# SIP-0048: Additional Runtime API endpoints


@app.post("/api/v1/cycles")  # SIP-0048: Alias for /api/v1/execution-cycles
async def create_cycle(
    cycle: ExecutionCycleCreate, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Create a new execution cycle (SIP-0048: alias for /api/v1/execution-cycles)"""
    return await create_execution_cycle(cycle, adapter)


@app.get("/api/v1/cycles/{cycle_id}")  # SIP-0048: Alias for /api/v1/execution-cycles/{cycle_id}
async def get_cycle(cycle_id: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)):
    """Get a single execution cycle by cycle_id (SIP-0048: alias for /api/v1/execution-cycles/{cycle_id})"""
    return await get_execution_cycle(cycle_id, adapter)


@app.get("/api/v1/cycles/{cycle_id}/tasks/pending")  # SIP-0048: List pending tasks for a cycle
async def get_pending_tasks_for_cycle(
    cycle_id: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Get pending tasks for a specific cycle (SIP-0048)"""
    try:
        filters = TaskFilters(cycle_id=cycle_id, status="pending")
        tasks = await adapter.list_tasks(filters)
        return [task_to_dict(task) for task in tasks]
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


@app.post("/api/v1/tasks/{task_id}/results")  # SIP-0048: Submit task result
async def submit_task_result(
    task_id: str, result: dict[str, Any], adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Submit task result (SIP-0048)"""
    try:
        # Update task with result data
        meta = {
            "artifacts": result.get("artifacts", []),
            "metrics": result.get("metrics", {}),
        }
        await adapter.update_task_state(task_id, TaskState.COMPLETED, meta)
        return {"status": "result_submitted", "task_id": task_id}
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


@app.get("/api/v1/agents")  # SIP-0048: List agents
async def list_agents():
    """List all agents (SIP-0048)"""
    try:
        # Query agent_status table for agent information
        from agents.memory.sql_adapter import SqlAdapter

        sql_adapter = SqlAdapter()

        # Get agent statuses from database
        # Note: This is a simplified implementation - can be enhanced with actual agent registry
        agents = []
        # For now, return a placeholder - this should query agent_status table
        return {"agents": agents, "count": len(agents)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing agents: {str(e)}")


@app.get("/api/v1/agents/{agent_id}/state")  # SIP-0048: Get agent runtime state
async def get_agent_state(agent_id: str):
    """Get agent runtime state (SIP-0048)"""
    try:
        # Query agent_status table for specific agent
        from agents.memory.sql_adapter import SqlAdapter

        sql_adapter = SqlAdapter()

        # For now, return a placeholder - this should query agent_status table
        return {
            "agent_id": agent_id,
            "status": "unknown",
            "last_heartbeat": None,
            "current_task_id": None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting agent state: {str(e)}")


@app.get("/api/v1/cycles/{cycle_id}/runtime")  # SIP-0048: Get cycle runtime state snapshot
async def get_cycle_runtime(
    cycle_id: str, adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Get comprehensive cycle runtime state snapshot (SIP-0048)"""
    try:
        # Get cycle information
        cycle = await adapter.get_flow(cycle_id)
        if not cycle:
            raise HTTPException(status_code=404, detail=f"Cycle {cycle_id} not found")

        # Get all tasks for this cycle
        tasks = await adapter.list_tasks_for_cycle_id(cycle_id)

        # Get task summary
        summary = await adapter.get_task_summary(cycle_id)

        return {
            "cycle": flow_to_dict(cycle),
            "tasks": [task_to_dict(task) for task in tasks],
            "summary": summary.dict() if hasattr(summary, "dict") else summary,
        }
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cycle runtime: {str(e)}")


@app.get("/api/v1/scheduler/status")  # SIP-0048: Get scheduler status
async def get_scheduler_status():
    """Get scheduler health and queue status (SIP-0048)"""
    try:
        # Placeholder implementation - should query actual scheduler state
        return {
            "status": "healthy",
            "queues": {},
            "message": "Scheduler status endpoint - implementation pending",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting scheduler status: {str(e)}")


@app.post("/api/v1/cycles/{cycle_id}/actions")  # SIP-0048: Control cycle (pause, resume, cancel)
async def cycle_action(
    cycle_id: str, action: dict[str, str], adapter: TaskAdapterBase = Depends(get_tasks_adapter_dep)
):
    """Control cycle (pause, resume, cancel) (SIP-0048)"""
    action_type = action.get("action")
    if action_type not in ["pause", "resume", "cancel"]:
        raise HTTPException(
            status_code=400, detail="Invalid action. Must be: pause, resume, or cancel"
        )

    try:
        # Map action to status
        status_map = {"pause": "paused", "resume": "active", "cancel": "cancelled"}

        update = ExecutionCycleUpdate(status=status_map[action_type])
        return await update_execution_cycle(cycle_id, update, adapter)
    except TaskAdapterError as e:
        raise handle_adapter_error(e) from e


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
