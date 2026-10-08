"""The repeat report (SIP-0110 §0.4; slice 3b, the 2.2 plan's D14).

It counts what recurs across **independent** units: a retry and the cycle it retries are one
lineage and count once (SIP-0109's retries carry their predecessor, ``prior_cycle``), and a
proposal's versions are one proposal. Two readings stay apart:
- **repeated shapes:** a correction round's failing cases, by the shape the runner's table
  matched; a plan review's refusing validators; a returned proposal's class. Each is a signature
  the records show, and a repeated one is a candidate, never a finding;
- **recurring target behaviors:** only where the auditor substantiated a target behavior in each
  case from the round's artifacts. Slice 3d records those; until then this reading is empty, and
  says so rather than promoting a signature.

Pure: the script ``memory_repeat_report.py`` reads the observations and the lineage.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from squadops.memory.observations import Observation, ObservationSource


@dataclass(frozen=True)
class RepeatRow:
    """One signature and where it occurred."""

    source: str
    signature: str
    #: Independent units: retry lineages for a cycle's observations, proposals for a ruling's.
    independent_cycles: int
    cycles: tuple[str, ...]
    campaigns: tuple[str, ...]
    observations: int


def root_of(cycle_id: str, prior: Mapping[str, str]) -> str:
    """The first cycle of ``cycle_id``'s retry lineage. ``prior`` maps a retry to the cycle it
    retries. A cycle with no predecessor is its own root; a cycle met twice ends the walk."""
    seen = {cycle_id}
    while cycle_id in prior and prior[cycle_id] not in seen:
        cycle_id = prior[cycle_id]
        seen.add(cycle_id)
    return cycle_id


def independent_unit(observation: Observation, prior: Mapping[str, str]) -> str:
    """What counts once. A returned proposal counts by its proposal: its versions are revisions,
    the within-unit rung (SIP-0109 §9.2), reported apart (§0.11). A cycle's observations count by
    its retry lineage."""
    if observation.source is ObservationSource.PROPOSAL_RULING:
        return f"proposal:{observation.campaign_id}:{observation.evidence.get('proposal_id')}"
    if observation.cycle_id:
        return root_of(observation.cycle_id, prior)
    return f"run:{observation.run_id}"


def _signatures(observation: Observation) -> list[str]:
    if observation.source is ObservationSource.CORRECTION_ROUND:
        shapes = observation.evidence.get("failure_shapes") or []
        return sorted({f"{s.get('runner')}:{s.get('shape')}" for s in shapes if s.get("shape")})
    if not observation.classification.is_classified:
        return []
    return [
        f"{observation.classification.vocabulary}:{v}" for v in observation.classification.values
    ]


def repeated_signatures(
    observations: Iterable[Observation], prior: Mapping[str, str], *, minimum: int = 2
) -> list[RepeatRow]:
    """Every signature seen in at least ``minimum`` independent units, most widespread first."""
    occurrences: dict[tuple[str, str], list[Observation]] = {}
    for observation in observations:
        for signature in _signatures(observation):
            occurrences.setdefault((observation.source.value, signature), []).append(observation)
    rows = []
    for (source, signature), seen in occurrences.items():
        units = {independent_unit(o, prior) for o in seen}
        if len(units) < minimum:
            continue
        rows.append(
            RepeatRow(
                source=source,
                signature=signature,
                independent_cycles=len(units),
                cycles=tuple(sorted({o.cycle_id or f"run:{o.run_id}" for o in seen})),
                campaigns=tuple(sorted({o.campaign_id for o in seen if o.campaign_id})),
                observations=len(seen),
            )
        )
    return sorted(rows, key=lambda r: (-r.independent_cycles, r.source, r.signature))
