"""Tests for build_task_name (adapters/cycles/task_naming.py, #185).

The Prefect/Gantt task label prefixes with the agent that ran the task
(``envelope.agent_id``) rather than the role, falling back to the role when
``agent_id`` is unset (correction/repair, gate boundaries). Focused-mode
envelopes additionally carry the manifest focus + index.
"""

from __future__ import annotations

import pytest

from adapters.cycles.task_naming import build_task_name
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_orchestration]


def _envelope(
    task_type: str = "development.develop",
    inputs: dict | None = None,
    agent_id: str = "neo",
    role: str | None = "dev",
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="task_abc",
        agent_id=agent_id,
        cycle_id="cyc_001",
        pulse_id="p1",
        project_id="proj_001",
        task_type=task_type,
        correlation_id="corr",
        causation_id="cause",
        trace_id="trace",
        span_id="span",
        inputs=inputs or {},
        metadata={"role": role} if role is not None else {},
    )


class TestBuildTaskName:
    """Gantt-friendly Prefect labels: prefix with the agent that ran the task,
    not the role (role duplicates the task_type's own domain segment)."""

    def test_prefixes_with_agent_name_not_role(self) -> None:
        # agent_id 'eve' wins over role 'qa' — the whole point of #185. Before
        # the change this rendered "qa: qa.define_test_strategy" (role repeats
        # the task_type domain).
        env = _envelope(task_type="qa.define_test_strategy", agent_id="eve", role="qa")
        assert build_task_name(env) == "eve: qa.define_test_strategy"

    def test_falls_back_to_role_when_agent_id_empty(self) -> None:
        # Correction/repair + gate-boundary envelopes leave agent_id="" — the
        # label must degrade to the role, not a blank prefix.
        env = _envelope(task_type="development.develop", agent_id="", role="dev")
        assert build_task_name(env) == "dev: development.develop"

    def test_falls_back_to_unknown_when_no_agent_and_no_role(self) -> None:
        env = _envelope(task_type="governance.review", agent_id="", role=None)
        assert build_task_name(env) == "unknown: governance.review"

    def test_focused_envelope_uses_agent_focus_and_index(self) -> None:
        env = _envelope(
            agent_id="neo",
            inputs={
                "subtask_focus": "Backend data models and in-memory repository",
                "subtask_index": 0,
            },
        )
        assert build_task_name(env) == "neo[0]: Backend data models and in-memory repository"

    def test_focused_envelope_without_index_omits_brackets(self) -> None:
        env = _envelope(
            agent_id="neo", inputs={"subtask_focus": "FastAPI endpoints and validation"}
        )
        assert build_task_name(env) == "neo: FastAPI endpoints and validation"

    def test_non_focused_envelope_falls_back_to_task_type(self) -> None:
        env = _envelope(task_type="development.develop", agent_id="neo", inputs={})
        assert build_task_name(env) == "neo: development.develop"

    def test_long_focus_truncates_at_60_chars(self) -> None:
        env = _envelope(agent_id="neo", inputs={"subtask_focus": "X" * 100, "subtask_index": 3})
        name = build_task_name(env)
        assert name == f"neo[3]: {'X' * 60}"
        assert len(name.split(": ", 1)[1]) == 60

    def test_index_zero_renders_as_zero_not_omitted(self) -> None:
        """Subtask index 0 must render as ``[0]`` — falsy but valid."""
        env = _envelope(agent_id="neo", inputs={"subtask_focus": "first", "subtask_index": 0})
        assert build_task_name(env) == "neo[0]: first"
