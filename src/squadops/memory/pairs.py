"""Whether two units built as a pair were handed the same bindings (SIP-0110 Appendix A §3.7, T16).

A paired comparison's arms, such as a lesson comparison's lessons-on and lessons-disabled units, are
read against each other. So each must be handed the same requirements, or a difference between
their results is the binding's and reads as the arms'. §3.7 says it plainly: "A pair whose arms
carry different bound revisions is invalid."

An arm's bindings are what its unit pinned and bound, read from the store:
- each project instruction its snapshot pinned, by record and revision;
- each task instruction its cycle was given, by text and the task types it selects;
- each reference either binds, by what it names, at the revision and digest it was bound to.

For a standalone cycle that is its own snapshot. A campaign's cycle reads its campaign's snapshot,
with its own bindings of the ``@current`` references (§5ad). Two arms that differ anywhere are an
invalid pair, and every difference is named, since the first alone would hide the rest.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from squadops.memory.lessons import UnitKind
from squadops.memory.records import Reference

if TYPE_CHECKING:
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.memory.cross_cycle import CrossCycleMemoryStorePort
    from squadops.ports.memory.records import MemoryRecordsPort


class PairUnreadable(Exception):
    """An arm whose bindings can't be read: its unit pinned no snapshot."""


@dataclass(frozen=True)
class ArmBindings:
    """One arm's bindings, keyed so two arms compare by what they name."""

    cycle_id: str
    #: Each pinned project instruction's revision, by record.
    project: Mapping[str, int]
    #: Each task instruction the cycle was given, as its text and the task types it selects.
    task: frozenset[tuple[str, tuple[str, ...]]]
    #: What each reference names (its ref before ``@``), and every revision and digest it was bound
    #: to in this arm.
    references: Mapping[str, frozenset[tuple[str, str | None]]]


def arm_bindings(
    cycle_id: str,
    pinned: Iterable,
    task_instructions: Iterable[tuple[str, tuple[str, ...], Iterable[Reference]]],
) -> ArmBindings:
    """An arm's bindings from its pinned project instructions and its cycle's task instructions,
    each task instruction as its text, its task types and its references."""
    pinned = list(pinned)
    task_instructions = list(task_instructions)
    references: dict[str, set[tuple[str, str | None]]] = {}
    for reference in [r for p in pinned for r in p.references] + [
        r for _, _, refs in task_instructions for r in refs
    ]:
        named, _, revision = reference.ref.rpartition("@")
        references.setdefault(named or reference.ref, set()).add((revision, reference.digest))
    return ArmBindings(
        cycle_id=cycle_id,
        project={p.record_id: p.revision for p in pinned},
        task=frozenset((text, tuple(sorted(types))) for text, types, _ in task_instructions),
        references={k: frozenset(v) for k, v in references.items()},
    )


def pair_differences(a: ArmBindings, b: ArmBindings) -> list[str]:
    """Every way ``a`` and ``b`` were handed different bindings; none when the pair is valid."""
    found: list[str] = []
    for record in sorted(set(a.project) | set(b.project)):
        mine, theirs = a.project.get(record), b.project.get(record)
        if mine != theirs:
            found.append(
                f"project instruction {record}: {_revision(mine)} in {a.cycle_id}, "
                f"{_revision(theirs)} in {b.cycle_id}"
            )
    for arm, other in ((a, b), (b, a)):
        for text, types in sorted(arm.task - other.task):
            found.append(
                f"task instruction for {', '.join(types)} given to {arm.cycle_id} only: {text[:80]}"
            )
    for named in sorted(set(a.references) | set(b.references)):
        mine, theirs = a.references.get(named, frozenset()), b.references.get(named, frozenset())
        if mine != theirs:
            found.append(
                f"{named}: bound {_bound(mine)} in {a.cycle_id}, {_bound(theirs)} in {b.cycle_id}"
            )
    return found


async def read_arm(
    cycle_id: str,
    *,
    project_id: str,
    store: CrossCycleMemoryStorePort,
    records: MemoryRecordsPort,
    cycles: CycleRegistryPort,
) -> ArmBindings:
    """An arm's bindings, as its unit pinned them and its cycle bound its references.

    Raises:
        PairUnreadable: the arm's unit pinned no snapshot.
    """
    cycle = await cycles.get_cycle(cycle_id)
    if cycle.campaign_id:
        snapshot = await store.get_snapshot(UnitKind.CAMPAIGN, cycle.campaign_id)
        binding = await store.get_cycle_binding(cycle_id)
        own = {(p.record_id, p.revision): p for p in (binding.instructions if binding else ())}
        pinned = (
            [own.get((p.record_id, p.revision), p) for p in snapshot.instructions]
            if snapshot
            else []
        )
    else:
        snapshot = await store.get_snapshot(UnitKind.CYCLE, cycle_id)
        pinned = list(snapshot.instructions) if snapshot else []
    if snapshot is None:
        raise PairUnreadable(f"{cycle_id}'s unit pinned no snapshot, so its bindings can't be read")
    given = [
        (r.current.body, tuple(r.current.target.task_types), r.current.references)
        for r in await records.list_project(project_id)
        if r.current.target is not None and r.current.target.cycle_id == cycle_id
    ]
    return arm_bindings(cycle_id, pinned, given)


def _revision(revision: int | None) -> str:
    return "not pinned" if revision is None else f"revision {revision}"


def _bound(bound: frozenset[tuple[str, str | None]]) -> str:
    if not bound:
        return "nothing"
    return ", ".join(
        f"@{revision[:12]} ({(digest or 'no digest')[:19]})"
        for revision, digest in sorted(bound, key=str)
    )
