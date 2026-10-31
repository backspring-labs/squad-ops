"""Project instructions as a dispatch is handed them (SIP-0110 Appendix A §3.6–§3.7; #2179).

A project instruction is a standing directive for a project's work, with an applicability (task types,
roles, stacks). It is in force from the next admission of a snapshot owner: the unit's snapshot pins
its revision at admission (§3.7), and every task of the unit reads that pinned revision, however the
record changes after. A binding section, as task instructions are (§3.6): never omitted, never cut.

Pure: the snapshot holds the pinned revisions, and these rules decide what a dispatch is handed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from squadops.memory.context import Disposition, Need, RecordRef, Section, SectionKind
from squadops.memory.lessons import Snapshot
from squadops.memory.records import MemoryRecord, PinnedInstruction, RecordKind, RecordScope
from squadops.memory.reference_reading import (
    ReferencesRead,
    handed_references,
    holding,
    measured,
)
from squadops.memory.task_instructions import binding_section

#: Where a dispatch is handed its project instructions, between the task instructions and lessons.
PROJECT_INSTRUCTIONS_INPUT = "project_instructions"


class PinUnknown(RuntimeError):
    """What a unit pinned can't be known: its snapshot is unreadable or absent, or its pin couldn't
    read the records, and the project holds project instructions. The message says which."""


def none_could_be_pinned(records: Iterable[MemoryRecord]) -> bool:
    """Whether a project's records rule out any pinned project instruction. The records are
    append-only, withdrawn ones kept, so a project that holds no project instruction now held none
    when any of its units was admitted."""
    return not any(
        r.kind == RecordKind.INSTRUCTION and r.scope == RecordScope.PROJECT for r in records
    )


def units_pinning(record_id: str, snapshots: Iterable[Snapshot]) -> list[Snapshot]:
    """The units whose snapshot pinned a revision of ``record_id``: the work its emergency
    withdrawal names, so it can be halted or restarted under a new snapshot without it and its
    measurements set apart (Appendix A §3.8, SIP-0110 §0.7). A pinned unit hands the revision to
    each later task it applies to, so pinning it is holding it, used yet or not."""
    return [s for s in snapshots if any(p.record_id == record_id for p in s.instructions)]


def applicable(
    pinned: Iterable[PinnedInstruction], *, task_type: str, role: str, stack: str | None
) -> list[PinnedInstruction]:
    """The pinned project instructions whose applicability covers this dispatch, in pin order."""
    return [
        p
        for p in pinned
        if p.applicability.covers(task_type=task_type, role=role, stack=stack or None)
    ]


def section_of(
    pinned: list[PinnedInstruction],
    *,
    budget: int,
    framing: int = 0,
    read: ReferencesRead | None = None,
) -> Section:
    """The project instructions' binding section, within what the task instructions left, measured
    with its framing and the content of each reference it is handed (#2179). An instruction whose
    required reference admission couldn't bind, or that can't be read at its bound revision, leaves
    it incomplete, naming the reference: the task is held, never handed it half-bound (§3.6, T16)."""
    read = read or ReferencesRead()
    held = [(p, f"required reference {ref} unbound: {why}", False)
            for p in pinned for ref, why in p.held_by]  # fmt: skip
    held += [
        (
            p,
            f"required reference {ref} can't be read at its bound revision: {u.why}",
            u.store_failed,
        )
        for p in pinned
        for ref, u in holding(_handed(p), read)
    ]
    if held:
        return Section(
            SectionKind.PROJECT_INSTRUCTIONS,
            Need.BINDING,
            Disposition.INCOMPLETE,
            unresolved=tuple((RecordRef(p.record_id, str(p.revision)), why) for p, why, _ in held),
            store_failed=any(store for *_, store in held),
        )
    return binding_section(
        SectionKind.PROJECT_INSTRUCTIONS,
        [
            (RecordRef(p.record_id, str(p.revision)), measured(p.text, _handed(p), read))
            for p in pinned
        ],  # fmt: skip
        budget=budget,
        framing=framing,
    )


def _handed(p: PinnedInstruction) -> list:
    """The references a dispatch is handed with ``p``: every one admission bound."""
    return [r for r in p.references if r.ref not in dict(p.unbound)]


def handed(
    pinned: list[PinnedInstruction], read: ReferencesRead | None = None
) -> dict[str, Any] | None:
    """What a task is handed on ``PROJECT_INSTRUCTIONS_INPUT``, or ``None`` when none applies. Each
    reference read is handed with its content, and an optional one that couldn't be is omitted
    and named (#2179)."""
    if not pinned:
        return None
    read = read or ReferencesRead()
    return {
        "instructions": [
            {
                "record_id": p.record_id,
                "revision": p.revision,
                "text": p.text,
                # §3.6: an optional reference admission couldn't bind, or that can't be read at its
                # bound revision, is omitted whole and disclosed, never handed as written (the
                # second read of T16); a required one holds the task before it is handed anything.
                **handed_references(_handed(p), read),
                **(
                    {"unbound": [{"ref": ref, "why": why} for ref, why in p.unbound]}
                    if p.unbound
                    else {}
                ),
            }
            for p in pinned
        ]
    }


def unbound_references(handed_input: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Each reference a task was handed without, because admission couldn't bind it: the
    instruction, the reference and why (§3.6). Only an optional one reaches a task this way."""
    return [
        {"record_id": i["record_id"], "ref": u["ref"], "why": u["why"]}
        for i in (handed_input or {}).get("instructions", ())
        for u in i.get("unbound") or ()
    ]


def bound_references(handed_input: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Each bound reference a task was handed: the instruction, the bound reference and its digest
    (§3.7, T16). A project instruction's was bound at its unit's admission, a task instruction's
    with its cycle. A reference written with its revision has no digest and isn't listed: its
    exposure already names the revision as written."""
    return [
        {"record_id": i["record_id"], "ref": r["ref"], "digest": r["digest"]}
        for i in (handed_input or {}).get("instructions", ())
        for r in i.get("references") or ()
        if r.get("digest")
    ]
