"""The context-assembly port, inert (SIP-0110 Appendix A §3.6; #2176).

What bugs would these catch? A chat turn or an unbound request that can carry a fabricated cycle or project
(T10); a task's lesson section that differs from recall's own answer, or asks the target cycle's snapshot
instead of its owner's; a recall that raised read as "none eligible", which would score as a lesson with no
effect; a chat turn handed lessons, or disclosed as a task's exposure.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.memory.recall import SnapshotRecall
from squadops.capabilities.lesson_supply import LessonContextAssembly, query_of
from squadops.memory.context import (
    ChatTurn,
    ContextRequest,
    Disposition,
    ProjectBound,
    RecordRef,
    SectionKind,
    TaskInvocation,
    Unbound,
    UnitRef,
)
from squadops.memory.recall import UnitKind
from tests.unit.cycles.test_failure_recall import _DESIGN, _pinned, _store_with

pytestmark = [pytest.mark.domain_memory]

_NOW = datetime(2026, 10, 12, tzinfo=UTC)
_CHAT = {"session_id": "s", "message_id": "m", "user_id": "u", "agent_id": "neo"}


def _task(**change) -> TaskInvocation:
    fields = {
        "run_id": "run_1",
        "task_id": "task_design",
        "attempt": 1,
        "target_cycle_id": "cyc_a",
        "snapshot_owner": UnitRef(UnitKind.CAMPAIGN, "cmp_1"),
        "task_type": "development.design_plan",
        "role": "dev",
        "stack": "fullstack_fastapi_react",
        "model_family": "qwen3.8",
        "agent_id": "neo",
        "prompt_budget": 20_000,
    }
    return TaskInvocation(**(fields | change))


@pytest.mark.parametrize(
    "build",
    [
        lambda: ChatTurn(**_CHAT, cycle_id="cyc_a"),
        lambda: ChatTurn(**_CHAT, run_id="run_1"),
        lambda: ChatTurn(**_CHAT, task_id="task_design"),
        lambda: Unbound(project_id="group_run"),
        lambda: ContextRequest(Unbound(), _task()),
    ],
    ids=["chat-cycle", "chat-run", "chat-task", "unbound-project", "unbound-task"],
)
def test_a_fabricated_cycle_or_project_cannot_be_constructed(build):
    """T10, at the type level."""
    with pytest.raises(TypeError):
        build()


async def test_a_tasks_lesson_section_is_recalls_answer_from_its_snapshot_owner():
    """The campaign's snapshot answers a cycle of the campaign; the target cycle has no snapshot of its own,
    so asking it would supply nothing."""
    store = await _store_with(("Name the manifest element each criterion checks.", _DESIGN))
    await _pinned(store, UnitKind.CAMPAIGN, "cmp_1")
    recall = SnapshotRecall(store)
    request = ContextRequest(ProjectBound("group_run"), _task())

    bundle = await LessonContextAssembly(recall, now=_NOW).assemble(request)

    assert bundle.recalled == await recall.recall(query_of(request))
    # #2178, #2179: the two binding sections beside it, none recorded or pinned for this unit.
    instructions, project, lessons = bundle.sections
    assert [(s.kind, s.disposition) for s in (instructions, project)] == [
        (SectionKind.TASK_INSTRUCTIONS, Disposition.NONE_ELIGIBLE),
        (SectionKind.PROJECT_INSTRUCTIONS, Disposition.NONE_ELIGIBLE),
    ]
    assert (lessons.kind, lessons.disposition, bundle.complete) == (
        SectionKind.LESSONS,
        Disposition.SUPPLIED,
        True,
    )
    [entry] = bundle.recalled.supplied
    assert lessons.supplied == (RecordRef(entry.revision.pattern_id, "1"),)
    assert lessons.effective_budget == 600


async def test_a_recall_that_raises_is_a_failed_section_and_a_failed_exposure_never_none_eligible():
    class _Raises(SnapshotRecall):
        async def recall(self, query):
            raise ConnectionError("store down")

    store = await _store_with()
    assembly = LessonContextAssembly(_Raises(store), now=_NOW)

    bundle = await assembly.assemble(ContextRequest(ProjectBound("group_run"), _task()))
    await assembly.disclose(bundle)

    assert bundle.section(SectionKind.LESSONS).disposition is Disposition.FAILED
    [exposure] = await store.list_exposures("run_1")
    assert (exposure.disposition, exposure.cycle_id) == ("recall_failed", "cyc_a")


async def test_a_chat_turn_gets_no_lessons_and_no_task_exposure():
    store = await _store_with(("Name the manifest element each criterion checks.", _DESIGN))
    assembly = LessonContextAssembly(SnapshotRecall(store), now=_NOW)

    bundle = await assembly.assemble(ContextRequest(Unbound(), ChatTurn(**_CHAT)))
    await assembly.disclose(bundle)

    assert [(s.kind, s.disposition) for s in bundle.sections] == [
        (SectionKind.LESSONS, Disposition.NOT_APPLICABLE)
    ]
    assert (bundle.complete, bundle.recalled) == (True, None)
    assert await store.list_exposures("run_1") == []
