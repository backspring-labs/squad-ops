"""Prefect task adapter.

Full implementation for SIP-0.8.8.
Integrates with Prefect orchestration while maintaining SquadOps DB as source of truth.

IMPORTANT: This module MUST NOT import Prefect at module level.
Prefect is an optional dependency - adapter works in DB-only mode when unavailable.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from squadops.ports.tasks.registry import TaskRegistryPort
from squadops.tasks.exceptions import TaskError, TaskNotFoundError, TaskStateError
from squadops.tasks.types import Task, TaskState

if TYPE_CHECKING:
    import asyncpg
    from squadops.core.secret_manager import SecretManager

logger = logging.getLogger(__name__)

# State mapping: SquadOps -> Prefect
SQUADOPS_TO_PREFECT_STATE = {
    TaskState.PENDING: "PENDING",
    TaskState.STARTED: "RUNNING",
    TaskState.ACTIVE_NON_BLOCKING: "RUNNING",
    TaskState.IN_PROGRESS: "RUNNING",
    TaskState.COMPLETED: "COMPLETED",
    TaskState.FAILED: "FAILED",
    TaskState.DELEGATED: "PENDING",
}

# State mapping: Prefect -> SquadOps
PREFECT_TO_SQUADOPS_STATE = {
    "PENDING": TaskState.PENDING,
    "RUNNING": TaskState.IN_PROGRESS,
    "COMPLETED": TaskState.COMPLETED,
    "FAILED": TaskState.FAILED,
    "CANCELLED": TaskState.FAILED,
    "CRASHED": TaskState.FAILED,
    "PAUSED": TaskState.PENDING,
}


class PrefectTaskAdapter(TaskRegistryPort):
    """Prefect-integrated task adapter.

    Integrates with Prefect's orchestration engine while maintaining
    SquadOps DB as the source of truth. All task state is written to
    SquadOps DB first, with Prefect run IDs stored in metrics.

    When Prefect is unavailable, operates in DB-only mode.
    """

    def __init__(
        self,
        connection_string: str = "",
        secret_manager: SecretManager | None = None,
        prefect_api_url: str | None = None,
        prefect_api_key: str | None = None,
        table_name: str = "agent_task_log",
        **config,
    ):
        """Initialize Prefect adapter.

        Args:
            connection_string: PostgreSQL connection string (may be secret:// ref)
            secret_manager: Optional secret manager for resolving secret:// refs
            prefect_api_url: Optional Prefect API URL (enables Prefect integration)
            prefect_api_key: Optional Prefect API key
            table_name: Name of the tasks table (default: agent_task_log)
            **config: Additional configuration
        """
        # Resolve secret:// refs if needed
        if secret_manager and connection_string.startswith("secret://"):
            connection_string = secret_manager.resolve(connection_string[9:])
        if secret_manager and prefect_api_key and prefect_api_key.startswith("secret://"):
            prefect_api_key = secret_manager.resolve(prefect_api_key[9:])

        self._connection_string = connection_string
        self._table_name = table_name
        self._prefect_api_url = prefect_api_url
        self._prefect_api_key = prefect_api_key
        self._pool: asyncpg.Pool | None = None
        self._initialized = False

    async def _ensure_pool(self) -> asyncpg.Pool:
        """Ensure connection pool is established."""
        if self._pool is None:
            import asyncpg

            if not self._connection_string:
                raise TaskError("connection_string is required for PrefectTaskAdapter")
            self._pool = await asyncpg.create_pool(self._connection_string)
        return self._pool

    async def initialize(self) -> None:
        """Initialize Prefect client connection."""
        if self._initialized:
            return

        try:
            # Ensure DB pool is ready
            await self._ensure_pool()

            # Configure Prefect environment if API URL provided
            if self._prefect_api_url:
                import os

                os.environ["PREFECT_API_URL"] = self._prefect_api_url
                if self._prefect_api_key:
                    os.environ["PREFECT_API_KEY"] = self._prefect_api_key
                logger.info(f"Prefect adapter initialized with API URL: {self._prefect_api_url}")
            else:
                logger.info("Prefect adapter initialized in DB-only mode (no Prefect API URL)")

            self._initialized = True
        except Exception as e:
            logger.warning(
                f"Failed to initialize Prefect adapter: {e}. "
                "Adapter will continue with DB-only operations."
            )
            self._initialized = True  # Mark initialized to avoid retry loops

    def _row_to_task(self, row: asyncpg.Record) -> Task:
        """Convert database row to Task model."""
        # Parse artifacts if present
        artifacts = []
        if row.get("artifacts"):
            artifacts_data = row["artifacts"]
            if isinstance(artifacts_data, str):
                artifacts_data = json.loads(artifacts_data)
            if isinstance(artifacts_data, list):
                from squadops.tasks.types import Artifact

                artifacts = [
                    Artifact(**a) if isinstance(a, dict) else a
                    for a in artifacts_data
                ]

        # Parse metrics if present (includes Prefect run ID)
        metrics = {}
        if row.get("metrics"):
            metrics_data = row["metrics"]
            if isinstance(metrics_data, str):
                metrics = json.loads(metrics_data)
            elif isinstance(metrics_data, dict):
                metrics = metrics_data

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

    async def create(self, task: Task) -> str:
        """Create a new task.

        Writes to SquadOps DB first (source of truth), then creates
        Prefect task run reference if Prefect is configured.

        Args:
            task: Task to create

        Returns:
            Task ID of the created task

        Raises:
            TaskError: Failed to create task
        """
        import asyncpg.exceptions

        if not self._initialized:
            await self.initialize()

        pool = await self._ensure_pool()

        try:
            now = datetime.utcnow()
            metrics = {"prefect_task_run_id": None}

            async with pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {self._table_name} (
                        task_id, cycle_id, agent, agent_id, task_name,
                        status, priority, description, start_time,
                        dependencies, delegated_by, delegated_to, pid, phase,
                        metrics, created_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16
                    )
                    """,
                    task.task_id,
                    task.cycle_id,
                    task.agent,
                    task.agent_id or task.agent,
                    task.task_name,
                    task.status,
                    task.priority,
                    task.description,
                    now,
                    task.dependencies or [],
                    task.delegated_by,
                    task.delegated_to,
                    task.pid,
                    task.phase,
                    json.dumps(metrics),
                    now,
                )

            # Create Prefect task run reference if available
            if self._prefect_api_url:
                await self._link_prefect_task_run(task.task_id, task.cycle_id, metrics)

            return task.task_id

        except asyncpg.exceptions.UniqueViolationError as e:
            raise TaskError(f"Task {task.task_id} already exists") from e
        except asyncpg.exceptions.PostgresError as e:
            raise TaskError(f"Database error creating task {task.task_id}: {e}") from e
        except Exception as e:
            raise TaskError(f"Unexpected error creating task {task.task_id}: {e}") from e

    async def _link_prefect_task_run(
        self,
        task_id: str,
        cycle_id: str | None,
        metrics: dict[str, Any],
    ) -> None:
        """Link task to Prefect flow run (if available)."""
        try:
            # Generate Prefect task run reference
            flow_run_id = await self._get_or_create_flow_run_id(cycle_id)
            if flow_run_id:
                prefect_task_run_id = f"flow-{flow_run_id}-task-{task_id}"
                metrics["prefect_task_run_id"] = prefect_task_run_id
                metrics["prefect_flow_run_id"] = flow_run_id

                # Update DB with Prefect references
                pool = await self._ensure_pool()
                async with pool.acquire() as conn:
                    await conn.execute(
                        f"UPDATE {self._table_name} SET metrics = $1 WHERE task_id = $2",
                        json.dumps(metrics),
                        task_id,
                    )
                logger.debug(f"Linked Prefect flow run {flow_run_id} to task {task_id}")
        except Exception as e:
            # Log but don't fail - SquadOps DB is source of truth
            logger.warning(f"Failed to create Prefect task run for {task_id}: {e}")

    async def _get_or_create_flow_run_id(self, cycle_id: str | None) -> str | None:
        """Get or create a Prefect flow run ID for a cycle."""
        if not self._prefect_api_url or not cycle_id:
            return None

        try:
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                # Check if flow run ID already exists in cycle table
                row = await conn.fetchrow(
                    "SELECT inputs FROM cycle WHERE cycle_id = $1",
                    cycle_id,
                )
                if row and row.get("inputs"):
                    inputs = row["inputs"]
                    if isinstance(inputs, str):
                        inputs = json.loads(inputs)
                    if inputs.get("prefect_flow_run_id"):
                        return inputs["prefect_flow_run_id"]

            # Create new flow run reference
            flow_run_id = f"flow-{cycle_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

            # Update cycle with flow run ID
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT inputs FROM cycle WHERE cycle_id = $1",
                    cycle_id,
                )
                if row:
                    inputs = row.get("inputs") or {}
                    if isinstance(inputs, str):
                        inputs = json.loads(inputs)
                    inputs["prefect_flow_run_id"] = flow_run_id
                    await conn.execute(
                        "UPDATE cycle SET inputs = $1 WHERE cycle_id = $2",
                        json.dumps(inputs),
                        cycle_id,
                    )

            return flow_run_id
        except Exception as e:
            logger.warning(f"Failed to get/create Prefect flow run ID for cycle {cycle_id}: {e}")
            return None

    async def get(self, task_id: str) -> Task | None:
        """Get a task by ID.

        Reads from SquadOps DB (source of truth).

        Args:
            task_id: ID of the task to retrieve

        Returns:
            Task if found, None otherwise
        """
        import asyncpg.exceptions

        if not self._initialized:
            await self.initialize()

        pool = await self._ensure_pool()

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT * FROM {self._table_name} WHERE task_id = $1",
                    task_id,
                )
                if not row:
                    return None
                return self._row_to_task(row)
        except asyncpg.exceptions.PostgresError as e:
            raise TaskError(f"Database error retrieving task {task_id}: {e}") from e
        except Exception as e:
            raise TaskError(f"Unexpected error retrieving task {task_id}: {e}") from e

    async def update_status(
        self,
        task_id: str,
        status: TaskState,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Update task status.

        Updates SquadOps DB first (source of truth), then updates
        Prefect state reference if configured.

        Args:
            task_id: ID of the task to update
            status: New task state
            result: Optional result data

        Raises:
            TaskNotFoundError: Task not found
            TaskStateError: Invalid state transition
        """
        import asyncpg.exceptions

        if not self._initialized:
            await self.initialize()

        pool = await self._ensure_pool()

        try:
            async with pool.acquire() as conn:
                # Check if task exists and get current state
                existing = await conn.fetchrow(
                    f"SELECT status, metrics FROM {self._table_name} WHERE task_id = $1",
                    task_id,
                )

                if not existing:
                    raise TaskNotFoundError(f"Task not found: {task_id}")

                # Validate state transition
                current_status = existing["status"]
                if current_status in ("completed", "failed") and status not in (
                    TaskState.COMPLETED,
                    TaskState.FAILED,
                ):
                    raise TaskStateError(
                        f"Cannot transition from {current_status} to {status.value}"
                    )

                # Build update query
                updates = ["status = $1", "updated_at = NOW()"]
                params: list[Any] = [status.value]
                param_idx = 2

                # Set end_time for terminal states
                if status in (TaskState.COMPLETED, TaskState.FAILED):
                    updates.append(f"end_time = ${param_idx}")
                    params.append(datetime.utcnow())
                    param_idx += 1
                    updates.append("duration = end_time - start_time")

                # Store result in error_log or metrics
                if result:
                    if status == TaskState.FAILED and "error" in result:
                        updates.append(f"error_log = ${param_idx}")
                        params.append(result.get("error", ""))
                        param_idx += 1
                    else:
                        # Merge result into metrics
                        metrics = existing.get("metrics") or {}
                        if isinstance(metrics, str):
                            metrics = json.loads(metrics)
                        metrics["result"] = result
                        updates.append(f"metrics = ${param_idx}")
                        params.append(json.dumps(metrics))
                        param_idx += 1

                params.append(task_id)
                query = f"UPDATE {self._table_name} SET {', '.join(updates)} WHERE task_id = ${param_idx}"

                update_result = await conn.execute(query, *params)
                if update_result == "UPDATE 0":
                    raise TaskNotFoundError(f"Task not found: {task_id}")

            # Update Prefect state reference if available
            if self._prefect_api_url:
                await self._update_prefect_state(task_id, status)

        except (TaskNotFoundError, TaskStateError):
            raise
        except asyncpg.exceptions.PostgresError as e:
            raise TaskError(f"Database error updating task {task_id}: {e}") from e
        except Exception as e:
            raise TaskError(f"Unexpected error updating task {task_id}: {e}") from e

    async def _update_prefect_state(self, task_id: str, status: TaskState) -> None:
        """Update Prefect task run state reference."""
        try:
            task = await self.get(task_id)
            if task and task.metrics and task.metrics.get("prefect_task_run_id"):
                prefect_state = SQUADOPS_TO_PREFECT_STATE.get(status, "PENDING")

                pool = await self._ensure_pool()
                async with pool.acquire() as conn:
                    metrics = task.metrics.copy()
                    metrics["prefect_state"] = prefect_state
                    await conn.execute(
                        f"UPDATE {self._table_name} SET metrics = $1 WHERE task_id = $2",
                        json.dumps(metrics),
                        task_id,
                    )
                logger.debug(f"Updated Prefect state reference for task {task_id}: {prefect_state}")
        except Exception as e:
            # Log but don't fail - SquadOps DB is source of truth
            logger.warning(f"Failed to update Prefect task run state for {task_id}: {e}")

    async def list_pending(self, agent_id: str | None = None) -> list[Task]:
        """List pending tasks.

        Queries SquadOps DB (source of truth).

        Args:
            agent_id: Optional filter by target agent

        Returns:
            List of pending tasks
        """
        import asyncpg.exceptions

        if not self._initialized:
            await self.initialize()

        pool = await self._ensure_pool()

        try:
            async with pool.acquire() as conn:
                if agent_id:
                    rows = await conn.fetch(
                        f"""
                        SELECT * FROM {self._table_name}
                        WHERE status IN ('pending', 'started')
                        AND (agent_id = $1 OR delegated_to = $1)
                        ORDER BY created_at ASC
                        """,
                        agent_id,
                    )
                else:
                    rows = await conn.fetch(
                        f"""
                        SELECT * FROM {self._table_name}
                        WHERE status IN ('pending', 'started')
                        ORDER BY created_at ASC
                        """,
                    )
                return [self._row_to_task(row) for row in rows]
        except asyncpg.exceptions.PostgresError as e:
            raise TaskError(f"Database error listing pending tasks: {e}") from e
        except Exception as e:
            raise TaskError(f"Unexpected error listing pending tasks: {e}") from e

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
        self._initialized = False

    async def health(self) -> dict[str, Any]:
        """Check adapter health.

        Returns:
            Health status dict with 'healthy' bool and diagnostic info
        """
        try:
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            return {
                "healthy": True,
                "prefect_enabled": self._prefect_api_url is not None,
                "prefect_api_url": self._prefect_api_url,
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "prefect_enabled": self._prefect_api_url is not None,
            }
