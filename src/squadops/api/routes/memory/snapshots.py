"""``/api/v1/projects/{project_id}/snapshots``: a unit's snapshot as it binds now, and its
re-binding (SIP-0110 Appendix A §3.7; #2179 stage 2).

- **read** (``memory:read``): a standalone cycle's or a campaign's snapshot: the project
  instructions it binds, and every re-binding since its admission;
- **re-bind** (``memory:instruct`` with the unit's authority: ``cycles:write`` for a standalone
  cycle, ``campaigns:supervise`` for a campaign): replace a bound project instruction's revision
  with the record's current one, or remove it when the record is withdrawn.

A re-binding goes forward: the unit's next dispatch binds the new revision. It is refused for a
unit any of whose dispatches was handed the replaced revision, since its later work would build on
work done under it: that is §3.7's restart path, which isn't built, so the work restarts as a new
unit (§5u). A campaign's re-binding is a row in its control log, which the intervention ledger reads
(SIP-0113 §4.3).
"""

from __future__ import annotations

import logging
from contextlib import AbstractAsyncContextManager, nullcontext
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request

from squadops.api.errors import http_error
from squadops.api.memory_schemas import (
    RebindRequest,
    RebindResponse,
    SnapshotBindingResponse,
)
from squadops.api.middleware.auth import require_scopes
from squadops.api.routes.cycles.mapping import cycle_status_of
from squadops.api.routes.memory.interventions import dispatch_turn, record_on_control_log
from squadops.api.runtime.deps import (
    get_campaign_launch,
    get_campaign_registry,
    get_cycle_registry,
    get_memory_records,
    get_memory_store,
    get_reference_resolvers,
)
from squadops.auth.models import Identity, Scope, scopes_for_roles
from squadops.campaigns.models import (
    CampaignNotFoundError,
    CampaignState,
    ControlOperation,
    LaunchIntentState,
)
from squadops.cycles.models import CycleNotFoundError, CycleStatus
from squadops.memory.cycle_bindings import instructions_bound_for, names_current
from squadops.memory.lessons import Snapshot, UnitKind
from squadops.memory.pinning import cycle_binding, source_commit_of
from squadops.memory.rebinding import RebindRefused, rebound, runs_handed
from squadops.memory.records import Rebinding, RecordStatus, pinned_of
from squadops.memory.reference_binding import bound_instruction
from squadops.memory.references import BindingContext
from squadops.ports.memory.cross_cycle import RecordIncompatible, SnapshotMoved

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id}/snapshots", tags=["memory"])

#: A unit in one of these has no dispatch ahead of it, so nothing is re-bound.
_ENDED_CYCLE = frozenset({CycleStatus.COMPLETED, CycleStatus.CANCELLED})
#: The authority over the unit a re-binding needs beside ``memory:instruct`` (§3.7).
_AUTHORITY = {UnitKind.CYCLE: Scope.CYCLES_WRITE, UnitKind.CAMPAIGN: Scope.CAMPAIGNS_SUPERVISE}


def _kind(unit_kind: str) -> UnitKind:
    try:
        return UnitKind(unit_kind)
    except ValueError:
        raise http_error(
            422, "VALIDATION_ERROR", f"a unit is a cycle or a campaign, not {unit_kind!r}"
        ) from None


async def _unit(request: Request, project_id: str, kind: UnitKind, unit_id: str) -> Any:
    """The project's standalone cycle or campaign, or 404. A campaign's cycle binds its
    campaign's snapshot, so it is refused with the unit to name instead."""
    try:
        if kind is UnitKind.CAMPAIGN:
            unit: Any = await get_campaign_registry(request).get_campaign(unit_id)
        else:
            unit = await get_cycle_registry(request).get_cycle(unit_id)
    except (CampaignNotFoundError, CycleNotFoundError):
        unit = None
    if unit is None or unit.project_id != project_id:
        raise http_error(404, "NOT_FOUND", f"no {kind.value} {unit_id} in {project_id}")
    if kind is UnitKind.CYCLE and getattr(unit, "campaign_id", None):
        raise http_error(
            422,
            "VALIDATION_ERROR",
            f"{unit_id} is campaign {unit.campaign_id}'s cycle, and binds the campaign's snapshot",
        )
    return unit


async def _snapshot(request: Request, kind: UnitKind, unit_id: str) -> Snapshot:
    store = get_memory_store(request)
    if store is None:
        raise http_error(503, "MEMORY_UNAVAILABLE", "the memory store is not configured")
    try:
        snapshot = await store.get_snapshot(kind, unit_id)
    except RecordIncompatible:
        raise http_error(
            409, "INCOMPATIBLE", f"{kind.value} {unit_id}'s snapshot can't be read by this version"
        ) from None
    if snapshot is None:
        raise http_error(404, "NOT_FOUND", f"{kind.value} {unit_id} pinned no snapshot")
    return snapshot


def _shown(s: Snapshot) -> dict[str, Any]:
    return {
        "unit_kind": s.unit_kind.value,
        "unit_id": s.unit_id,
        "snapshot_id": s.snapshot_id,
        "pinned_at": s.pinned_at.isoformat(),
        "instructions": [i.to_dict() for i in s.instructions],
        "instructions_unread": s.instructions_unread,
        "memory_context_withheld": s.context_withheld,
        "rebindings": [r.to_dict() for r in s.rebindings],
    }


@router.get("/{unit_kind}/{unit_id}")
async def get_unit_snapshot(
    request: Request,
    project_id: str,
    unit_kind: str,
    unit_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_READ)),
) -> SnapshotBindingResponse:
    """The unit's snapshot as it binds now, with every re-binding since its admission."""
    kind = _kind(unit_kind)
    await _unit(request, project_id, kind, unit_id)
    return SnapshotBindingResponse.model_validate(_shown(await _snapshot(request, kind, unit_id)))


async def _ended(request: Request, kind: UnitKind, unit: Any) -> bool:
    if kind is UnitKind.CAMPAIGN:
        return unit.state is CampaignState.COMPLETED
    cycles = get_cycle_registry(request)
    return cycle_status_of(unit, await cycles.list_runs(unit.cycle_id)) in _ENDED_CYCLE


@router.post("/{unit_kind}/{unit_id}/rebindings", status_code=201)
async def rebind_unit(
    request: Request,
    project_id: str,
    unit_kind: str,
    unit_id: str,
    body: RebindRequest,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_INSTRUCT)),
) -> RebindResponse:
    """Re-bind a running unit (§3.7): the record's permission and the unit's authority, both."""
    kind = _kind(unit_kind)
    if identity is None:
        raise http_error(401, "UNAUTHENTICATED", "a re-binding names who made it")
    authority = _AUTHORITY[kind]
    if authority not in frozenset(identity.scopes) | scopes_for_roles(identity.roles):
        raise http_error(
            403, "FORBIDDEN", f"a re-binding needs the {kind.value}'s authority too: {authority}"
        )
    unit = await _unit(request, project_id, kind, unit_id)
    if await _ended(request, kind, unit):
        raise http_error(409, "UNIT_ENDED", f"{kind.value} {unit_id} has ended: nothing follows it")
    snapshot = await _snapshot(request, kind, unit_id)
    records = get_memory_records(request)
    if records is None:
        raise http_error(
            503, "MEMORY_RECORDS_UNAVAILABLE", "the memory records' store is not configured"
        )
    record = await records.get(body.record_id)
    if record is None or record.project_id != project_id:
        raise http_error(404, "NOT_FOUND", f"no record {body.record_id} in {project_id}")
    store = get_memory_store(request)
    now = datetime.now(UTC)
    try:
        replacement = await _replacement(request, record, kind, project_id, unit_id, unit)
        updated = rebound(
            snapshot, record, by=identity.user_id, at=now, why=body.why, replacement=replacement
        )
    except RebindRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    # Only the check, the running cycles' bindings and the commit hold launches and the unit's
    # dispatches: the unit's own binding of the replacement, above, reads no cycle. #2545: no
    # dispatch composes between the check of what the unit's dispatches were handed and the write.
    async with _launches_held(request, kind), dispatch_turn(request, (kind, unit_id)):
        _refuse_handed(snapshot, body.record_id, await store.list_project_exposures(project_id))
        try:
            if kind is UnitKind.CAMPAIGN:
                await _bind_running_cycles(request, store, unit_id, replacement, now)
            await store.rebind_snapshot(updated, after=len(snapshot.rebindings))
        except SnapshotMoved as e:
            raise http_error(409, "CONFLICT", str(e)) from e
        except _CyclesUnbound as e:
            raise http_error(
                503,
                "CYCLES_UNBOUND",
                f"the campaign's running cycles couldn't bind the replacement ({e}); nothing was "
                "re-bound, so the re-binding can be sent again",
            ) from e
    rebinding = updated.rebindings[-1]
    entry_id = None
    if kind is UnitKind.CAMPAIGN:
        entry_id = await _record_on_control_log(request, identity, updated, rebinding)
    return RebindResponse.model_validate(
        {
            **_shown(updated),
            "rebinding": rebinding.to_dict(),
            "control_log_entry_id": entry_id,
            "next": _next(kind, rebinding, entry_id),
        }
    )


def _refuse_handed(snapshot: Snapshot, record_id: str, exposures: list[Any]) -> None:
    """Refuse (409) a re-binding when a dispatch of the unit was handed the revision it replaces."""
    handed = runs_handed(snapshot, record_id, exposures)
    if handed:
        runs = ", ".join(sorted({run_id for _, run_id in handed}))
        raise http_error(
            409,
            "RESTART_REQUIRED",
            f"{runs} dispatched with the revision being replaced, so the "
            f"{snapshot.unit_kind.value}'s later work would build on work done under it. Forward "
            "re-binding is for a unit none of whose dispatches had it; restart the work as a new "
            "standalone cycle or campaign, which binds the record's current revision (SIP-0110 "
            "Appendix A §3.7, §5u)",
        )


async def _replacement(
    request: Request, record: Any, kind: UnitKind, project_id: str, unit_id: str, unit: Any
) -> Any:
    """The record's current revision as this unit pins it, or ``None`` for a withdrawal or a
    revision with no applicability. #2179 T16: its ``@current`` references are bound for the unit,
    as its admission bound the old one's."""
    if record.status == RecordStatus.WITHDRAWN or record.current.applicability is None:
        return None
    return await bound_instruction(
        pinned_of(record),
        get_reference_resolvers(request),
        BindingContext(project_id, kind.value, unit_id, source_commit_of(unit)),
    )


class _CyclesUnbound(Exception):
    """A running cycle's binding of the replacement couldn't be made: the re-binding is refused."""


def _launches_held(request: Request, kind: UnitKind) -> AbstractAsyncContextManager[Any]:
    """§5ad: a campaign's re-binding holds its launches, from listing its running cycles until its
    snapshot names the new revision (``CampaignLaunchService.launches_held``). A cycle launched
    before is listed and bound; one launched after binds at the committed snapshot. Without it, a
    cycle launched in between bound the revision being replaced, and nothing bound the new one
    before its first task read it (the fifth read of #2570)."""
    if kind is not UnitKind.CAMPAIGN:
        return nullcontext()
    return get_campaign_launch(request).launches_held()


async def _bind_running_cycles(
    request: Request, store: Any, campaign_id: str, replacement: Any, now: datetime
) -> None:
    """§5ad: the replacement as each of the campaign's running cycles binds it, at the commit that
    cycle pins, stored **before** the snapshot names the new revision. Each revision is its own
    entry, so the cycle still holds the one being replaced, and a dispatch reading either revision
    finds its own: there is no moment between the snapshot and the cycles' entries.

    A cycle is running until it completes or is cancelled, so a paused one, which can resume, is
    bound too. A resolver's refusal is kept unbound with why. A fault (a resolver that fails, cycles
    that can't be read, an entry that can't be stored) raises, and the re-binding is refused with
    the snapshot unchanged. An entry already stored then names a revision no snapshot names, and is
    never read. A withdrawal binds nothing: the pin no longer holds the record."""
    if replacement is None or not names_current((replacement,)):
        return  # nothing a cycle binds for itself, so no cycle is read
    cycles = get_cycle_registry(request)
    resolvers = get_reference_resolvers(request)
    try:
        intents = await get_campaign_registry(request).launch_intents(campaign_id)
        for cycle_id in [
            i.cycle_id for i in intents if i.state is LaunchIntentState.LAUNCHED and i.cycle_id
        ]:
            cycle = await cycles.get_cycle(cycle_id)
            if cycle_status_of(cycle, await cycles.list_runs(cycle_id)) in _ENDED_CYCLE:
                continue
            bound = await instructions_bound_for((replacement,), resolvers, cycle_binding(cycle))
            if bound:
                await store.record_cycle_bindings(
                    cycle_id, UnitKind.CAMPAIGN.value, campaign_id, bound, now
                )
    except Exception as e:
        logger.warning("cycle_rebinding_unbound campaign=%s", campaign_id, exc_info=True)
        raise _CyclesUnbound(f"{type(e).__name__}: {e}") from e


async def _record_on_control_log(
    request: Request, identity: Identity, snapshot: Snapshot, rebinding: Rebinding
) -> str | None:
    replacement = rebinding.replacement
    return await record_on_control_log(
        request,
        identity,
        snapshot.unit_id,
        operation=ControlOperation.REBIND,
        reason=rebinding.why,
        idempotency_key=f"rebind:{snapshot.snapshot_id}:{len(snapshot.rebindings)}",
        target=rebinding.record_id,
        binding={
            "snapshot_id": snapshot.snapshot_id,
            "record_id": rebinding.record_id,
            "replaced_revision": rebinding.replaced.revision,
            "replacement_revision": replacement.revision if replacement else None,
        },
    )


def _next(kind: UnitKind, r: Rebinding, entry_id: str | None) -> str:
    bound = (
        f"revision {r.replacement.revision} of {r.record_id}"
        if r.replacement
        else f"no revision of {r.record_id}, withdrawn"
    )
    said = [
        f"the {kind.value}'s dispatches from now bind {bound}. Set its measurements apart from the "
        "first task this affects: the re-binding changed a listed input (SIP-0110 §0.12)."
    ]
    if kind is UnitKind.CAMPAIGN and entry_id is None:
        said.append(
            "The campaign's control log couldn't record it, so the intervention ledger can't see "
            "it: declare it there (POST /api/v1/intervention-ledgers/{campaign_id}/declared)."
        )
    return " ".join(said)
