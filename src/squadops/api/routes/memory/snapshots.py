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
from squadops.api.routes.memory.interventions import record_on_control_log
from squadops.api.runtime.deps import (
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
from squadops.memory.cycle_bindings import CycleBinding, instructions_bound_for, replacing
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
    handed = runs_handed(snapshot, body.record_id, await store.list_project_exposures(project_id))
    if handed:
        runs = ", ".join(sorted({run_id for _, run_id in handed}))
        raise http_error(
            409,
            "RESTART_REQUIRED",
            f"{runs} dispatched with the revision being replaced, so the {kind.value}'s later work "
            "would build on work done under it. Forward re-binding is for a unit none of whose "
            "dispatches had it; restart the work as a new standalone cycle or campaign, which "
            "binds the record's current revision (SIP-0110 Appendix A §3.7, §5u)",
        )
    now = datetime.now(UTC)
    try:
        replacement = None
        if record.status != RecordStatus.WITHDRAWN and record.current.applicability is not None:
            # #2179 T16: the new revision's ``@current`` references are bound for this unit, as
            # its admission bound the old one's.
            replacement = await bound_instruction(
                pinned_of(record),
                get_reference_resolvers(request),
                BindingContext(project_id, kind.value, unit_id, source_commit_of(unit)),
            )
        updated = rebound(
            snapshot, record, by=identity.user_id, at=now, why=body.why, replacement=replacement
        )
        await store.rebind_snapshot(updated, after=len(snapshot.rebindings))
    except RebindRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    except SnapshotMoved as e:
        raise http_error(409, "CONFLICT", str(e)) from e
    rebinding = updated.rebindings[-1]
    entry_id = None
    if kind is UnitKind.CAMPAIGN:
        entry_id = await _record_on_control_log(request, identity, updated, rebinding)
        await _rebind_running_cycles(request, unit_id, record.record_id, replacement, now)
    return RebindResponse.model_validate(
        {
            **_shown(updated),
            "rebinding": rebinding.to_dict(),
            "control_log_entry_id": entry_id,
            "next": _next(kind, rebinding, entry_id),
        }
    )


async def _rebind_running_cycles(
    request: Request, campaign_id: str, record_id: str, replacement: Any, now: datetime
) -> None:
    """§5ad: a campaign's re-bound revision reaches its running cycles as each binds it, at the
    commit that cycle pins. Its later cycles bind it at their launch.

    The snapshot is re-bound and its control-log row written before this runs, and nothing here
    fails the response. A cycle that can't be rebound now is logged, and the launcher's next drain
    fills it (``_reconcile_bindings``). Until then a required reference holds its task rather than
    reading the revision the re-binding replaced."""
    try:
        store = get_memory_store(request)
        cycles = get_cycle_registry(request)
        resolvers = get_reference_resolvers(request)
        intents = await get_campaign_registry(request).launch_intents(campaign_id)
    except Exception:  # noqa: BLE001 — the drain fills what this couldn't
        logger.warning("cycle_rebinding_unread campaign=%s", campaign_id, exc_info=True)
        return
    launched = [i.cycle_id for i in intents if i.state is LaunchIntentState.LAUNCHED and i.cycle_id]
    for cycle_id in launched:
        try:
            cycle = await cycles.get_cycle(cycle_id)
            if cycle_status_of(cycle, await cycles.list_runs(cycle_id)) in _ENDED_CYCLE:
                continue  # a paused cycle can resume, so it is rebound
            bound = (
                await instructions_bound_for((replacement,), resolvers, cycle_binding(cycle))
                if replacement is not None
                else ()
            )
            held = await store.get_cycle_binding(cycle_id)
            if held is None and not bound:
                continue  # the cycle reads the campaign's pin, which now holds the revision
            base = held or CycleBinding(cycle_id, UnitKind.CAMPAIGN.value, campaign_id, (), now)
            await store.record_cycle_binding(replacing(base, {record_id}, bound, at=now))
        except Exception:  # noqa: BLE001 — the drain fills what this couldn't
            logger.warning(
                "cycle_rebinding_failed cycle=%s record=%s", cycle_id, record_id, exc_info=True
            )


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
