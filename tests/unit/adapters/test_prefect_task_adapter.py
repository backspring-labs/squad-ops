"""Unit tests for PrefectTaskAdapter.

Tests the SIP-0.8.8 full implementation of PrefectTaskAdapter
that integrates with Prefect while maintaining SquadOps DB as source of truth.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.tasks.prefect import (
    PREFECT_TO_SQUADOPS_STATE,
    SQUADOPS_TO_PREFECT_STATE,
    PrefectTaskAdapter,
)
from squadops.tasks.exceptions import TaskError, TaskNotFoundError, TaskStateError
from squadops.tasks.types import Task, TaskState


class MockConnectionContext:
    """Async context manager for mocking pool.acquire()."""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_asyncpg_pool():
    """Create mock asyncpg pool and connection."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire = MagicMock(return_value=MockConnectionContext(conn))
    return pool, conn


@pytest.fixture
def mock_asyncpg_module(mock_asyncpg_pool):
    """Patch asyncpg.create_pool to return mock pool."""
    pool, conn = mock_asyncpg_pool

    async def create_pool_mock(*args, **kwargs):
        return pool

    with patch("asyncpg.create_pool", side_effect=create_pool_mock):
        with patch("asyncpg.exceptions") as mock_exceptions:
            # Set up exception classes
            mock_exceptions.UniqueViolationError = type("UniqueViolationError", (Exception,), {})
            mock_exceptions.PostgresError = type("PostgresError", (Exception,), {})
            yield pool, conn


class TestPrefectTaskAdapterStateMappings:
    """Tests for state mapping constants."""

    def test_squadops_to_prefect_mapping(self):
        """SquadOps states map to Prefect states correctly."""
        assert SQUADOPS_TO_PREFECT_STATE[TaskState.PENDING] == "PENDING"
        assert SQUADOPS_TO_PREFECT_STATE[TaskState.STARTED] == "RUNNING"
        assert SQUADOPS_TO_PREFECT_STATE[TaskState.IN_PROGRESS] == "RUNNING"
        assert SQUADOPS_TO_PREFECT_STATE[TaskState.COMPLETED] == "COMPLETED"
        assert SQUADOPS_TO_PREFECT_STATE[TaskState.FAILED] == "FAILED"

    def test_prefect_to_squadops_mapping(self):
        """Prefect states map to SquadOps states correctly."""
        assert PREFECT_TO_SQUADOPS_STATE["PENDING"] == TaskState.PENDING
        assert PREFECT_TO_SQUADOPS_STATE["RUNNING"] == TaskState.IN_PROGRESS
        assert PREFECT_TO_SQUADOPS_STATE["COMPLETED"] == TaskState.COMPLETED
        assert PREFECT_TO_SQUADOPS_STATE["FAILED"] == TaskState.FAILED
        assert PREFECT_TO_SQUADOPS_STATE["CANCELLED"] == TaskState.FAILED


@pytest.mark.asyncio
class TestPrefectTaskAdapterCreate:
    """Tests for task creation."""

    async def test_create_task_db_only(self, mock_asyncpg_module):
        """create() writes to DB when Prefect is not configured."""
        pool, conn = mock_asyncpg_module
        conn.execute = AsyncMock()

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        task = Task(
            task_id="task-001",
            cycle_id="cycle-001",
            agent="test-agent",
            agent_id="test-agent",
            status="pending",
        )

        result = await adapter.create(task)

        assert result == "task-001"
        conn.execute.assert_called_once()
        # Verify INSERT was called
        call_args = conn.execute.call_args[0][0]
        assert "INSERT INTO agent_task_log" in call_args

    async def test_create_task_with_prefect(self, mock_asyncpg_module):
        """create() links to Prefect when configured."""
        pool, conn = mock_asyncpg_module
        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)  # No existing flow

        adapter = PrefectTaskAdapter(
            connection_string="postgresql://localhost/test",
            prefect_api_url="http://prefect:4200",
        )
        adapter._pool = pool
        adapter._initialized = True

        task = Task(
            task_id="task-001",
            cycle_id="cycle-001",
            agent="test-agent",
            status="pending",
        )

        result = await adapter.create(task)

        assert result == "task-001"
        # Should have multiple execute calls (initial insert + prefect link update)
        assert conn.execute.call_count >= 1

    async def test_create_task_duplicate_raises_error(self, mock_asyncpg_module):
        """create() raises TaskError on duplicate task_id."""
        pool, conn = mock_asyncpg_module

        # Import real exception to raise
        import asyncpg.exceptions

        conn.execute = AsyncMock(
            side_effect=asyncpg.exceptions.UniqueViolationError("duplicate key")
        )

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        task = Task(
            task_id="task-001",
            cycle_id="cycle-001",
            agent="test-agent",
            status="pending",
        )

        with pytest.raises(TaskError, match="already exists"):
            await adapter.create(task)


@pytest.mark.asyncio
class TestPrefectTaskAdapterGet:
    """Tests for task retrieval."""

    async def test_get_task_found(self, mock_asyncpg_module):
        """get() returns Task when found."""
        pool, conn = mock_asyncpg_module

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "task_id": "task-001",
            "cycle_id": "cycle-001",
            "agent": "test-agent",
            "status": "started",
            "metrics": None,
            "artifacts": None,
            "dependencies": [],
        }.get(k)
        mock_row.get = lambda k, d=None: {
            "task_id": "task-001",
            "cycle_id": "cycle-001",
            "agent": "test-agent",
            "agent_id": "test-agent",
            "status": "started",
            "metrics": None,
            "artifacts": None,
            "dependencies": [],
            "task_name": None,
            "phase": None,
            "priority": None,
            "description": None,
            "start_time": None,
            "end_time": None,
            "duration": None,
            "error_log": None,
            "delegated_by": None,
            "delegated_to": None,
            "created_at": None,
            "pid": None,
        }.get(k, d)

        conn.fetchrow = AsyncMock(return_value=mock_row)

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        result = await adapter.get("task-001")

        assert result is not None
        assert result.task_id == "task-001"
        assert result.status == "started"
        conn.fetchrow.assert_called_once()

    async def test_get_task_not_found(self, mock_asyncpg_module):
        """get() returns None when task not found."""
        pool, conn = mock_asyncpg_module
        conn.fetchrow = AsyncMock(return_value=None)

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        result = await adapter.get("non-existent")

        assert result is None

    async def test_get_task_with_metrics(self, mock_asyncpg_module):
        """get() parses metrics JSON correctly."""
        pool, conn = mock_asyncpg_module

        metrics_data = {"prefect_task_run_id": "flow-001-task-001", "custom": "value"}

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "task_id": "task-001",
            "cycle_id": "cycle-001",
            "agent": "test-agent",
            "status": "started",
            "metrics": json.dumps(metrics_data),
            "artifacts": None,
            "dependencies": [],
        }.get(k)
        mock_row.get = lambda k, d=None: {
            "task_id": "task-001",
            "cycle_id": "cycle-001",
            "agent": "test-agent",
            "agent_id": None,
            "status": "started",
            "metrics": json.dumps(metrics_data),
            "artifacts": None,
            "dependencies": [],
            "task_name": None,
            "phase": None,
            "priority": None,
            "description": None,
            "start_time": None,
            "end_time": None,
            "duration": None,
            "error_log": None,
            "delegated_by": None,
            "delegated_to": None,
            "created_at": None,
            "pid": None,
        }.get(k, d)

        conn.fetchrow = AsyncMock(return_value=mock_row)

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        result = await adapter.get("task-001")

        assert result is not None
        assert result.metrics["prefect_task_run_id"] == "flow-001-task-001"
        assert result.metrics["custom"] == "value"


@pytest.mark.asyncio
class TestPrefectTaskAdapterUpdateStatus:
    """Tests for task status updates."""

    async def test_update_status_success(self, mock_asyncpg_module):
        """update_status() updates task in DB."""
        pool, conn = mock_asyncpg_module

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {"status": "started", "metrics": None}.get(k)
        mock_row.get = lambda k, d=None: {"status": "started", "metrics": None}.get(k, d)

        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.execute = AsyncMock(return_value="UPDATE 1")

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        await adapter.update_status("task-001", TaskState.COMPLETED)

        # Verify UPDATE was called
        update_calls = [c for c in conn.execute.call_args_list if "UPDATE" in str(c)]
        assert len(update_calls) >= 1

    async def test_update_status_not_found(self, mock_asyncpg_module):
        """update_status() raises TaskNotFoundError when task missing."""
        pool, conn = mock_asyncpg_module
        conn.fetchrow = AsyncMock(return_value=None)

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        with pytest.raises(TaskNotFoundError, match="not found"):
            await adapter.update_status("non-existent", TaskState.COMPLETED)

    async def test_update_status_invalid_transition(self, mock_asyncpg_module):
        """update_status() raises TaskStateError on invalid transition."""
        pool, conn = mock_asyncpg_module

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {"status": "completed", "metrics": None}.get(k)
        mock_row.get = lambda k, d=None: {"status": "completed", "metrics": None}.get(k, d)

        conn.fetchrow = AsyncMock(return_value=mock_row)

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        with pytest.raises(TaskStateError, match="Cannot transition"):
            await adapter.update_status("task-001", TaskState.STARTED)

    async def test_update_status_with_error_result(self, mock_asyncpg_module):
        """update_status() stores error in error_log for failed tasks."""
        pool, conn = mock_asyncpg_module

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {"status": "started", "metrics": None}.get(k)
        mock_row.get = lambda k, d=None: {"status": "started", "metrics": None}.get(k, d)

        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.execute = AsyncMock(return_value="UPDATE 1")

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        await adapter.update_status(
            "task-001",
            TaskState.FAILED,
            result={"error": "Something went wrong"},
        )

        # Verify error_log was included in update
        call_args = str(conn.execute.call_args_list)
        assert "error_log" in call_args


@pytest.mark.asyncio
class TestPrefectTaskAdapterListPending:
    """Tests for listing pending tasks."""

    async def test_list_pending_all(self, mock_asyncpg_module):
        """list_pending() returns all pending tasks."""
        pool, conn = mock_asyncpg_module

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "task_id": "task-001",
            "cycle_id": "cycle-001",
            "agent": "test-agent",
            "status": "pending",
            "metrics": None,
            "artifacts": None,
            "dependencies": [],
        }.get(k)
        mock_row.get = lambda k, d=None: {
            "task_id": "task-001",
            "cycle_id": "cycle-001",
            "agent": "test-agent",
            "agent_id": None,
            "status": "pending",
            "metrics": None,
            "artifacts": None,
            "dependencies": [],
            "task_name": None,
            "phase": None,
            "priority": None,
            "description": None,
            "start_time": None,
            "end_time": None,
            "duration": None,
            "error_log": None,
            "delegated_by": None,
            "delegated_to": None,
            "created_at": None,
            "pid": None,
        }.get(k, d)

        conn.fetch = AsyncMock(return_value=[mock_row])

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        result = await adapter.list_pending()

        assert len(result) == 1
        assert result[0].task_id == "task-001"
        assert result[0].status == "pending"
        # Verify query filters by status
        call_args = conn.fetch.call_args[0][0]
        assert "pending" in call_args or "started" in call_args

    async def test_list_pending_by_agent(self, mock_asyncpg_module):
        """list_pending() filters by agent_id."""
        pool, conn = mock_asyncpg_module
        conn.fetch = AsyncMock(return_value=[])

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        await adapter.list_pending(agent_id="specific-agent")

        # Verify agent filter was applied
        call_args = conn.fetch.call_args
        assert "specific-agent" in str(call_args)

    async def test_list_pending_empty(self, mock_asyncpg_module):
        """list_pending() returns empty list when no pending tasks."""
        pool, conn = mock_asyncpg_module
        conn.fetch = AsyncMock(return_value=[])

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        result = await adapter.list_pending()

        assert result == []


@pytest.mark.asyncio
class TestPrefectTaskAdapterHealth:
    """Tests for health check."""

    async def test_health_success_db_only(self, mock_asyncpg_module):
        """health() returns healthy when DB is accessible."""
        pool, conn = mock_asyncpg_module
        conn.fetchval = AsyncMock(return_value=1)

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool

        result = await adapter.health()

        assert result["healthy"] is True
        assert result["prefect_enabled"] is False

    async def test_health_success_with_prefect(self, mock_asyncpg_module):
        """health() indicates Prefect is enabled when configured."""
        pool, conn = mock_asyncpg_module
        conn.fetchval = AsyncMock(return_value=1)

        adapter = PrefectTaskAdapter(
            connection_string="postgresql://localhost/test",
            prefect_api_url="http://prefect:4200",
        )
        adapter._pool = pool

        result = await adapter.health()

        assert result["healthy"] is True
        assert result["prefect_enabled"] is True
        assert result["prefect_api_url"] == "http://prefect:4200"

    async def test_health_failure(self, mock_asyncpg_module):
        """health() returns unhealthy on DB error."""
        pool, conn = mock_asyncpg_module
        conn.fetchval = AsyncMock(side_effect=Exception("Connection failed"))

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool

        result = await adapter.health()

        assert result["healthy"] is False
        assert "error" in result


@pytest.mark.asyncio
class TestPrefectTaskAdapterClose:
    """Tests for connection cleanup."""

    async def test_close_pool(self, mock_asyncpg_module):
        """close() closes the connection pool."""
        pool, conn = mock_asyncpg_module
        pool.close = AsyncMock()

        adapter = PrefectTaskAdapter(connection_string="postgresql://localhost/test")
        adapter._pool = pool
        adapter._initialized = True

        await adapter.close()

        pool.close.assert_called_once()
        assert adapter._pool is None
        assert adapter._initialized is False


class TestTasksFactory:
    """Tests for task registry factory with Prefect provider."""

    def test_factory_creates_prefect_provider(self):
        """Factory creates PrefectTaskAdapter for 'prefect' provider."""
        from adapters.tasks.factory import create_task_registry_provider

        provider = create_task_registry_provider(
            provider="prefect",
            connection_string="postgresql://localhost/test",
        )

        assert isinstance(provider, PrefectTaskAdapter)

    def test_factory_passes_prefect_config(self):
        """Factory passes Prefect configuration to adapter."""
        from adapters.tasks.factory import create_task_registry_provider

        provider = create_task_registry_provider(
            provider="prefect",
            connection_string="postgresql://localhost/test",
            prefect_api_url="http://prefect:4200",
            prefect_api_key="test-key",
        )

        assert provider._prefect_api_url == "http://prefect:4200"
        assert provider._prefect_api_key == "test-key"

    def test_factory_requires_connection_string(self):
        """Factory raises ValueError if connection_string missing for Prefect."""
        from adapters.tasks.factory import create_task_registry_provider

        with pytest.raises(ValueError, match="connection_string is required"):
            create_task_registry_provider(provider="prefect")
