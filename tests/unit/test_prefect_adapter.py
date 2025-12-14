"""
Unit tests for PrefectTasksAdapter
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.tasks.models import (
    Artifact,
    FlowRun,
    Task,
    TaskCreate,
    TaskFilters,
    TaskState,
)
from agents.tasks.prefect_adapter import PrefectTasksAdapter


class TestPrefectTasksAdapter:
    """Test Prefect adapter implementation"""

    @pytest.fixture
    def mock_db_pool(self):
        """Create mock database pool"""
        pool = AsyncMock()
        conn = AsyncMock()

        # Create a proper async context manager for pool.acquire()
        class MockConnectionContext:
            def __init__(self, conn):
                self.conn = conn

            async def __aenter__(self):
                return self.conn

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        pool.acquire = MagicMock(return_value=MockConnectionContext(conn))
        return pool, conn

    @pytest.fixture
    def adapter(self, mock_db_pool):
        """Create Prefect adapter with mocked pool"""
        pool, _ = mock_db_pool
        return PrefectTasksAdapter(pool)

    @pytest.fixture
    def mock_task_row(self):
        """Create mock task row"""
        row = MagicMock()
        row.get.side_effect = lambda k, d=None: {
            "task_id": "test-001",
            "cycle_id": "cycle-001",
            "agent": "test-agent",
            "agent_id": "test-agent",
            "task_name": "test-task",
            "status": "started",
            "priority": "MEDIUM",
            "description": "Test task",
            "dependencies": [],
            "artifacts": None,
            "metrics": '{"prefect_task_run_id": "prefect-001"}',
            "start_time": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        }.get(k, d)
        row.__getitem__ = lambda self, k: {
            "task_id": "test-001",
            "cycle_id": "cycle-001",
            "agent": "test-agent",
            "agent_id": "test-agent",
            "task_name": "test-task",
            "status": "started",
            "priority": "MEDIUM",
            "description": "Test task",
            "dependencies": [],
            "artifacts": None,
            "metrics": '{"prefect_task_run_id": "prefect-001"}',
            "start_time": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        }[k]
        return row

    @pytest.fixture
    def mock_flow_row(self):
        """Create mock flow row"""
        row = MagicMock()
        row.get.side_effect = lambda k, d=None: {
            "cycle_id": "cycle-001",
            "pid": "pid-001",
            "project_id": "test-project",
            "run_type": "project",
            "title": "Test Cycle",
            "description": "Test description",
            "name": "Test Cycle",
            "goal": "Test goal",
            "start_time": datetime.utcnow(),
            "inputs": '{"prefect_flow_run_id": "prefect-flow-001"}',
            "created_at": datetime.utcnow(),
            "initiated_by": "test-user",
            "status": "active",
        }.get(k, d)
        row.__getitem__ = lambda self, k: {
            "cycle_id": "cycle-001",
            "pid": "pid-001",
            "project_id": "test-project",
            "run_type": "project",
            "title": "Test Cycle",
            "description": "Test description",
            "name": "Test Cycle",
            "goal": "Test goal",
            "start_time": datetime.utcnow(),
            "inputs": '{"prefect_flow_run_id": "prefect-flow-001"}',
            "created_at": datetime.utcnow(),
            "initiated_by": "test-user",
            "status": "active",
        }[k]
        return row

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initialize(self, adapter):
        """Test adapter initialization"""
        with patch("agents.tasks.prefect_adapter.get_config") as mock_config:
            mock_config.return_value.get_prefect_api_url.return_value = "http://prefect:4200/api"
            mock_config.return_value.get_prefect_api_key.return_value = None

            await adapter.initialize()
            assert adapter._initialized is True
            assert adapter._prefect_api_url == "http://prefect:4200/api"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_task(self, adapter, mock_db_pool, mock_task_row):
        """Test task creation"""
        pool, conn = mock_db_pool

        # Mock database operations
        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_task_row)

        task_create = TaskCreate(
            task_id="test-001",
            cycle_id="cycle-001",
            agent="test-agent",
            task_type="code_generate",  # ACI v0.8: required field
            inputs={},  # ACI v0.8: required field
            status="started",
            description="Test task",
        )

        from agents.tasks.models import FlowRun
        
        with (
            patch.object(
                adapter,
                "get_task",
                return_value=Task(
                    task_id="test-001",
                    cycle_id="cycle-001",
                    agent="test-agent",
                    status="started",
                    description="Test task",
                ),
            ),
            patch.object(
                adapter,
                "get_flow",
                return_value=FlowRun(
                    cycle_id="cycle-001",
                    pid="p-001",
                    run_type="warmboot",
                    title="Test Cycle",
                    status="active",
                ),
            ),
        ):
            result = await adapter.create_task(task_create)
            assert result.task_id == "test-001"
            assert result.cycle_id == "cycle-001"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_task(self, adapter, mock_db_pool, mock_task_row):
        """Test getting a task"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=mock_task_row)

        result = await adapter.get_task("test-001")
        assert result is not None
        assert result.task_id == "test-001"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_task_not_found(self, adapter, mock_db_pool):
        """Test getting a non-existent task"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=None)

        result = await adapter.get_task("nonexistent")
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_tasks(self, adapter, mock_db_pool, mock_task_row):
        """Test listing tasks"""
        pool, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[mock_task_row])

        filters = TaskFilters(cycle_id="cycle-001")
        results = await adapter.list_tasks(filters)
        assert len(results) == 1
        assert results[0].task_id == "test-001"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_task_state(self, adapter, mock_db_pool, mock_task_row):
        """Test updating task state"""
        pool, conn = mock_db_pool
        conn.execute = AsyncMock(return_value="UPDATE 1")
        conn.fetchrow = AsyncMock(return_value=mock_task_row)

        with patch.object(
            adapter,
            "get_task",
            return_value=Task(
                task_id="test-001",
                cycle_id="cycle-001",
                agent="test-agent",
                status="completed",
                metrics={"prefect_task_run_id": "prefect-001"},
            ),
        ):
            result = await adapter.update_task_state("test-001", TaskState.COMPLETED)
            assert result.status == "completed"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_add_artifact(self, adapter, mock_db_pool, mock_task_row):
        """Test adding an artifact"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=mock_task_row)
        conn.execute = AsyncMock()

        artifact = Artifact(
            type="code",
            path="/path/to/file.py",
            metadata={"language": "python"},
        )

        with patch.object(
            adapter,
            "get_task",
            return_value=Task(
                task_id="test-001",
                cycle_id="cycle-001",
                agent="test-agent",
                status="started",
            ),
        ):
            await adapter.add_artifact("test-001", artifact)
            # Should not raise

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_flow(self, adapter, mock_db_pool, mock_flow_row):
        """Test creating a flow"""
        pool, conn = mock_db_pool
        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_flow_row)

        with patch.object(
            adapter,
            "get_flow",
            return_value=FlowRun(
                cycle_id="cycle-001",
                pid="pid-001",
                run_type="project",
                title="Test Cycle",
            ),
        ):
            result = await adapter.create_flow(
                "cycle-001",
                "pid-001",
                {
                    "run_type": "project",
                    "title": "Test Cycle",
                },
            )
            assert result.cycle_id == "cycle-001"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_flow(self, adapter, mock_db_pool, mock_flow_row):
        """Test getting a flow"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=mock_flow_row)

        result = await adapter.get_flow("cycle-001")
        assert result is not None
        assert result.cycle_id == "cycle-001"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_task_summary(self, adapter, mock_db_pool):
        """Test getting task summary"""
        pool, conn = mock_db_pool

        mock_summary_row = MagicMock()
        mock_summary_row.get.side_effect = lambda k, d=None: {
            "total_tasks": 10,
            "completed": 8,
            "in_progress": 1,
            "delegated": 0,
            "failed": 1,
            "avg_duration": None,
        }.get(k, d)

        conn.fetchrow = AsyncMock(return_value=mock_summary_row)

        result = await adapter.get_task_summary("cycle-001")
        assert result.total_tasks == 10
        assert result.completed == 8
        assert result.failed == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_state_mapping(self):
        """Test state mapping between SquadOps and Prefect"""
        from agents.tasks.prefect_adapter import (
            PREFECT_TO_SQUADOPS_STATE,
            SQUADOPS_TO_PREFECT_STATE,
        )

        # Test SquadOps to Prefect mapping
        assert SQUADOPS_TO_PREFECT_STATE[TaskState.PENDING] == "PENDING"
        assert SQUADOPS_TO_PREFECT_STATE[TaskState.COMPLETED] == "COMPLETED"
        assert SQUADOPS_TO_PREFECT_STATE[TaskState.FAILED] == "FAILED"

        # Test Prefect to SquadOps mapping
        assert PREFECT_TO_SQUADOPS_STATE["PENDING"] == TaskState.PENDING
        assert PREFECT_TO_SQUADOPS_STATE["COMPLETED"] == TaskState.COMPLETED
        assert PREFECT_TO_SQUADOPS_STATE["FAILED"] == TaskState.FAILED

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_shutdown(self, adapter):
        """Test adapter shutdown"""
        pool = AsyncMock()
        pool.close = AsyncMock()
        adapter.db_pool = pool

        await adapter.shutdown()
        pool.close.assert_called_once()
