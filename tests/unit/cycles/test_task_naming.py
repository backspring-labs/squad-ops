"""Tests for build_task_name (adapters/cycles/task_naming.py, #185 / #277).

The Prefect/Gantt task label is ``{agent} [{n}/{total}]: {task_type}[ — focus]``:
prefix with the agent that ran the task (``envelope.agent_id``), falling back to
the role when ``agent_id`` is unset (correction/repair, gate boundaries); the
descriptor is the raw ``task_type`` (#277) with any free-text ``subtask_focus``
appended; planned runs carry a 1-based per-agent ``[n/total]`` count (#94),
spaced off the prefix so it doesn't read as an array subscript.
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
    descriptor is the raw task_type (#277)."""

    def test_prefixes_with_agent_name_not_role(self) -> None:
        # agent_id 'eve' wins over role 'qa'. The raw task_type already carries
        # the role in its domain segment, so the label reads
        # "eve: qa.define_test_strategy" — agent identity + role + verb, no dup.
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

    def test_focused_envelope_appends_focus_to_task_type(self) -> None:
        # #277: focus is appended to the raw task_type, not used in its place —
        # the task_type spine stays so the label is uniform and greppable.
        env = _envelope(
            agent_id="neo",
            task_type="development.develop",
            inputs={
                "subtask_focus": "Backend data models and in-memory repository",
                "subtask_index": 0,
            },
        )
        assert build_task_name(env) == (
            "neo [0]: development.develop — Backend data models and in-memory repository"
        )

    def test_focused_envelope_without_index_omits_brackets(self) -> None:
        env = _envelope(
            agent_id="neo",
            task_type="development.develop",
            inputs={"subtask_focus": "FastAPI endpoints and validation"},
        )
        assert build_task_name(env) == (
            "neo: development.develop — FastAPI endpoints and validation"
        )

    def test_non_focused_envelope_falls_back_to_task_type(self) -> None:
        env = _envelope(task_type="development.develop", agent_id="neo", inputs={})
        assert build_task_name(env) == "neo: development.develop"

    def test_long_focus_truncates_at_60_chars(self) -> None:
        env = _envelope(
            agent_id="neo",
            task_type="development.develop",
            inputs={"subtask_focus": "X" * 100, "subtask_index": 3},
        )
        name = build_task_name(env)
        assert name == f"neo [3]: development.develop — {'X' * 60}"
        # only the focus portion is truncated; the task_type spine is untouched.
        assert name.split(" — ", 1)[1] == "X" * 60

    def test_index_zero_renders_as_zero_not_omitted(self) -> None:
        """Subtask index 0 must render as ``[0]`` — falsy but valid."""
        env = _envelope(
            agent_id="neo",
            task_type="development.develop",
            inputs={"subtask_focus": "first", "subtask_index": 0},
        )
        assert build_task_name(env) == "neo [0]: development.develop — first"


class TestPerRoleNumbering:
    """#94/#277: planned-run envelopes carry per-agent role_index/role_total and
    render ``prefix [n/total]: task_type[ — focus]`` (1-based, spaced bracket)."""

    def test_implementation_focused_uses_per_role_count(self) -> None:
        env = _envelope(
            agent_id="neo",
            task_type="development.develop",
            inputs={
                "subtask_focus": "Backend Pydantic models & in-memory repository",
                "role_index": 1,
                "role_total": 4,
            },
        )
        assert build_task_name(env) == (
            "neo [1/4]: development.develop — Backend Pydantic models & in-memory repository"
        )

    def test_framing_non_focused_uses_raw_task_type_and_count(self) -> None:
        # #277: framing tasks show the raw task_type (role + verb), not a
        # humanized leaf that drops the domain ("strategy.frame_objective", not
        # "Frame objective").
        env = _envelope(
            task_type="strategy.frame_objective",
            agent_id="nat",
            role="strat",
            inputs={"role_index": 1, "role_total": 1},
        )
        assert build_task_name(env) == "nat [1/1]: strategy.frame_objective"

    @pytest.mark.parametrize(
        "task_type",
        [
            "qa.define_test_strategy",
            "governance.assess_readiness",
            "data.research_context",
            "development.design_plan",
            "noseparator",
        ],
    )
    def test_raw_task_type_is_the_descriptor(self, task_type) -> None:
        env = _envelope(
            task_type=task_type, agent_id="x", inputs={"role_index": 2, "role_total": 5}
        )
        assert build_task_name(env) == f"x [2/5]: {task_type}"

    def test_count_is_one_based(self) -> None:
        """Per-role index is 1-based — the #94 fix for confusing 0-based UI labels."""
        env = _envelope(
            agent_id="neo",
            task_type="development.develop",
            inputs={"subtask_focus": "first", "role_index": 1, "role_total": 2},
        )
        assert build_task_name(env) == "neo [1/2]: development.develop — first"

    def test_bracket_is_spaced_off_prefix(self) -> None:
        """#277: the count bracket must be spaced (``neo [1/2]``) so it doesn't
        read as an array subscript (``neo[1]``)."""
        env = _envelope(agent_id="neo", inputs={"role_index": 1, "role_total": 2})
        name = build_task_name(env)
        assert " [1/2]:" in name
        assert "neo[" not in name

    def test_long_focus_still_truncates_with_count(self) -> None:
        env = _envelope(
            agent_id="neo",
            task_type="development.develop",
            inputs={"subtask_focus": "X" * 100, "role_index": 2, "role_total": 4},
        )
        assert build_task_name(env) == f"neo [2/4]: development.develop — {'X' * 60}"

    def test_partial_count_falls_back_to_legacy(self) -> None:
        """role_index without role_total (defensive) must not render ``[1/None]`` —
        fall back to the legacy non-focused shape."""
        env = _envelope(task_type="development.develop", agent_id="neo", inputs={"role_index": 1})
        assert build_task_name(env) == "neo: development.develop"
