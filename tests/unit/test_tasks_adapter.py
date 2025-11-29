#!/usr/bin/env python3
"""
Unit tests for Tasks Adapter Framework
Tests adapter interface, SQL adapter, and registry
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

from agents.tasks.base_adapter import TaskAdapterBase
from agents.tasks.errors import (
    TaskAdapterError,
    TaskConflictError,
    TaskNotFoundError,
)
from agents.tasks.models import (
    Artifact,
    FlowState,
    Task,
    TaskCreate,
    TaskFilters,
    TaskState,
    TaskSummary,
)
from agents.tasks.registry import clear_test_adapter, get_tasks_adapter, set_adapter_for_testing
from agents.tasks.sql_adapter import SqlTasksAdapter


class TestTaskAdapterBase:
    """Test base adapter interface conformance"""
    
    @pytest.mark.unit
    def test_base_adapter_is_abstract(self):
        """Test that TaskAdapterBase cannot be instantiated directly"""
        with pytest.raises(TypeError):
            TaskAdapterBase()


class TestSqlTasksAdapter:
    """Test SQL adapter implementation"""
    
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
        """Create SQL adapter with mocked pool"""
        pool, _ = mock_db_pool
        return SqlTasksAdapter(pool)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_task(self, adapter, mock_db_pool):
        """Test task creation"""
        pool, conn = mock_db_pool
        
        # Mock the get_task call after creation
        mock_row = MagicMock()
        mock_row.get.side_effect = lambda k, d=None: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "priority": "MEDIUM",
            "description": "Test task",
            "dependencies": [],
            "artifacts": None,
            "start_time": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        }.get(k, d)
        mock_row.__getitem__ = lambda self, k: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "priority": "MEDIUM",
            "description": "Test task",
            "dependencies": [],
            "artifacts": None,
            "start_time": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        }[k]
        
        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_row)
        
        task_create = TaskCreate(
            task_id="test-001",
            ecid="ecid-001",
            agent="test-agent",
            status="started",
            priority="MEDIUM",
            description="Test task",
        )
        
        task = await adapter.create_task(task_create)
        
        assert task.task_id == "test-001"
        assert task.ecid == "ecid-001"
        assert task.agent == "test-agent"
        conn.execute.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_task(self, adapter, mock_db_pool):
        """Test getting a task by ID"""
        pool, conn = mock_db_pool
        
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "priority": "MEDIUM",
            "description": "Test task",
            "dependencies": [],
            "artifacts": None,
            "start_time": None,
            "end_time": None,
            "duration": None,
            "error_log": None,
            "delegated_by": None,
            "delegated_to": None,
            "created_at": None,
            "pid": None,
            "phase": None,
        }[k]
        mock_row.get = lambda k, d=None: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "priority": "MEDIUM",
            "description": "Test task",
            "dependencies": [],
            "artifacts": None,
            "start_time": None,
            "end_time": None,
            "duration": None,
            "error_log": None,
            "delegated_by": None,
            "delegated_to": None,
            "created_at": None,
            "pid": None,
            "phase": None,
        }.get(k, d)
        
        conn.fetchrow = AsyncMock(return_value=mock_row)
        
        task = await adapter.get_task("test-001")
        
        assert task is not None
        assert task.task_id == "test-001"
        conn.fetchrow.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_tasks(self, adapter, mock_db_pool):
        """Test listing tasks with filters"""
        pool, conn = mock_db_pool
        
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "dependencies": [],
            "artifacts": None,
        }[k]
        mock_row.get = lambda k, d=None: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "dependencies": [],
            "artifacts": None,
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
            "phase": None,
        }.get(k, d)
        
        conn.fetch = AsyncMock(return_value=[mock_row])
        
        filters = TaskFilters(ecid="ecid-001", agent="test-agent")
        tasks = await adapter.list_tasks(filters)
        
        assert len(tasks) == 1
        assert tasks[0].task_id == "test-001"
        conn.fetch.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_task_state(self, adapter, mock_db_pool):
        """Test updating task state"""
        pool, conn = mock_db_pool
        
        # Mock get_task call
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "completed",
            "dependencies": [],
            "artifacts": None,
        }[k]
        mock_row.get = lambda k, d=None: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "completed",
            "dependencies": [],
            "artifacts": None,
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
            "phase": None,
        }.get(k, d)
        
        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_row)
        
        task = await adapter.update_task_state("test-001", TaskState.COMPLETED)
        
        assert task.status == "completed"
        conn.execute.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_tasks_for_ecid(self, adapter, mock_db_pool):
        """Test listing tasks for an execution cycle"""
        pool, conn = mock_db_pool
        
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "dependencies": [],
            "artifacts": None,
        }[k]
        mock_row.get = lambda k, d=None: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "dependencies": [],
            "artifacts": None,
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
            "phase": None,
        }.get(k, d)
        
        conn.fetch = AsyncMock(return_value=[mock_row])
        
        tasks = await adapter.list_tasks_for_ecid("ecid-001")
        
        assert len(tasks) == 1
        assert tasks[0].ecid == "ecid-001"
        conn.fetch.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_flow(self, adapter, mock_db_pool):
        """Test creating an execution cycle"""
        pool, conn = mock_db_pool
        
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "ecid": "ecid-001",
            "pid": "pid-001",
            "run_type": "warmboot",
            "title": "Test Flow",
            "status": "active",
        }[k]
        mock_row.get = lambda k, d=None: {
            "ecid": "ecid-001",
            "pid": "pid-001",
            "run_type": "warmboot",
            "title": "Test Flow",
            "status": "active",
            "description": None,
            "created_at": None,
            "initiated_by": None,
            "notes": None,
        }.get(k, d)
        
        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_row)
        
        flow = await adapter.create_flow(
            "ecid-001",
            "pid-001",
            meta={
                "run_type": "warmboot",
                "title": "Test Flow",
                "initiated_by": "test-agent",
            }
        )
        
        assert flow.ecid == "ecid-001"
        assert flow.pid == "pid-001"
        conn.execute.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_task_status(self, adapter, mock_db_pool):
        """Test getting task status"""
        pool, conn = mock_db_pool
        
        mock_row = {
            "task_id": "test-001",
            "agent_name": "test-agent",
            "status": "in_progress",
            "progress": 50.0,
            "eta": "5 minutes",
            "updated_at": datetime.utcnow(),
        }
        
        conn.fetchrow = AsyncMock(return_value=mock_row)
        
        status = await adapter.get_task_status("test-001")
        
        assert status is not None
        assert status["task_id"] == "test-001"
        assert status["status"] == "in_progress"
        conn.fetchrow.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_task_status(self, adapter, mock_db_pool):
        """Test updating task status"""
        pool, conn = mock_db_pool
        
        mock_status = {
            "task_id": "test-001",
            "agent_name": "test-agent",
            "status": "completed",
            "progress": 100.0,
            "eta": None,
            "updated_at": datetime.utcnow(),
        }
        
        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_status)
        
        result = await adapter.update_task_status(
            "test-001",
            "completed",
            100.0,
            None,
            "test-agent"
        )
        
        assert result["status"] == "completed"
        conn.execute.assert_called_once()


class TestTasksAdapterRegistry:
    """Test adapter registry"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_tasks_adapter_default_sql(self):
        """Test registry returns SQL adapter by default"""
        with patch('agents.tasks.registry.asyncpg.create_pool') as mock_pool, \
             patch('agents.tasks.registry.get_config') as mock_config:
            
            mock_config_instance = MagicMock()
            mock_config_instance.get_postgres_url.return_value = "postgresql://test:test@localhost/test"
            mock_config.return_value = mock_config_instance
            
            # Create a proper mock pool with async context manager
            mock_pool_instance = AsyncMock()
            mock_conn = AsyncMock()
            class MockConnectionContext:
                def __init__(self, conn):
                    self.conn = conn
                
                async def __aenter__(self):
                    return self.conn
                
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            
            mock_pool_instance.acquire = MagicMock(return_value=MockConnectionContext(mock_conn))
            # asyncpg.create_pool is async, so we need to make the mock awaitable
            async def create_pool_mock(*args, **kwargs):
                return mock_pool_instance
            mock_pool.side_effect = create_pool_mock
            
            # Clear any existing adapter
            import agents.tasks.registry as registry_module
            registry_module._adapter = None
            
            adapter = await get_tasks_adapter()
            
            assert isinstance(adapter, SqlTasksAdapter)
            mock_pool.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_tasks_adapter_test_injection(self):
        """Test registry supports test adapter injection"""
        mock_adapter = MagicMock(spec=TaskAdapterBase)
        
        set_adapter_for_testing(mock_adapter)
        
        try:
            adapter = await get_tasks_adapter()
            assert adapter is mock_adapter
        finally:
            clear_test_adapter()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_tasks_adapter_prefect_not_implemented(self):
        """Test registry raises error for unimplemented Prefect backend"""
        # Clear any existing adapter
        import agents.tasks.registry as registry_module
        registry_module._adapter = None
        
        with patch.dict('os.environ', {'TASKS_BACKEND': 'prefect'}):
            # Prefect adapter exists but raises NotImplementedError when used
            adapter = await get_tasks_adapter()
            # Verify it's a Prefect adapter
            from agents.tasks.prefect_adapter import PrefectTasksAdapter
            assert isinstance(adapter, PrefectTasksAdapter)
            # Verify it raises NotImplementedError when methods are called
            with pytest.raises(NotImplementedError):
                await adapter.create_task(TaskCreate(
                    task_id="test", ecid="ecid", agent="agent", status="started"
                ))


class TestTasksModels:
    """Test task models and DTOs"""
    
    @pytest.mark.unit
    def test_task_create_model(self):
        """Test TaskCreate model"""
        task_create = TaskCreate(
            task_id="test-001",
            ecid="ecid-001",
            agent="test-agent",
            status="started",
            priority="HIGH",
            description="Test task",
            dependencies=["dep-001"],
        )
        
        assert task_create.task_id == "test-001"
        assert task_create.ecid == "ecid-001"
        assert task_create.agent == "test-agent"
        assert task_create.status == "started"
        assert task_create.priority == "HIGH"
        assert task_create.dependencies == ["dep-001"]
    
    @pytest.mark.unit
    def test_task_filters_model(self):
        """Test TaskFilters model"""
        filters = TaskFilters(
            ecid="ecid-001",
            agent="test-agent",
            status="started",
            limit=100
        )
        
        assert filters.ecid == "ecid-001"
        assert filters.agent == "test-agent"
        assert filters.status == "started"
        assert filters.limit == 100
    
    @pytest.mark.unit
    def test_artifact_model(self):
        """Test Artifact model"""
        artifact = Artifact(
            type="code",
            path="/path/to/file.py",
            metadata={"lines": 100},
        )
        
        assert artifact.type == "code"
        assert artifact.path == "/path/to/file.py"
        assert artifact.metadata == {"lines": 100}
    
    @pytest.mark.unit
    def test_task_state_enum(self):
        """Test TaskState enum"""
        assert TaskState.STARTED == "started"
        assert TaskState.COMPLETED == "completed"
        assert TaskState.FAILED == "failed"
    
    @pytest.mark.unit
    def test_flow_state_enum(self):
        """Test FlowState enum"""
        assert FlowState.ACTIVE == "active"
        assert FlowState.COMPLETED == "completed"
        assert FlowState.FAILED == "failed"
    
    @pytest.mark.unit
    def test_tasksummary_model(self):
        """Test TaskSummary model"""
        summary = TaskSummary(
            total_tasks=10,
            completed=5,
            in_progress=3,
            delegated=1,
            failed=1,
            avg_duration="00:05:00",
        )
        
        assert summary.total_tasks == 10
        assert summary.completed == 5
        assert summary.in_progress == 3
        assert summary.delegated == 1
        assert summary.failed == 1
        assert summary.avg_duration == "00:05:00"


class TestErrorWrapping:
    """Test error wrapping in SQL adapter"""
    
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
        """Create SQL adapter with mocked pool"""
        pool, _ = mock_db_pool
        return SqlTasksAdapter(pool)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_unique_violation_wraps_to_conflict_error(self, adapter, mock_db_pool):
        """Test that UniqueViolationError is wrapped to TaskConflictError"""
        pool, conn = mock_db_pool
        
        conn.execute = AsyncMock(side_effect=asyncpg.exceptions.UniqueViolationError("duplicate key"))
        
        task_create = TaskCreate(
            task_id="test-001",
            ecid="ecid-001",
            agent="test-agent",
            status="started",
        )
        
        with pytest.raises(TaskConflictError) as exc_info:
            await adapter.create_task(task_create)
        
        assert "already exists" in str(exc_info.value)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_postgres_error_wraps_to_adapter_error(self, adapter, mock_db_pool):
        """Test that PostgresError is wrapped to TaskAdapterError"""
        pool, conn = mock_db_pool
        
        conn.fetchrow = AsyncMock(side_effect=asyncpg.exceptions.PostgresError("connection failed"))
        
        with pytest.raises(TaskAdapterError) as exc_info:
            await adapter.get_task("test-001")
        
        assert "Database error" in str(exc_info.value)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_not_found_raises_not_found_error(self, adapter, mock_db_pool):
        """Test that missing tasks raise TaskNotFoundError"""
        pool, conn = mock_db_pool
        
        conn.execute = AsyncMock(return_value="UPDATE 0")
        conn.fetchrow = AsyncMock(return_value=None)
        
        with pytest.raises(TaskNotFoundError) as exc_info:
            await adapter.update_task_state("test-001", TaskState.COMPLETED)
        
        assert "not found" in str(exc_info.value)


class TestLifecycleHooks:
    """Test adapter lifecycle hooks"""
    
    @pytest.fixture
    def mock_db_pool(self):
        """Create mock database pool"""
        pool = AsyncMock()
        pool.close = AsyncMock()
        
        # Create a proper async context manager for pool.acquire()
        conn = AsyncMock()
        class MockConnectionContext:
            def __init__(self, conn):
                self.conn = conn
            
            async def __aenter__(self):
                return self.conn
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        pool.acquire = MagicMock(return_value=MockConnectionContext(conn))
        
        return pool
    
    @pytest.fixture
    def adapter(self, mock_db_pool):
        """Create SQL adapter with mocked pool"""
        pool = mock_db_pool
        return SqlTasksAdapter(pool)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initialize_is_noop(self, adapter):
        """Test that initialize() is a no-op for SQL adapter"""
        # Should not raise
        await adapter.initialize()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_shutdown_closes_pool(self, adapter, mock_db_pool):
        """Test that shutdown() closes the connection pool"""
        await adapter.shutdown()
        mock_db_pool.close.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_shutdown_handles_errors(self, adapter, mock_db_pool):
        """Test that shutdown() wraps pool close errors"""
        mock_db_pool.close = AsyncMock(side_effect=Exception("Close failed"))
        
        with pytest.raises(TaskAdapterError) as exc_info:
            await adapter.shutdown()
        
        assert "Failed to close connection pool" in str(exc_info.value)


class TestDTOPurity:
    """Test that adapters return DTOs only, not dicts"""
    
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
        """Create SQL adapter with mocked pool"""
        pool, _ = mock_db_pool
        return SqlTasksAdapter(pool)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_task_returns_dto(self, adapter, mock_db_pool):
        """Test that get_task returns Task DTO, not dict"""
        pool, conn = mock_db_pool
        
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "dependencies": [],
            "artifacts": None,
        }[k]
        mock_row.get = lambda k, d=None: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "dependencies": [],
            "artifacts": None,
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
            "phase": None,
        }.get(k, d)
        
        conn.fetchrow = AsyncMock(return_value=mock_row)
        
        result = await adapter.get_task("test-001")
        
        assert isinstance(result, Task)
        assert not isinstance(result, dict)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_tasks_returns_dto_list(self, adapter, mock_db_pool):
        """Test that list_tasks returns list of Task DTOs, not dicts"""
        pool, conn = mock_db_pool
        
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "dependencies": [],
            "artifacts": None,
        }[k]
        mock_row.get = lambda k, d=None: {
            "task_id": "test-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "dependencies": [],
            "artifacts": None,
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
            "phase": None,
        }.get(k, d)
        
        conn.fetch = AsyncMock(return_value=[mock_row])
        
        filters = TaskFilters(ecid="ecid-001")
        results = await adapter.list_tasks(filters)
        
        assert len(results) == 1
        assert isinstance(results[0], Task)
        assert not isinstance(results[0], dict)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_task_summary_returns_dto(self, adapter, mock_db_pool):
        """Test that get_task_summary returns TaskSummary DTO, not dict"""
        pool, conn = mock_db_pool
        
        mock_row = {
            "total_tasks": 10,
            "completed": 5,
            "in_progress": 3,
            "delegated": 1,
            "failed": 1,
            "avg_duration": None,
        }
        
        conn.fetchrow = AsyncMock(return_value=mock_row)
        
        result = await adapter.get_task_summary("ecid-001")
        
        assert isinstance(result, TaskSummary)
        assert not isinstance(result, dict)
        assert result.total_tasks == 10
        assert result.completed == 5
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_task_summary_no_tasks(self, adapter, mock_db_pool):
        """Test get_task_summary when no tasks exist"""
        pool, conn = mock_db_pool
        
        conn.fetchrow = AsyncMock(return_value=None)
        
        result = await adapter.get_task_summary("ecid-001")
        
        assert isinstance(result, TaskSummary)
        assert result.total_tasks == 0
        assert result.completed == 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_flow(self, adapter, mock_db_pool):
        """Test getting an execution cycle by ECID"""
        pool, conn = mock_db_pool
        
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "ecid": "ecid-001",
            "pid": "pid-001",
            "run_type": "warmboot",
            "title": "Test Flow",
            "status": "active",
        }.get(k)
        mock_row.get = lambda k, d=None: {
            "ecid": "ecid-001",
            "pid": "pid-001",
            "run_type": "warmboot",
            "title": "Test Flow",
            "status": "active",
            "description": None,
            "created_at": None,
            "initiated_by": None,
            "notes": None,
        }.get(k, d)
        
        conn.fetchrow = AsyncMock(return_value=mock_row)
        
        flow = await adapter.get_flow("ecid-001")
        
        assert flow is not None
        assert flow.ecid == "ecid-001"
        assert flow.pid == "pid-001"
        conn.fetchrow.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_flow_not_found(self, adapter, mock_db_pool):
        """Test getting flow that doesn't exist"""
        pool, conn = mock_db_pool
        
        conn.fetchrow = AsyncMock(return_value=None)
        
        flow = await adapter.get_flow("non-existent")
        
        assert flow is None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_flows(self, adapter, mock_db_pool):
        """Test listing execution cycles"""
        pool, conn = mock_db_pool
        
        mock_row1 = MagicMock()
        mock_row1.__getitem__ = lambda self, k: {
            "ecid": "ecid-001",
            "pid": "pid-001",
            "run_type": "warmboot",
            "title": "Flow 1",
            "status": "active",
        }.get(k)
        mock_row1.get = lambda k, d=None: {
            "ecid": "ecid-001",
            "pid": "pid-001",
            "run_type": "warmboot",
            "title": "Flow 1",
            "status": "active",
            "description": None,
            "created_at": None,
            "initiated_by": None,
            "notes": None,
        }.get(k, d)
        
        mock_row2 = MagicMock()
        mock_row2.__getitem__ = lambda self, k: {
            "ecid": "ecid-002",
            "pid": "pid-002",
            "run_type": "standard",
            "title": "Flow 2",
            "status": "completed",
        }.get(k)
        mock_row2.get = lambda k, d=None: {
            "ecid": "ecid-002",
            "pid": "pid-002",
            "run_type": "standard",
            "title": "Flow 2",
            "status": "completed",
            "description": None,
            "created_at": None,
            "initiated_by": None,
            "notes": None,
        }.get(k, d)
        
        conn.fetch = AsyncMock(return_value=[mock_row1, mock_row2])
        
        flows = await adapter.list_flows()
        
        assert len(flows) == 2
        assert flows[0].ecid == "ecid-001"
        assert flows[1].ecid == "ecid-002"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_flows_with_run_type(self, adapter, mock_db_pool):
        """Test listing execution cycles filtered by run_type"""
        pool, conn = mock_db_pool
        
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "ecid": "ecid-001",
            "pid": "pid-001",
            "run_type": "warmboot",
            "title": "WarmBoot Flow",
            "status": "active",
        }.get(k)
        mock_row.get = lambda k, d=None: {
            "ecid": "ecid-001",
            "pid": "pid-001",
            "run_type": "warmboot",
            "title": "WarmBoot Flow",
            "status": "active",
            "description": None,
            "created_at": None,
            "initiated_by": None,
            "notes": None,
        }.get(k, d)
        
        conn.fetch = AsyncMock(return_value=[mock_row])
        
        flows = await adapter.list_flows(run_type="warmboot")
        
        assert len(flows) == 1
        assert flows[0].run_type == "warmboot"
        # Verify query included run_type filter
        call_args = conn.fetch.call_args[0]
        assert "run_type" in call_args[0] or "warmboot" in str(call_args)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_flows_empty(self, adapter, mock_db_pool):
        """Test listing flows when none exist"""
        pool, conn = mock_db_pool
        
        conn.fetch = AsyncMock(return_value=[])
        
        flows = await adapter.list_flows()
        
        assert len(flows) == 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_add_artifact(self, adapter, mock_db_pool):
        """Test adding artifact to a task"""
        pool, conn = mock_db_pool
        
        # Mock get_task to return existing task
        mock_task_row = MagicMock()
        mock_task_row.__getitem__ = lambda self, k: {
            "task_id": "task-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "artifacts": None,
        }.get(k)
        mock_task_row.get = lambda k, d=None: {
            "task_id": "task-001",
            "ecid": "ecid-001",
            "agent": "test-agent",
            "status": "started",
            "artifacts": None,
            "priority": None,
            "description": None,
            "start_time": None,
            "end_time": None,
            "duration": None,
            "dependencies": [],
        }.get(k, d)
        
        conn.fetchrow = AsyncMock(return_value=mock_task_row)
        conn.execute = AsyncMock()
        
        artifact = Artifact(
            type="file",
            path="/path/to/file",
            description="Test artifact"
        )
        
        await adapter.add_artifact("task-001", artifact)
        
        conn.execute.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_add_artifact_task_not_found(self, adapter, mock_db_pool):
        """Test adding artifact to non-existent task"""
        pool, conn = mock_db_pool
        
        conn.fetchrow = AsyncMock(return_value=None)
        
        artifact = Artifact(
            type="file",
            path="/path/to/file",
            description="Test artifact"
        )
        
        with pytest.raises(TaskNotFoundError):
            await adapter.add_artifact("non-existent", artifact)

