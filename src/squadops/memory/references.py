"""The values an instruction's reference is bound with (SIP-0110 Appendix A §3.6, §3.7; #2179 T16).

The resolver itself is a port, one per family (``squadops.ports.memory.references``). These are the
domain's: the unit a reference is bound for, the bound reference, and the refusal. The port module
re-exports them, so an adapter raises the same ``ReferenceUnresolved`` the pin catches.
"""

from __future__ import annotations

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
