"""A campaign cycle's own bindings of its campaign's pinned instructions (SIP-0110 §5ad; #2179 T16).

The owner's ruling of 2026-10-20 resolved §5z's conflict with SIP-0112 §B.5.1:
- **The campaign's snapshot keeps fixing which instruction revisions are in force,** shared by every
  cycle (§0.7, §5t).
- **Each cycle binds their ``@current`` references at its own pinned source commit** when the campaign
  launches it. The binding is recorded with the cycle, and every dispatch of the cycle reads it. It is
  never bound at dispatch.

A campaign has no source context of its own, so its snapshot leaves a repository reference unbound
(§5z). A cycle has one, so the instructions are comparable across the campaign, and the files they
point at are the ones the cycle's code comes from.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING

from squadops.memory.records import PinnedInstruction, is_current
from squadops.memory.reference_binding import bound_instruction

if TYPE_CHECKING:
    from squadops.memory.references import BindingContext
    from squadops.ports.memory.references import ReferenceResolverPort


@dataclass(frozen=True)
class CycleBinding:
    """One campaign cycle's bindings, as read: each of its campaign's pinned instructions that names
    an ``@current`` reference, as this cycle bound it, one per record and revision. Read by record
    and revision, so a re-bound revision is never read under the old one's binding."""

    cycle_id: str
    unit_kind: str
    unit_id: str
    instructions: tuple[PinnedInstruction, ...]
    bound_at: datetime


def names_current(pinned: Iterable[PinnedInstruction]) -> bool:
    """Whether any of ``pinned`` names a reference still written ``@current``: only then can a
    cycle's binding differ from its campaign's pin."""
    return any(is_current(r.ref) for p in pinned for r in p.references)


async def instructions_bound_for(
    pinned: Iterable[PinnedInstruction],
    resolvers: Mapping[str, ReferenceResolverPort],
    ctx: BindingContext,
) -> tuple[PinnedInstruction, ...]:
    """Each of ``pinned`` that names an ``@current`` reference, bound for the cycle ``ctx`` names
    (§5ad). A reference its resolver refuses is kept unbound with why, as at admission (§5z). A
    resolver that fails otherwise raises, so the launch or the reconciliation that asked repeats it
    rather than leaving the reference unbound for the cycle's life. The rest need no binding of their
    own, since the campaign's pin is already what the cycle reads."""
    out = []
    for p in pinned:
        if not any(is_current(r.ref) for r in p.references):
            continue
        # The campaign's own attempt is dropped: every unbound entry is an @current reference,
        # bound now for this cycle instead.
        out.append(await bound_instruction(replace(p, unbound=()), resolvers, ctx, strict=True))
    return tuple(out)


def missing_from(
    binding: CycleBinding | None, pinned: Iterable[PinnedInstruction]
) -> tuple[PinnedInstruction, ...]:
    """The pinned instructions naming ``@current`` that ``binding`` holds no entry for, by record
    and revision: a revision a re-binding put in force that couldn't reach this cycle, or a launch
    that raced it. Filling them never changes an entry the cycle holds, so nothing already handed
    moves."""
    held = {(p.record_id, p.revision) for p in binding.instructions} if binding else set()
    return tuple(
        p
        for p in pinned
        if any(is_current(r.ref) for r in p.references) and (p.record_id, p.revision) not in held
    )


def as_bound_for(
    pinned: Iterable[PinnedInstruction], binding: CycleBinding | None
) -> tuple[PinnedInstruction, ...]:
    """``pinned``, each instruction the cycle bound replaced by its binding, matched by record and
    revision. One the cycle has no binding for is the campaign's pin, as it was."""
    if binding is None:
        return tuple(pinned)
    bound = {(p.record_id, p.revision): p for p in binding.instructions}
    return tuple(bound.get((p.record_id, p.revision), p) for p in pinned)
