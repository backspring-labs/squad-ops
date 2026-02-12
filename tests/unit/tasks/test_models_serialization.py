"""Tests for TaskEnvelope / TaskResult JSON serialization round-trip.

Verifies to_dict() and from_dict() preserve all fields across
JSON transport (used by DistributedFlowExecutor).
"""

from __future__ import annotations

import json

import pytest

from squadops.tasks.models import TaskEnvelope, TaskResult


pytestmark = [pytest.mark.domain_orchestration]


class TestTaskEnvelopeSerialization:
    """TaskEnvelope.to_dict() / from_dict() round-trip."""

    @pytest.fixture
    def envelope(self) -> TaskEnvelope:
        return TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="pulse_001",
            project_id="proj_001",
            task_type="development.implement",
            correlation_id="corr_001",
            causation_id="cause_001",
            trace_id="trace_001",
            span_id="span_001",
            inputs={"prd": "Build a widget", "resolved_config": {"model": "gpt-4"}},
            priority="HIGH",
            timeout=120.0,
            metadata={"step_index": 1, "role": "dev"},
            task_name="implement-feature",
        )

    def test_round_trip_preserves_all_fields(self, envelope: TaskEnvelope) -> None:
        """from_dict(to_dict()) produces an identical TaskEnvelope."""
        rebuilt = TaskEnvelope.from_dict(envelope.to_dict())
        assert rebuilt == envelope

    def test_json_round_trip(self, envelope: TaskEnvelope) -> None:
        """JSON encode/decode round-trip preserves all fields."""
        json_str = json.dumps(envelope.to_dict())
        rebuilt = TaskEnvelope.from_dict(json.loads(json_str))
        assert rebuilt == envelope

    def test_to_dict_returns_plain_dict(self, envelope: TaskEnvelope) -> None:
        """to_dict() returns a plain dict (not dataclass)."""
        d = envelope.to_dict()
        assert isinstance(d, dict)
        assert d["task_id"] == "task_abc"
        assert d["agent_id"] == "neo"
        assert d["inputs"]["prd"] == "Build a widget"

    def test_minimal_envelope_round_trip(self) -> None:
        """Envelope with only required fields round-trips cleanly."""
        envelope = TaskEnvelope(
            task_id="t1",
            agent_id="nat",
            cycle_id="c1",
            pulse_id="p1",
            project_id="proj1",
            task_type="strategy.analyze_prd",
            correlation_id="corr1",
            causation_id="cause1",
            trace_id="trace1",
            span_id="span1",
        )
        rebuilt = TaskEnvelope.from_dict(envelope.to_dict())
        assert rebuilt == envelope
        assert rebuilt.inputs == {}
        assert rebuilt.metadata == {}
        assert rebuilt.priority is None


class TestTaskResultSerialization:
    """TaskResult.to_dict() / from_dict() round-trip."""

    def test_succeeded_round_trip(self) -> None:
        result = TaskResult(
            task_id="task_abc",
            status="SUCCEEDED",
            outputs={"summary": "done", "artifacts": [{"name": "out.md", "content": "# OK"}]},
        )
        rebuilt = TaskResult.from_dict(result.to_dict())
        assert rebuilt == result

    def test_failed_round_trip(self) -> None:
        result = TaskResult(
            task_id="task_abc",
            status="FAILED",
            error="kaboom",
        )
        rebuilt = TaskResult.from_dict(result.to_dict())
        assert rebuilt == result

    def test_with_execution_evidence(self) -> None:
        result = TaskResult(
            task_id="task_abc",
            status="SUCCEEDED",
            outputs={"summary": "ok"},
            execution_evidence={"handler": "strategy.analyze_prd", "latency_ms": 1200},
        )
        rebuilt = TaskResult.from_dict(result.to_dict())
        assert rebuilt == result

    def test_json_round_trip(self) -> None:
        result = TaskResult(
            task_id="task_abc",
            status="SUCCEEDED",
            outputs={"data": [1, 2, 3]},
        )
        json_str = json.dumps(result.to_dict())
        rebuilt = TaskResult.from_dict(json.loads(json_str))
        assert rebuilt == result
