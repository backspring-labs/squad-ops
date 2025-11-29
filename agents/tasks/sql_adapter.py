"""
SqlTasksAdapter - PostgreSQL-based task management adapter
Implements TaskAdapterBase for SQL backend
"""

import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncpg
from agents.tasks.base_adapter import TaskAdapterBase
from agents.tasks.models import (
    Task,
    TaskCreate,
    TaskState,
    TaskFilters,
    Artifact,
    FlowRun,
    FlowState,
    TaskSummary,
)
from agents.tasks.errors import (
    TaskAdapterError,
    TaskNotFoundError,
    TaskConflictError,
)

logger = logging.getLogger(__name__)


class SqlTasksAdapter(TaskAdapterBase):
    """
    SQL adapter for task management using PostgreSQL.
    Handles agent_task_log, execution_cycle, and task_status tables.
    
    **DTO Purity:**
    This adapter returns canonical DTOs (Task, FlowRun, etc.) only.
    Response-shape formatting is handled in the FastAPI layer.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize SQL adapter with database connection pool.

        Args:
            db_pool: AsyncPG connection pool
        """
        self.db_pool = db_pool

    async def initialize(self) -> None:
        """
        Initialize SQL adapter (no-op since pool is created in registry).
        Pool is already available, so initialization is not needed.
        """
        # Pool is created in registry, no additional initialization needed
        return None

    async def shutdown(self) -> None:
        """
        Shutdown SQL adapter by closing the database connection pool.
        """
        if self.db_pool:
            try:
                await self.db_pool.close()
                logger.info("SQL adapter connection pool closed")
            except Exception as e:
                logger.error(f"Error closing SQL adapter connection pool: {e}")
                raise TaskAdapterError(f"Failed to close connection pool: {str(e)}") from e

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
                # Single artifact dict
                artifacts = [Artifact(**artifacts_data)]
            elif isinstance(artifacts_data, list):
                # List of artifacts
                artifacts = [Artifact(**a) if isinstance(a, dict) else a for a in artifacts_data]

        return Task(
            task_id=row["task_id"],
            pid=row.get("pid"),
            ecid=row.get("ecid"),
            agent=row["agent"],
            phase=row.get("phase"),
            status=row["status"],
            priority=row.get("priority"),
            description=row.get("description"),
            start_time=row.get("start_time"),
            end_time=row.get("end_time"),
            duration=str(row["duration"]) if row.get("duration") else None,
            artifacts=artifacts,
            dependencies=row.get("dependencies") or [],
            error_log=row.get("error_log"),
            delegated_by=row.get("delegated_by"),
            delegated_to=row.get("delegated_to"),
            created_at=row.get("created_at"),
        )

    def _row_to_flow(self, row: asyncpg.Record) -> FlowRun:
        """Convert database row to FlowRun DTO"""
        return FlowRun(
            ecid=row["ecid"],
            pid=row["pid"],
            project_id=row.get("project_id"),  # SIP-0047
            run_type=row["run_type"],
            title=row["title"],
            description=row.get("description"),
            created_at=row.get("created_at"),
            initiated_by=row.get("initiated_by"),
            status=row.get("status", "active"),
            notes=row.get("notes"),
        )

    async def create_task(self, task: TaskCreate) -> Task:
        """Create a new task"""
        try:
            async with self.db_pool.acquire() as conn:
                try:
                    now = datetime.utcnow()
                    await conn.execute("""
                        INSERT INTO agent_task_log 
                        (task_id, ecid, agent, status, priority, description, start_time, 
                         dependencies, delegated_by, delegated_to, pid, phase, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    """, 
                        task.task_id, 
                        task.ecid, 
                        task.agent, 
                        task.status, 
                        task.priority, 
                        task.description, 
                        now,
                        task.dependencies or [], 
                        task.delegated_by, 
                        task.delegated_to,
                        task.pid,
                        task.phase,
                        now
                    )
                    result = await self.get_task(task.task_id)
                    if not result:
                        raise TaskNotFoundError(f"Task {task.task_id} was created but could not be retrieved")
                    return result
                except asyncpg.exceptions.UniqueViolationError as e:
                    raise TaskConflictError(f"Task {task.task_id} already exists") from e
                except asyncpg.exceptions.PostgresError as e:
                    raise TaskAdapterError(f"Database error creating task {task.task_id}: {str(e)}") from e
        except (TaskAdapterError, TaskNotFoundError, TaskConflictError):
            raise
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error creating task {task.task_id}: {str(e)}") from e

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID"""
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

    async def list_tasks(self, filters: TaskFilters) -> List[Task]:
        """List tasks matching filters"""
        try:
            async with self.db_pool.acquire() as conn:
                conditions = []
                params = []
                param_count = 1

                if filters.ecid:
                    conditions.append(f"ecid = ${param_count}")
                    params.append(filters.ecid)
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
        self, task_id: str, state: TaskState, meta: Optional[Dict[str, Any]] = None
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

            params.append(task_id)
            query = f"UPDATE agent_task_log SET {', '.join(updates)} WHERE task_id = ${param_count}"

            async with self.db_pool.acquire() as conn:
                result = await conn.execute(query, *params)
                if result == "UPDATE 0":
                    raise TaskNotFoundError(f"Task {task_id} not found")

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
                existing_artifacts.append(artifact.dict())
                await conn.execute(
                    "UPDATE agent_task_log SET artifacts = $1 WHERE task_id = $2",
                    json.dumps(existing_artifacts),
                    task_id,
                )
        except (TaskAdapterError, TaskNotFoundError):
            raise
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(f"Database error adding artifact to task {task_id}: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error adding artifact to task {task_id}: {str(e)}") from e

    async def add_dependency(self, task_id: str, depends_on_id: str) -> None:
        """Add a dependency relationship"""
        try:
            task = await self.get_task(task_id)
            if not task:
                raise TaskNotFoundError(f"Task {task_id} not found")

            dependencies = task.dependencies or []
            if depends_on_id not in dependencies:
                dependencies.append(depends_on_id)
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE agent_task_log SET dependencies = $1 WHERE task_id = $2",
                        dependencies,
                        task_id,
                    )
        except (TaskAdapterError, TaskNotFoundError):
            raise
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(f"Database error adding dependency to task {task_id}: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error adding dependency to task {task_id}: {str(e)}") from e

    async def list_tasks_for_pid(self, pid: str) -> List[Task]:
        """List all tasks for a process ID"""
        filters = TaskFilters(pid=pid)
        return await self.list_tasks(filters)

    async def list_tasks_for_ecid(self, ecid: str) -> List[Task]:
        """List all tasks for an execution cycle ID"""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM agent_task_log 
                    WHERE ecid = $1 
                    ORDER BY created_at ASC
                """,
                    ecid,
                )
                return [self._row_to_task(row) for row in rows]
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(f"Database error listing tasks for ECID {ecid}: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error listing tasks for ECID {ecid}: {str(e)}") from e

    async def create_flow(
        self, ecid: str, pid: str, meta: Optional[Dict[str, Any]] = None
    ) -> FlowRun:
        """Create a new execution cycle"""
        try:
            meta = meta or {}
            project_id = meta.get("project_id")
            
            # Validate project_id if provided (SIP-0047)
            if project_id:
                from agents.cycle_data.project_validator import validate_project_id
                await validate_project_id(project_id, self.db_pool)
            
            async with self.db_pool.acquire() as conn:
                try:
                    now = datetime.utcnow()
                    await conn.execute(
                        """
                        INSERT INTO execution_cycle 
                        (ecid, pid, project_id, run_type, title, description, initiated_by, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                        ecid,
                        pid,
                        project_id,
                        meta.get("run_type", "project"),
                        meta.get("title", ""),
                        meta.get("description"),
                        meta.get("initiated_by", ""),
                        now,
                    )
                    result = await self.get_flow(ecid)
                    if not result:
                        raise TaskNotFoundError(f"Execution cycle {ecid} was created but could not be retrieved")
                    return result
                except asyncpg.exceptions.UniqueViolationError as e:
                    raise TaskConflictError(f"Execution cycle {ecid} already exists") from e
                except asyncpg.exceptions.PostgresError as e:
                    raise TaskAdapterError(f"Database error creating execution cycle {ecid}: {str(e)}") from e
        except (TaskAdapterError, TaskNotFoundError, TaskConflictError):
            raise
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error creating execution cycle {ecid}: {str(e)}") from e

    async def update_flow(
        self, flow_id: str, state: FlowState, meta: Optional[Dict[str, Any]] = None
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
            query = f"UPDATE execution_cycle SET {', '.join(updates)} WHERE ecid = ${param_count}"

            async with self.db_pool.acquire() as conn:
                result = await conn.execute(query, *params)
                if result == "UPDATE 0":
                    raise TaskNotFoundError(f"Execution cycle {flow_id} not found")

            flow = await self.get_flow(flow_id)
            if not flow:
                raise TaskNotFoundError(f"Execution cycle {flow_id} was updated but could not be retrieved")
            return flow
        except (TaskAdapterError, TaskNotFoundError):
            raise
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(f"Database error updating execution cycle {flow_id}: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error updating execution cycle {flow_id}: {str(e)}") from e

    async def get_flow(self, ecid: str) -> Optional[FlowRun]:
        """Get an execution cycle by ECID"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM execution_cycle WHERE ecid = $1", ecid
                )
                if not row:
                    return None
                return self._row_to_flow(row)
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(f"Database error retrieving execution cycle {ecid}: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error retrieving execution cycle {ecid}: {str(e)}") from e

    async def list_flows(self, run_type: Optional[str] = None) -> List[FlowRun]:
        """List execution cycles, optionally filtered by run_type"""
        try:
            async with self.db_pool.acquire() as conn:
                if run_type:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM execution_cycle 
                        WHERE run_type = $1 
                        ORDER BY created_at DESC
                    """,
                        run_type,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM execution_cycle 
                        ORDER BY created_at DESC
                    """
                    )
                return [self._row_to_flow(row) for row in rows]
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(f"Database error listing execution cycles: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error listing execution cycles: {str(e)}") from e

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status from task_status table"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM task_status WHERE task_id = $1", task_id
                )
                if not row:
                    return None
                return dict(row)
        except asyncpg.exceptions.PostgresError as e:
            raise TaskAdapterError(f"Database error retrieving task status {task_id}: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error retrieving task status {task_id}: {str(e)}") from e

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: float = 0.0,
        eta: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update task status in task_status table"""
        try:
            async with self.db_pool.acquire() as conn:
                now = datetime.utcnow()
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
                return await self.get_task_status(task_id) or {}
        except (TaskAdapterError, TaskNotFoundError):
            raise
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Database error updating task status {task_id}: {e}")
            raise TaskAdapterError(f"Database error updating task status {task_id}: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error updating task status {task_id}: {e}")
            raise TaskAdapterError(f"Unexpected error updating task status {task_id}: {str(e)}") from e

    async def get_task_summary(self, ecid: str) -> TaskSummary:
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
                    WHERE ecid = $1
                """,
                    ecid,
                )
                if not row:
                    # Return empty summary if no tasks found
                    return TaskSummary(
                        total_tasks=0,
                        completed=0,
                        in_progress=0,
                        delegated=0,
                        failed=0,
                        avg_duration=None,
                    )
                
                # Convert duration interval to string if present
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
            raise TaskAdapterError(f"Database error retrieving task summary for ECID {ecid}: {str(e)}") from e
        except Exception as e:
            raise TaskAdapterError(f"Unexpected error retrieving task summary for ECID {ecid}: {str(e)}") from e

