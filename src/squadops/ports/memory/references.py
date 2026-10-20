"""Resolving an instruction's references to the revision a unit binds (SIP-0110 Appendix A §3.6, §3.7;
#2179 T16; SIP-0112 §B.5.1, contract 6).

A reference names its target and the revision it means: ``<family>:<kind>:<id>@<revision>``. A
reference written ``@current`` means the revision current when the instruction is bound to a unit,
which is the unit's admission and never a dispatch. A resolver per family binds it: it gives the
concrete revision and a digest of the content at that revision. It also reads the content back at
a bound revision, refusing a digest that no longer matches.

The composition root registers resolvers by family. Project Lifecycle Management supplies the
repository family (``repo:file:<path>@current``), bound at the commit the unit's source context
pins. A family with no resolver can't bind ``@current``, and the records refuse one written for it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ReferenceUnresolved(Exception):
    """A reference that can't be bound, or read at its bound revision, with why. Admission records
    it on the pinned instruction, and a required one holds the task it applies to (§3.6)."""


@dataclass(frozen=True)
class BindingContext:
    """The unit a reference is bound for, as admission knows it.

    ``source_commit`` is the commit the unit's source context pins (SIP-0112 FR-04). It is ``None``
    for a project with no source context, which a resolver that needs one refuses rather than
    binding to a default (SIP-0112 §B.5.1)."""

    project_id: str
    unit_kind: str
    unit_id: str
    source_commit: str | None = None


@dataclass(frozen=True)
class BoundReference:
    """A reference bound to a concrete revision: ``ref`` is rewritten from ``…@current`` to
    ``…@<revision>``, and ``digest`` is the content's at that revision."""

    ref: str
    revision: str
    digest: str


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
