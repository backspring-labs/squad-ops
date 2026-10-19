"""The lesson-text diagnostic and the arms a report keeps apart (SIP-0110 Appendix A §3.7, T9; #2179
stage 2)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from squadops.memory.exposures import (
    ARM_CONTEXT_NONE,
    ARM_LESSONS_DISABLED,
    ARM_LESSONS_ON,
    Exposure,
    arm_of,
)
from squadops.memory.lesson_text import (
    LessonTextSignal,
    lesson_text_signals,
    withheld_lesson_signals,
)
from squadops.memory.lessons import RecallDisposition, Recalled
from squadops.memory.recall import RecallQuery
from tests.unit.memory.test_lessons import T0, _approve, _revision

pytestmark = [pytest.mark.domain_memory]

_CAPTURED = T0 + timedelta(hours=2)


def _envelope(task_id: str, *contents: str, seam: str = "plan_writing") -> dict:
    return {
        "task_id": task_id,
        "seam": seam,
        "captured_at": _CAPTURED.isoformat(),
        "messages": [{"role": "user", "content": c} for c in contents],
    }


def _exposure(run_id: str, disposition: RecallDisposition) -> Exposure:
    return Exposure.of(
        run_id=run_id,
        task_id="task-design",
        cycle_id=f"cyc_{run_id}",
        agent_id="neo",
        seam="plan_writing",
        query=RecallQuery("group_run", "development.design_plan", "dev"),
        recalled=Recalled(f"snp_{run_id}", disposition),
        recorded_at=_CAPTURED,
    )


def test_a_prompt_holding_a_lesson_in_force_at_its_capture_is_flagged_whatever_its_spacing():
    """Bug caught: a lesson's text reflowed across lines in the prompt going unflagged; or a lesson
    approved after the prompt, or revoked before it, flagged, when it could not have reached it."""
    held = _revision("behavior_held", text="Name each route's handler\nafter its path.")
    later = _revision("behavior_later", text="Keep the join idempotent.")
    revoked = _revision("behavior_revoked", text="Pin the lockfile.")
    absent = _revision("behavior_absent", text="Never drop the error envelope.")
    approvals = [
        _approve(held, at=T0),
        _approve(later, at=_CAPTURED + timedelta(minutes=1)),
        _approve(revoked, at=T0, revoked_at=T0 + timedelta(hours=1)),
        _approve(absent, at=T0),
    ]
    prompt = _envelope(
        "task-design",
        "You plan the build.",
        "Name each route's   handler after\n its path. Keep the join idempotent. Pin the lockfile.",
    )

    got = lesson_text_signals("run_off", [prompt], [held, later, revoked, absent], approvals)

    assert got == (
        LessonTextSignal(
            "run_off", "task-design", "plan_writing", _CAPTURED.isoformat(), held.revision_id
        ),
    )


async def test_only_the_runs_whose_unit_withheld_the_lessons_are_read():
    """The report's entry (``withheld_lesson_signals``). Bug caught: a lessons-on run, whose prompt
    holds the lesson because it was supplied, flagged as a leak; or a ``memory_context: none`` run
    left out, when it withholds the lessons too."""
    store = InMemoryCrossCycleMemoryStore()
    lesson = _revision("behavior_held", text="Name each route's handler after its path.")
    await store.record_revision(lesson)
    await store.record_approval(_approve(lesson, at=T0))

    class Envelopes:
        async def list_authoring_envelopes(self, run_id: str) -> list[dict]:
            return [_envelope("task-design", "Name each route's handler after its path.")]

    exposures = [
        _exposure("run_on", RecallDisposition.SUPPLIED),
        _exposure("run_off", RecallDisposition.DISABLED),
        _exposure("run_none", RecallDisposition.CONTEXT_NONE),
    ]

    got = await withheld_lesson_signals(
        exposures, project_id="group_run", cycles=Envelopes(), store=store
    )

    assert [(s.run_id, s.revision_id) for s in got] == [
        ("run_none", lesson.revision_id),
        ("run_off", lesson.revision_id),
    ]
    assert await withheld_lesson_signals(exposures[:1], project_id="group_run",
                                         cycles=Envelopes(), store=store) == ()  # fmt: skip


@pytest.mark.parametrize(
    ("dispositions", "arm"),
    [
        ((RecallDisposition.CONTEXT_NONE, RecallDisposition.FAILED), ARM_CONTEXT_NONE),
        ((RecallDisposition.DISABLED, RecallDisposition.FAILED), ARM_LESSONS_DISABLED),
        ((RecallDisposition.SUPPLIED, RecallDisposition.NONE_ELIGIBLE), ARM_LESSONS_ON),
        ((RecallDisposition.FAILED,), ARM_LESSONS_ON),
    ],
)
def test_a_builds_arm_is_its_units_declaration(dispositions, arm):
    """Bug caught: a ``memory_context: none`` build reported as the lessons-disabled control, or
    a build with one failed recall moved out of the arm it ran."""
    exposures = [_exposure(f"run_{n}", d) for n, d in enumerate(dispositions)]

    assert arm_of(exposures) == arm
