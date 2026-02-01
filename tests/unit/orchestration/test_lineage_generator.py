#!/usr/bin/env python3
"""
Unit tests for LineageGenerator
Tests ACI v0.8 lineage field generation rules
"""

import pytest

from agents.utils.lineage_generator import LineageGenerator


@pytest.mark.unit
class TestLineageGenerator:
    """Test LineageGenerator field generation rules, determinism, and placeholder formatting"""

    def test_generate_correlation_id_deterministic(self):
        """Test correlation_id generation is deterministic"""
        cycle_id = "CYCLE-001"
        result1 = LineageGenerator.generate_correlation_id(cycle_id)
        result2 = LineageGenerator.generate_correlation_id(cycle_id)

        assert result1 == "corr-CYCLE-001"
        assert result2 == "corr-CYCLE-001"
        assert result1 == result2  # Deterministic

    def test_generate_causation_id_with_parent_task(self):
        """Test causation_id generation with parent task ID"""
        result = LineageGenerator.generate_causation_id(
            parent_task_id="task-123",
            parent_event_id="event-456",
        )

        assert result == "cause-task-task-123"
        # Parent task ID takes precedence over parent event ID

    def test_generate_causation_id_with_parent_event(self):
        """Test causation_id generation with parent event ID only"""
        result = LineageGenerator.generate_causation_id(parent_event_id="event-456")

        assert result == "cause-event-event-456"

    def test_generate_causation_id_root(self):
        """Test causation_id generation for root events"""
        result = LineageGenerator.generate_causation_id()

        assert result == "cause-root"

    def test_generate_trace_id_placeholder(self):
        """Test trace_id placeholder generation"""
        task_id = "task-001"
        result = LineageGenerator.generate_trace_id(task_id, use_placeholder=True)

        assert result == "trace-placeholder-task-001"
        assert isinstance(result, str)

    def test_generate_span_id_placeholder(self):
        """Test span_id placeholder generation"""
        task_id = "task-001"
        result = LineageGenerator.generate_span_id(task_id, use_placeholder=True)

        assert result == "span-placeholder-task-001"
        assert isinstance(result, str)

    def test_ensure_lineage_fields_never_omits(self):
        """Test ensure_lineage_fields always returns all 4 lineage fields"""
        cycle_id = "CYCLE-001"
        task_id = "task-001"

        # Test with no fields provided
        result1 = LineageGenerator.ensure_lineage_fields(cycle_id, task_id)
        assert "correlation_id" in result1
        assert "causation_id" in result1
        assert "trace_id" in result1
        assert "span_id" in result1
        assert len(result1) == 4

        # Test with some fields provided
        result2 = LineageGenerator.ensure_lineage_fields(
            cycle_id,
            task_id,
            correlation_id="custom-corr",
            causation_id="custom-cause",
        )
        assert result2["correlation_id"] == "custom-corr"
        assert result2["causation_id"] == "custom-cause"
        assert "trace_id" in result2  # Generated
        assert "span_id" in result2  # Generated
        assert len(result2) == 4

        # Test with all fields provided
        result3 = LineageGenerator.ensure_lineage_fields(
            cycle_id,
            task_id,
            correlation_id="custom-corr",
            causation_id="custom-cause",
            trace_id="custom-trace",
            span_id="custom-span",
        )
        assert result3["correlation_id"] == "custom-corr"
        assert result3["causation_id"] == "custom-cause"
        assert result3["trace_id"] == "custom-trace"
        assert result3["span_id"] == "custom-span"
        assert len(result3) == 4

        # Test with parent_task_id
        result4 = LineageGenerator.ensure_lineage_fields(
            cycle_id,
            task_id,
            parent_task_id="parent-task-123",
        )
        assert result4["causation_id"] == "cause-task-parent-task-123"
        assert len(result4) == 4

        # Test with parent_event_id
        result5 = LineageGenerator.ensure_lineage_fields(
            cycle_id,
            task_id,
            parent_event_id="parent-event-456",
        )
        assert result5["causation_id"] == "cause-event-parent-event-456"
        assert len(result5) == 4

