"""Task instructions as a dispatch is handed them (SIP-0110 Appendix A §3.5–§3.7; #2178).

A task instruction is a directive for selected tasks of **one target cycle**. It matches by that cycle
and its task selector only, never through the campaign whose snapshot the cycle shares (§3.7). Within
the cycle it reaches every dispatch that authors or revises the targeted output: the first dispatch, a
re-dispatched attempt or re-take, and the repairs that revise that output. Each dispatch reads the
records again, so a withdrawal stops the next dispatch. Nothing is copied from the attempt before.

It is a **binding** section (§3.6): never omitted, never cut. A task instruction that can't be loaded or
fitted into the prompt budget leaves the section incomplete, and the task is not dispatched.

**An instruction given with the cycle's create request is an admitted input.** One added or revised
after it is an **intervention** (§3.5): allowed only while no task it selects has dispatched in any
run of the cycle, and marked in the envelope and the exposure of each dispatch that receives it, so
its measurement is set apart.

Pure: the composer reads the records and the budget, and these rules decide what is handed.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from squadops.memory.context import Disposition, Need, RecordRef, Section, SectionKind
from squadops.memory.exposures import Exposure
from squadops.memory.lessons import _tokens
from squadops.memory.records import (
    LESSON_CITED,
    MemoryRecord,
    RecordKind,
    RecordRefused,
    RecordScope,
    RecordStatus,
    Reference,
    Revision,
    Source,
    SourceKind,
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
    #: Added or revised after its cycle was admitted (§3.5): an intervention.
    intervention: bool = False

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
            bound.append(
                Bound(
                    record.record_id, current.number, current.body, current.references,
                    intervention=is_intervention(record),
                )
            )  # fmt: skip
    return bound


def is_intervention(record: MemoryRecord) -> bool:
    """Whether a task instruction's current revision came after its cycle's admission: anything but
    the cycle's own create request (§3.5). A revision of an admitted one is an intervention too."""
    return record.current.source.kind != SourceKind.CYCLE_REQUEST


def cited_lesson(revision: Revision) -> str | None:
    """The lesson revision a task instruction's provenance cites, or ``None``."""
    value = revision.source.ids.get(LESSON_CITED)
    return str(value) if value else None


def refuse_for_lessons_disabled(revision: Revision, snapshot: Any) -> None:
    """§3.7's structural guarantee: a ``lessons: disabled`` unit is the lesson-effectiveness control,
    so no lesson reaches it, through a task instruction either. One whose provenance cites a lesson
    revision is refused for it, and refused too when the unit's snapshot can't be read, since
    whether it is the control is then unknown. An instruction citing no lesson is never refused
    here: the text check is a diagnostic, not this guarantee (§5s)."""
    lesson = cited_lesson(revision)
    if lesson is None:
        return
    if snapshot is None:
        raise RecordRefused(
            f"it applies lesson {lesson}, and whether its cycle's unit disables lessons can't be "
            "read"
        )
    if snapshot.disabled:
        raise RecordRefused(
            f"it applies lesson {lesson}, and its cycle's unit declares lessons disabled: the "
            "lesson-effectiveness control, which no lesson reaches (SIP-0110 Appendix A §3.7)"
        )


def dispatched(
    selector: Collection[str], exposures: Iterable[Exposure], *, cycle_id: str
) -> list[tuple[str, str]]:
    """Each ``(run_id, task_id)`` of ``cycle_id`` that dispatched a selected task type, in any run,
    in the order first seen. An instruction added or revised for one is refused: the task, its
    re-takes, its repairs and the work built on its output would mix a binding it never had (§3.5).
    Read from the exposures, which every dispatch of an authoring task records."""
    seen: list[tuple[str, str]] = []
    for e in exposures:
        if e.cycle_id == cycle_id and e.query.task_type in selector:
            if (e.run_id, e.task_id) not in seen:
                seen.append((e.run_id, e.task_id))
    return seen


def binding_section(
    kind: SectionKind, entries: list[tuple[RecordRef, str]], *, budget: int, framing: int = 0
) -> Section:
    """A binding section for ``entries`` (each record's revision and its text). Over the prompt
    budget left to it, or with no known budget (``budget < 0``: an unknown never means room), it is
    incomplete: a binding section is never cut (§3.6). The task and project instructions share the
    budget, the task's first."""
    if not entries:
        return Section(kind, Need.BINDING, Disposition.NONE_ELIGIBLE)
    # §3.6: a binding section is measured with its slot's fixed framing (its heading and precedence).
    tokens = framing + sum(_tokens(text) for _, text in entries)
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


def section_of(bound: list[Bound], *, budget: int, framing: int = 0) -> Section:
    """The task instructions' binding section for what applies, measured with its framing."""
    return binding_section(
        SectionKind.TASK_INSTRUCTIONS,
        [(b.ref, b.text) for b in bound],
        budget=budget,
        framing=framing,
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
                # Only when it is one, so an admitted instruction's envelope is what it was.
                **({"intervention": True} if b.intervention else {}),
            }
            for b in bound
        ]
    }


def interventions(handed_input: Mapping[str, Any] | None) -> list[str]:
    """The record ids of the interventions among what a task was handed, for its exposure."""
    return [
        str(i["record_id"])
        for i in (handed_input or {}).get("instructions", ())
        if i.get("intervention")
    ]


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
