"""Unit tests for capability handler base classes.

Tests CapabilityHandler ABC, HandlerResult, HandlerEvidence.
Part of SIP-0.8.8 Phase 5.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.agents.base import PortsBundle
from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.context import ExecutionContext


class TestHandlerEvidence:
    """Tests for HandlerEvidence dataclass."""

    def test_create_evidence(self):
        """Should create evidence with all fields."""
        evidence = HandlerEvidence.create(
            handler_name="test_handler",
            capability_id="test.capability",
            duration_ms=100.5,
            inputs_hash="abc123",
            outputs_hash="def456",
            metadata={"key": "value"},
        )

        assert evidence.handler_name == "test_handler"
        assert evidence.capability_id == "test.capability"
        assert evidence.duration_ms == 100.5
        assert evidence.inputs_hash == "abc123"
        assert evidence.outputs_hash == "def456"
        assert evidence.metadata["key"] == "value"
        assert isinstance(evidence.executed_at, datetime)

    def test_evidence_is_frozen(self):
        """Evidence should be immutable."""
        evidence = HandlerEvidence.create(
            handler_name="test",
            capability_id="test",
            duration_ms=0,
        )

        with pytest.raises(AttributeError):
            evidence.handler_name = "changed"


class TestHandlerResult:
    """Tests for HandlerResult dataclass."""

    def test_create_success_result(self):
        """Should create successful result."""
        evidence = HandlerEvidence.create(
            handler_name="test",
            capability_id="test",
            duration_ms=0,
        )
        result = HandlerResult(
            success=True,
            outputs={"key": "value"},
            _evidence=evidence,
        )

        assert result.success is True
        assert result.outputs["key"] == "value"
        assert result.error is None
        assert result.evidence == evidence

    def test_create_failure_result(self):
        """Should create failed result with error."""
        evidence = HandlerEvidence.create(
            handler_name="test",
            capability_id="test",
            duration_ms=0,
        )
        result = HandlerResult(
            success=False,
            outputs={},
            _evidence=evidence,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.outputs == {}

    def test_result_with_artifacts(self):
        """Should include artifacts in result."""
        evidence = HandlerEvidence.create(
            handler_name="test",
            capability_id="test",
            duration_ms=0,
        )
        result = HandlerResult(
            success=True,
            outputs={},
            _evidence=evidence,
            artifacts={"code_file": "/path/to/file.py"},
        )

        assert result.artifacts["code_file"] == "/path/to/file.py"

    def test_evidence_property(self):
        """evidence property should return _evidence."""
        evidence = HandlerEvidence.create(
            handler_name="test",
            capability_id="test",
            duration_ms=0,
        )
        result = HandlerResult(
            success=True,
            outputs={},
            _evidence=evidence,
        )

        assert result.evidence is evidence


class TestExecutionContext:
    """Tests for ExecutionContext."""

    @pytest.fixture
    def mock_ports(self):
        """Create mock ports."""
        llm = MagicMock()
        llm.chat = AsyncMock()

        return PortsBundle(
            llm=llm,
            memory=MagicMock(),
            prompt_service=MagicMock(),
            queue=MagicMock(),
            metrics=MagicMock(),
            events=MagicMock(),
            filesystem=MagicMock(),
        )

    def test_create_context(self, mock_ports):
        """Should create context with all fields."""
        context = ExecutionContext.create(
            agent_id="agent-1",
            role_id="lead",
            task_id="task-1",
            cycle_id="cycle-1",
            ports=mock_ports,
        )

        assert context.agent_id == "agent-1"
        assert context.role_id == "lead"
        assert context.task_id == "task-1"
        assert context.cycle_id == "cycle-1"
        assert context.ports is mock_ports

    def test_create_context_defaults(self):
        """project_id and correlation_context should default to empty."""
        context = ExecutionContext.create(
            agent_id="agent-1",
            role_id="lead",
            task_id="task-1",
            cycle_id="cycle-1",
            ports=MagicMock(),
        )

        assert context.project_id == ""
        assert context.correlation_context is None
