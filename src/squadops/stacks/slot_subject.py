"""What a slot assertion is about — its subject (SIP-0104 §13f, #2664).

A fill slot's assertions are the qa author's. When one fails, a repair may rewrite it, and
§13d rules that a repair never resolves an ambiguous failure by deleting or weakening the
assertion. The slot-subject gate (``capabilities.verification_scaffold_fill``) enforces that by
comparing *subjects*: the surface an assertion reads and the field it reads there. This module
is the vocabulary both sides of that comparison share — the stack's reader produces it, the
stack-neutral gate consumes it — so it holds no stack's syntax.

**The three surfaces** (the MacBook lane's G4, point 1):

- ``response``: the body the shell's handler call returned (``body.<f>``);
- ``error_envelope``: the frozen error envelope inside it (``body.error.<f>``);
- ``store``: one of the frozen store's tables (``TABLES.<T>``, ``all(TABLES.<T>)[i].<f>``).

A subject's ``field`` is the first property read on its surface; ``""`` is the surface as a
whole (``body``, ``all(TABLES.Run)``). An assertion whose target is none of these has no
subject: its reader returns ``None``, and the gate records ``subject_unreadable`` rather than
refusing anything it cannot show.

**Matcher classes** carry the softer signal (G4 point 3): a matcher loosened on the same
subject, from an exact value to existence or shape, passes the gate and is recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SubjectSurface(StrEnum):
    """Where an assertion's subject lives."""

    RESPONSE = "response"
    ERROR_ENVELOPE = "error_envelope"
    STORE = "store"


class MatcherClass(StrEnum):
    """How much a matcher pins: an exact value, mere existence, a shape, or something else."""

    VALUE = "exact_value"
    EXISTENCE = "existence"
    SHAPE = "shape"
    OTHER = "other"


#: The classes a matcher loosened from ``VALUE`` lands in for the softer signal.
LOOSER_THAN_VALUE: frozenset[MatcherClass] = frozenset({MatcherClass.EXISTENCE, MatcherClass.SHAPE})


@dataclass(frozen=True)
class AssertionSubject:
    """One assertion's subject: a surface, the table when the surface is the store, a field."""

    surface: SubjectSurface
    field: str = ""
    table: str = ""

    def describe(self) -> str:
        """``participant_count`` on store table ``RunDetail`` — the form a carry entry names."""
        where = {
            SubjectSurface.RESPONSE: "the response",
            SubjectSurface.ERROR_ENVELOPE: "the error envelope",
            SubjectSurface.STORE: f"store table `{self.table}`",
        }[self.surface]
        return f"`{self.field}` on {where}" if self.field else where

    def to_dict(self) -> dict[str, str]:
        return {"surface": str(self.surface), "table": self.table, "field": self.field}


@dataclass(frozen=True)
class SlotAssertion:
    """One ``expect(...)`` in a slot body, as its stack's reader saw it.

    ``first_line``/``last_line`` are 1-based lines of the body: the ``expect(`` and the matcher
    call, which is the line a runner reports when the assertion fails. ``resolved`` is the
    target after the reader normalised it and substituted the body's own aliases.
    """

    target: str
    resolved: str
    first_line: int
    last_line: int
    matcher: str
    matcher_class: MatcherClass
    subject: AssertionSubject | None

    def covers(self, line: int) -> bool:
        return self.first_line <= line <= self.last_line
