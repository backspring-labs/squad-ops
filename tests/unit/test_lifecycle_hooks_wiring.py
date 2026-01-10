#!/usr/bin/env python3
"""
Unit tests for LifecycleHookManager hook invocation plumbing
Tests ACI v0.8 lifecycle hooks are callable and receive full lineage context
"""

from unittest.mock import patch

import pytest

from agents.base_agent import BaseAgent, LifecycleHookManager
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse


class ConcreteTestAgent(BaseAgent):
    """Concrete test agent for testing lifecycle hooks"""

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
class TestLifecycleHooksWiring:
    """Test LifecycleHookManager hook invocation plumbing using spies/mocks"""

    def test_lifecycle_hooks_callable(self):
        """Test all lifecycle hooks are callable methods"""
        hooks = LifecycleHookManager()

        # All hooks should be callable
        assert callable(hooks.on_agent_start)
        assert callable(hooks.on_agent_stop)
        assert callable(hooks.on_cycle_start)
        assert callable(hooks.on_cycle_end)
        assert callable(hooks.on_pulse_start)
        assert callable(hooks.on_pulse_end)
        assert callable(hooks.on_task_created)
        assert callable(hooks.on_task_start)
        assert callable(hooks.on_task_complete)
        assert callable(hooks.on_task_failed)
        assert callable(hooks.on_failure)
        assert callable(hooks.on_exception)

    @pytest.mark.asyncio
    async def test_on_task_created_hook_invoked(self, mock_unified_config, sample_task_envelope):
        """Test on_task_created hook is called during process_task"""
        with patch("infra.config.loader.load_config", return_value=mock_unified_config):
            agent = ConcreteTestAgent(name="test-agent", agent_type="test", reasoning_style="test")

        # Spy on on_task_created
        original_hook = agent._lifecycle_hooks.on_task_created
        call_count = 0
        call_context = None

        async def spy_hook(context):
            nonlocal call_count, call_context
            call_count += 1
            call_context = context
            await original_hook(context)

        agent._lifecycle_hooks.on_task_created = spy_hook

        await agent.process_task(sample_task_envelope)

        assert call_count == 1
        assert call_context is not None
        assert call_context["task_id"] == sample_task_envelope.task_id
        assert call_context["correlation_id"] == sample_task_envelope.correlation_id
        assert call_context["causation_id"] == sample_task_envelope.causation_id
        assert call_context["trace_id"] == sample_task_envelope.trace_id
        assert call_context["span_id"] == sample_task_envelope.span_id

    @pytest.mark.asyncio
    async def test_on_task_start_hook_invoked(self, mock_unified_config, sample_task_envelope):
        """Test on_task_start hook is called after on_task_created"""
        with patch("infra.config.loader.load_config", return_value=mock_unified_config):
            agent = ConcreteTestAgent(name="test-agent", agent_type="test", reasoning_style="test")

        # Spy on hooks to track order
        hook_calls = []

        original_created = agent._lifecycle_hooks.on_task_created
        original_start = agent._lifecycle_hooks.on_task_start

        async def spy_created(context):
            hook_calls.append(("on_task_created", context))
            await original_created(context)

        async def spy_start(context):
            hook_calls.append(("on_task_start", context))
            await original_start(context)

        agent._lifecycle_hooks.on_task_created = spy_created
        agent._lifecycle_hooks.on_task_start = spy_start

        await agent.process_task(sample_task_envelope)

        # Verify both hooks called
        hook_names = [name for name, _ in hook_calls]
        assert "on_task_created" in hook_names
        assert "on_task_start" in hook_names

        # Verify on_task_start called after on_task_created
        created_idx = hook_names.index("on_task_created")
        start_idx = hook_names.index("on_task_start")
        assert start_idx > created_idx

    @pytest.mark.asyncio
    async def test_on_task_complete_hook_invoked_on_success(self, mock_unified_config, sample_task_envelope):
        """Test on_task_complete hook is called when task succeeds"""
        with patch("infra.config.loader.load_config", return_value=mock_unified_config):
            agent = ConcreteTestAgent(name="test-agent", agent_type="test", reasoning_style="test")

        # Spy on on_task_complete
        call_count = 0
        call_context = None

        original_hook = agent._lifecycle_hooks.on_task_complete

        async def spy_hook(context):
            nonlocal call_count, call_context
            call_count += 1
            call_context = context
            await original_hook(context)

        agent._lifecycle_hooks.on_task_complete = spy_hook

        await agent.process_task(sample_task_envelope)

        assert call_count == 1
        assert call_context is not None
        assert call_context["task_id"] == sample_task_envelope.task_id
        assert "error" not in call_context  # No error on success

    @pytest.mark.asyncio
    async def test_on_task_failed_hook_invoked_on_error(self, mock_unified_config, sample_task_envelope):
        """Test on_task_failed and on_exception hooks are called when task fails"""
        with patch("infra.config.loader.load_config", return_value=mock_unified_config):
            agent = ConcreteTestAgent(name="test-agent", agent_type="test", reasoning_style="test")

        # Mock handle_agent_request to raise exception
        async def failing_handler(request):
            raise Exception("Task execution failed")

        agent.handle_agent_request = failing_handler

        # Spy on hooks
        failed_calls = []
        exception_calls = []

        original_failed = agent._lifecycle_hooks.on_task_failed
        original_exception = agent._lifecycle_hooks.on_exception

        async def spy_failed(context):
            failed_calls.append(context)
            await original_failed(context)

        async def spy_exception(context):
            exception_calls.append(context)
            await original_exception(context)

        agent._lifecycle_hooks.on_task_failed = spy_failed
        agent._lifecycle_hooks.on_exception = spy_exception

        await agent.process_task(sample_task_envelope)

        # Verify both hooks called
        assert len(failed_calls) == 1
        assert len(exception_calls) == 1

        # Verify context contains error
        assert "error" in failed_calls[0]
        assert "error" in exception_calls[0]

