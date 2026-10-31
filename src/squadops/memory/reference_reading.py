"""A bound reference's content, read at a dispatch (SIP-0110 Appendix A §3.6; #2179).

An instruction names an authoritative record by reference, and the binding section includes what it
references (§3.6): a dispatch is handed the reference's content at the revision its unit (or, for a
task instruction, its cycle) bound, never at whatever the record says now. Each reference is read
once per dispatch, through its family's resolver, which refuses content that no longer matches the
digest bound (§3.7, T16).

- **A required reference that can't be read holds its task** (§3.6): the binding section is
  incomplete, naming the reference and why. A refusal (``ReferenceUnresolved``) is the operator's
  input, released by a re-binding or a revision. A resolver that failed is the store not answering.
- **An optional one is omitted whole and disclosed** (the second read of T16), as one admission
  couldn't bind is: the task runs without it, and its exposure says which and why.

Pure apart from the read it's given.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from squadops.memory.records import Reference
from squadops.memory.references import ReferenceUnresolved


@dataclass(frozen=True)
class Unread:
    """Why a reference couldn't be read, and whether the store failed rather than the reference."""

    why: str
    store_failed: bool = False


@dataclass(frozen=True)
class ReferencesRead:
    """A dispatch's references: each one read, by its ref, and each one that couldn't be."""

    contents: Mapping[str, str] = field(default_factory=dict)
    unread: Mapping[str, Unread] = field(default_factory=dict)


async def read_references(
    references: Iterable[Reference], read: Callable[[Reference], Awaitable[str]]
) -> ReferencesRead:
    """Each of ``references`` read once, in order."""
    contents: dict[str, str] = {}
    unread: dict[str, Unread] = {}
    for reference in references:
        if reference.ref in contents or reference.ref in unread:
            continue
        try:
            contents[reference.ref] = await read(reference)
        except ReferenceUnresolved as e:
            unread[reference.ref] = Unread(str(e))
        except Exception as e:  # noqa: BLE001 — a resolver's failure says nothing of the reference
            unread[reference.ref] = Unread(
                f"its {reference.family} resolver failed ({type(e).__name__}: {e})",
                store_failed=True,
            )
    return ReferencesRead(contents, unread)


def holding(references: Iterable[Reference], read: ReferencesRead) -> list[tuple[str, Unread]]:
    """The required references among ``references`` that couldn't be read: what holds the task."""
    return [(r.ref, read.unread[r.ref]) for r in references if r.required and r.ref in read.unread]


def measured(text: str, references: Iterable[Reference], read: ReferencesRead) -> str:
    """An instruction as its binding section is measured: its text and each reference it is
    handed, since a binding section's size includes what it references (§3.6)."""
    shown = [read.contents[r.ref] for r in references if r.ref in read.contents]
    return "\n".join([text, *shown]) if shown else text


def handed_references(references: Iterable[Reference], read: ReferencesRead) -> dict[str, Any]:
    """An instruction's references as a dispatch is handed them: each one read, with its content,
    and each optional one that couldn't be, omitted and named (``unread``). Nothing is added for an
    instruction whose references weren't read, so its input is what it was before #2179's read."""
    shown, omitted = [], []
    for r in references:
        if r.ref in read.contents:
            shown.append({**r.to_dict(), "content": read.contents[r.ref]})
        elif r.ref in read.unread:
            omitted.append({"ref": r.ref, "why": read.unread[r.ref].why})
        else:
            shown.append(r.to_dict())
    return {"references": shown, **({"unread": omitted} if omitted else {})}


def unread_references(handed_input: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Each optional reference a task was handed without, because it couldn't be read at its bound
    revision: the instruction, the reference and why, for its exposure (§3.6)."""
    return [
        {"record_id": i["record_id"], "ref": u["ref"], "why": u["why"]}
        for i in (handed_input or {}).get("instructions", ())
        for u in i.get("unread") or ()
    ]
