"""What used a memory record, kept apart from what it did (SIP-0110 Appendix A §3.11; #2182).

A record's uses are the dispatches and chat turns whose context supplied it: each task exposure that
handed it as a task or project instruction, with the revision and the section's disposition, and any hold
it caused; and each chat turn that held it. A chat turn is the person's own: another person's turns are
counted, never opened (§3.4: following a chat turn is authorized like reading it).

**"Used" and "improved the outcome" never share a column.** A use names the build it fed and that build's
indicators, observed (§0.10). An effect is a separate reading, and for a note or an instruction none
exists: no experiment reads one, so the view says "no effect measured", and says why a green build beside
an exposure isn't evidence the record helped.

Pure: the routes read the stores, and these rules decide what the view shows.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from squadops.memory.chat import ChatExposure
from squadops.memory.exposures import INSTRUCTION_SECTIONS, Exposure
from squadops.memory.records import MemoryRecord, RecordStatus

#: §A.3.11's effect for a record no experiment reads, said with its reason.
NO_EFFECT_MEASURED = (
    "No effect measured: no experiment reads this record. A green build beside an exposure is not "
    "evidence the record helped (SIP-0110 §0.10). An application-quality claim needs Outcome "
    "Evaluation's independent scenarios (§0.13)."
)


@dataclass(frozen=True)
class TaskUse:
    """One dispatch whose binding section handed the record, or held its task for it."""

    exposure_id: str
    cycle_id: str
    run_id: str
    task_id: str
    attempt: int
    seam: str
    section: str
    revision: str
    disposition: str
    #: Why the record held its task undispatched (§3.6), or ``None`` when it was supplied.
    held: str | None = None


@dataclass(frozen=True)
class ChatUse:
    """One chat turn of the reader's own whose context held the record."""

    session_id: str
    message_id: str
    revision: str
    disposition: str
    assembled_at: datetime


@dataclass(frozen=True)
class WithdrawnUse:
    """An instruction an exposure was handed whose record is withdrawn now (§A.3.8)."""

    record_id: str
    revision: str
    section: str
    withdrawn_by: str
    withdrawn_at: datetime
    why: str


def _incomplete(exposure: Exposure) -> list[str]:
    """The binding sections that couldn't be completed (``Exposure.incomplete_sections``)."""
    return list(exposure.incomplete_sections)


def handed_instructions(exposure: Exposure) -> bool:
    """Whether a binding section handed ``exposure`` an instruction that reached the model: a held
    task was handed none."""
    return not _incomplete(exposure) and any(
        (getattr(exposure, s, None) or {}).get("supplied") for s in INSTRUCTION_SECTIONS
    )


def withdrawn_uses(exposure: Exposure, records: Mapping[str, MemoryRecord]) -> list[WithdrawnUse]:
    """The instructions ``exposure`` was handed whose records are withdrawn now, in section order.
    The exposure keeps what it used, and the mark is read beside it: correcting or withdrawing a
    record never rewrites an exposure (§A.3.8, "what a person sees"). A held task used none."""
    if _incomplete(exposure):
        return []
    marked = []
    for section in INSTRUCTION_SECTIONS:
        held = getattr(exposure, section, None) or {}
        for entry in held.get("supplied") or ():
            record = records.get(str(entry.get("record_id")))
            if record is None or record.status != RecordStatus.WITHDRAWN:
                continue
            change = record.status_changes[-1]
            marked.append(
                WithdrawnUse(
                    record_id=record.record_id,
                    revision=str(entry.get("revision", "")),
                    section=section,
                    withdrawn_by=change.by,
                    withdrawn_at=change.at,
                    why=change.why,
                )
            )
    return marked


def _named(entries: Iterable[Mapping[str, Any]] | None, record_id: str) -> Mapping[str, Any] | None:
    return next((e for e in entries or () if e.get("record_id") == record_id), None)


def task_uses(record_id: str, exposures: Iterable[Exposure]) -> list[TaskUse]:
    """The dispatches that supplied ``record_id``, or that it held, in the store's order. A task is
    held when either binding section is incomplete (§3.6: the bundle is), so a record supplied beside
    an instruction that couldn't be fitted is a use of a task that never ran, and reads as held."""
    uses = []
    for exposure in exposures:
        sections = {name: getattr(exposure, name, None) for name in INSTRUCTION_SECTIONS}
        incomplete = _incomplete(exposure)
        for section, held in sections.items():
            if not held:
                continue
            supplied = _named(held.get("supplied"), record_id)
            unresolved = _named(held.get("unresolved"), record_id)
            entry = supplied or unresolved
            if entry is None:
                continue
            reason = None if supplied is not None else str((unresolved or {}).get("why", ""))
            other = next((name for name in incomplete if name != section), None)
            if reason is None and other is not None:
                reason = f"the task was held: its {other.replace('_', ' ')} were incomplete"
            uses.append(
                TaskUse(
                    exposure_id=exposure.exposure_id,
                    cycle_id=exposure.cycle_id,
                    run_id=exposure.run_id,
                    task_id=exposure.task_id,
                    attempt=exposure.attempt,
                    seam=exposure.seam,
                    section=section,
                    revision=str(entry.get("revision", "")),
                    disposition=str(held.get("disposition", "")),
                    held=reason,
                )
            )
    return uses


def chat_uses(
    record_id: str, exposures: Iterable[ChatExposure], *, viewer_id: str
) -> tuple[list[ChatUse], int]:
    """The reader's own chat turns that held ``record_id``, and how many other people's did."""
    yours: list[ChatUse] = []
    others = 0
    for exposure in exposures:
        held = next(
            (
                (ref, section)
                for section in exposure.sections
                for ref in section.supplied
                if ref.record_id == record_id
            ),
            None,
        )
        if held is None:
            continue
        if exposure.user_id != viewer_id:
            others += 1
            continue
        ref, section = held
        yours.append(
            ChatUse(
                session_id=exposure.session_id,
                message_id=exposure.message_id,
                revision=ref.revision,
                disposition=section.disposition.value,
                assembled_at=exposure.assembled_at,
            )
        )
    return yours, others
