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
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.llm.model_registry import model_family_of
from squadops.memory.exposures import Exposure
from squadops.memory.lessons import Recalled
from squadops.memory.recall import LESSONS_INPUT, RecallQuery, UnitKind

if TYPE_CHECKING:
    from squadops.cycles.models import Cycle
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
        query = query_for(envelope, unit=unit, stack=stack)
        recalled = await recall.recall(query)
        await recall.disclose(
            Exposure.of(
                run_id=run_id,
                task_id=envelope.task_id,
                cycle_id=envelope.cycle_id,
                seam=seam.value,
                query=query,
                recalled=recalled,
                recorded_at=now,
            )
        )
        handed = lessons_input(recalled)
        if handed is None:
            supplied.append(envelope)
        else:
            inputs = {**envelope.inputs, LESSONS_INPUT: handed}
            supplied.append(dataclasses.replace(envelope, inputs=inputs))
    return supplied
