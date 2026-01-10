#!/usr/bin/env python3
"""
Unit tests for BaseAgent ACI contract
Tests BaseAgent.process_task() strict contract behavior
"""

from unittest.mock import patch

import pytest

from agents.base_agent import BaseAgent
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse
from agents.tasks.models import TaskEnvelope, TaskResult


class ConcreteTestAgent(BaseAgent):
    """Concrete test agent for testing BaseAgent ACI contract"""

    async def handle_agent_request(self, request: AgentRequest) -> AgentResponse:
        """Mock implementation of handle_agent_request"""
        return AgentResponse.success(
            result={"action": request.action, "status": "completed"},
            idempotency_key=request.generate_idempotency_key(self.name),
        )

    async def handle_message(self, message) -> None:
        """Mock implementation of handle_message"""
        pass


@pytest.mark.unit
class TestBaseAgentACIContract:
    """Test BaseAgent.process_task() strict contract: rejects legacy dict, accepts only TaskEnvelope"""

    @pytest.fixture
    def agent(self, mock_unified_config):
        """Create test agent instance"""
        with patch("infra.config.loader.load_config", return_value=mock_unified_config):
            return ConcreteTestAgent(name="test-agent", agent_type="test", reasoning_style="test")

    @pytest.mark.asyncio
    async def test_process_task_accepts_task_envelope(self, agent, sample_task_envelope):
        """Test process_task accepts TaskEnvelope and returns TaskResult format"""
        result = await agent.process_task(sample_task_envelope)

        assert isinstance(result, dict)
        assert "task_id" in result
        assert "status" in result
        assert result["task_id"] == sample_task_envelope.task_id
        assert result["status"] in ["SUCCEEDED", "FAILED", "CANCELED"]

        # Validate it matches TaskResult model
        task_result = TaskResult(**result)
        assert task_result.task_id == sample_task_envelope.task_id

    @pytest.mark.asyncio
    async def test_process_task_rejects_legacy_dict(self, agent, legacy_task_dict):
        """Test process_task rejects legacy dict format"""
        result = await agent.process_task(legacy_task_dict)

        # Should return FAILED TaskResult (process_task tries to convert dict to TaskEnvelope, which fails validation)
        assert isinstance(result, dict)
        assert "status" in result
        assert result["status"] == "FAILED"
        assert "error" in result
        assert "task_id" in result

    @pytest.mark.asyncio
    async def test_process_task_validates_envelope_structure(self, agent):
        """Test invalid TaskEnvelope causes validation failure"""
        # Create envelope missing required field (correlation_id)
        invalid_envelope_dict = {
            "task_id": "task-001",
            "agent_id": "agent-001",
            "cycle_id": "CYCLE-001",
            "pulse_id": "pulse-001",
            "project_id": "project-001",
            "task_type": "code_generate",
            "inputs": {},
            "causation_id": "cause-root",
            "trace_id": "trace-placeholder-task-001",
            "span_id": "span-placeholder-task-001",
            # Missing correlation_id
        }

        # Try to create TaskEnvelope (will fail validation)
        try:
            invalid_envelope = TaskEnvelope(**invalid_envelope_dict)
            # If it somehow passes, process_task should still validate
            result = await agent.process_task(invalid_envelope)
            assert result["status"] == "FAILED"
            assert "error" in result
        except Exception:
            # Expected: validation should fail
            pass

    @pytest.mark.asyncio
    async def test_process_task_result_shape_succeeded(self, agent, sample_task_envelope):
        """Test successful task returns TaskResult with SUCCEEDED status"""
        result = await agent.process_task(sample_task_envelope)

        assert result["status"] == "SUCCEEDED"
        assert "outputs" in result
        assert result["outputs"] is not None
        assert isinstance(result["outputs"], dict)
        assert result["task_id"] == sample_task_envelope.task_id

    @pytest.mark.asyncio
    async def test_process_task_result_shape_failed(self, agent, sample_task_envelope):
        """Test failed task returns TaskResult with FAILED status"""
        # Mock handle_agent_request to raise exception
        async def failing_handler(request):
            raise Exception("Task execution failed")

        agent.handle_agent_request = failing_handler

        result = await agent.process_task(sample_task_envelope)

        assert result["status"] == "FAILED"
        assert "error" in result
        assert isinstance(result["error"], str)
        assert result["task_id"] == sample_task_envelope.task_id

    @pytest.mark.asyncio
    async def test_process_task_extracts_inputs_from_envelope(self, agent, sample_task_envelope):
        """Test process_task extracts inputs from envelope and passes to AgentRequest"""
        # Spy on handle_agent_request
        original_handler = agent.handle_agent_request
        call_args = []

        async def spy_handler(request):
            call_args.append(request)
            return await original_handler(request)

        agent.handle_agent_request = spy_handler

        await agent.process_task(sample_task_envelope)

        # Verify handle_agent_request was called
        assert len(call_args) > 0
        request = call_args[0]
        assert isinstance(request, AgentRequest)

        # Verify inputs are in payload
        assert request.payload == sample_task_envelope.inputs

        # Verify lineage fields are in metadata
        assert request.metadata["cycle_id"] == sample_task_envelope.cycle_id
        assert request.metadata["pulse_id"] == sample_task_envelope.pulse_id
        assert request.metadata["project_id"] == sample_task_envelope.project_id
        assert request.metadata["correlation_id"] == sample_task_envelope.correlation_id
        assert request.metadata["causation_id"] == sample_task_envelope.causation_id
        assert request.metadata["trace_id"] == sample_task_envelope.trace_id
        assert request.metadata["span_id"] == sample_task_envelope.span_id

