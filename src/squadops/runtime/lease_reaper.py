"""
Stranded FocusLease hygiene (#373/#529 — the #672 activity sweeps, applied to leases).

`focus_leases` enforces one active lease per agent (§3.2, the partial unique
index), and #288 makes a same-mode `cycle` request from a *different* owner a
hard reject. Those two are correct together only while every lease is eventually
released. A run that dies, or is cancelled outside the executor's finalize path,
leaves its cycle leases held — with `expires_at = NULL`, so nothing reclaims
them — and every later cycle recruiting those agents pauses at admission with
`focus_lease_conflict` before dispatching a single task. Recovery is manual SQL
today. Two sweeps close the class, mirroring `activity_reaper`:

- :func:`release_owner_leases` — cancel / run finalize: the owning run is over,
  so any lease still held for it is stranded; release them all. This is the
  sweep the executor's ``recruited_agent_ids`` release cannot be: it clears
  leases the run *holds*, not just the ones one call *recorded*.
- :func:`reap_stale_leases` — sweep every held cycle lease whose owner is
  finished, for callers that cannot enumerate owners (rows stranded by a process
  death that skipped finalize, and historic rows predating the sweep).

Both drive the **coordinator**, not the lease port directly. A stranded lease
comes with a stranded ``mode = cycle``: releasing only the lease would leave the
agent pinned in `cycle`, where the next recruitment takes the #288 same-mode
path, finds no conflicting lease, and *idempotently skips* — admitted without
ever acquiring, so finalize releases nothing and the agent is lost mid-run to
the next owner. ``request_transition(…, "ambient")`` writes the mode and
releases the lease in one unit of work (§4.5/D25) and emits the canonical
events. A lease the transition did not clear — the agent was already `ambient`,
which the null-UoW path can produce when a mode write commits and its release
then fails — is released through the port afterwards, because the coordinator
has no transition that expresses that case.

Only `cycle` leases are swept. A `duty` lease's ``owner_ref`` is an assignment
id, not a run id, so a run-shaped predicate does not apply to it and a live duty
window must never be reaped by a question about runs.

Both are best-effort and per-row isolated, like ``admission.release_participants``:
one bad row never blocks clearing the rest, since a single stranded lease blocks
all of that agent's future recruitment.

Pure orchestration: depends only on the coordinator, the lease port, and
``runtime.reasons``. Run-status knowledge enters through the ``owner_is_finished``
predicate the composition root supplies — ``squadops.runtime`` never imports the
cycles domain (D26 direction).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from squadops.ports.runtime.focus_lease import FocusLeasePort
    from squadops.runtime.coordinator import RuntimeCoordinator
    from squadops.runtime.models import FocusLease

logger = logging.getLogger(__name__)

# The only owner type these sweeps clear. A `duty` lease is owned by an
# assignment window, not a run, and `ambient` holds no lease in v1.1 (§10.4).
_CYCLE_OWNER_TYPE: Final[str] = "cycle"


async def release_owner_leases(
    coordinator: RuntimeCoordinator,
    focus_lease: FocusLeasePort,
    owner_ref: str,
    *,
    reason_code: str,
) -> int:
    """Release every active cycle lease held for ``owner_ref``; return how many cleared.

    Cancel / run-finalize sweep: the owning run has no dispatch loop left to
    release what it took, so anything still held under its id is stranded.
    ``reason_code`` is explicit — the two call sites are different situations
    (`LEASE_STRANDED_AT_CANCEL` vs `LEASE_STRANDED_AT_RUN_FINALIZE`) and the
    reason is what an operator reads back off the transition.
    """
    released = 0
    for lease in await focus_lease.list_active_leases(owner_ref=owner_ref):
        if lease.owner_type != _CYCLE_OWNER_TYPE:
            continue
        if await _return_to_ambient(coordinator, focus_lease, lease, reason_code):
            released += 1
    return released


async def reap_stale_leases(
    coordinator: RuntimeCoordinator,
    focus_lease: FocusLeasePort,
    *,
    owner_is_finished: Callable[[str], Awaitable[bool]],
    reason_code: str,
) -> int:
    """Release every held cycle lease whose owner is finished; return how many cleared.

    ``owner_is_finished`` decides — this module deliberately does not equate
    "finished" with a terminal run status, because a run whose process was
    killed keeps a non-terminal status forever (#373). The caller knows what
    liveness means in its context; see ``api.runtime.startup_reaps``.

    Non-cycle leases are left alone (their ``owner_ref`` is not a run). A
    predicate or release failure skips that row only — the reaper must clear
    what it can.
    """
    reaped = 0
    for lease in await focus_lease.list_active_leases():
        if lease.owner_type != _CYCLE_OWNER_TYPE:
            continue
        try:
            if not await owner_is_finished(lease.owner_ref):
                continue
        except Exception:
            logger.warning(
                "liveness check for stranded lease %s (agent=%s, owner_ref=%s) failed",
                lease.lease_id,
                lease.agent_id,
                lease.owner_ref,
                exc_info=True,
            )
            continue
        if await _return_to_ambient(coordinator, focus_lease, lease, reason_code):
            reaped += 1
    return reaped


async def _return_to_ambient(
    coordinator: RuntimeCoordinator,
    focus_lease: FocusLeasePort,
    lease: FocusLease,
    reason_code: str,
) -> bool:
    """Return one agent to ambient and clear ``lease``; True iff the lease is gone.

    The coordinator transition is the primary path — it writes ``mode`` and
    releases the lease atomically (§4.5/D25). The port release that follows is
    the residue handler, not a second path: it fires only when the agent was
    already `ambient`, where ``request_transition`` is a same-mode idempotent
    skip that never reaches lease arbitration and so leaves the lease held.

    A *different* lease occupying the agent's slot afterwards means ours was
    released and someone re-acquired; that counts as cleared and is left alone.
    """
    try:
        await coordinator.request_transition(
            lease.agent_id,
            "ambient",
            reason_code,
            requester_kind="coordinator",
            owner_ref=lease.owner_ref,
        )
    except Exception:
        logger.warning(
            "best-effort ambient transition for stranded lease %s (agent=%s) failed",
            lease.lease_id,
            lease.agent_id,
            exc_info=True,
        )

    try:
        current = await focus_lease.get_current_lease(lease.agent_id)
        if current is not None and current.lease_id == lease.lease_id:
            await focus_lease.release_lease(lease.lease_id, reason_code)
            current = await focus_lease.get_current_lease(lease.agent_id)
        cleared = current is None or current.lease_id != lease.lease_id
    except Exception:
        logger.warning(
            "best-effort release of stranded lease %s (agent=%s, owner_ref=%s) failed",
            lease.lease_id,
            lease.agent_id,
            lease.owner_ref,
            exc_info=True,
        )
        return False

    if cleared:
        logger.info(
            "released stranded focus lease %s (agent=%s, owner_ref=%s, reason=%s)",
            lease.lease_id,
            lease.agent_id,
            lease.owner_ref,
            reason_code,
        )
    return cleared
