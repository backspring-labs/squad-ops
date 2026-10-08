"""Supplying approved lessons to the authoring seams (SIP-0110 §0.9; slice 3c, #2096).

Each task at a consuming seam asks the recall before it is dispatched, with its scope taken from
trusted context: the project and task type from its envelope, the role and model the plan resolved
for it, the cycle's stack, and its unit's pinned snapshot. Every such task's answer is disclosed as
an exposure, a memory-disabled one included. A task is handed lessons only when some are supplied,
on ``LESSONS_INPUT``; a task handed none has exactly the inputs it had before memory existed, so its
prompt renders byte-identical (§0.9).

Which task types consume is their context-assembly contract's declaration (``authoring_seam_of``),
never a branch on the type. Plan writing and build authoring are supplied here, when the run's plan
is composed; repair when the correction runner composes a repair, and proposal writing when a
campaign composes its proposal, each through the same function.

An exposure is one authoring invocation's (§0.2), so a task the loop dispatches again (a correction
round's re-take, an emission retry) asks again and discloses its own answer, under its attempt
(:func:`supply_the_redispatch`, #2162).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.capabilities.handlers.fault_injection import PRIOR_ATTEMPTS_KEY
from squadops.llm.model_registry import model_family_of
from squadops.memory.exposures import Exposure
from squadops.memory.lessons import Recalled
from squadops.memory.recall import LESSONS_INPUT, RecallQuery, UnitKind

if TYPE_CHECKING:
    from squadops.cycles.models import Cycle
    from squadops.memory.authoring_envelope import AuthoringSeam
    from squadops.ports.memory.recall import FailurePatternRecallPort
    from squadops.tasks.models import TaskEnvelope


def unit_of(cycle: Cycle) -> tuple[UnitKind, str]:
    """The unit whose snapshot a cycle's tasks select from (§0.7): its campaign's, or its own."""
    if cycle.campaign_id:
        return UnitKind.CAMPAIGN, cycle.campaign_id
    return UnitKind.CYCLE, cycle.cycle_id


def query_for(envelope: TaskEnvelope, *, unit: tuple[UnitKind, str], stack: str) -> RecallQuery:
    """The task's recall query. The role is the plan step's and the model the one the plan resolved
    for it, both written by the framework, never by an agent (§0.8 step 1)."""
    return RecallQuery(
        project_id=envelope.project_id,
        task_type=str(envelope.task_type),
        role=str((envelope.metadata or {}).get("role") or ""),
        stack=stack,
        model_family=model_family_of(str(envelope.inputs.get("agent_model") or "")),
        unit_kind=unit[0],
        unit_id=unit[1],
    )


def attempt_of(envelope: TaskEnvelope) -> int:
    """Which dispatch of its task ``envelope``'s next one is: the executor's attempt stamp (#1304),
    which counts the attempts already made, plus one. The captured envelope carries the same
    stamp, so an exposure and its authoring join on it."""
    return int((envelope.inputs or {}).get(PRIOR_ATTEMPTS_KEY) or 0) + 1


def lessons_input(recalled: Recalled) -> dict | None:
    """What a task is handed on ``LESSONS_INPUT``, or ``None`` when nothing was supplied."""
    if not recalled.supplied:
        return None
    return {
        "snapshot": recalled.snapshot_id,
        "lessons": [
            {"revision_id": e.revision.revision_id, "text": e.revision.text}
            for e in recalled.supplied
        ],
    }


async def supply_for_cycle(
    envelopes: Sequence[TaskEnvelope],
    *,
    recall: FailurePatternRecallPort,
    cycle: Cycle,
    run_id: str,
    now: datetime,
) -> list[TaskEnvelope]:
    """:func:`supply_lessons` for a run of ``cycle``: its unit and its stack (``cycle_stack``)."""
    from squadops.cycles.benchmark_registry import cycle_stack

    return await supply_lessons(
        envelopes,
        recall=recall,
        unit=unit_of(cycle),
        stack=cycle_stack(cycle) or "",
        run_id=run_id,
        now=now,
    )


async def supply_lessons(
    envelopes: Sequence[TaskEnvelope],
    *,
    recall: FailurePatternRecallPort,
    unit: tuple[UnitKind, str],
    stack: str,
    run_id: str,
    now: datetime,
) -> list[TaskEnvelope]:
    """``envelopes``, each consuming task's with the lessons it is supplied, in order. Every
    consuming task's answer is disclosed; a task that consumes nothing is passed through as is."""
    supplied: list[TaskEnvelope] = []
    for envelope in envelopes:
        seam = authoring_seam_of(str(envelope.task_type))
        if seam is None:
            supplied.append(envelope)
            continue
        handed = await _ask_and_disclose(
            envelope, seam, recall=recall, unit=unit, stack=stack, run_id=run_id, now=now
        )
        if handed is None:
            supplied.append(envelope)
        else:
            inputs = {**envelope.inputs, LESSONS_INPUT: handed}
            supplied.append(dataclasses.replace(envelope, inputs=inputs))
    return supplied


async def supply_the_redispatch(
    envelopes: Sequence[TaskEnvelope | None],
    *,
    recall: FailurePatternRecallPort,
    cycle: Cycle,
    run_id: str,
    now: datetime,
) -> None:
    """A task the loop is about to dispatch again is another authoring invocation (§0.2, #2162):
    it asks its unit's snapshot again and discloses its own exposure, under its attempt.

    The loop re-dispatches the envelopes it already holds, so what this attempt is handed replaces
    what the one before it was handed, in place, on each of them: a lesson the earlier answer
    supplied and this one does not is taken off, or the envelope would carry a lesson its exposure
    says it never got. The first of ``envelopes`` is the task's own; the rest (the enriched copy the
    loop dispatches) are kept equal to it. A task at no consuming seam is left as it is.
    """
    from squadops.cycles.benchmark_registry import cycle_stack

    held = [e for e in envelopes if e is not None]
    if not held:
        return
    seam = authoring_seam_of(str(held[0].task_type))
    if seam is None:
        return
    handed = await _ask_and_disclose(
        held[0],
        seam,
        recall=recall,
        unit=unit_of(cycle),
        stack=cycle_stack(cycle) or "",
        run_id=run_id,
        now=now,
    )
    for envelope in held:
        if handed is None:
            envelope.inputs.pop(LESSONS_INPUT, None)
        else:
            envelope.inputs[LESSONS_INPUT] = handed


async def _ask_and_disclose(
    envelope: TaskEnvelope,
    seam: AuthoringSeam,
    *,
    recall: FailurePatternRecallPort,
    unit: tuple[UnitKind, str],
    stack: str,
    run_id: str,
    now: datetime,
) -> dict | None:
    """One invocation's recall: asked with the task's trusted scope, disclosed under its attempt,
    and what it is handed (``None`` when nothing is supplied)."""
    query = query_for(envelope, unit=unit, stack=stack)
    recalled = await recall.recall(query)
    await recall.disclose(
        Exposure.of(
            run_id=run_id,
            task_id=envelope.task_id,
            cycle_id=envelope.cycle_id,
            agent_id=envelope.agent_id,
            seam=seam.value,
            query=query,
            recalled=recalled,
            recorded_at=now,
            attempt=attempt_of(envelope),
        )
    )
    return lessons_input(recalled)
