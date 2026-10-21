"""A memory change after a unit's admission: the rules that make it an intervention, and its row in
a campaign's control log (SIP-0110 Appendix A §3.5, §3.7; #2178, #2179, #2180).

A task instruction written after its cycle's admission, through the records API or captured in chat,
names a cycle of its project, selects authoring tasks, is refused once one of them has dispatched,
and is recorded on its campaign's control log when its cycle is a campaign's.

A task instruction changed on a campaign's cycle after admission, and a re-binding of a campaign's
snapshot, are interventions. Each is a record-only control-log row, which the intervention ledger
reads (SIP-0113 §4.3), so a measurement window reports it. The memory change is already stored
when the row is written: a row that can't be written is said, never implied.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Request

from squadops.api.errors import http_error
from squadops.api.routes.campaigns.campaigns import actor_from
from squadops.api.runtime.deps import get_campaign_registry, get_cycle_registry, get_memory_store
from squadops.auth.models import Identity
from squadops.campaigns.models import CampaignTransition, ControlOperation
from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.capabilities.lesson_supply import unit_of
from squadops.memory.dispatch_turns import CHANGE_WAIT_SECONDS, DispatchTurnUnavailable
from squadops.memory.lessons import UnitKind
from squadops.memory.records import MemoryRecord, RecordRefused, RecordScope
from squadops.memory.task_instructions import (
    cited_lesson,
    dispatched,
    refuse_for_lessons_disabled,
)

logger = logging.getLogger(__name__)


async def record_on_control_log(
    request: Request,
    identity: Identity | None,
    campaign_id: str,
    *,
    operation: ControlOperation,
    reason: str,
    idempotency_key: str,
    target: str,
    binding: dict[str, Any],
) -> str | None:
    """The row's id, or ``None`` when it couldn't be written (logged at WARNING)."""
    actor, role = actor_from(identity)
    transition = CampaignTransition(
        operation=operation,
        actor=actor,
        actor_role=role,
        reason=reason,
        idempotency_key=idempotency_key,
        next_state=None,
        target=target,
        binding=binding,
    )
    try:
        result = await get_campaign_registry(request).transition(campaign_id, transition)
    except Exception:  # noqa: BLE001 — a missing row is said, never implied
        logger.warning(
            "memory_intervention_not_logged campaign=%s op=%s", campaign_id, operation,
            exc_info=True,
        )  # fmt: skip
        return None
    return result.entry.entry_id


async def target_cycle(request: Request, scope: str, project_id: str | None, target) -> Any:
    """A task instruction's target cycle, after checking it is a cycle of the record's project and
    that every task type it selects is an authoring task (#2178: an instruction for any other would
    reach nothing). ``None`` for any other record."""
    if scope != RecordScope.TASK or target is None:
        return None
    unreachable = [t for t in target.task_types if authoring_seam_of(t) is None]
    if unreachable:
        raise http_error(
            422,
            "VALIDATION_ERROR",
            f"{', '.join(unreachable)} authors nothing an instruction reaches",
        )
    try:
        cycle = await get_cycle_registry(request).get_cycle(target.cycle_id)
    except Exception as e:
        raise http_error(422, "VALIDATION_ERROR", f"no cycle {target.cycle_id}") from e
    if cycle.project_id != project_id:
        raise http_error(
            422, "VALIDATION_ERROR", f"{target.cycle_id} is not a cycle of {project_id}"
        )
    return cycle


def of_campaign(cycle: Any) -> bool:
    return bool(getattr(cycle, "campaign_id", None))


@asynccontextmanager
async def dispatch_turn(request: Request, unit: tuple[UnitKind, str] | None) -> AsyncIterator[None]:
    """#2545: ``unit``'s dispatch turn, held by a change to what its dispatches are handed from its
    check of their exposures to its write, so no dispatch composes between the two. Nothing is held
    for no unit (a record no cycle's dispatch reads), or with no store, whose check refuses. A turn
    that isn't given within a change's bound answers 503, with nothing written."""
    store = get_memory_store(request)
    if unit is None or store is None:
        yield
        return
    try:
        async with store.dispatch_turn(*unit, wait_seconds=CHANGE_WAIT_SECONDS):
            yield
    except DispatchTurnUnavailable as e:
        raise http_error(
            503, "DISPATCH_TURN_UNAVAILABLE", f"{e}; nothing was written, so it can be sent again"
        ) from e


def turn_of(cycle: Any) -> tuple[UnitKind, str] | None:
    """The unit whose dispatches a task instruction for ``cycle`` reaches: its campaign's, or its
    own. ``None`` for a record with no cycle."""
    return unit_of(cycle) if cycle is not None else None


async def refuse_dispatched(request: Request, cycle: Any, target: Any) -> None:
    """Refuse (409) an instruction added or revised after admission for a task its cycle has
    dispatched, in any run; unknown refuses too (503), never reads as undispatched."""
    store = get_memory_store(request)
    try:
        if store is None:
            raise LookupError("the memory store is not configured")
        exposures = await store.list_project_exposures(cycle.project_id)
    except Exception:  # noqa: BLE001 — an unknown dispatch is refused, never assumed absent
        logger.warning("task_instruction_dispatch_unread cycle=%s", cycle.cycle_id, exc_info=True)
        raise http_error(
            503,
            "MEMORY_UNAVAILABLE",
            f"whether {cycle.cycle_id}'s selected tasks have dispatched can't be read",
        ) from None
    hit = dispatched(target.task_types, exposures, cycle_id=cycle.cycle_id)
    if hit:
        raise http_error(
            409,
            "TASK_DISPATCHED",
            f"{', '.join(f'{run} {task}' for run, task in hit)} already dispatched, so the work "
            "would mix a binding its first dispatch didn't have. Give it to a cycle whose selected "
            "tasks haven't dispatched: a new cycle's create request, or a campaign's next cycle "
            "(SIP-0110 Appendix A §3.5)",
        )


async def log_intervention(
    request: Request, identity: Identity | None, cycle: Any, record: MemoryRecord, action: str
) -> str | None:
    """A campaign cycle's task instruction changed after admission, as a row in the campaign's
    control log (§3.5): ``None`` for a standalone cycle's, or when the row couldn't be written."""
    if not of_campaign(cycle):
        return None
    current = record.current
    return await record_on_control_log(
        request,
        identity,
        cycle.campaign_id,
        operation=ControlOperation.INSTRUCT,
        reason=current.body if action != "withdraw" else record.status_changes[-1].why,
        idempotency_key=f"instruct:{record.record_id}:{action}:{current.number}",
        target=record.record_id,
        binding={
            "action": action,
            "record_id": record.record_id,
            "revision": current.number,
            "cycle_id": cycle.cycle_id,
            "task_types": list(current.target.task_types) if current.target else [],
        },
    )


async def refuse_lesson_for_control(request: Request, cycle: Any, revision: Any) -> None:
    """§3.7: a task instruction citing a lesson is refused (422) for a lessons-disabled unit, read
    from its cycle's snapshot owner (its campaign's, or its own)."""
    snapshot = None
    store = get_memory_store(request)
    if cited_lesson(revision) is not None and store is not None:
        try:
            snapshot = await store.get_snapshot(*unit_of(cycle))
        except Exception:  # noqa: BLE001 — unreadable leaves it unknown, which refuses
            logger.warning(
                "lesson_citation_snapshot_unread cycle=%s", cycle.cycle_id, exc_info=True
            )
    try:
        refuse_for_lessons_disabled(revision, snapshot)
    except RecordRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
