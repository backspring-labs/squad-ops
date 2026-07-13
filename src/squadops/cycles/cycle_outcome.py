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

from typing import TYPE_CHECKING

from squadops.cycles.verification_integrity import CycleOutcome, aggregate_cycle_outcome

if TYPE_CHECKING:
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort


async def resolve_cycle_outcome(registry: CycleRegistryPort, cycle_id: str) -> CycleOutcome:
    """Derive a cycle's ``CycleOutcome`` from its persisted per-run summaries (§10).

    ``waived`` (operator gate waivers, §6.5) and ``inert`` (chronic not-executed, §9)
    stay empty until their Phase-3 slices wire them — the roll-up shape carries them,
    but there is no source yet, so we pass nothing rather than fabricate.
    """
    summaries = await registry.list_run_verification_summaries(cycle_id)
    return aggregate_cycle_outcome(summaries)
