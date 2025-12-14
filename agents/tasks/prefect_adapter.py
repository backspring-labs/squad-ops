"""
PrefectTasksAdapter - Prefect-based task management adapter
Implements TaskAdapterBase for Prefect backend

This adapter integrates with Prefect's orchestration engine while maintaining
SquadOps DB as the source of truth. All task/flow state is written to SquadOps DB first,
with Prefect run IDs stored as metadata.
"""

import json
import logging
from datetime import datetime
from typing import Any

import asyncpg

from agents.tasks.base_adapter import TaskAdapterBase
from agents.tasks.errors import (
    TaskAdapterError,
    TaskConflictError,
    TaskNotFoundError,
)
from agents.tasks.models import (
    Artifact,
    FlowRun,
    FlowState,
    Task,
    TaskCreate,
    TaskFilters,
    TaskState,
    TaskSummary,
)
from config.unified_config import get_config

logger = logging.getLogger(__name__)

# State mapping constants
SQUADOPS_TO_PREFECT_STATE = {
    TaskState.PENDING: "PENDING",
    TaskState.STARTED: "RUNNING",
    TaskState.ACTIVE_NON_BLOCKING: "RUNNING",
    TaskState.IN_PROGRESS: "RUNNING",
    TaskState.COMPLETED: "COMPLETED",
    TaskState.FAILED: "FAILED",
    TaskState.DELEGATED: "PENDING",
}

PREFECT_TO_SQUADOPS_STATE = {
    "PENDING": TaskState.PENDING,
    "RUNNING": TaskState.IN_PROGRESS,
    "COMPLETED": TaskState.COMPLETED,
    "FAILED": TaskState.FAILED,
    "CANCELLED": TaskState.FAILED,
    "CRASHED": TaskState.FAILED,
    "PAUSED": TaskState.PENDING,
}


class PrefectTasksAdapter(TaskAdapterBase):
    """
    Prefect adapter for task management.

    This adapter integrates with Prefect's orchestration engine to:
    - Use Prefect flows for execution cycles
    - Use Prefect task runs for SquadOps tasks
    - Leverage Prefect's retry, caching, and state management

    **Source of Truth:**
    SquadOps DB is always the source of truth. All state is written to SquadOps DB first.
    Prefect run IDs are stored in metadata (metrics JSON for tasks, inputs/metadata for flows).
    """

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize Prefect adapter with database connection pool.

        Args:
            db_pool: AsyncPG connection pool for SquadOps DB access
        """
        self.db_pool = db_pool
        self._prefect_api_url: str | None = None
        self._prefect_api_key: str | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Prefect client connection"""
        if self._initialized:
            return

        try:
            config = get_config()
            api_url = config.get_prefect_api_url()
            api_key = config.get_prefect_api_key()

            # Store Prefect configuration
            self._prefect_api_url = api_url
            self._prefect_api_key = api_key

            # Set Prefect API URL in environment for Prefect client
            import os

            if api_url:
                os.environ["PREFECT_API_URL"] = api_url
            if api_key:
                os.environ["PREFECT_API_KEY"] = api_key

            self._initialized = True
            logger.info(f"Prefect adapter initialized with API URL: {api_url}")
        except Exception as e:
            logger.warning(
                f"Failed to initialize Prefect adapter: {e}. Adapter will continue with DB-only operations."
            )
            # Don't raise - adapter can still work with DB-only operations
            self._prefect_api_url = None
            self._prefect_api_key = None
            self._initialized = True  # Mark as initialized to avoid retry loops

    async def shutdown(self) -> None:
        """Shutdown Prefect adapter and close database pool"""
        self.prefect_client = None

        if self.db_pool:
            try:
                await self.db_pool.close()
                logger.info("Prefect adapter database pool closed")
            except Exception as e:
                logger.error(f"Error closing database pool: {e}")
                raise TaskAdapterError(f"Failed to close database pool: {str(e)}") from e

    def _row_to_task(self, row: asyncpg.Record) -> Task:
        """Convert database row to Task DTO"""
        # Parse artifacts if present
        artifacts = []
        if row.get("artifacts"):
            if isinstance(row["artifacts"], str):
                artifacts_data = json.loads(row["artifacts"])
            else:
                artifacts_data = row["artifacts"]

            if isinstance(artifacts_data, dict):
                artifacts = [Artifact(**artifacts_data)]
            elif isinstance(artifacts_data, list):
                artifacts = [Artifact(**a) if isinstance(a, dict) else a for a in artifacts_data]

        # Parse metrics if present (includes Prefect run ID)
        metrics = {}
        if row.get("metrics"):
            if isinstance(row["metrics"], str):
                metrics = json.loads(row["metrics"])
            else:
                metrics = row["metrics"]
            if not isinstance(metrics, dict):
                metrics = {}

        return Task(
            task_id=row["task_id"],
            pid=row.get("pid"),
            cycle_id=row.get("cycle_id"),
            agent=row["agent"],
            agent_id=row.get("agent_id") or row.get("agent"),
            task_name=row.get("task_name"),
            phase=row.get("phase"),
            status=row["status"],
            priority=row.get("priority"),
            description=row.get("description"),
            start_time=row.get("start_time"),
            end_time=row.get("end_time"),
            duration=str(row["duration"]) if row.get("duration") else None,
            artifacts=artifacts,
            metrics=metrics,
            dependencies=row.get("dependencies") or [],
            error_log=row.get("error_log"),
            delegated_by=row.get("delegated_by"),
            delegated_to=row.get("delegated_to"),
            created_at=row.get("created_at"),
        )

    def _row_to_flow(self, row: asyncpg.Record) -> FlowRun:
        """Convert database row to FlowRun DTO"""
        # Parse inputs if present (includes Prefect flow run ID)
        inputs = {}
        if row.get("inputs"):
            if isinstance(row["inputs"], str):
                inputs = json.loads(row["inputs"])
            else:
                inputs = row["inputs"]
            if not isinstance(inputs, dict):
                inputs = {}

        return FlowRun(
            cycle_id=row["cycle_id"],
            pid=row["pid"],
            project_id=row.get("project_id"),
            run_type=row["run_type"],
            title=row["title"],
            description=row.get("description"),
            name=row.get("name") or row.get("title"),
            goal=row.get("goal"),
            start_time=row.get("start_time") or row.get("created_at"),
            end_time=row.get("end_time"),
            inputs=inputs,
            created_at=row.get("created_at"),
            initiated_by=row.get("initiated_by"),
            status=row.get("status", "active"),
            notes=row.get("notes"),
        )

    async def create_task(self, task_create: TaskCreate) -> Task:
        """Create a new task"""
        try:
            # Ensure Prefect client is initialized
            if not self._initialized:
                await self.initialize()

            # ACI v0.8: Generate missing lineage fields if not provided
            from agents.utils.lineage_generator import LineageGenerator
            
            lineage = LineageGenerator.ensure_lineage_fields(
                cycle_id=task_create.cycle_id,
                task_id=task_create.task_id,
                correlation_id=getattr(task_create, "correlation_id", None),
                causation_id=getattr(task_create, "causation_id", None),
                trace_id=getattr(task_create, "trace_id", None),
                span_id=getattr(task_create, "span_id", None),
                tracing_enabled=False,
            )
            
            # Get project_id and pulse_id
            project_id = getattr(task_create, "project_id", None)
            if not project_id:
                # Try to get from cycle
                flow = await self.get_flow(task_create.cycle_id)
                if flow and flow.project_id:
                    project_id = flow.project_id
                else:
                    project_id = "project-placeholder"
            
            pulse_id = getattr(task_create, "pulse_id", None) or f"pulse-placeholder-{task_create.task_id}"
            task_type = getattr(task_create, "task_type", None) or getattr(task_create, "task_name", None) or "unknown"
            inputs = getattr(task_create, "inputs", None) or {}
            
            # First, write to SquadOps DB (source of truth)
            async with self.db_pool.acquire() as conn:
                try:
                    now = datetime.utcnow()
                    metrics = {
                        "prefect_task_run_id": None
                    }  # Will be updated after Prefect run creation

                    await conn.execute(
                        """
                        INSERT INTO agent_task_log 
                        (task_id, cycle_id, agent, agent_id, task_name, task_type, inputs, status, priority, description, start_time, 
                         dependencies, delegated_by, delegated_to, pid, phase, metrics, created_at,
                         project_id, pulse_id, correlation_id, causation_id, trace_id, span_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24)
                    """,
                        task_create.task_id,
                        task_create.cycle_id,
                        task_create.agent,
                        getattr(task_create, "agent_id", None) or task_create.agent,
                        getattr(task_create, "task_name", None),
                        task_type,
                        json.dumps(inputs),
                        task_create.status,
                        task_create.priority,
                        task_create.description,
                        now,
                        task_create.dependencies or [],
                        task_create.delegated_by,
                        task_create.delegated_to,
                        task_create.pid,
                        task_create.phase,
                        json.dumps(metrics),
                        now,
                        project_id,
                        pulse_id,
                        lineage["correlation_id"],
                        lineage["causation_id"],
                        lineage["trace_id"],
                        lineage["span_id"],
                    )
                except asyncpg.exceptions.UniqueViolationError as e:
                    raise TaskConflictError(f"Task {task_create.task_id} already exists") from e
                except asyncpg.exceptions.PostgresError as e:
                    raise TaskAdapterError(
                        f"Database error creating task {task_create.task_id}: {str(e)}"
                    ) from e

            # Then, create Prefect task run reference if Prefect is available
            prefect_task_run_id = None
            if self._initialized and self._prefect_api_url:
                try:
                    # Get or create a flow for this cycle (with lineage)
                    flow_run_id = await self._get_or_create_flow_run_id_for_cycle(
                        task_create.cycle_id,
                        project_id=project_id,
                        correlation_id=lineage["correlation_id"],
                    )
                    if flow_run_id:
                        # Create a task run reference
                        prefect_task_run_id = f"flow-{flow_run_id}-task-{task_create.task_id}"

                        # Update SquadOps DB with Prefect run ID
                        async with self.db_pool.acquire() as conn:
                            metrics["prefect_task_run_id"] = prefect_task_run_id
                            metrics["prefect_flow_run_id"] = flow_run_id
                            await conn.execute(
                                "UPDATE agent_task_log SET metrics = $1 WHERE task_id = $2",
                                json.dumps(metrics),
                                task_create.task_id,
                            )
                        logger.debug(
                            f"Linked Prefect flow run {flow_run_id} to task {task_create.task_id}"
                        )
                except Exception as e:
                    # Log but don't fail - SquadOps DB is source of truth
                    logger.warning(
                        f"Failed to create Prefect task run for {task_create.task_id}: {e}"
                    )

            # Return the task from SquadOps DB
            result = await self.get_task(task_create.task_id)
            if not result:
                raise TaskNotFoundError(
                    f"Task {task_create.task_id} was created but could not be retrieved"
                )
            return result
        except (TaskAdapterError, TaskNotFoundError, TaskConflictError):
            raise
        except Exception as e:
            raise TaskAdapterError(
                f"Unexpected error creating task {task_create.task_id}: {str(e)}"
            ) from e

    async def _get_or_create_flow_run_id_for_cycle(
        self, cycle_id: str, project_id: str | None = None, correlation_id: str | None = None
    ) -> str | None:
        """
        Get or create a Prefect flow run ID for a cycle.
        
        ACI v0.8: Includes project_id and correlation_id in flow metadata for lineage.
        """
        if not self._initialized or not self._prefect_api_url:
            return None

        try:
            # First check if flow run already exists in SquadOps DB
            flow = await self.get_flow(cycle_id)
            if flow and flow.inputs.get("prefect_flow_run_id"):
                return flow.inputs["prefect_flow_run_id"]

            # Get project_id from flow if not provided
            if not project_id and flow:
                project_id = flow.project_id

            # Generate correlation_id if not provided
            if not correlation_id:
                from agents.utils.lineage_generator import LineageGenerator
                correlation_id = LineageGenerator.generate_correlation_id(cycle_id)

            # Create a new flow run ID reference
            # In production, this would create an actual Prefect flow run
            # For now, we create a reference ID that can be used for linking
            flow_run_id = f"flow-{cycle_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

            # Update SquadOps DB with Prefect flow run ID and lineage
            if flow:
                async with self.db_pool.acquire() as conn:
                    inputs = flow.inputs.copy() if flow.inputs else {}
                    inputs["prefect_flow_run_id"] = flow_run_id
                    if project_id:
                        inputs["project_id"] = project_id
                    if correlation_id:
                        inputs["correlation_id"] = correlation_id
                    await conn.execute(
                        "UPDATE cycle SET inputs = $1 WHERE cycle_id = $2",
                        json.dumps(inputs),
                        cycle_id,
                    )

            return flow_run_id
        except Exception as e:
            logger.warning(f"Failed to get or create Prefect flow run ID for cycle {cycle_id}: {e}")
            return None

    async def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID (reads from SquadOps DB, source of truth)"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM agent_task_log WHERE task_id = $1", task_id
                )
                if not row:
                    return None
                return self._row_to_task(row)
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(f"Database error retrieving task {task_id}: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error retrieving task {task_id}: {str(e)}") from e

    async def list_tasks(self, filters: TaskFilters) -> list[Task]:
        """List tasks matching filters (queries SquadOps DB)"""
        try:
            async with self.db_pool.acquire() as conn:
                conditions = []
                params = []
                param_count = 1

                if filters.cycle_id:
                    conditions.append(f"cycle_id = ${param_count}")
                    params.append(filters.cycle_id)
                    param_count += 1

                if filters.agent:
                    conditions.append(f"agent = ${param_count}")
                    params.append(filters.agent)
                    param_count += 1

                if filters.status:
                    conditions.append(f"status = ${param_count}")
                    params.append(filters.status)
                    param_count += 1

                if filters.pid:
                    conditions.append(f"pid = ${param_count}")
                    params.append(filters.pid)
                    param_count += 1

                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

                limit = filters.limit or 50
                limit_clause = f"LIMIT ${param_count}"
                params.append(limit)

                query = f"""
                    SELECT * FROM agent_task_log 
                    {where_clause}
                    ORDER BY created_at DESC 
                    {limit_clause}
                """
                rows = await conn.fetch(query, *params)
                return [self._row_to_task(row) for row in rows]
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(f"Database error listing tasks: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error listing tasks: {str(e)}") from e

    async def update_task_state(
        self, task_id: str, state: TaskState, meta: dict[str, Any] | None = None
    ) -> Task:
        """Update task state"""
        try:
            meta = meta or {}
            updates = []
            params = []
            param_count = 1

            updates.append(f"status = ${param_count}")
            params.append(state.value)
            param_count += 1

            if "end_time" in meta:
                updates.append(f"end_time = ${param_count}")
                params.append(meta["end_time"])
                param_count += 1
                updates.append("duration = end_time - start_time")

            if "artifacts" in meta:
                updates.append(f"artifacts = ${param_count}")
                params.append(json.dumps(meta["artifacts"]))
                param_count += 1

            if "error_log" in meta:
                updates.append(f"error_log = ${param_count}")
                params.append(meta["error_log"])
                param_count += 1

            if "metrics" in meta:
                updates.append(f"metrics = ${param_count}")
                params.append(json.dumps(meta["metrics"]))
                param_count += 1

            if "dependencies" in meta:
                updates.append(f"dependencies = ${param_count}")
                params.append(meta["dependencies"])
                param_count += 1

            params.append(task_id)
            query = f"UPDATE agent_task_log SET {', '.join(updates)} WHERE task_id = ${param_count}"

            async with self.db_pool.acquire() as conn:
                result = await conn.execute(query, *params)
                if result == "UPDATE 0":
                    raise TaskNotFoundError(f"Task {task_id} not found")

            # Update Prefect task run state reference if available
            # Note: In Prefect 2.x, state updates are typically handled by the flow execution
            # We'll store the state reference in metrics
            if self._initialized:
                try:
                    task_obj = await self.get_task(task_id)
                    if task_obj and task_obj.metrics.get("prefect_task_run_id"):
                        prefect_state = SQUADOPS_TO_PREFECT_STATE.get(state, "PENDING")
                        # Store state in metrics for reference
                        async with self.db_pool.acquire() as conn:
                            metrics = task_obj.metrics.copy()
                            metrics["prefect_state"] = prefect_state
                            await conn.execute(
                                "UPDATE agent_task_log SET metrics = $1 WHERE task_id = $2",
                                json.dumps(metrics),
                                task_id,
                            )
                        logger.debug(
                            f"Updated Prefect state reference for task {task_id}: {prefect_state}"
                        )
                except Exception as e:
                    # Log but don't fail - SquadOps DB is source of truth
                    logger.warning(f"Failed to update Prefect task run state for {task_id}: {e}")

            task = await self.get_task(task_id)
            if not task:
                raise TaskNotFoundError(f"Task {task_id} was updated but could not be retrieved")
            return task
        except (TaskAdapterError, TaskNotFoundError):
            raise
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(f"Database error updating task {task_id}: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error updating task {task_id}: {str(e)}") from e

    async def add_artifact(self, task_id: str, artifact: Artifact) -> None:
        """Add an artifact to a task"""
        try:
            task = await self.get_task(task_id)
            if not task:
                raise TaskNotFoundError(f"Task {task_id} not found")

            # Get existing artifacts
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT artifacts FROM agent_task_log WHERE task_id = $1", task_id
                )
                existing_artifacts = []
                if row and row.get("artifacts"):
                    if isinstance(row["artifacts"], str):
                        existing_artifacts = json.loads(row["artifacts"])
                    else:
                        existing_artifacts = row["artifacts"]
                    if not isinstance(existing_artifacts, list):
                        existing_artifacts = [existing_artifacts]

                # Add new artifact
                existing_artifacts.append(artifact.model_dump())

                await conn.execute(
                    "UPDATE agent_task_log SET artifacts = $1 WHERE task_id = $2",
                    json.dumps(existing_artifacts),
                    task_id,
                )
        except (TaskAdapterError, TaskNotFoundError):
            raise
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(
                f"Database error adding artifact to task {task_id}: {str(e)}"
            ) from e
        except Exception as e:
            raise TaskAdapterError(
                f"Unexpected error adding artifact to task {task_id}: {str(e)}"
            ) from e

    async def add_dependency(self, task_id: str, depends_on_id: str) -> None:
        """Add a dependency relationship between tasks"""
        try:
            task = await self.get_task(task_id)
            if not task:
                raise TaskNotFoundError(f"Task {task_id} not found")

            # Update dependencies in SquadOps DB
            async with self.db_pool.acquire() as conn:
                existing_deps = task.dependencies or []
                if depends_on_id not in existing_deps:
                    existing_deps.append(depends_on_id)
                    await conn.execute(
                        "UPDATE agent_task_log SET dependencies = $1 WHERE task_id = $2",
                        existing_deps,
                        task_id,
                    )
        except (TaskAdapterError, TaskNotFoundError):
            raise
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(
                f"Database error adding dependency for task {task_id}: {str(e)}"
            ) from e
        except Exception as e:
            raise TaskAdapterError(
                f"Unexpected error adding dependency for task {task_id}: {str(e)}"
            ) from e

    async def list_tasks_for_pid(self, pid: str) -> list[Task]:
        """List all tasks for a process ID"""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM agent_task_log 
                    WHERE pid = $1 
                    ORDER BY created_at ASC
                """,
                    pid,
                )
                return [self._row_to_task(row) for row in rows]
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(f"Database error listing tasks for pid {pid}: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error listing tasks for pid {pid}: {str(e)}") from e

    async def list_tasks_for_cycle_id(self, cycle_id: str) -> list[Task]:
        """List all tasks for an execution cycle ID"""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM agent_task_log 
                    WHERE cycle_id = $1 
                    ORDER BY created_at ASC
                """,
                    cycle_id,
                )
                return [self._row_to_task(row) for row in rows]
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(
                f"Database error listing tasks for cycle_id {cycle_id}: {str(e)}"
            ) from e
        except Exception as e:
            raise TaskAdapterError(
                f"Unexpected error listing tasks for cycle_id {cycle_id}: {str(e)}"
            ) from e

    async def create_flow(
        self, cycle_id: str, pid: str, meta: dict[str, Any] | None = None
    ) -> FlowRun:
        """Create a new execution cycle (flow)"""
        try:
            # Ensure Prefect client is initialized
            if not self._initialized:
                await self.initialize()

            meta = meta or {}
            project_id = meta.get("project_id")

            # Validate project_id if provided
            if project_id:
                from agents.cycle_data.project_validator import validate_project_id

                await validate_project_id(project_id, self.db_pool)

            # First, write to SquadOps DB (source of truth)
            async with self.db_pool.acquire() as conn:
                try:
                    now = datetime.utcnow()
                    inputs = meta.get("inputs") or {}
                    inputs["prefect_flow_run_id"] = (
                        None  # Will be updated after Prefect flow creation
                    )

                    await conn.execute(
                        """
                        INSERT INTO cycle 
                        (cycle_id, pid, project_id, run_type, title, description, name, goal, start_time, inputs, initiated_by, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                        cycle_id,
                        pid,
                        project_id,
                        meta.get("run_type", "project"),
                        meta.get("title", ""),
                        meta.get("description"),
                        meta.get("name") or meta.get("title", ""),
                        meta.get("goal"),
                        meta.get("start_time") or now,
                        json.dumps(inputs),
                        meta.get("initiated_by", ""),
                        now,
                    )
                except asyncpg.exceptions.UniqueViolationError as e:
                    raise TaskConflictError(f"Execution cycle {cycle_id} already exists") from e
                except asyncpg.exceptions.PostgresError as e:
                    raise TaskAdapterError(
                        f"Database error creating execution cycle {cycle_id}: {str(e)}"
                    ) from e

            # Then, create Prefect flow run reference if Prefect is available
            if self._initialized and self._prefect_api_url:
                try:
                    # Create a flow run reference
                    # In production, flows should be deployed first, then runs created
                    flow_run_id = f"flow-{cycle_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

                    # Update SquadOps DB with Prefect flow run ID
                    async with self.db_pool.acquire() as conn:
                        inputs["prefect_flow_run_id"] = flow_run_id
                        await conn.execute(
                            "UPDATE cycle SET inputs = $1 WHERE cycle_id = $2",
                            json.dumps(inputs),
                            cycle_id,
                        )
                    logger.debug(
                        f"Created Prefect flow run reference {flow_run_id} for cycle {cycle_id}"
                    )
                except Exception as e:
                    # Log but don't fail - SquadOps DB is source of truth
                    logger.warning(f"Failed to create Prefect flow run for cycle {cycle_id}: {e}")

            result = await self.get_flow(cycle_id)
            if not result:
                raise TaskNotFoundError(
                    f"Execution cycle {cycle_id} was created but could not be retrieved"
                )
            return result
        except (TaskAdapterError, TaskNotFoundError, TaskConflictError):
            raise
        except Exception as e:
            raise TaskAdapterError(
                f"Unexpected error creating execution cycle {cycle_id}: {str(e)}"
            ) from e

    async def update_flow(
        self, flow_id: str, state: FlowState, meta: dict[str, Any] | None = None
    ) -> FlowRun:
        """Update an execution cycle"""
        try:
            meta = meta or {}
            updates = []
            params = []
            param_count = 1

            # Use state or meta status
            status = meta.get("status", state.value)
            updates.append(f"status = ${param_count}")
            params.append(status)
            param_count += 1

            if "notes" in meta:
                updates.append(f"notes = ${param_count}")
                params.append(meta["notes"])
                param_count += 1

            params.append(flow_id)
            query = f"UPDATE cycle SET {', '.join(updates)} WHERE cycle_id = ${param_count}"

            async with self.db_pool.acquire() as conn:
                result = await conn.execute(query, *params)
                if result == "UPDATE 0":
                    raise TaskNotFoundError(f"Execution cycle {flow_id} not found")

            # Update Prefect flow run state reference if available
            # Note: In Prefect 2.x, state updates are typically handled by the flow execution
            # We'll store the state reference in inputs
            if self._initialized:
                try:
                    flow = await self.get_flow(flow_id)
                    if flow and flow.inputs.get("prefect_flow_run_id"):
                        prefect_state = (
                            "COMPLETED"
                            if state == FlowState.COMPLETED
                            else "FAILED"
                            if state == FlowState.FAILED
                            else "RUNNING"
                        )
                        # Store state in inputs for reference
                        async with self.db_pool.acquire() as conn:
                            inputs = flow.inputs.copy()
                            inputs["prefect_state"] = prefect_state
                            await conn.execute(
                                "UPDATE cycle SET inputs = $1 WHERE cycle_id = $2",
                                json.dumps(inputs),
                                flow_id,
                            )
                        logger.debug(
                            f"Updated Prefect state reference for flow {flow_id}: {prefect_state}"
                        )
                except Exception as e:
                    # Log but don't fail - SquadOps DB is source of truth
                    logger.warning(f"Failed to update Prefect flow run state for {flow_id}: {e}")

            flow = await self.get_flow(flow_id)
            if not flow:
                raise TaskNotFoundError(
                    f"Execution cycle {flow_id} was updated but could not be retrieved"
                )
            return flow
        except (TaskAdapterError, TaskNotFoundError):
            raise
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(
                f"Database error updating execution cycle {flow_id}: {str(e)}"
            ) from e
        except Exception as e:
            raise TaskAdapterError(
                f"Unexpected error updating execution cycle {flow_id}: {str(e)}"
            ) from e

    async def get_flow(self, cycle_id: str) -> FlowRun | None:
        """Get an execution cycle by cycle_id"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM cycle WHERE cycle_id = $1", cycle_id)
                if not row:
                    return None
                return self._row_to_flow(row)
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(
                f"Database error retrieving execution cycle {cycle_id}: {str(e)}"
            ) from e
        except Exception as e:
            raise TaskAdapterError(
                f"Unexpected error retrieving execution cycle {cycle_id}: {str(e)}"
            ) from e

    async def list_flows(self, run_type: str | None = None) -> list[FlowRun]:
        """List execution cycles, optionally filtered by run_type"""
        try:
            async with self.db_pool.acquire() as conn:
                if run_type:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM cycle 
                        WHERE run_type = $1 
                        ORDER BY created_at DESC
                    """,
                        run_type,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM cycle 
                        ORDER BY created_at DESC
                    """
                    )
                return [self._row_to_flow(row) for row in rows]
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(f"Database error listing execution cycles: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error listing execution cycles: {str(e)}") from e

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Get task status from task_status table"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM task_status WHERE task_id = $1", task_id)
                if not row:
                    return None
                return dict(row)
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(
                f"Database error retrieving task status {task_id}: {str(e)}"
            ) from e
        except Exception as e:
            raise TaskAdapterError(
                f"Unexpected error retrieving task status {task_id}: {str(e)}"
            ) from e

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: float = 0.0,
        eta: str | None = None,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        """Update task status in task_status table and agent_task_log.status"""
        try:
            async with self.db_pool.acquire() as conn:
                now = datetime.utcnow()
                # Update task_status table
                await conn.execute(
                    """
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
                """,
                    task_id,
                    agent_name or "",
                    status,
                    progress,
                    eta,
                    now,
                )
                # Also update agent_task_log.status (normalize to lowercase for consistency)
                normalized_status = status.lower()
                await conn.execute(
                    """
                    UPDATE agent_task_log 
                    SET status = $1
                    WHERE task_id = $2
                """,
                    normalized_status,
                    task_id,
                )
                return await self.get_task_status(task_id) or {}
        except (TaskAdapterError, TaskNotFoundError):
            raise
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Database error updating task status {task_id}: {e}")
            raise TaskAdapterError(
                f"Database error updating task status {task_id}: {str(e)}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error updating task status {task_id}: {e}")
            raise TaskAdapterError(
                f"Unexpected error updating task status {task_id}: {str(e)}"
            ) from e

    async def get_task_summary(self, cycle_id: str) -> TaskSummary:
        """Get task summary statistics for an execution cycle"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT 
                        COUNT(*) as total_tasks,
                        COUNT(*) FILTER (WHERE status = 'completed') as completed,
                        COUNT(*) FILTER (WHERE status = 'started') as in_progress,
                        COUNT(*) FILTER (WHERE status = 'delegated') as delegated,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed,
                        AVG(duration) as avg_duration
                    FROM agent_task_log 
                    WHERE cycle_id = $1
                """,
                    cycle_id,
                )
                if not row:
                    return TaskSummary(
                        total_tasks=0,
                        completed=0,
                        in_progress=0,
                        delegated=0,
                        failed=0,
                        avg_duration=None,
                    )

                avg_duration = None
                if row.get("avg_duration"):
                    avg_duration = str(row["avg_duration"])

                return TaskSummary(
                    total_tasks=row.get("total_tasks", 0) or 0,
                    completed=row.get("completed", 0) or 0,
                    in_progress=row.get("in_progress", 0) or 0,
                    delegated=row.get("delegated", 0) or 0,
                    failed=row.get("failed", 0) or 0,
                    avg_duration=avg_duration,
                )
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(
                f"Database error retrieving task summary for cycle_id {cycle_id}: {str(e)}"
            ) from e
        except Exception as e:
            raise TaskAdapterError(
                f"Unexpected error retrieving task summary for cycle_id {cycle_id}: {str(e)}"
            ) from e
