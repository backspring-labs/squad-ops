#!/usr/bin/env python3
"""
Unit tests for TaskEnvelope JSON serialization/deserialization
Tests ACI v0.8 RabbitMQ payload integrity
"""

import json

import pytest

from agents.tasks.models import TaskEnvelope
from agents.utils.task_envelope import (
    deserialize_envelope_from_json,
    serialize_envelope_to_json,
)


@pytest.mark.unit
class TestTaskEnvelopeCodec:
    """Test TaskEnvelope JSON serialization/deserialization for RabbitMQ payload integrity"""

    def test_serialize_envelope_to_json(self, sample_task_envelope):
        """Test serialize_envelope_to_json produces valid JSON"""
        json_str = serialize_envelope_to_json(sample_task_envelope)

        assert isinstance(json_str, str)
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed["task_id"] == sample_task_envelope.task_id
        assert parsed["agent_id"] == sample_task_envelope.agent_id
        assert parsed["cycle_id"] == sample_task_envelope.cycle_id

    def test_deserialize_envelope_from_json(self, sample_task_envelope):
        """Test deserialize_envelope_from_json creates TaskEnvelope from JSON"""
        json_str = serialize_envelope_to_json(sample_task_envelope)
        deserialized = deserialize_envelope_from_json(json_str)

        assert isinstance(deserialized, TaskEnvelope)
        assert deserialized.task_id == sample_task_envelope.task_id
        assert deserialized.agent_id == sample_task_envelope.agent_id
        assert deserialized.cycle_id == sample_task_envelope.cycle_id
        assert deserialized.inputs == sample_task_envelope.inputs

    def test_round_trip_json_integrity(self, sample_task_envelope):
        """Test serialize → deserialize preserves all fields"""
        # Serialize
        json_str = serialize_envelope_to_json(sample_task_envelope)

        # Deserialize
        deserialized = deserialize_envelope_from_json(json_str)

        # Field-by-field comparison
        assert deserialized.task_id == sample_task_envelope.task_id
        assert deserialized.agent_id == sample_task_envelope.agent_id
        assert deserialized.cycle_id == sample_task_envelope.cycle_id
        assert deserialized.pulse_id == sample_task_envelope.pulse_id
        assert deserialized.project_id == sample_task_envelope.project_id
        assert deserialized.task_type == sample_task_envelope.task_type
        assert deserialized.inputs == sample_task_envelope.inputs
        assert deserialized.correlation_id == sample_task_envelope.correlation_id
        assert deserialized.causation_id == sample_task_envelope.causation_id
        assert deserialized.trace_id == sample_task_envelope.trace_id
        assert deserialized.span_id == sample_task_envelope.span_id
        assert deserialized.metadata == sample_task_envelope.metadata

    def test_deserialize_invalid_json_raises_error(self):
        """Test invalid JSON raises ValueError"""
        with pytest.raises(ValueError):
            deserialize_envelope_from_json("not valid json")

        with pytest.raises(ValueError):
            deserialize_envelope_from_json("{invalid: json}")

    def test_deserialize_missing_required_field_raises_error(self):
        """Test JSON missing required field raises error"""
        # Create JSON missing task_id
        invalid_json = json.dumps(
            {
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
        )

        with pytest.raises((ValueError, Exception)):  # Pydantic ValidationError wrapped in ValueError
            deserialize_envelope_from_json(invalid_json)

