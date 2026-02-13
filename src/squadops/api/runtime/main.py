"""
SquadOps Runtime API - Task and cycle management.

SIP-0048: Runtime API for task management, execution cycles, and memory operations.
Part of SIP-0.8.8 migration from _v0_legacy/infra/runtime-api/main.py

Usage:
    uvicorn squadops.api.runtime.main:app --host 0.0.0.0 --port 8001
"""

import logging
import os
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import aio_pika
import asyncpg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from squadops import __version__ as SQUADOPS_VERSION
from squadops.comms.envelope import send_envelope_to_agent_queue
from squadops.config import config_fingerprint, load_config, redact_config
from squadops.core.lineage import LineageGenerator
from squadops.ports.tasks.registry import TaskRegistryPort
from squadops.tasks.exceptions import TaskError, TaskNotFoundError, TaskStateError
from squadops.tasks.legacy_models import (
    LegacyTaskEnvelope,
    TaskCreate,
    TaskState,
)

from .deps import (
    get_tasks_adapter_dep,
    set_audit_port,
    set_auth_ports,
    set_cycle_ports,
    set_tasks_adapter,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SquadOps Runtime API",
    version=SQUADOPS_VERSION,
    description="SIP-0048: Runtime API for task management and execution cycles",
)

# Load configuration with profile selection and validation
strict_mode = os.getenv("SQUADOPS_STRICT_CONFIG", "false").lower() == "true"
config = load_config(strict=strict_mode)

# Extract configuration values
POSTGRES_URL = config.db.url
RABBITMQ_URL = config.comms.rabbitmq.url

# Log configuration at startup (SIP-051 requirement)
config_dict = config.model_dump()
redacted_config_dict = redact_config(config_dict)
fingerprint = config_fingerprint(redacted_config_dict)
logger.info(f"Configuration fingerprint: {fingerprint} (strict={strict_mode})")


def _extract_origin(uri: str) -> str:
    """Extract scheme://host:port from a URI (no path)."""
    parsed = urlparse(uri)
    origin = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        origin += f":{parsed.port}"
    return origin


# SIP-0062 Phase 3a: CORS middleware for browser-based clients
auth_config = config.auth
_cors_origins: set[str] = set()
if auth_config.console:
    _cors_origins.add(_extract_origin(auth_config.console.redirect_uri))
    if auth_config.console.post_logout_redirect_uri:
        _cors_origins.add(_extract_origin(auth_config.console.post_logout_redirect_uri))
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(_cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# SIP-0062: Add middleware in correct order (Request-ID → Auth → exception handling)
# Middleware is added in reverse order because Starlette processes them LIFO.
from squadops.api.middleware.auth import AuthMiddleware, RequestIDMiddleware

if auth_config.enabled:
    app.add_middleware(
        AuthMiddleware,
        auth_port=None,  # Port set at startup via deps; middleware uses deps.get_auth_port()
        provider=auth_config.provider,
        expose_docs=auth_config.expose_docs,
    )
app.add_middleware(RequestIDMiddleware)

# SIP-0062 Phase 3a: Include auth routes
from squadops.api.routes.auth import router as auth_router

app.include_router(auth_router)

# SIP-0064: Include cycle execution routes
from squadops.api.routes.cycles import (
    artifacts_router,
    cycles_router,
    profiles_router,
    projects_router,
    runs_router,
)

app.include_router(projects_router)
app.include_router(cycles_router)
app.include_router(runs_router)
app.include_router(profiles_router)
app.include_router(artifacts_router)

# Global connection pool (for memory endpoints only)
pool: asyncpg.Pool | None = None

# Global RabbitMQ connection and channel (for task publishing)
rabbitmq_connection: aio_pika.Connection | None = None
rabbitmq_channel: aio_pika.Channel | None = None

# PrefectReporter for shutdown cleanup
_prefect_reporter = None


@app.on_event("startup")
async def startup_event():
    """Initialize database and message queue connections."""
    global pool, rabbitmq_connection, rabbitmq_channel

    # Initialize PostgreSQL pool
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=10)

    # Initialize RabbitMQ connection (persistent, like agents do)
    try:
        logger.info("Attempting to connect to RabbitMQ...")
        rabbitmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
        rabbitmq_channel = await rabbitmq_connection.channel()
        logger.info("RabbitMQ connection established during startup")
    except Exception as e:
        # Log error but don't fail startup - connection will be retried on first use
        logger.error(f"Failed to initialize RabbitMQ connection during startup: {e}", exc_info=True)

    # Initialize auth adapters (SIP-0062)
    try:
        auth_config = config.auth
        if auth_config.enabled and auth_config.provider != "disabled":
            from adapters.auth.factory import create_auth_provider, create_authorization_provider

            auth_port = create_auth_provider(
                auth_config.provider,
                issuer_url=auth_config.oidc.issuer_url,
                audience=auth_config.oidc.audience,
                jwks_url=auth_config.oidc.jwks_url,
                roles_claim_path=auth_config.oidc.roles_claim_path,
                jwks_cache_ttl_seconds=auth_config.oidc.jwks_cache_ttl_seconds,
                jwks_forced_refresh_min_interval_seconds=auth_config.oidc.jwks_forced_refresh_min_interval_seconds,
                clock_skew_seconds=auth_config.oidc.clock_skew_seconds,
                issuer_public_url=auth_config.oidc.issuer_public_url,
            )
            authz_port = create_authorization_provider(
                auth_config.provider,
                roles_mode=auth_config.roles_mode,
                roles_client_id=auth_config.roles_client_id,
            )
            set_auth_ports(auth=auth_port, authz=authz_port)
            logger.info("Auth adapters initialized (provider=%s)", auth_config.provider)
        elif auth_config.enabled and auth_config.provider == "disabled":
            logger.info("Auth enabled but provider=disabled — protected endpoints return 503")
        else:
            logger.info("Auth disabled — no middleware attached")
    except Exception as e:
        logger.error(f"Failed to initialize auth adapters during startup: {e}")

    # Initialize audit adapter (SIP-0062 Phase 3b)
    try:
        from adapters.audit.factory import create_audit_provider

        audit = create_audit_provider("logging")
        set_audit_port(audit)
        logger.info("Audit adapter initialized")
    except Exception as e:
        logger.error(f"Failed to initialize audit adapter during startup: {e}")

    # Initialize service token clients (SIP-0062 Phase 3b)
    try:
        auth_config = config.auth
        if auth_config.service_clients and auth_config.oidc:
            from adapters.auth.factory import create_service_token_client

            for svc_name, svc_config in auth_config.service_clients.items():
                # secret_manager=None is correct: config loader pre-resolves
                # all secret:// references before AppConfig is created.
                create_service_token_client(
                    svc_name, svc_config, auth_config.oidc, secret_manager=None,
                )
                logger.info("Service token client initialized: %s", svc_name)
    except Exception as e:
        logger.error(f"Failed to initialize service token clients: {e}")

    # Initialize tasks adapter
    try:
        from adapters.tasks import create_task_registry_provider

        adapter = create_task_registry_provider(
            provider="sql",
            connection_string=POSTGRES_URL,
        )
        set_tasks_adapter(adapter)
        logger.info("Tasks adapter initialized")
    except Exception as e:
        logger.error(f"Failed to initialize tasks adapter during startup: {e}")

    # Initialize SIP-0064 cycle ports + SIP-0066 orchestrator bootstrap
    try:
        from adapters.cycles.factory import (
            create_artifact_vault,
            create_cycle_registry,
            create_flow_executor,
            create_project_registry,
            create_squad_profile_port,
        )

        project_registry = create_project_registry("config")
        cycle_registry = create_cycle_registry("memory")
        squad_profile = create_squad_profile_port("config")
        artifact_vault = create_artifact_vault("filesystem")

        # Distributed executor: dispatch tasks to agent containers via RabbitMQ.
        # Each agent uses its own LLM model and PromptService — no orchestrator
        # or handler registry needed in the runtime-api container.
        from adapters.comms.rabbitmq import RabbitMQAdapter
        from adapters.telemetry.factory import create_llm_observability_provider

        queue_adapter = RabbitMQAdapter(url=RABBITMQ_URL)
        llm_obs = create_llm_observability_provider(config=config.langfuse)

        # Create PrefectReporter with module-level ref for shutdown cleanup
        global _prefect_reporter
        if config.prefect.api_url:
            from adapters.cycles.prefect_reporter import PrefectReporter

            _prefect_reporter = PrefectReporter(api_url=config.prefect.api_url)

        flow_executor = create_flow_executor(
            "distributed",
            cycle_registry=cycle_registry,
            artifact_vault=artifact_vault,
            squad_profile=squad_profile,
            project_registry=project_registry,
            queue=queue_adapter,
            llm_observability=llm_obs,
            prefect_reporter=_prefect_reporter,
        )

        set_cycle_ports(
            project_registry=project_registry,
            cycle_registry=cycle_registry,
            squad_profile=squad_profile,
            artifact_vault=artifact_vault,
            flow_executor=flow_executor,
        )
        logger.info("SIP-0064 cycle ports + SIP-0066 orchestrator initialized")
    except Exception as e:
        logger.error(f"Failed to initialize cycle ports: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections."""
    global pool, rabbitmq_connection
    if pool:
        await pool.close()
    if rabbitmq_connection:
        await rabbitmq_connection.close()
    if _prefect_reporter:
        await _prefect_reporter.close()


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
    agent_id: str | None = None  # SIP-0048: Agent identifier
    task_name: str | None = None  # Optional human-readable label
    task_type: str  # Required standardized taxonomy/behavior category (ACI)
    inputs: dict[str, Any] = Field(default_factory=dict)
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
    """Map TaskError to appropriate HTTPException"""
    if isinstance(e, TaskNotFoundError):
        return HTTPException(status_code=404, detail=str(e))
    elif isinstance(e, TaskStateError):
        return HTTPException(status_code=409, detail=str(e))
    elif isinstance(e, TaskError):
        return HTTPException(status_code=500, detail=str(e))
    else:
        return HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


# GET endpoints for querying tasks and execution cycles


@app.get("/api/v1/tasks/ec/{cycle_id}")  # SIP-0048: renamed from ecid
async def get_tasks_by_cycle_id(
    cycle_id: str, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Get all tasks for a specific execution cycle"""
    try:
        tasks = await adapter.list_pending(agent_id=None)
        # Filter by cycle_id - this is a simplified implementation
        # Full implementation would have adapter method for cycle filtering
        filtered = [t for t in tasks if getattr(t, "cycle_id", None) == cycle_id]
        return [task_to_dict(task) for task in filtered]
    except TaskError as e:
        raise handle_adapter_error(e) from e


@app.get("/api/v1/tasks/agent/{agent_name}")
async def get_tasks_by_agent(
    agent_name: str,
    cycle_id: str | None = None,  # SIP-0048: renamed from ecid
    limit: int = 50,
    adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep),
):
    """Get recent tasks for a specific agent"""
    try:
        tasks = await adapter.list_pending(agent_id=agent_name)
        if cycle_id:
            tasks = [t for t in tasks if getattr(t, "cycle_id", None) == cycle_id]
        return [task_to_dict(task) for task in tasks[:limit]]
    except TaskError as e:
        raise handle_adapter_error(e) from e


@app.get("/api/v1/tasks/status/{status}")
async def get_tasks_by_status(
    status: str, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Get tasks by status"""
    try:
        # Simplified - full implementation would filter by status in adapter
        tasks = await adapter.list_pending()
        filtered = [t for t in tasks if getattr(t, "status", None) == status]
        return [task_to_dict(task) for task in filtered]
    except TaskError as e:
        raise handle_adapter_error(e) from e


@app.get("/api/v1/execution-cycles")
async def get_execution_cycles(
    run_type: str | None = None, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Get execution cycles, optionally filtered by type"""
    # Placeholder - full implementation would query cycles from adapter
    return []


@app.get("/api/v1/tasks/summary/{cycle_id}")  # SIP-0048: renamed from ecid
async def get_task_summary(
    cycle_id: str, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Get task summary for an execution cycle"""
    # Placeholder - full implementation would aggregate from adapter
    return {
        "total_tasks": 0,
        "completed": 0,
        "in_progress": 0,
        "delegated": 0,
        "failed": 0,
        "avg_duration": None,
    }


# POST/PUT endpoints for agents to create and update tasks


@app.post("/api/v1/execution-cycles")
async def create_execution_cycle(
    cycle: ExecutionCycleCreate, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Create a new execution cycle"""
    # Placeholder - full implementation would create via adapter
    return {"status": "created", "cycle_id": cycle.cycle_id}


@app.put("/api/v1/execution-cycles/{cycle_id}")  # SIP-0048: renamed from ecid
async def update_execution_cycle(
    cycle_id: str,
    update: ExecutionCycleUpdate,
    adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep),
):
    """Update execution cycle status or notes"""
    if not update.status and not update.notes:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Placeholder - full implementation would update via adapter
    return {"status": "updated", "cycle_id": cycle_id}


@app.post("/api/v1/execution-cycles/{cycle_id}/complete")
async def complete_execution_cycle(
    cycle_id: str,
    notes: str | None = None,
    adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep),
):
    """Mark execution cycle as completed"""
    update = ExecutionCycleUpdate(status="completed", notes=notes)
    return await update_execution_cycle(cycle_id, update, adapter)


@app.post("/api/v1/execution-cycles/{cycle_id}/fail")
async def fail_execution_cycle(
    cycle_id: str, notes: str, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Mark execution cycle as failed"""
    update = ExecutionCycleUpdate(status="failed", notes=notes)
    return await update_execution_cycle(cycle_id, update, adapter)


@app.post("/api/v1/tasks/start")
async def start_task(
    task: TaskLogCreate, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """
    Create task with ACI TaskEnvelope contract.

    Returns fully populated TaskEnvelope (not legacy task dict).
    """
    try:
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

        # Get project_id or use placeholder
        project_id = task.project_id or "project-placeholder"

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

        # Create task via adapter
        from squadops.tasks.legacy_models import Task

        created_task = Task(
            task_id=task_create.task_id,
            cycle_id=task_create.cycle_id,
            agent=task_create.agent,
            agent_id=task_create.agent_id,
            task_name=task_create.task_name,
            status=task_create.status,
            priority=task_create.priority,
            description=task_create.description,
            pid=task_create.pid,
            dependencies=task_create.dependencies,
            delegated_by=task_create.delegated_by,
            delegated_to=task_create.delegated_to,
        )

        # Construct TaskEnvelope
        envelope = LegacyTaskEnvelope(
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
        try:
            global rabbitmq_channel

            if rabbitmq_channel is None:
                logger.warning("RabbitMQ channel not available, creating temporary connection")
                connection = await aio_pika.connect_robust(RABBITMQ_URL)
                try:
                    channel = await connection.channel()
                    await send_envelope_to_agent_queue(channel, envelope.agent_id, envelope)
                finally:
                    await connection.close()
            else:
                await send_envelope_to_agent_queue(rabbitmq_channel, envelope.agent_id, envelope)
        except Exception as e:
            # Log error but don't fail task creation
            logger.warning(f"Failed to publish task {envelope.task_id} to RabbitMQ: {e}")

        return envelope.model_dump()
    except TaskError as e:
        raise handle_adapter_error(e) from e


@app.put("/api/v1/tasks/{task_id}")
async def update_task(
    task_id: str, update: TaskLogUpdate, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
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
                state = TaskState.STARTED

        result = {}
        if update.end_time:
            result["end_time"] = update.end_time
        if update.artifacts:
            result["artifacts"] = update.artifacts
        if update.metrics:
            result["metrics"] = update.metrics
        if update.dependencies:
            result["dependencies"] = update.dependencies
        if update.error_log:
            result["error_log"] = update.error_log

        await adapter.update_status(task_id, state, result if result else None)
        return {"status": "updated", "task_id": task_id}
    except TaskError as e:
        raise handle_adapter_error(e) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}") from e


@app.post("/api/v1/tasks/complete")
async def complete_task(
    request: TaskCompleteRequest, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Mark task as completed with optional artifacts"""
    update = TaskLogUpdate(
        status="completed", end_time=datetime.utcnow(), artifacts=request.artifacts
    )
    return await update_task(request.task_id, update, adapter)


@app.post("/api/v1/tasks/fail")
async def fail_task(
    request: TaskFailRequest, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Mark task as failed with error log"""
    update = TaskLogUpdate(status="failed", end_time=datetime.utcnow(), error_log=request.error_log)
    return await update_task(request.task_id, update, adapter)


# Task Status Management Endpoints


@app.post("/api/v1/task-status")
async def create_or_update_task_status(
    task_status: TaskStatusCreate, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Create or update task status"""
    # Placeholder - full implementation would use adapter
    return {"status": "updated", "task_id": task_status.task_id}


@app.put("/api/v1/task-status/{task_id}")
async def update_task_status_endpoint(
    task_id: str,
    update: TaskStatusUpdate,
    adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep),
):
    """Update task status fields"""
    if not update.status and update.progress is None and not update.eta:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Placeholder - full implementation would use adapter
    return {"status": "updated", "task_id": task_id}


@app.get("/api/v1/task-status/{task_id}")
async def get_task_status_endpoint(
    task_id: str, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Get task status by task_id"""
    # Placeholder - full implementation would use adapter
    raise HTTPException(status_code=404, detail=f"Task status {task_id} not found")


@app.get("/api/v1/execution-cycles/{cycle_id}")
async def get_execution_cycle(
    cycle_id: str, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Get a single execution cycle by cycle_id"""
    # Placeholder - full implementation would use adapter
    raise HTTPException(status_code=404, detail=f"Execution cycle {cycle_id} not found")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "runtime-api", "version": SQUADOPS_VERSION}


# SIP-0048: Additional Runtime API endpoints


@app.post("/api/v1/cycles")
async def create_cycle(
    cycle: ExecutionCycleCreate, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Create a new execution cycle (alias for /api/v1/execution-cycles)"""
    return await create_execution_cycle(cycle, adapter)


@app.get("/api/v1/cycles/{cycle_id}")
async def get_cycle(cycle_id: str, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)):
    """Get a single execution cycle by cycle_id"""
    return await get_execution_cycle(cycle_id, adapter)


@app.get("/api/v1/cycles/{cycle_id}/tasks/pending")
async def get_pending_tasks_for_cycle(
    cycle_id: str, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Get pending tasks for a specific cycle"""
    try:
        tasks = await adapter.list_pending()
        filtered = [
            t
            for t in tasks
            if getattr(t, "cycle_id", None) == cycle_id and getattr(t, "status", None) == "pending"
        ]
        return [task_to_dict(task) for task in filtered]
    except TaskError as e:
        raise handle_adapter_error(e) from e


@app.post("/api/v1/tasks/{task_id}/results")
async def submit_task_result(
    task_id: str, result: dict[str, Any], adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Submit task result"""
    try:
        await adapter.update_status(
            task_id,
            TaskState.COMPLETED,
            {
                "artifacts": result.get("artifacts", []),
                "metrics": result.get("metrics", {}),
            },
        )
        return {"status": "result_submitted", "task_id": task_id}
    except TaskError as e:
        raise handle_adapter_error(e) from e


@app.get("/api/v1/agents")
async def list_agents():
    """List all agents"""
    # Placeholder - full implementation would query agent registry
    return {"agents": [], "count": 0}


@app.get("/api/v1/agents/{agent_id}/state")
async def get_agent_state(agent_id: str):
    """Get agent runtime state"""
    return {
        "agent_id": agent_id,
        "status": "unknown",
        "last_heartbeat": None,
        "current_task_id": None,
    }


@app.get("/api/v1/cycles/{cycle_id}/runtime")
async def get_cycle_runtime(
    cycle_id: str, adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep)
):
    """Get comprehensive cycle runtime state snapshot"""
    # Placeholder - full implementation would aggregate from adapter
    return {
        "cycle": None,
        "tasks": [],
        "summary": {
            "total_tasks": 0,
            "completed": 0,
            "in_progress": 0,
            "delegated": 0,
            "failed": 0,
        },
    }


@app.get("/api/v1/scheduler/status")
async def get_scheduler_status():
    """Get scheduler health and queue status"""
    return {
        "status": "healthy",
        "queues": {},
        "message": "Scheduler status endpoint",
    }


@app.post("/api/v1/cycles/{cycle_id}/actions")
async def cycle_action(
    cycle_id: str,
    action: dict[str, str],
    adapter: TaskRegistryPort = Depends(get_tasks_adapter_dep),
):
    """Control cycle (pause, resume, cancel)"""
    action_type = action.get("action")
    if action_type not in ["pause", "resume", "cancel"]:
        raise HTTPException(
            status_code=400, detail="Invalid action. Must be: pause, resume, or cancel"
        )

    status_map = {"pause": "paused", "resume": "active", "cancel": "cancelled"}
    update = ExecutionCycleUpdate(status=status_map[action_type])
    return await update_execution_cycle(cycle_id, update, adapter)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
