"""Task instructions as a dispatch is handed them (SIP-0110 Appendix A §3.5–§3.7; #2178).

A task instruction is a directive for selected tasks of **one target cycle**. It matches by that cycle
and its task selector only, never through the campaign whose snapshot the cycle shares (§3.7). Within
the cycle it reaches every dispatch that authors or revises the targeted output: the first dispatch, a
re-dispatched attempt or re-take, and the repairs that revise that output. Each dispatch reads the
records again, so a withdrawal stops the next dispatch. Nothing is copied from the attempt before.

It is a **binding** section (§3.6): never omitted, never cut. A task instruction that can't be loaded or
fitted into the prompt budget leaves the section incomplete, and the task is not dispatched.

Pure: the composer reads the records and the budget, and these rules decide what is handed.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from squadops.memory.context import Disposition, Need, RecordRef, Section, SectionKind
from squadops.memory.lessons import _tokens
from squadops.memory.records import (
    MemoryRecord,
    RecordKind,
    RecordRefused,
    RecordScope,
    RecordStatus,
    Reference,
    Revision,
    Source,
    TaskTarget,
    new_record,
    reference_of,
)

#: Where a dispatch is handed its task instructions, beside ``LESSONS_INPUT``.
TASK_INSTRUCTIONS_INPUT = "task_instructions"


class TaskInstructionsUnavailable(RuntimeError):
    """A task's binding section is incomplete: an instruction that applies to it couldn't be read or
    fitted. The task is not dispatched, and this says why (§3.6)."""


@dataclass(frozen=True)
class Bound:
    """One task instruction, as the revision a dispatch is handed."""

    record_id: str
    revision: int
    text: str
    references: tuple[Reference, ...] = ()

    @property
    def ref(self) -> RecordRef:
        return RecordRef(self.record_id, str(self.revision))


def applicable(
    records: Iterable[MemoryRecord],
    *,
    cycle_id: str,
    reaches: Callable[[Collection[str]], bool],
) -> list[Bound]:
    """The active task instructions for ``cycle_id`` whose selector ``reaches`` this dispatch, in
    the order they were recorded. ``reaches`` is given the selector's task types."""
    bound = []
    for record in records:
        if (
            record.kind != RecordKind.INSTRUCTION
            or record.scope != RecordScope.TASK
            or record.status != RecordStatus.ACTIVE
        ):
            continue
        current = record.current
        if current.target is None or current.target.cycle_id != cycle_id:
            continue
        if reaches(current.target.task_types):
            bound.append(Bound(record.record_id, current.number, current.body, current.references))
    return bound


def binding_section(
    kind: SectionKind, entries: list[tuple[RecordRef, str]], *, budget: int
) -> Section:
    """A binding section for ``entries`` (each record's revision and its text). Over the prompt
    budget left to it, or with no known budget (``budget < 0``: an unknown never means room), it is
    incomplete: a binding section is never cut (§3.6). The task and project instructions share the
    budget, the task's first."""
    if not entries:
        return Section(kind, Need.BINDING, Disposition.NONE_ELIGIBLE)
    tokens = sum(_tokens(text) for _, text in entries)
    if budget < 0 or tokens > budget:
        why = (
            f"the {kind.value.replace('_', ' ')} take {tokens} tokens and the prompt has {budget}"
            if budget >= 0
            else "the model's prompt budget is unknown"
        )
        return Section(
            kind,
            Need.BINDING,
            Disposition.INCOMPLETE,
            unresolved=tuple((r, why) for r, _ in entries),
        )
    return Section(kind, Need.BINDING, Disposition.SUPPLIED, supplied=tuple(r for r, _ in entries))


def section_of(bound: list[Bound], *, budget: int) -> Section:
    """The task instructions' binding section for what applies."""
    return binding_section(
        SectionKind.TASK_INSTRUCTIONS, [(b.ref, b.text) for b in bound], budget=budget
    )


def tokens_of(bound: list[Bound]) -> int:
    return sum(_tokens(b.text) for b in bound)


def handed(bound: list[Bound]) -> dict[str, Any] | None:
    """What a task is handed on ``TASK_INSTRUCTIONS_INPUT``, or ``None`` when none applies, so its
    inputs are exactly what they were without instructions."""
    if not bound:
        return None
    return {
        "instructions": [
            {
                "record_id": b.record_id,
                "revision": b.revision,
                "text": b.text,
                "references": [{"ref": r.ref, "required": r.required} for r in b.references],
            }
            for b in bound
        ]
    }


def unresolved_reason(section: Section) -> str:
    """Why an incomplete binding section holds its task, for the record."""
    return "; ".join(f"{ref.record_id}@{ref.revision}: {why}" for ref, why in section.unresolved)


def admitted(
    requested: Iterable[Mapping[str, Any]],
    *,
    project_id: str,
    cycle_id: str,
    actor: str,
    now: datetime,
    instructable: Callable[[str], bool],
    source: Source,
) -> list[MemoryRecord]:
    """The task instructions a cycle is created with, as records whose target is that cycle,
    confirmed by its creator (§3.5). Refused, before anything is stored, for a task type that is no
    authoring task (an instruction for it would reach nothing) or for any record §A.3.2's rules
    refuse."""
    records = []
    for n, item in enumerate(requested, start=1):
        types = tuple(str(t) for t in item.get("task_types") or ())
        unreachable = [t for t in types if not instructable(t)]
        if unreachable:
            raise RecordRefused(
                f"instruction {n}: {', '.join(unreachable)} authors nothing an instruction reaches"
            )
        revision = Revision(
            number=1,
            body=str(item.get("text") or ""),
            author=actor,
            created_at=now,
            source=source,
            confirmed_by=actor,
            target=TaskTarget(cycle_id, types),
            references=tuple(reference_of(r) for r in item.get("references") or ()),
        )
        records.append(
            new_record(
                record_id=f"mrec_{uuid.uuid4().hex[:16]}",
                kind=RecordKind.INSTRUCTION,
                scope=RecordScope.TASK,
                project_id=project_id,
                owner_id=actor,
                revision=revision,
            )
        )
    return records
