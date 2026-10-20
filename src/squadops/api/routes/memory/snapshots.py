"""``/api/v1/projects/{project_id}/snapshots``: a unit's snapshot as it binds now, and its
re-binding (SIP-0110 Appendix A §3.7; #2179 stage 2).

- **read** (``memory:read``): a standalone cycle's or a campaign's snapshot: the project
  instructions it binds, and every re-binding since its admission;
- **re-bind** (``memory:instruct`` with the unit's authority: ``cycles:write`` for a standalone
  cycle, ``campaigns:supervise`` for a campaign): replace a bound project instruction's revision
  with the record's current one, or remove it when the record is withdrawn.

A re-binding goes forward: the unit's next dispatch binds the new revision. A run still running
that was handed the replaced revision is halted first, so the route refuses until it has ended. An
ended one is history: it is named, never resumed, and its measurements are set apart. A campaign's
re-binding is a row in its control log, which the intervention ledger reads (SIP-0113 §4.3).
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
from squadops.api.routes.campaigns.campaigns import actor_from
from squadops.api.routes.cycles.mapping import cycle_status_of
from squadops.api.runtime.deps import (
    get_campaign_registry,
    get_cycle_registry,
    get_memory_records,
    get_memory_store,
)
from squadops.auth.models import Identity, Scope, scopes_for_roles
from squadops.campaigns.models import (
    CampaignNotFoundError,
    CampaignState,
    CampaignTransition,
    ControlOperation,
)
from squadops.cycles.lifecycle import TERMINAL_STATES
from squadops.cycles.models import CycleNotFoundError, CycleStatus, RunStatus
from squadops.memory.lessons import Snapshot, UnitKind
from squadops.memory.rebinding import RebindRefused, rebound, runs_handed
from squadops.memory.records import Rebinding
from squadops.ports.memory.cross_cycle import RecordIncompatible, SnapshotMoved

router = APIRouter(prefix="/api/v1/projects/{project_id}/snapshots", tags=["memory"])
logger = logging.getLogger(__name__)

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


async def _still_running(request: Request, runs: list[tuple[str, str]]) -> list[str]:
    """The runs that haven't ended. A run that can't be read counts as running: a re-binding
    would rather wait for one run too many than carry a run's work across a changed binding."""
    cycles = get_cycle_registry(request)
    running = []
    for _, run_id in runs:
        try:
            ended = RunStatus((await cycles.get_run(run_id)).status) in TERMINAL_STATES
        except Exception:  # noqa: BLE001 — unreadable counts as running
            ended = False
        if not ended:
            running.append(run_id)
    return running


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
    running = await _still_running(request, handed)
    if running:
        one = len(running) == 1
        raise http_error(
            409,
            "RESTART_REQUIRED",
            f"{', '.join(running)} {'was' if one else 'were'} handed the revision being replaced "
            f"and {'is' if one else 'are'} still running: halt {'it' if one else 'them'} first, "
            "and the next run restarts under the new binding (SIP-0110 Appendix A §3.7, §3.8)",
        )
    now = datetime.now(UTC)
    try:
        updated = rebound(
            snapshot, record, by=identity.user_id, at=now, why=body.why,
            received_by=[run_id for _, run_id in handed],
        )  # fmt: skip
        await store.rebind_snapshot(updated, after=len(snapshot.rebindings))
    except RebindRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    except SnapshotMoved as e:
        raise http_error(409, "CONFLICT", str(e)) from e
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


async def _record_on_control_log(
    request: Request, identity: Identity, snapshot: Snapshot, rebinding: Rebinding
) -> str | None:
    """The campaign's control-log row, or ``None`` when it couldn't be written: the re-binding
    stands either way, and the answer says the row is missing."""
    actor, role = actor_from(identity)
    replacement = rebinding.replacement
    transition = CampaignTransition(
        operation=ControlOperation.REBIND,
        actor=actor,
        actor_role=role,
        reason=rebinding.why,
        idempotency_key=f"rebind:{snapshot.snapshot_id}:{len(snapshot.rebindings)}",
        next_state=None,
        target=rebinding.record_id,
        binding={
            "snapshot_id": snapshot.snapshot_id,
            "record_id": rebinding.record_id,
            "replaced_revision": rebinding.replaced.revision,
            "replacement_revision": replacement.revision if replacement else None,
            "received_by": list(rebinding.received_by),
        },
    )
    try:
        result = await get_campaign_registry(request).transition(snapshot.unit_id, transition)
    except Exception:  # noqa: BLE001 — a missing row is said, never implied
        logger.warning("memory_rebind_not_logged campaign=%s", snapshot.unit_id, exc_info=True)
        return None
    return result.entry.entry_id


def _next(kind: UnitKind, r: Rebinding, entry_id: str | None) -> str:
    bound = (
        f"revision {r.replacement.revision} of {r.record_id}"
        if r.replacement
        else f"no revision of {r.record_id}, withdrawn"
    )
    said = [
        f"the {kind.value}'s later dispatches bind {bound}. Its measurements are set apart from "
        f"{r.at.isoformat()}: the re-binding changed a listed input (SIP-0110 §0.12)."
    ]
    if r.received_by:
        said.append(
            f"{', '.join(r.received_by)} had been handed revision {r.replaced.revision}: their "
            "history is kept and never resumed, so the work goes on in a new run."
        )
    if kind is UnitKind.CAMPAIGN and entry_id is None:
        said.append(
            "The campaign's control log couldn't record it: until a row is written, the "
            "intervention ledger doesn't see this re-binding."
        )
    return " ".join(said)
