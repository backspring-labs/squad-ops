"""Derive-on-read of the per-cycle ``CycleOutcome`` roll-up (SIP-0096 §10, Phase 3).

The cycle-level analogue of ``lifecycle.derive_cycle_status``: rather than persist a
roll-up at a cycle-completion seam (there is none — a cycle's terminal state is itself
derived on read), we compute the ``CycleOutcome`` on demand from the durable per-run
``RunVerificationSummary`` rows (slice 2a) via the pure ``aggregate_cycle_outcome``.

Thin I/O orchestration only — one registry read, then the pure choke point. Reusable
by every consumer (cycle-detail API here; wrap-up, gates, and the 1.6 Campaign
continuation decision later).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from squadops.cycles.inert_detection import (
    INERT_CYCLE_THRESHOLD_DEFAULT,
    INERT_LOOKBACK_CYCLES,
    cycle_check_state,
    detect_inert_checks,
)
from squadops.cycles.replay import (
    REPLAY_COMPATIBILITY_ELEMENTS,
    parse_replay_declaration,
)
from squadops.cycles.verification_integrity import (
    CycleOutcome,
    ReplayProvenance,
    WaivedCheck,
    aggregate_cycle_outcome,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from squadops.cycles.models import Cycle
    from squadops.cycles.verification_integrity import RunVerificationSummary
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort

logger = logging.getLogger(__name__)


def _configured_inert_threshold() -> int:
    """The §9 N from config, or the SIP default when config isn't loaded.

    ``SQUADOPS__CYCLES__INERT_CYCLE_THRESHOLD`` in deployments; library/test use
    without a loaded config falls back to the same declared default (a drift
    test pins the schema default to the constant).
    """
    from squadops.config import get_config

    try:
        return get_config().cycles.inert_cycle_threshold
    except RuntimeError:
        return INERT_CYCLE_THRESHOLD_DEFAULT


async def _collect_inert(
    registry: CycleRegistryPort,
    cycle: Cycle,
    current_summaries: Sequence[RunVerificationSummary],
    threshold: int,
) -> tuple[str, ...]:
    """Walk the cycle's prior same-project/profile cycles for §9 streaks (#684).

    Series scope is strict: same ``project_id`` + ``squad_profile_id`` +
    ``request_profile``, created strictly before the perspective cycle — cross-
    profile history could accrue streaks against checks with different
    applicability (false inerts). The walk consults at most
    ``INERT_LOOKBACK_CYCLES`` prior cycles (``list_cycles`` returns newest
    first — the port's ordering contract); a streak not resolvable within the
    window is not flagged.
    """
    cycles = await registry.list_cycles(cycle.project_id, limit=50)
    series = [
        c
        for c in cycles
        if c.cycle_id != cycle.cycle_id
        and c.created_at < cycle.created_at
        and c.squad_profile_id == cycle.squad_profile_id
        and c.request_profile == cycle.request_profile
    ][:INERT_LOOKBACK_CYCLES]
    states = [cycle_check_state(current_summaries)]
    for prior in series:
        states.append(
            cycle_check_state(await registry.list_run_verification_summaries(prior.cycle_id))
        )
    return detect_inert_checks(states, threshold=threshold)


async def resolve_cycle_outcome(
    registry: CycleRegistryPort,
    cycle_id: str,
    *,
    inert_threshold: int | None = None,
) -> CycleOutcome:
    """Derive a cycle's ``CycleOutcome`` from its persisted per-run summaries (§10).

    ``waived`` (#682): populated from the cycle's recorded gate decisions — an
    operator accept-with-waiver sits beside the verdict, never altering it (§6.5).

    ``inert`` (#684, §9): chronic not-executed streaks derived by walking prior
    same-project/profile cycles' summaries — disclosure-only enrichment, so a
    history-read failure logs and yields an empty list, never a failed roll-up;
    the verdict and the #683 confidence ceiling never depend on it.
    ``inert_threshold`` overrides the configured N (tests; ``None`` = config).

    SIP-0101 Slice 3.4: a replay-mode cycle's outcome carries ``ReplayProvenance``
    derived from the immutable, create-time-validated declaration — same
    derive-on-read philosophy as the rest of this module, so a replayed outcome
    can never render unmarked regardless of which consumer asks.
    """
    summaries = await registry.list_run_verification_summaries(cycle_id)
    cycle = await registry.get_cycle(cycle_id)
    # #682: operator gate waivers (§6.5) — collected off the cycle's recorded
    # gate decisions, one WaivedCheck per waived id, decided_by as provenance.
    runs = await registry.list_runs(cycle_id)
    waived = [
        WaivedCheck(check_id=check_id, reason=gd.waiver_reason or "", waived_by=gd.decided_by)
        for run in runs
        for gd in run.gate_decisions
        for check_id in gd.waived_checks
    ]
    replay_req = parse_replay_declaration(cycle.execution_overrides or {})
    replay = (
        ReplayProvenance(
            source_run_id=replay_req.source_run_id,
            boundary_index=replay_req.boundary_index,
            compatibility_set=REPLAY_COMPATIBILITY_ELEMENTS,
        )
        if replay_req is not None
        else None
    )
    try:
        threshold = (
            inert_threshold if inert_threshold is not None else _configured_inert_threshold()
        )
        inert = await _collect_inert(registry, cycle, summaries, threshold)
    except Exception:
        logger.warning("inert-check detection failed for %s", cycle_id, exc_info=True)
        inert = ()
    return aggregate_cycle_outcome(summaries, waived=waived, inert=inert, replay=replay)
