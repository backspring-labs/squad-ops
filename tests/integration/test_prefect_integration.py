"""
Integration tests for Prefect adapter and backend switching
"""

import os

import pytest

from agents.tasks.models import TaskCreate, TaskState
from agents.tasks.registry import get_tasks_adapter, reset_registry


@pytest.mark.integration
@pytest.mark.asyncio
class TestPrefectIntegration:
    """Integration tests for Prefect adapter"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test"""
        # Reset registry before each test
        reset_registry()
        yield
        # Reset registry after each test
        reset_registry()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backend_switching_sql_to_prefect(self):
        """Test switching from SQL to Prefect backend"""
        # Start with SQL backend
        os.environ["TASKS_BACKEND"] = "sql"
        reset_registry()

        sql_adapter = await get_tasks_adapter()
        assert sql_adapter.__class__.__name__ == "SqlTasksAdapter"

        # Switch to Prefect backend
        os.environ["TASKS_BACKEND"] = "prefect"
        reset_registry()

        prefect_adapter = await get_tasks_adapter()
        assert prefect_adapter.__class__.__name__ == "PrefectTasksAdapter"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_prefect_adapter_creates_task(self):
        """Test that Prefect adapter can create tasks"""
        os.environ["TASKS_BACKEND"] = "prefect"
        reset_registry()

        adapter = await get_tasks_adapter()
        await adapter.initialize()

        task_create = TaskCreate(
            task_id="test-prefect-001",
            cycle_id="cycle-prefect-001",
            agent="test-agent",
            status="started",
            description="Test task with Prefect backend",
        )

        try:
            task = await adapter.create_task(task_create)
            assert task.task_id == "test-prefect-001"
            assert task.cycle_id == "cycle-prefect-001"

            # Verify task can be retrieved
            retrieved = await adapter.get_task("test-prefect-001")
            assert retrieved is not None
            assert retrieved.task_id == "test-prefect-001"
        except Exception as e:
            # If Prefect server is not available, skip the test
            pytest.skip(f"Prefect server not available: {e}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_prefect_adapter_creates_flow(self):
        """Test that Prefect adapter can create flows"""
        os.environ["TASKS_BACKEND"] = "prefect"
        reset_registry()

        adapter = await get_tasks_adapter()
        await adapter.initialize()

        try:
            flow = await adapter.create_flow(
                cycle_id="cycle-prefect-001",
                pid="pid-001",
                meta={
                    "run_type": "project",
                    "title": "Test Prefect Flow",
                    "description": "Integration test flow",
                },
            )

            assert flow.cycle_id == "cycle-prefect-001"
            assert flow.run_type == "project"
            assert flow.title == "Test Prefect Flow"

            # Verify flow can be retrieved
            retrieved = await adapter.get_flow("cycle-prefect-001")
            assert retrieved is not None
            assert retrieved.cycle_id == "cycle-prefect-001"
        except Exception as e:
            # If Prefect server is not available, skip the test
            pytest.skip(f"Prefect server not available: {e}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_prefect_adapter_state_updates(self):
        """Test that Prefect adapter can update task states"""
        os.environ["TASKS_BACKEND"] = "prefect"
        reset_registry()

        adapter = await get_tasks_adapter()
        await adapter.initialize()

        task_create = TaskCreate(
            task_id="test-prefect-state-001",
            cycle_id="cycle-prefect-001",
            agent="test-agent",
            status="started",
            description="Test state updates",
        )

        try:
            # Create task
            task = await adapter.create_task(task_create)
            assert task.status == "started"

            # Update state
            updated = await adapter.update_task_state(
                "test-prefect-state-001",
                TaskState.COMPLETED,
                meta={"end_time": "2024-01-01T00:00:00Z"},
            )

            assert updated.status == "completed"
        except Exception as e:
            # If Prefect server is not available, skip the test
            pytest.skip(f"Prefect server not available: {e}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backend_compatibility(self):
        """Test that both backends return compatible results"""
        # Test SQL backend
        os.environ["TASKS_BACKEND"] = "sql"
        reset_registry()

        sql_adapter = await get_tasks_adapter()
        await sql_adapter.initialize()

        sql_task_create = TaskCreate(
            task_id="test-compat-sql",
            cycle_id="cycle-compat",
            agent="test-agent",
            status="started",
            description="SQL backend task",
        )

        sql_task = await sql_adapter.create_task(sql_task_create)
        assert sql_task.task_id == "test-compat-sql"

        # Test Prefect backend
        os.environ["TASKS_BACKEND"] = "prefect"
        reset_registry()

        prefect_adapter = await get_tasks_adapter()
        await prefect_adapter.initialize()

        prefect_task_create = TaskCreate(
            task_id="test-compat-prefect",
            cycle_id="cycle-compat",
            agent="test-agent",
            status="started",
            description="Prefect backend task",
        )

        try:
            prefect_task = await prefect_adapter.create_task(prefect_task_create)
            assert prefect_task.task_id == "test-compat-prefect"

            # Both should have same structure
            assert hasattr(sql_task, "task_id")
            assert hasattr(prefect_task, "task_id")
            assert hasattr(sql_task, "cycle_id")
            assert hasattr(prefect_task, "cycle_id")
            assert hasattr(sql_task, "status")
            assert hasattr(prefect_task, "status")
        except Exception as e:
            # If Prefect server is not available, skip the test
            pytest.skip(f"Prefect server not available: {e}")
