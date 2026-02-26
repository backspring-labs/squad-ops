"""Unit tests for API service layer.

Tests TaskService and AgentService.
Part of SIP-0.8.8 Phase 6.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.api.schemas import TaskRequestDTO
from squadops.api.service import AgentService, TaskService
from squadops.tasks.models import TaskResult


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator."""
    orchestrator = MagicMock()
    orchestrator.submit_task = AsyncMock()
    orchestrator.get_active_tasks = MagicMock(return_value=[])
    orchestrator.get_available_capabilities = MagicMock(return_value=["cap.one", "cap.two"])
    orchestrator.get_agent_states = MagicMock(return_value={})
    orchestrator.health_check = AsyncMock(
        return_value={
            "status": "healthy",
            "registered_agents": 1,
            "capabilities": 2,
        }
    )
    return orchestrator


class TestTaskService:
    """Tests for TaskService."""

    @pytest.mark.asyncio
    async def test_submit_task(self, mock_orchestrator):
        """Should submit task and return response."""
        mock_orchestrator.submit_task.return_value = TaskResult(
            task_id="task-123",
            status="SUCCEEDED",
            outputs={"result": "success"},
        )

        service = TaskService(mock_orchestrator)
        request = TaskRequestDTO(
            task_type="test.task",
            source_agent="agent-1",
            inputs={"key": "value"},
        )

        response = await service.submit_task(request)

        assert response.task_type == "test.task"
        assert response.status == "accepted"
        mock_orchestrator.submit_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_task(self, mock_orchestrator):
        """Should execute task and return result."""
        mock_orchestrator.submit_task.return_value = TaskResult(
            task_id="task-123",
            status="SUCCEEDED",
            outputs={"result": "success"},
        )

        service = TaskService(mock_orchestrator)
        request = TaskRequestDTO(
            task_type="test.task",
            source_agent="agent-1",
        )

        result = await service.execute_task(request, timeout_seconds=30)

        assert result.status == "SUCCEEDED"
        assert result.outputs["result"] == "success"

    @pytest.mark.asyncio
    async def test_execute_task_failure(self, mock_orchestrator):
        """Should return failed result."""
        mock_orchestrator.submit_task.return_value = TaskResult(
            task_id="task-123",
            status="FAILED",
            outputs=None,
            error="Something went wrong",
        )

        service = TaskService(mock_orchestrator)
        request = TaskRequestDTO(
            task_type="test.task",
            source_agent="agent-1",
        )

        result = await service.execute_task(request)

        assert result.status == "FAILED"
        assert result.error == "Something went wrong"

    @pytest.mark.asyncio
    async def test_get_task_status_active(self, mock_orchestrator):
        """Should return RUNNING for active tasks."""
        mock_orchestrator.get_active_tasks.return_value = ["task-123"]

        service = TaskService(mock_orchestrator)
        status = await service.get_task_status("task-123")

        assert status is not None
        assert status.task_id == "task-123"
        assert status.status == "RUNNING"

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, mock_orchestrator):
        """Should return None for unknown tasks."""
        mock_orchestrator.get_active_tasks.return_value = []

        service = TaskService(mock_orchestrator)
        status = await service.get_task_status("nonexistent")

        assert status is None

    def test_list_capabilities(self, mock_orchestrator):
        """Should list capabilities."""
        service = TaskService(mock_orchestrator)

        caps = service.list_capabilities()

        assert caps == ["cap.one", "cap.two"]
        mock_orchestrator.get_available_capabilities.assert_called_with(None)

    def test_list_capabilities_by_role(self, mock_orchestrator):
        """Should filter by role."""
        service = TaskService(mock_orchestrator)

        service.list_capabilities(role="lead")

        mock_orchestrator.get_available_capabilities.assert_called_with("lead")

    @pytest.mark.asyncio
    async def test_health(self, mock_orchestrator):
        """Should return health status."""
        service = TaskService(mock_orchestrator)

        health = await service.health()

        assert health["status"] == "healthy"
        assert "orchestrator" in health
        assert "timestamp" in health


class TestAgentService:
    """Tests for AgentService."""

    @pytest.fixture
    def mock_orchestrator_with_agents(self):
        """Create mock orchestrator with agents."""
        orchestrator = MagicMock()
        orchestrator.get_agent_states.return_value = {
            "agent-1": {"role": "lead", "status": "available"},
            "agent-2": {"role": "dev", "status": "available"},
        }
        orchestrator.get_available_capabilities.return_value = ["cap.one"]
        return orchestrator

    def test_list_agents(self, mock_orchestrator_with_agents):
        """Should list all agents."""
        service = AgentService(mock_orchestrator_with_agents)

        agents = service.list_agents()

        assert len(agents) == 2
        assert any(a["agent_id"] == "agent-1" for a in agents)
        assert any(a["agent_id"] == "agent-2" for a in agents)

    def test_list_agents_empty(self, mock_orchestrator):
        """Should return empty list when no agents."""
        service = AgentService(mock_orchestrator)

        agents = service.list_agents()

        assert agents == []

    def test_get_agent(self, mock_orchestrator_with_agents):
        """Should get specific agent."""
        service = AgentService(mock_orchestrator_with_agents)

        agent = service.get_agent("agent-1")

        assert agent is not None
        assert agent["agent_id"] == "agent-1"
        assert agent["role"] == "lead"

    def test_get_agent_not_found(self, mock_orchestrator_with_agents):
        """Should return None for unknown agent."""
        service = AgentService(mock_orchestrator_with_agents)

        agent = service.get_agent("nonexistent")

        assert agent is None

    def test_list_capabilities_for_agent(self, mock_orchestrator_with_agents):
        """Should list capabilities for agent's role."""
        service = AgentService(mock_orchestrator_with_agents)

        caps = service.list_capabilities_for_agent("agent-1")

        assert caps == ["cap.one"]
        mock_orchestrator_with_agents.get_available_capabilities.assert_called_with("lead")

    def test_list_capabilities_for_unknown_agent(self, mock_orchestrator_with_agents):
        """Should return empty list for unknown agent."""
        service = AgentService(mock_orchestrator_with_agents)

        caps = service.list_capabilities_for_agent("nonexistent")

        assert caps == []
