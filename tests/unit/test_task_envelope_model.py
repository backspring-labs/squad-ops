#!/usr/bin/env python3
"""
Unit tests for TaskEnvelope Pydantic model
Tests ACI v0.8 strict contract validation
"""

import pytest
from pydantic import ValidationError

from agents.tasks.models import TaskEnvelope


@pytest.mark.unit
class TestTaskEnvelopeModel:
    """Test TaskEnvelope Pydantic model validation and strict field requirements"""

    def test_task_envelope_happy_path(self):
        """Test TaskEnvelope can be created with all required fields"""
        envelope = TaskEnvelope(
            task_id="task-001",
            agent_id="agent-001",
            cycle_id="CYCLE-001",
            pulse_id="pulse-001",
            project_id="project-001",
            task_type="code_generate",
            inputs={"action": "build"},
            correlation_id="corr-CYCLE-001",
            causation_id="cause-root",
            trace_id="trace-placeholder-task-001",
            span_id="span-placeholder-task-001",
        )

        assert envelope.task_id == "task-001"
        assert envelope.agent_id == "agent-001"
        assert envelope.cycle_id == "CYCLE-001"
        assert envelope.pulse_id == "pulse-001"
        assert envelope.project_id == "project-001"
        assert envelope.task_type == "code_generate"
        assert envelope.inputs == {"action": "build"}
        assert envelope.correlation_id == "corr-CYCLE-001"
        assert envelope.causation_id == "cause-root"
        assert envelope.trace_id == "trace-placeholder-task-001"
        assert envelope.span_id == "span-placeholder-task-001"

    def test_task_envelope_missing_required_identity_fields(self):
        """Test missing required identity fields raise ValidationError"""
        base_fields = {
            "agent_id": "agent-001",
            "cycle_id": "CYCLE-001",
            "pulse_id": "pulse-001",
            "project_id": "project-001",
            "task_type": "code_generate",
            "inputs": {},
            "correlation_id": "corr-CYCLE-001",
            "causation_id": "cause-root",
            "trace_id": "trace-placeholder-task-001",
            "span_id": "span-placeholder-task-001",
        }

        # Test missing task_id
        with pytest.raises(ValidationError) as exc_info:
            TaskEnvelope(**{**base_fields})
        assert "task_id" in str(exc_info.value)

        # Test missing agent_id
        with pytest.raises(ValidationError) as exc_info:
            TaskEnvelope(task_id="task-001", **{k: v for k, v in base_fields.items() if k != "agent_id"})
        assert "agent_id" in str(exc_info.value)

        # Test missing cycle_id
        with pytest.raises(ValidationError) as exc_info:
            TaskEnvelope(task_id="task-001", **{k: v for k, v in base_fields.items() if k != "cycle_id"})
        assert "cycle_id" in str(exc_info.value)

        # Test missing pulse_id
        with pytest.raises(ValidationError) as exc_info:
            TaskEnvelope(task_id="task-001", **{k: v for k, v in base_fields.items() if k != "pulse_id"})
        assert "pulse_id" in str(exc_info.value)

        # Test missing project_id
        with pytest.raises(ValidationError) as exc_info:
            TaskEnvelope(task_id="task-001", **{k: v for k, v in base_fields.items() if k != "project_id"})
        assert "project_id" in str(exc_info.value)

        # Test missing task_type
        with pytest.raises(ValidationError) as exc_info:
            TaskEnvelope(task_id="task-001", **{k: v for k, v in base_fields.items() if k != "task_type"})
        assert "task_type" in str(exc_info.value)

    def test_task_envelope_missing_lineage_fields(self):
        """Test missing lineage fields raise ValidationError"""
        base_fields = {
            "task_id": "task-001",
            "agent_id": "agent-001",
            "cycle_id": "CYCLE-001",
            "pulse_id": "pulse-001",
            "project_id": "project-001",
            "task_type": "code_generate",
            "inputs": {},
        }

        # Test missing correlation_id
        with pytest.raises(ValidationError) as exc_info:
            TaskEnvelope(
                **base_fields,
                causation_id="cause-root",
                trace_id="trace-placeholder-task-001",
                span_id="span-placeholder-task-001",
            )
        assert "correlation_id" in str(exc_info.value)

        # Test missing causation_id
        with pytest.raises(ValidationError) as exc_info:
            TaskEnvelope(
                **base_fields,
                correlation_id="corr-CYCLE-001",
                trace_id="trace-placeholder-task-001",
                span_id="span-placeholder-task-001",
            )
        assert "causation_id" in str(exc_info.value)

        # Test missing trace_id
        with pytest.raises(ValidationError) as exc_info:
            TaskEnvelope(
                **base_fields,
                correlation_id="corr-CYCLE-001",
                causation_id="cause-root",
                span_id="span-placeholder-task-001",
            )
        assert "trace_id" in str(exc_info.value)

        # Test missing span_id
        with pytest.raises(ValidationError) as exc_info:
            TaskEnvelope(
                **base_fields,
                correlation_id="corr-CYCLE-001",
                causation_id="cause-root",
                trace_id="trace-placeholder-task-001",
            )
        assert "span_id" in str(exc_info.value)

    def test_task_envelope_inputs_always_present(self):
        """Test inputs field is always present (defaults to {})"""
        base_fields = {
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

        # Test inputs omitted (should default to {})
        envelope1 = TaskEnvelope(**base_fields)
        assert envelope1.inputs == {}

        # Test inputs as empty dict
        envelope2 = TaskEnvelope(**base_fields, inputs={})
        assert envelope2.inputs == {}

        # Test inputs as non-empty dict
        envelope3 = TaskEnvelope(**base_fields, inputs={"action": "build", "target": "app"})
        assert envelope3.inputs == {"action": "build", "target": "app"}

        # Test inputs cannot be None
        with pytest.raises(ValidationError):
            TaskEnvelope(**base_fields, inputs=None)

    def test_task_envelope_optional_fields(self):
        """Test optional fields can be None or provided"""
        base_fields = {
            "task_id": "task-001",
            "agent_id": "agent-001",
            "cycle_id": "CYCLE-001",
            "pulse_id": "pulse-001",
            "project_id": "project-001",
            "task_type": "code_generate",
            "inputs": {},
            "correlation_id": "corr-CYCLE-001",
            "causation_id": "cause-root",
            "trace_id": "trace-placeholder-task-001",
            "span_id": "span-placeholder-task-001",
        }

        # Test all optional fields omitted
        envelope1 = TaskEnvelope(**base_fields)
        assert envelope1.priority is None
        assert envelope1.timeout is None
        assert envelope1.metadata == {}
        assert envelope1.task_name is None

        # Test optional fields provided
        envelope2 = TaskEnvelope(
            **base_fields,
            priority="HIGH",
            timeout=30.0,
            metadata={"pid": "PID-001"},
            task_name="Build application",
        )
        assert envelope2.priority == "HIGH"
        assert envelope2.timeout == 30.0
        assert envelope2.metadata == {"pid": "PID-001"}
        assert envelope2.task_name == "Build application"

        # Test optional fields as None
        envelope3 = TaskEnvelope(
            **base_fields,
            priority=None,
            timeout=None,
            task_name=None,
        )
        assert envelope3.priority is None
        assert envelope3.timeout is None
        assert envelope3.task_name is None

    def test_task_envelope_placeholders_allowed(self):
        """Test placeholder values are allowed for trace_id and span_id"""
        envelope = TaskEnvelope(
            task_id="task-001",
            agent_id="agent-001",
            cycle_id="CYCLE-001",
            pulse_id="pulse-001",
            project_id="project-001",
            task_type="code_generate",
            inputs={},
            correlation_id="corr-CYCLE-001",
            causation_id="cause-root",
            trace_id="trace-placeholder-task-001",
            span_id="span-placeholder-task-001",
        )

        assert envelope.trace_id == "trace-placeholder-task-001"
        assert envelope.span_id == "span-placeholder-task-001"
        # Placeholders are valid string values
        assert isinstance(envelope.trace_id, str)
        assert isinstance(envelope.span_id, str)

    def test_task_envelope_immutability_not_enforced_by_model(self):
        """Test that Pydantic model allows field mutation (immutability is runtime contract)"""
        envelope = TaskEnvelope(
            task_id="task-001",
            agent_id="agent-001",
            cycle_id="CYCLE-001",
            pulse_id="pulse-001",
            project_id="project-001",
            task_type="code_generate",
            inputs={},
            correlation_id="corr-CYCLE-001",
            causation_id="cause-root",
            trace_id="trace-placeholder-task-001",
            span_id="span-placeholder-task-001",
        )

        # Pydantic models allow field mutation (immutability is enforced at runtime, not model level)
        original_task_id = envelope.task_id
        envelope.task_id = "task-modified"
        assert envelope.task_id == "task-modified"
        assert envelope.task_id != original_task_id

    def test_task_envelope_metadata_vs_inputs_semantics(self):
        """Test that inputs and metadata are separate fields with different semantics"""
        envelope = TaskEnvelope(
            task_id="task-001",
            agent_id="agent-001",
            cycle_id="CYCLE-001",
            pulse_id="pulse-001",
            project_id="project-001",
            task_type="code_generate",
            inputs={"action": "build", "target": "app"},  # Execution-relevant
            correlation_id="corr-CYCLE-001",
            causation_id="cause-root",
            trace_id="trace-placeholder-task-001",
            span_id="span-placeholder-task-001",
            metadata={"pid": "PID-001", "phase": "implementation"},  # Orchestration info
        )

        # inputs and metadata are separate fields
        assert envelope.inputs == {"action": "build", "target": "app"}
        assert envelope.metadata == {"pid": "PID-001", "phase": "implementation"}
        assert envelope.inputs != envelope.metadata

