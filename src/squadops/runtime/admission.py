"""
Cycle recruitment admission through the coordinator — SIP-0089 §3.5.

After the §2.5 reserve-buffer guard (:func:`squadops.runtime.recruitment.reserve_buffer_decision`)
admits a run, this module routes each participating agent through the
:class:`~squadops.runtime.coordinator.RuntimeCoordinator` to transition
``ambient → cycle``. The cycle FocusLease rides that mode write (§3.4,
``_owner_type_for_mode("cycle")``), so recruitment never touches the lease
directly — the coordinator stays the sole lease arbiter and mode writer (D16).

A lease conflict **defers** the run: the coordinator returns a typed
``focus_lease_*`` reason, which the executor surfaces on the existing
``RUN_PAUSED`` payload — no new ``cycle.recruitment.rejected`` EventType (the
§2.5 / #222 locked-taxonomy precedent).

Partial admission is rolled back. If agent *N* conflicts after agents *1..N-1*
already entered ``cycle``, those are returned to ``ambient`` before deferring, so
a deferred run never strands an agent in ``cycle`` mode. Release is symmetric:
on run finalize the executor releases exactly the agents it recruited
(``applied`` transitions only — an agent already in ``cycle`` for another run is
left alone). Both paths are **best-effort** compensation in v1.1; the
single-Postgres-transaction wrapping (D25) is #244, gated on this work.

Pure orchestration: depends only on the coordinator (a runtime-domain object) and
``runtime.reasons`` — never on ``adapters.*`` (D26). The executor (an adapter)
imports *down* into this module, never the reverse.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from squadops.runtime import reasons

if TYPE_CHECKING:
    from collections.abc import Sequence

    from squadops.runtime.coordinator import RuntimeCoordinator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdmissionResult:
    """Outcome of routing a run's participants through the coordinator.

    ``admitted=True`` → every participant holds a cycle lease (or already did);
    ``recruited_agent_ids`` are the agents this call transitioned ``ambient →
    cycle`` and therefore the agents the caller must release on finalize.

    ``admitted=False`` → a participant's lease conflicts; the run defers.
    ``blocking_agent_id`` / ``reason`` are populated and any agents recruited
    earlier in the same call have already been rolled back to ``ambient``
    (so ``recruited_agent_ids`` is empty).
    """

    admitted: bool
    blocking_agent_id: str | None = None
    reason: str | None = None
    recruited_agent_ids: tuple[str, ...] = field(default_factory=tuple)


async def admit_participants(
    coordinator: RuntimeCoordinator,
    participating_agent_ids: Sequence[str],
    *,
    owner_ref: str,
) -> AdmissionResult:
    """Acquire a cycle FocusLease for each participant via an ``ambient → cycle`` transition.

    Agents are processed in a deterministic (sorted) order so a conflict reports
    the same blocking agent across retries. Per agent:

      * ``applied`` → recruited (release it on finalize);
      * ``idempotent_skip`` → already in ``cycle`` (replay or another owner) —
        admitted, but **not** recorded as recruited-by-us, so finalize won't
        release a lease we didn't take;
      * rejected → defer: roll back everyone recruited so far, then return the
        coordinator's typed reason (a ``focus_lease_*`` code).

    ``owner_ref`` identifies the lease owner (the run/cycle id); the coordinator
    derives a stable lease idem key from it, so retrying the same run replays the
    same leases rather than minting duplicates.
    """
    recruited: list[str] = []
    for agent_id in sorted(participating_agent_ids):
        outcome = await coordinator.request_transition(
            agent_id,
            "cycle",
            reasons.CYCLE_RECRUITED,
            requester_kind="external",
            owner_ref=owner_ref,
        )
        if outcome.applied:
            recruited.append(agent_id)
        elif outcome.idempotent_skip:
            continue
        else:
            await release_participants(coordinator, recruited, owner_ref=owner_ref)
            return AdmissionResult(
                admitted=False,
                blocking_agent_id=agent_id,
                reason=outcome.rejected_reason or reasons.FOCUS_LEASE_CONFLICT,
            )
    return AdmissionResult(admitted=True, recruited_agent_ids=tuple(recruited))


async def release_participants(
    coordinator: RuntimeCoordinator,
    agent_ids: Sequence[str],
    *,
    owner_ref: str,
) -> None:
    """Return recruited agents to ``ambient`` (``cycle → ambient``, releasing the lease).

    Called on run finalize (completed/failed/paused) and for partial-admission
    rollback. Best-effort and per-agent isolated: a failure releasing one agent
    is logged and never blocks releasing the rest, since a stranded cycle lease
    would block *all* of that agent's future recruitment.
    """
    for agent_id in agent_ids:
        try:
            await coordinator.request_transition(
                agent_id,
                "ambient",
                reasons.CYCLE_COMPLETED,
                requester_kind="external",
                owner_ref=owner_ref,
            )
        except Exception:
            logger.warning(
                "best-effort release of cycle recruitment failed for agent %s (owner_ref=%s)",
                agent_id,
                owner_ref,
                exc_info=True,
            )
