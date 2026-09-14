"""Re-grade the benchmark registry's declared rolls from the stores (SIP-0108 §4.3).

The I/O half of ``squadops.cycles.benchmark_registry``. For each declared roll it reads the
cycle and its evidence once, runs the preflight on them, and assesses only what the preflight
admits. The assessment is the same projection a live cycle gets (``assess``), and its references
are resolved back against the same two stores. A refused roll is kept as a row that names its
refusals, never dropped: the preflight states which rolls are re-gradeable and why the rest are
not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.cycles.cycle_evidence import assemble_cycle_evidence, unresolved_refs
from squadops.cycles.benchmark_registry import (
    BenchmarkRoll,
    BenchmarkRow,
    lineage_for,
    preflight,
)
from squadops.cycles.cycle_assessment import assess
from squadops.cycles.cycle_outcome import resolve_cycle_outcome
from squadops.cycles.lineage import series_for
from squadops.cycles.models import CycleNotFoundError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from squadops.cycles.cycle_assessment import AssessorIdentity
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort


async def regrade_roll(
    registry: CycleRegistryPort,
    vault: ArtifactVaultPort,
    roll: BenchmarkRoll,
    *,
    assessor: AssessorIdentity,
) -> BenchmarkRow:
    try:
        cycle = await registry.get_cycle(roll.cycle_id)
    except CycleNotFoundError:
        return BenchmarkRow(roll=roll, preflight=preflight(roll, None, None))
    evidence = await assemble_cycle_evidence(registry, vault, roll.cycle_id)
    reading = preflight(roll, cycle, evidence)
    row = BenchmarkRow(
        roll=roll,
        preflight=reading,
        series=series_for(cycle),
        lineage=lineage_for(roll, cycle),
    )
    if not reading.gradeable:
        return row
    outcome = await resolve_cycle_outcome(registry, roll.cycle_id)
    assessment = assess(outcome, evidence, assessor=assessor)
    missing = await unresolved_refs(assessment, registry, vault)
    return BenchmarkRow(
        roll=row.roll,
        preflight=row.preflight,
        series=row.series,
        lineage=row.lineage,
        assessment=assessment,
        unresolved_refs=tuple(missing),
    )


async def regrade(
    registry: CycleRegistryPort,
    vault: ArtifactVaultPort,
    rolls: Iterable[BenchmarkRoll],
    *,
    assessor: AssessorIdentity,
) -> tuple[BenchmarkRow, ...]:
    """Every declared roll's row, in declaration order."""
    return tuple([await regrade_roll(registry, vault, r, assessor=assessor) for r in rolls])
