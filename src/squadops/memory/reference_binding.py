"""Binding an instruction's ``@current`` references (SIP-0110 Appendix A §3.6, §3.7; #2179 and #2178
T16): a project instruction's at its unit's admission, a task instruction's with its cycle.

``@current`` is resolved once, when the instruction is bound to a unit, and never at dispatch. The pin
asks each reference's family resolver for the revision current for the unit, and keeps it: the
reference is rewritten to that revision, with the content's digest. So every task of the unit, every
re-dispatch and both arms of a comparison admitted together carry the same revision, however the
target changes after. A unit admitted later binds whatever is current then.

A reference that can't be bound is kept on the pin with why. A required one leaves its instruction's
binding section incomplete, so the task it applies to is held (§3.6). An optional one is omitted and
listed.

A task instruction is its cycle's binding, so it is bound when it is written: with the cycle's create
request, at the increment gate's approval, by an intervention, or carried into a continuation. The
record keeps the bound revision and what was written, which a continuation binds again. One that
won't bind is refused there, and its writer names the revision or drops it.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import TYPE_CHECKING

from squadops.memory.records import PinnedInstruction, RecordRefused, Reference, is_current
from squadops.memory.references import BindingContext, BoundReference, ReferenceUnresolved

if TYPE_CHECKING:
    from squadops.ports.memory.references import ReferenceResolverPort

logger = logging.getLogger(__name__)


async def bound_instruction(
    pinned: PinnedInstruction,
    resolvers: Mapping[str, ReferenceResolverPort],
    ctx: BindingContext,
    *,
    strict: bool = False,
) -> PinnedInstruction:
    """``pinned`` with each ``@current`` reference bound for ``ctx``'s unit, or kept unbound with
    why. A reference naming a revision is kept as written. ``strict``: a resolver that fails
    otherwise than by refusing raises, for a caller that can repeat the binding (a campaign cycle's
    launch, §5ad), rather than keeping the reference unbound for the unit's life."""
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
        except Exception as e:  # noqa: BLE001 — a resolver that fails leaves this one unbound
            if strict:
                raise
            # Not the unit's other instructions, nor its lessons: one reference that couldn't be
            # bound holds what it applies to, and only if it is required (the second read).
            logger.warning(
                "reference_bind_failed ref=%s unit=%s:%s", reference.ref, ctx.unit_kind,
                ctx.unit_id, exc_info=True,
            )  # fmt: skip
            unbound.append(
                (reference.ref, f"the {reference.family} resolver failed: {type(e).__name__}")
            )
            references.append(reference)
            continue
        references.append(Reference(bound.ref, reference.required, digest=bound.digest))
    return replace(pinned, references=tuple(references), unbound=tuple(unbound))


async def bound_for_cycle(
    references: Iterable[Reference],
    resolvers: Mapping[str, ReferenceResolverPort],
    ctx: BindingContext,
) -> dict[str, BoundReference]:
    """Each ``@current`` reference among a task instruction's ``references``, as written, bound for
    ``ctx``'s cycle (§3.7; #2178 T16). Refused, naming every one that won't bind, since the record
    would bind its task to nothing (§3.6). A resolver that fails otherwise is a fault and propagates,
    so the write is answered as one, never as its writer's mistake."""
    bound: dict[str, BoundReference] = {}
    refused: list[str] = []
    for reference in references:
        written = reference.written or reference.ref
        if not is_current(written) or written in bound:
            continue
        resolver = resolvers.get(reference.family)
        try:
            if resolver is None:
                raise ReferenceUnresolved(f"no resolver binds the {reference.family} family")
            bound[written] = await resolver.bind(written, ctx)
        except ReferenceUnresolved as e:
            refused.append(f"{written} ({e})")
    if refused:
        raise RecordRefused(
            f"a task instruction's reference won't bind for cycle {ctx.unit_id}: "
            f"{'; '.join(refused)}. Name the revision it means, or drop it"
        )
    return bound


def with_bindings(
    references: Iterable[Reference], bound: Mapping[str, BoundReference]
) -> tuple[Reference, ...]:
    """``references`` with each one written ``@current`` replaced by its binding in ``bound``, which
    keeps what was written. One ``bound`` lacks is refused rather than kept as it was, so a carried
    copy never keeps the binding of the cycle it came from."""
    out = []
    for reference in references:
        written = reference.written or reference.ref
        if not is_current(written):
            out.append(reference)
            continue
        b = bound.get(written)
        if b is None:
            raise RecordRefused(f"{written} isn't bound for this cycle")
        out.append(Reference(b.ref, reference.required, digest=b.digest, written=written))
    return tuple(out)
