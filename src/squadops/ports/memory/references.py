"""Resolving an instruction's references to the revision a unit binds (SIP-0110 Appendix A §3.6, §3.7;
#2179 T16; SIP-0112 §B.5.1, contract 6).

A reference names its target and the revision it means: ``<family>:<kind>:<id>@<revision>``. A
reference written ``@current`` means the revision current when the instruction is bound to a unit,
and never at a dispatch: a project instruction at its unit's admission, a task instruction with its
cycle, when it is written (#2178). A resolver per family binds it: it gives the
concrete revision and a digest of the content at that revision. It also reads the content back at
a bound revision, refusing a digest that no longer matches.

The composition root registers resolvers by family. Project Lifecycle Management supplies the
repository family (``repo:file:<path>@current``), bound at the commit the unit's source context
pins. A family with no resolver can't bind ``@current``, and the records refuse one written for it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.memory.references import BindingContext, BoundReference, ReferenceUnresolved

__all__ = ["BindingContext", "BoundReference", "ReferenceResolverPort", "ReferenceUnresolved"]


class ReferenceResolverPort(ABC):
    """One reference family's resolver."""

    #: The family it resolves: the reference's first segment (``repo`` for ``repo:file:…``).
    family: str

    @abstractmethod
    async def bind(self, ref: str, ctx: BindingContext) -> BoundReference:
        """Bind ``ref`` (written ``…@current``) to the revision current for ``ctx``'s unit. Raises
        :class:`ReferenceUnresolved` when it can't be bound."""

    @abstractmethod
    async def read(self, bound: BoundReference, ctx: BindingContext) -> str:
        """The content at ``bound``'s revision. Raises :class:`ReferenceUnresolved` when it can't
        be read there, or its digest no longer matches."""

    async def binds_nothing_for(self, project_id: str) -> str | None:
        """Why this family can bind no reference for any unit of ``project_id``, or ``None`` when
        it may. The records refuse a project instruction naming such a reference at write, since
        every unit would pin it unbound, and a required one would hold every task it applies to
        (§3.6). The repository family binds nothing for a Project with no source repository. A
        family that can always try answers ``None``, the default."""
        return None
