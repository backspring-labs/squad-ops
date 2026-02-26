"""SQL task registry adapter.

PostgreSQL-based task persistence.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from __future__ import annotations

from typing import Any

from squadops.ports.tasks.registry import TaskRegistryPort
from squadops.tasks.exceptions import TaskNotFoundError, TaskStateError
from squadops.tasks.types import Task, TaskState


class SQLTaskAdapter(TaskRegistryPort):
    """SQL-based task registry adapter.

    Uses PostgreSQL for task persistence. Connection management
    is handled via the provided connection string.
    """

    def __init__(
        self,
        connection_string: str,
        table_name: str = "tasks",
        **config,
    ):
        """Initialize SQL adapter.

        Args:
            connection_string: PostgreSQL connection string
            table_name: Name of the tasks table
            **config: Additional configuration
        """
        self._connection_string = connection_string
        self._table_name = table_name
        self._pool: Any = None

    async def _ensure_pool(self) -> Any:
        """Ensure connection pool is established."""
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(self._connection_string)
        return self._pool

    async def create(self, task: Task) -> str:
        """Create a new task."""
        pool = await self._ensure_pool()

        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {self._table_name} (
                    task_id, cycle_id, agent, agent_id, task_name, task_type,
                    status, priority, description, phase, pid,
                    correlation_id, causation_id, trace_id, span_id,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                    $12, $13, $14, $15, NOW(), NOW()
                )
                """,
                task.task_id,
                task.cycle_id,
                task.agent,
                task.agent_id,
                task.task_name,
                task.task_type,
                task.status,
                task.priority,
                task.description,
                task.phase,
                task.pid,
                task.correlation_id,
                task.causation_id,
                task.trace_id,
                task.span_id,
            )

        return task.task_id

    async def get(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        pool = await self._ensure_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {self._table_name} WHERE task_id = $1",
                task_id,
            )

        if not row:
            return None

        return self._row_to_task(row)

    async def update_status(
        self,
        task_id: str,
        status: TaskState,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Update task status."""
        import json

        pool = await self._ensure_pool()

        async with pool.acquire() as conn:
            # Check if task exists
            existing = await conn.fetchrow(
                f"SELECT status FROM {self._table_name} WHERE task_id = $1",
                task_id,
            )

            if not existing:
                raise TaskNotFoundError(f"Task not found: {task_id}")

            # Validate state transition (basic validation)
            current_status = existing["status"]
            if current_status in ("completed", "failed") and status not in (
                TaskState.COMPLETED,
                TaskState.FAILED,
            ):
                raise TaskStateError(f"Cannot transition from {current_status} to {status.value}")

            # Update
            result_json = json.dumps(result) if result else None
            await conn.execute(
                f"""
                UPDATE {self._table_name}
                SET status = $1, result = $2, updated_at = NOW()
                WHERE task_id = $3
                """,
                status.value,
                result_json,
                task_id,
            )

    async def list_pending(self, agent_id: str | None = None) -> list[Task]:
        """List pending tasks."""
        pool = await self._ensure_pool()

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

    def _row_to_task(self, row: Any) -> Task:
        """Convert database row to Task model."""
        return Task(
            task_id=row["task_id"],
            cycle_id=row["cycle_id"],
            agent=row["agent"],
            agent_id=row.get("agent_id"),
            task_name=row.get("task_name"),
            task_type=row.get("task_type", "unknown"),
            status=row.get("status", "pending"),
            priority=row.get("priority"),
            description=row.get("description"),
            phase=row.get("phase"),
            pid=row.get("pid"),
            correlation_id=row.get("correlation_id"),
            causation_id=row.get("causation_id"),
            trace_id=row.get("trace_id"),
            span_id=row.get("span_id"),
        )

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
