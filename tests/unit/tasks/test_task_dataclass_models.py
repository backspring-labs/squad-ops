"""Unit tests for frozen dataclass task models.

Tests the SIP-0.8.8 migration of TaskEnvelope and TaskResult
from Pydantic BaseModel to frozen dataclasses.
"""
import pytest
from dataclasses import FrozenInstanceError

from squadops.tasks.models import TaskEnvelope, TaskIdentity, TaskResult


class TestTaskIdentity:
    """Tests for TaskIdentity frozen dataclass."""

    def test_create_with_required_fields(self):
        """TaskIdentity can be created with required fields."""
        identity = TaskIdentity(
            task_id="task-001",
            task_type="code_generate",
            source_agent="agent-001",
        )

        assert identity.task_id == "task-001"
        assert identity.task_type == "code_generate"
        assert identity.source_agent == "agent-001"
        assert identity.target_agent is None
        assert identity.correlation_id is None

    def test_create_with_all_fields(self):
        """TaskIdentity can be created with all fields."""
        identity = TaskIdentity(
            task_id="task-001",
            task_type="code_generate",
            source_agent="agent-001",
            target_agent="agent-002",
            correlation_id="corr-001",
            causation_id="cause-001",
            trace_id="trace-001",
        )

        assert identity.target_agent == "agent-002"
        assert identity.correlation_id == "corr-001"
        assert identity.causation_id == "cause-001"
        assert identity.trace_id == "trace-001"

    def test_is_frozen(self):
        """TaskIdentity is immutable (frozen)."""
        identity = TaskIdentity(
            task_id="task-001",
            task_type="code_generate",
            source_agent="agent-001",
        )

        with pytest.raises(FrozenInstanceError):
            identity.task_id = "task-modified"


class TestTaskEnvelope:
    """Tests for TaskEnvelope frozen dataclass."""

    @pytest.fixture
    def valid_envelope_fields(self):
        """Return valid fields for creating a TaskEnvelope."""
        return {
            "task_id": "task-001",
            "agent_id": "agent-001",
            "cycle_id": "CYCLE-001",
            "pulse_id": "pulse-001",
            "project_id": "project-001",
            "task_type": "code_generate",
            "correlation_id": "corr-CYCLE-001",
            "causation_id": "cause-root",
            "trace_id": "trace-placeholder-task-001",
            "span_id": "span-placeholder-task-001",
        }

    def test_create_with_required_fields(self, valid_envelope_fields):
        """TaskEnvelope can be created with required fields."""
        envelope = TaskEnvelope(**valid_envelope_fields)

        assert envelope.task_id == "task-001"
        assert envelope.agent_id == "agent-001"
        assert envelope.cycle_id == "CYCLE-001"
        assert envelope.pulse_id == "pulse-001"
        assert envelope.project_id == "project-001"
        assert envelope.task_type == "code_generate"
        assert envelope.correlation_id == "corr-CYCLE-001"
        assert envelope.causation_id == "cause-root"
        assert envelope.trace_id == "trace-placeholder-task-001"
        assert envelope.span_id == "span-placeholder-task-001"

    def test_inputs_defaults_to_empty_dict(self, valid_envelope_fields):
        """inputs field defaults to empty dict."""
        envelope = TaskEnvelope(**valid_envelope_fields)
        assert envelope.inputs == {}

    def test_inputs_with_values(self, valid_envelope_fields):
        """inputs field can contain values."""
        envelope = TaskEnvelope(
            **valid_envelope_fields,
            inputs={"action": "build", "target": "app"},
        )
        assert envelope.inputs == {"action": "build", "target": "app"}

    def test_optional_fields_default_to_none(self, valid_envelope_fields):
        """Optional fields default to None."""
        envelope = TaskEnvelope(**valid_envelope_fields)

        assert envelope.priority is None
        assert envelope.timeout is None
        assert envelope.task_name is None

    def test_metadata_defaults_to_empty_dict(self, valid_envelope_fields):
        """metadata field defaults to empty dict."""
        envelope = TaskEnvelope(**valid_envelope_fields)
        assert envelope.metadata == {}

    def test_optional_fields_with_values(self, valid_envelope_fields):
        """Optional fields can be provided."""
        envelope = TaskEnvelope(
            **valid_envelope_fields,
            priority="HIGH",
            timeout=30.0,
            metadata={"pid": "PID-001"},
            task_name="Build application",
        )

        assert envelope.priority == "HIGH"
        assert envelope.timeout == 30.0
        assert envelope.metadata == {"pid": "PID-001"}
        assert envelope.task_name == "Build application"

    def test_is_frozen(self, valid_envelope_fields):
        """TaskEnvelope is immutable (frozen)."""
        envelope = TaskEnvelope(**valid_envelope_fields)

        with pytest.raises(FrozenInstanceError):
            envelope.task_id = "task-modified"

        with pytest.raises(FrozenInstanceError):
            envelope.correlation_id = "new-correlation"

    def test_missing_required_field_raises_error(self, valid_envelope_fields):
        """Missing required fields raise TypeError."""
        # Remove required field
        del valid_envelope_fields["task_id"]

        with pytest.raises(TypeError):
            TaskEnvelope(**valid_envelope_fields)

    def test_placeholders_allowed_for_lineage_fields(self, valid_envelope_fields):
        """Placeholder values are allowed for trace_id and span_id."""
        envelope = TaskEnvelope(
            **valid_envelope_fields,
        )

        assert envelope.trace_id == "trace-placeholder-task-001"
        assert envelope.span_id == "span-placeholder-task-001"
        assert isinstance(envelope.trace_id, str)
        assert isinstance(envelope.span_id, str)


class TestTaskResult:
    """Tests for TaskResult frozen dataclass."""

    def test_create_succeeded_result(self):
        """TaskResult can represent succeeded status with outputs."""
        result = TaskResult(
            task_id="task-001",
            status="SUCCEEDED",
            outputs={"result": "ok", "data": {"value": 42}},
        )

        assert result.task_id == "task-001"
        assert result.status == "SUCCEEDED"
        assert result.outputs == {"result": "ok", "data": {"value": 42}}
        assert result.error is None

    def test_create_failed_result(self):
        """TaskResult can represent failed status with error."""
        result = TaskResult(
            task_id="task-001",
            status="FAILED",
            error="Task execution failed: timeout",
        )

        assert result.task_id == "task-001"
        assert result.status == "FAILED"
        assert result.error == "Task execution failed: timeout"
        assert result.outputs is None

    def test_create_canceled_result(self):
        """TaskResult can represent canceled status with error."""
        result = TaskResult(
            task_id="task-001",
            status="CANCELED",
            error="Task was canceled by user",
        )

        assert result.task_id == "task-001"
        assert result.status == "CANCELED"
        assert result.error == "Task was canceled by user"
        assert result.outputs is None

    def test_is_frozen(self):
        """TaskResult is immutable (frozen)."""
        result = TaskResult(
            task_id="task-001",
            status="SUCCEEDED",
            outputs={"result": "ok"},
        )

        with pytest.raises(FrozenInstanceError):
            result.task_id = "task-modified"

        with pytest.raises(FrozenInstanceError):
            result.status = "FAILED"

    def test_outputs_defaults_to_none(self):
        """outputs field defaults to None."""
        result = TaskResult(
            task_id="task-001",
            status="FAILED",
        )
        assert result.outputs is None

    def test_error_defaults_to_none(self):
        """error field defaults to None."""
        result = TaskResult(
            task_id="task-001",
            status="SUCCEEDED",
        )
        assert result.error is None

    def test_missing_required_field_raises_error(self):
        """Missing required fields raise TypeError."""
        with pytest.raises(TypeError):
            TaskResult(status="SUCCEEDED")  # Missing task_id


class TestTaskModelsImport:
    """Tests for importing task models from various locations."""

    def test_import_from_models(self):
        """Models can be imported from squadops.tasks.models."""
        from squadops.tasks.models import TaskEnvelope, TaskIdentity, TaskResult

        assert TaskEnvelope is not None
        assert TaskIdentity is not None
        assert TaskResult is not None

    def test_import_from_tasks_package(self):
        """Models can be imported from squadops.tasks package."""
        from squadops.tasks import TaskEnvelope, TaskIdentity, TaskResult

        assert TaskEnvelope is not None
        assert TaskIdentity is not None
        assert TaskResult is not None

    def test_import_from_types_bridge(self):
        """Models can be imported from squadops.tasks.types bridge."""
        from squadops.tasks.types import TaskEnvelope, TaskIdentity, TaskResult

        assert TaskEnvelope is not None
        assert TaskIdentity is not None
        assert TaskResult is not None

    def test_legacy_models_available_from_bridge(self):
        """Legacy Pydantic models available via types bridge."""
        from squadops.tasks.types import (
            LegacyTaskEnvelope,
            LegacyTaskResult,
            Task,
            TaskState,
        )

        assert LegacyTaskEnvelope is not None
        assert LegacyTaskResult is not None
        assert Task is not None
        assert TaskState is not None
