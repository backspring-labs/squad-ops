"""Binding a pinned instruction's ``@current`` references at its unit's admission (SIP-0110 Appendix A
§3.6, §3.7; #2179 T16).

``@current`` is resolved once, when the instruction is bound to a unit, and never at dispatch. The pin
asks each reference's family resolver for the revision current for the unit, and keeps it: the
reference is rewritten to that revision, with the content's digest. So every task of the unit, every
re-dispatch and both arms of a comparison admitted together carry the same revision, however the
target changes after. A unit admitted later binds whatever is current then.

A reference that can't be bound is kept on the pin with why. A required one leaves its instruction's
binding section incomplete, so the task it applies to is held (§3.6). An optional one is omitted and
listed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from squadops.memory.records import PinnedInstruction, Reference, is_current
from squadops.ports.memory.references import (
    BindingContext,
    ReferenceResolverPort,
    ReferenceUnresolved,
)


async def bound_instruction(
    pinned: PinnedInstruction,
    resolvers: Mapping[str, ReferenceResolverPort],
    ctx: BindingContext,
) -> PinnedInstruction:
    """``pinned`` with each ``@current`` reference bound for ``ctx``'s unit, or kept unbound with
    why. A reference naming a revision is kept as written."""
    references: list[Reference] = []
    unbound: list[tuple[str, str]] = list(pinned.unbound)
    for reference in pinned.references:
        if not is_current(reference.ref):
            references.append(reference)
            continue
        resolver = resolvers.get(reference.family)
        try:
            if resolver is None:
                raise ReferenceUnresolved(f"no resolver binds the {reference.family} family")
            bound = await resolver.bind(reference.ref, ctx)
        except ReferenceUnresolved as e:
            unbound.append((reference.ref, str(e)))
            references.append(reference)
            continue
        references.append(Reference(bound.ref, reference.required, digest=bound.digest))
    return replace(pinned, references=tuple(references), unbound=tuple(unbound))
