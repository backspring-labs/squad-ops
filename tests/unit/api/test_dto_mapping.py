"""Unit tests for API DTO mapping.

Tests the SIP-0.8.8 API boundary mapping between
Pydantic DTOs and internal frozen dataclasses.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from squadops.api.mapping import (
    dto_to_envelope,
    envelope_to_response,
    response_to_dict,
    result_dto_to_dict,
    result_to_dto,
)
from squadops.api.schemas import (
    TaskRequestDTO,
    TaskResponseDTO,
    TaskResultDTO,
    TaskStatusDTO,
)
from squadops.tasks.models import TaskEnvelope, TaskResult


class TestTaskRequestDTO:
    """Tests for TaskRequestDTO validation."""

    def test_valid_request_minimal(self):
        """Valid request with minimal fields."""
        dto = TaskRequestDTO(
            task_type="analyze",
            source_agent="test-agent",
        )

        assert dto.task_type == "analyze"
        assert dto.source_agent == "test-agent"
        assert dto.target_agent is None
        assert dto.inputs == {}
        assert dto.priority == 5
        assert dto.timeout is None
        assert dto.metadata == {}

    def test_valid_request_full(self):
        """Valid request with all fields."""
        dto = TaskRequestDTO(
            task_type="code_generate",
            source_agent="lead-001",
            target_agent="dev-001",
            inputs={"description": "Generate unit tests"},
            priority=8,
            timeout=30.0,
            metadata={"pid": "PID-001"},
            task_name="Generate Tests",
        )

        assert dto.task_type == "code_generate"
        assert dto.target_agent == "dev-001"
        assert dto.inputs == {"description": "Generate unit tests"}
        assert dto.priority == 8
        assert dto.timeout == 30.0
        assert dto.metadata == {"pid": "PID-001"}
        assert dto.task_name == "Generate Tests"

    def test_missing_required_task_type(self):
        """Missing task_type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TaskRequestDTO(source_agent="test-agent")

        assert "task_type" in str(exc_info.value)

    def test_missing_required_source_agent(self):
        """Missing source_agent raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TaskRequestDTO(task_type="analyze")

        assert "source_agent" in str(exc_info.value)

    def test_priority_validation(self):
        """Priority must be between 1 and 10."""
        # Valid boundaries
        dto_min = TaskRequestDTO(task_type="t", source_agent="a", priority=1)
        assert dto_min.priority == 1

        dto_max = TaskRequestDTO(task_type="t", source_agent="a", priority=10)
        assert dto_max.priority == 10

        # Invalid: too low
        with pytest.raises(ValidationError):
            TaskRequestDTO(task_type="t", source_agent="a", priority=0)

        # Invalid: too high
        with pytest.raises(ValidationError):
            TaskRequestDTO(task_type="t", source_agent="a", priority=11)

    def test_timeout_validation(self):
        """Timeout must be non-negative."""
        dto_zero = TaskRequestDTO(task_type="t", source_agent="a", timeout=0)
        assert dto_zero.timeout == 0

        dto_positive = TaskRequestDTO(task_type="t", source_agent="a", timeout=30.0)
        assert dto_positive.timeout == 30.0

        with pytest.raises(ValidationError):
            TaskRequestDTO(task_type="t", source_agent="a", timeout=-1.0)

    def test_extra_fields_forbidden(self):
        """Extra fields are rejected."""
        with pytest.raises(ValidationError):
            TaskRequestDTO(
                task_type="analyze",
                source_agent="test-agent",
                unknown_field="value",
            )


class TestDtoToEnvelope:
    """Tests for dto_to_envelope mapping function."""

    def test_basic_mapping(self):
        """DTO maps to TaskEnvelope with generated IDs."""
        dto = TaskRequestDTO(
            task_type="analyze",
            source_agent="test-agent",
            inputs={"key": "value"},
        )

        envelope = dto_to_envelope(dto)

        assert envelope.task_type == "analyze"
        assert envelope.agent_id == "test-agent"
        assert envelope.inputs == {"key": "value"}
        assert envelope.task_id.startswith("task-")
        assert envelope.cycle_id.startswith("cycle-")
        assert envelope.pulse_id.startswith("pulse-")
        assert envelope.project_id.startswith("project-")
        assert envelope.correlation_id.startswith("corr-")
        assert envelope.causation_id.startswith("cause-")
        assert "trace-placeholder" in envelope.trace_id
        assert "span-placeholder" in envelope.span_id

    def test_explicit_ids(self):
        """Explicit IDs are used when provided."""
        dto = TaskRequestDTO(
            task_type="analyze",
            source_agent="test-agent",
        )

        envelope = dto_to_envelope(
            dto,
            task_id="explicit-task-id",
            agent_id="explicit-agent-id",
            cycle_id="explicit-cycle-id",
            pulse_id="explicit-pulse-id",
            project_id="explicit-project-id",
            correlation_id="explicit-corr-id",
            causation_id="explicit-cause-id",
            trace_id="explicit-trace-id",
            span_id="explicit-span-id",
        )

        assert envelope.task_id == "explicit-task-id"
        assert envelope.agent_id == "explicit-agent-id"
        assert envelope.cycle_id == "explicit-cycle-id"
        assert envelope.pulse_id == "explicit-pulse-id"
        assert envelope.project_id == "explicit-project-id"
        assert envelope.correlation_id == "explicit-corr-id"
        assert envelope.causation_id == "explicit-cause-id"
        assert envelope.trace_id == "explicit-trace-id"
        assert envelope.span_id == "explicit-span-id"

    def test_priority_conversion(self):
        """Priority int is converted to string."""
        dto = TaskRequestDTO(
            task_type="analyze",
            source_agent="test-agent",
            priority=8,
        )

        envelope = dto_to_envelope(dto)
        assert envelope.priority == "8"

    def test_optional_fields_mapped(self):
        """Optional fields are correctly mapped."""
        dto = TaskRequestDTO(
            task_type="analyze",
            source_agent="test-agent",
            timeout=30.0,
            metadata={"key": "value"},
            task_name="Test Task",
        )

        envelope = dto_to_envelope(dto)
        assert envelope.timeout == 30.0
        assert envelope.metadata == {"key": "value"}
        assert envelope.task_name == "Test Task"

    def test_returns_frozen_dataclass(self):
        """Result is a frozen TaskEnvelope."""
        dto = TaskRequestDTO(task_type="t", source_agent="a")
        envelope = dto_to_envelope(dto)

        assert isinstance(envelope, TaskEnvelope)

        # Verify frozen (immutable)
        from dataclasses import FrozenInstanceError

        with pytest.raises(FrozenInstanceError):
            envelope.task_id = "modified"


class TestEnvelopeToResponse:
    """Tests for envelope_to_response mapping function."""

    def test_basic_mapping(self):
        """Envelope maps to response DTO."""
        envelope = TaskEnvelope(
            task_id="task-001",
            agent_id="agent-001",
            cycle_id="cycle-001",
            pulse_id="pulse-001",
            project_id="project-001",
            task_type="analyze",
            correlation_id="corr-001",
            causation_id="cause-001",
            trace_id="trace-001",
            span_id="span-001",
        )

        response = envelope_to_response(envelope)

        assert response.task_id == "task-001"
        assert response.task_type == "analyze"
        assert response.status == "accepted"
        assert response.created_at is not None

    def test_explicit_timestamp(self):
        """Explicit timestamp is used when provided."""
        envelope = TaskEnvelope(
            task_id="task-001",
            agent_id="agent-001",
            cycle_id="cycle-001",
            pulse_id="pulse-001",
            project_id="project-001",
            task_type="analyze",
            correlation_id="corr-001",
            causation_id="cause-001",
            trace_id="trace-001",
            span_id="span-001",
        )

        explicit_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        response = envelope_to_response(envelope, created_at=explicit_time)

        assert response.created_at == explicit_time

    def test_returns_pydantic_dto(self):
        """Result is a Pydantic DTO."""
        envelope = TaskEnvelope(
            task_id="task-001",
            agent_id="agent-001",
            cycle_id="cycle-001",
            pulse_id="pulse-001",
            project_id="project-001",
            task_type="analyze",
            correlation_id="corr-001",
            causation_id="cause-001",
            trace_id="trace-001",
            span_id="span-001",
        )

        response = envelope_to_response(envelope)
        assert isinstance(response, TaskResponseDTO)


class TestResultToDto:
    """Tests for result_to_dto mapping function."""

    def test_succeeded_result(self):
        """Succeeded result maps correctly."""
        result = TaskResult(
            task_id="task-001",
            status="SUCCEEDED",
            outputs={"result": "ok", "data": 42},
        )

        dto = result_to_dto(result)

        assert dto.task_id == "task-001"
        assert dto.status == "SUCCEEDED"
        assert dto.outputs == {"result": "ok", "data": 42}
        assert dto.error is None

    def test_failed_result(self):
        """Failed result maps correctly."""
        result = TaskResult(
            task_id="task-001",
            status="FAILED",
            error="Task failed: timeout",
        )

        dto = result_to_dto(result)

        assert dto.task_id == "task-001"
        assert dto.status == "FAILED"
        assert dto.outputs is None
        assert dto.error == "Task failed: timeout"

    def test_returns_pydantic_dto(self):
        """Result is a Pydantic DTO."""
        result = TaskResult(task_id="task-001", status="SUCCEEDED")
        dto = result_to_dto(result)
        assert isinstance(dto, TaskResultDTO)


class TestResponseSerialization:
    """Tests for response serialization to dict."""

    def test_response_to_dict(self):
        """Response DTO serializes to dict."""
        response = TaskResponseDTO(
            task_id="task-001",
            task_type="analyze",
            status="accepted",
            created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
        )

        result = response_to_dict(response)

        assert isinstance(result, dict)
        assert result["task_id"] == "task-001"
        assert result["task_type"] == "analyze"
        assert result["status"] == "accepted"
        assert "created_at" in result

    def test_result_dto_to_dict_excludes_none(self):
        """Result DTO serializes to dict excluding None values."""
        dto = TaskResultDTO(
            task_id="task-001",
            status="SUCCEEDED",
            outputs={"value": 42},
        )

        result = result_dto_to_dict(dto)

        assert "task_id" in result
        assert "status" in result
        assert "outputs" in result
        assert "error" not in result  # None values excluded


class TestTaskStatusDTO:
    """Tests for TaskStatusDTO."""

    def test_create_status_dto(self):
        """TaskStatusDTO can be created with execution evidence."""
        dto = TaskStatusDTO(
            task_id="task-001",
            status="completed",
            task_type="analyze",
            execution_mode="real",
            execution_evidence={"implementation": "real", "evidence_level": "real"},
            mock_components=[],
        )

        assert dto.task_id == "task-001"
        assert dto.status == "completed"
        assert dto.execution_mode == "real"
        assert dto.execution_evidence["implementation"] == "real"
        assert dto.mock_components == []

    def test_mock_components_tracked(self):
        """Mock components are tracked in status."""
        dto = TaskStatusDTO(
            task_id="task-001",
            status="completed",
            execution_mode="mock",
            mock_components=["skill:llm_query", "skill:file_write"],
        )

        assert dto.execution_mode == "mock"
        assert len(dto.mock_components) == 2
        assert "skill:llm_query" in dto.mock_components


class TestRoundTrip:
    """Tests for DTO ↔ dataclass round-trip."""

    def test_request_to_envelope_to_response(self):
        """Full round-trip: DTO → Envelope → Response."""
        # 1. API request comes in as DTO
        request = TaskRequestDTO(
            task_type="code_generate",
            source_agent="lead-001",
            target_agent="dev-001",
            inputs={"description": "Generate tests"},
            priority=7,
        )

        # 2. Map to internal envelope
        envelope = dto_to_envelope(request, task_id="task-roundtrip-001")

        # 3. Map to API response
        response = envelope_to_response(envelope)

        # Verify data preserved through round-trip
        assert response.task_id == "task-roundtrip-001"
        assert response.task_type == "code_generate"
        assert response.status == "accepted"
