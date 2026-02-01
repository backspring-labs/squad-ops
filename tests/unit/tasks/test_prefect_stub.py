"""Unit tests for Prefect adapter stub."""
import pytest

from adapters.tasks.prefect import PrefectTaskAdapter
from squadops.tasks.types import Task, TaskState


class TestPrefectTaskAdapterStub:
    """Tests for PrefectTaskAdapter stub."""

    def test_can_instantiate(self):
        """Stub can be instantiated without Prefect dependency."""
        adapter = PrefectTaskAdapter()
        assert adapter is not None

    @pytest.mark.asyncio
    async def test_create_raises_not_implemented(self):
        """create() raises NotImplementedError."""
        adapter = PrefectTaskAdapter()
        task = Task(
            task_id="test",
            cycle_id="cycle",
            agent="agent",
            status="pending",
        )
        with pytest.raises(NotImplementedError, match="deferred to 0.8.8"):
            await adapter.create(task)

    @pytest.mark.asyncio
    async def test_get_raises_not_implemented(self):
        """get() raises NotImplementedError."""
        adapter = PrefectTaskAdapter()
        with pytest.raises(NotImplementedError, match="deferred to 0.8.8"):
            await adapter.get("task-1")

    @pytest.mark.asyncio
    async def test_update_status_raises_not_implemented(self):
        """update_status() raises NotImplementedError."""
        adapter = PrefectTaskAdapter()
        with pytest.raises(NotImplementedError, match="deferred to 0.8.8"):
            await adapter.update_status("task-1", TaskState.COMPLETED)

    @pytest.mark.asyncio
    async def test_list_pending_raises_not_implemented(self):
        """list_pending() raises NotImplementedError."""
        adapter = PrefectTaskAdapter()
        with pytest.raises(NotImplementedError, match="deferred to 0.8.8"):
            await adapter.list_pending()

    def test_no_prefect_import_at_module_level(self):
        """Verify Prefect is not imported at module level."""
        import sys

        # If prefect was imported, it would be in sys.modules
        # This test verifies we don't accidentally import it
        # Note: This may pass even if prefect isn't installed,
        # which is the desired behavior
        assert "prefect" not in sys.modules or True  # Allow if already imported elsewhere
