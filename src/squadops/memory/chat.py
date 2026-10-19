"""Chat on the memory substrate (SIP-0110 Appendix A §3.3–§3.6, §3.10; #2180 stage A).

A chat turn is answered from context the runtime API assembles and the agent only renders: the person's
preferences, the notes in scope, the project instructions in force and the task instructions for the cycles
the turn names. Its project is the session's stored binding, never the client's claim, and an unbound
session sees only its owner's private records (T4).

**Nothing in a chat turn is binding** (§3.5): a chat turn executes no work. Every section is optional. A
record that doesn't fit the turn's budget is omitted whole and listed, and a read that fails leaves its
section ``failed``, disclosed in the reply, and the turn runs. A lesson never reaches chat (§3.5: its
applicability names task types, roles, stacks and models, and a chat turn is none of these).

**Capture is explicit and confirmed** (§3.5): the agent proposes, the person confirms, and only the
confirmation stores. The choices a card offers are the person's permissions (§3.3), and stage A captures
notes and preferences only.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from squadops.auth.models import Scope
from squadops.memory.context import (
    ChatTurn,
    ContextBundle,
    Disposition,
    Need,
    ProjectBound,
    RecordRef,
    Section,
    SectionKind,
)
from squadops.memory.lessons import _tokens
from squadops.memory.records import (
    MemoryRecord,
    RecordKind,
    RecordScope,
    retrieved,
)

logger = logging.getLogger(__name__)

#: A cycle a turn names, by its id: the cycles whose task instructions the turn sees (§3.5).
NAMED_CYCLE = re.compile(r"\bcyc_[0-9a-f]{12}\b")

#: The record sections a chat turn holds, in the order they're filled and shown: the instructions, which
#: direct the squad's work, before what the person keeps for themselves.
CHAT_SECTIONS = (
    SectionKind.PROJECT_INSTRUCTIONS,
    SectionKind.TASK_INSTRUCTIONS,
    SectionKind.PREFERENCES,
    SectionKind.NOTES,
)

#: Why a record was left out of the turn: the turn's token budget, or the note count.
OMITTED_BY_TOKENS = "budget"
OMITTED_BY_COUNT = "count"


@dataclass(frozen=True)
class ChatLimits:
    """The chat budget's record part (§3.6: history first, then records under their caps)."""

    max_notes: int
    max_tokens: int


@dataclass(frozen=True)
class Loaded:
    """One read's records, or why there are none. A failed read is never an empty one."""

    records: tuple[MemoryRecord, ...] = ()
    failure: str | None = None


def named_cycles(text: str) -> frozenset[str]:
    return frozenset(NAMED_CYCLE.findall(text))


def _entry(record: MemoryRecord) -> dict[str, Any]:
    current = record.current
    entry: dict[str, Any] = {
        "record_id": record.record_id,
        "revision": current.number,
        "scope": record.scope,
        "text": current.body,
    }
    if current.target is not None:
        entry["cycle_id"] = current.target.cycle_id
        entry["task_types"] = list(current.target.task_types)
    if current.suggestion:
        entry["suggestion"] = True
    return entry


def _eligible(
    kind: SectionKind, loaded: Loaded, *, turn: ChatTurn, project_id: str | None
) -> list[MemoryRecord]:
    """The records ``kind`` may hold for this turn, in the order they're offered: what the person may read
    (``retrieved``: active and visible, T4), then the section's own filter."""
    visible = retrieved(
        loaded.records,
        viewer_id=turn.user_id,
        viewer_scopes=turn.viewer_scopes,
        project_id=project_id,
    )
    if kind is SectionKind.PREFERENCES:
        return [r for r in visible if r.kind == RecordKind.PREFERENCE]
    if kind is SectionKind.NOTES:
        return [r for r in visible if r.kind == RecordKind.NOTE]
    if kind is SectionKind.PROJECT_INSTRUCTIONS:
        return [
            r
            for r in visible
            if r.kind == RecordKind.INSTRUCTION
            and r.scope == RecordScope.PROJECT
            and r.current.confirmed_by is not None
        ]
    named = named_cycles(turn.text)
    return [
        r
        for r in visible
        if r.kind == RecordKind.INSTRUCTION
        and r.scope == RecordScope.TASK
        and r.current.target is not None
        and r.current.target.cycle_id in named
    ]


def chat_context(
    *,
    turn: ChatTurn,
    project_id: str | None,
    reads: Mapping[SectionKind, Loaded],
    limits: ChatLimits,
) -> tuple[tuple[Section, ...], dict[str, Any]]:
    """The turn's sections and what its agent is handed. Pure: ``reads`` gives each section the records
    its read returned, or its failure. The sections fill in ``CHAT_SECTIONS``'s order from one token
    budget, each record whole or omitted and listed; notes are also bounded by count (§3.10)."""
    left = limits.max_tokens
    sections: list[Section] = []
    handed: list[dict[str, Any]] = []
    unavailable: list[str] = []
    for kind in CHAT_SECTIONS:
        loaded = reads.get(kind)
        if loaded is None or (project_id is None and kind in _PROJECT_SECTIONS):
            sections.append(Section(kind, Need.OPTIONAL, Disposition.NOT_APPLICABLE))
            continue
        if loaded.failure is not None:
            sections.append(Section(kind, Need.OPTIONAL, Disposition.FAILED))
            unavailable.append(kind.value)
            continue
        eligible = _eligible(kind, loaded, turn=turn, project_id=project_id)
        supplied: list[MemoryRecord] = []
        omitted: list[tuple[RecordRef, str]] = []
        for record in eligible:
            ref = RecordRef(record.record_id, str(record.current.number))
            cost = _tokens(record.current.body)
            if kind is SectionKind.NOTES and len(supplied) == limits.max_notes:
                omitted.append((ref, OMITTED_BY_COUNT))
            elif cost > left:
                omitted.append((ref, OMITTED_BY_TOKENS))
            else:
                supplied.append(record)
                left -= cost
        if supplied:
            disposition = Disposition.SUPPLIED
        elif omitted:
            disposition = Disposition.OMITTED_BY_BUDGET
        else:
            disposition = Disposition.NONE_ELIGIBLE
        sections.append(
            Section(
                kind,
                Need.OPTIONAL,
                disposition,
                supplied=tuple(RecordRef(r.record_id, str(r.current.number)) for r in supplied),
                omitted=tuple(omitted),
                effective_budget=limits.max_tokens,
            )
        )
        if supplied or omitted:
            handed.append(
                {
                    "kind": kind.value,
                    "entries": [_entry(r) for r in supplied],
                    "omitted": len(omitted),
                }
            )
    # §3.5: a lesson never reaches chat.
    sections.append(Section(SectionKind.LESSONS, Need.OPTIONAL, Disposition.NOT_APPLICABLE))
    return tuple(sections), {
        "project_id": project_id,
        "sections": handed,
        "unavailable": unavailable,
    }


#: The sections only a project-bound turn holds: an unbound session sees its owner's records only.
_PROJECT_SECTIONS = frozenset({SectionKind.PROJECT_INSTRUCTIONS, SectionKind.TASK_INSTRUCTIONS})


@dataclass(frozen=True)
class ChatExposure:
    """What one chat turn's context held (§3.6 Disclosure), keyed by session and message: no cycle, run
    or task. Every failure stays a failure."""

    session_id: str
    message_id: str
    user_id: str
    agent_id: str
    project_id: str | None
    assembled_at: datetime
    sections: tuple[Section, ...] = field(default_factory=tuple)

    def sections_document(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": s.kind.value,
                "need": s.need.value,
                "disposition": s.disposition.value,
                "supplied": [
                    {"record_id": r.record_id, "revision": r.revision} for r in s.supplied
                ],
                "omitted": [
                    {"record_id": r.record_id, "revision": r.revision, "limit": why}
                    for r, why in s.omitted
                ],
                "effective_budget": s.effective_budget,
            }
            for s in self.sections
        ]

    @classmethod
    def from_document(cls, row: Mapping[str, Any]) -> ChatExposure:
        """An exposure as the store holds it: its keys, and ``sections_document()``."""
        return cls(
            session_id=str(row["session_id"]),
            message_id=str(row["message_id"]),
            user_id=str(row["user_id"]),
            agent_id=str(row["agent_id"]),
            project_id=row["project_id"],
            assembled_at=row["assembled_at"],
            sections=tuple(
                Section(
                    SectionKind(s["kind"]),
                    Need(s["need"]),
                    Disposition(s["disposition"]),
                    supplied=tuple(RecordRef(r["record_id"], r["revision"]) for r in s["supplied"]),
                    omitted=tuple(
                        (RecordRef(r["record_id"], r["revision"]), r["limit"]) for r in s["omitted"]
                    ),
                    effective_budget=s["effective_budget"],
                )
                for s in row["sections"]
            ),
        )

    @classmethod
    def of(cls, bundle: ContextBundle, *, at: datetime) -> ChatExposure:
        turn = bundle.request.consumer
        if not isinstance(turn, ChatTurn):
            raise TypeError("a chat exposure records a chat turn")
        binding = bundle.request.binding
        return cls(
            session_id=turn.session_id,
            message_id=turn.message_id,
            user_id=turn.user_id,
            agent_id=turn.agent_id,
            project_id=binding.project_id if isinstance(binding, ProjectBound) else None,
            assembled_at=at,
            sections=bundle.sections,
        )


# =============================================================================
# Capture (§3.5): proposed by the agent, chosen and confirmed by the person
# =============================================================================


@dataclass(frozen=True)
class CaptureChoice:
    """A kind and scope a confirmation card may offer: one the person may write (§3.3)."""

    kind: str
    scope: str
    project_id: str | None

    @property
    def takes_effect(self) -> str:
        """When a record of this choice reaches what it reaches: §3.5's sentence for the reply."""
        if self.scope == RecordScope.PROJECT:
            return (
                f"in chats bound to {self.project_id} from their next turn; no task receives a note"
            )
        return "in your chats from your next turn; no task receives it"


def capture_choices(
    *, scopes: Collection[str], project_id: str | None
) -> tuple[CaptureChoice, ...]:
    """What a card offers this person in this session. Stage A captures notes and preferences: a private
    note or a preference always; a project note when the session is bound and the person holds
    ``memory:note``. Instructions arrive with stage B."""
    choices = [
        CaptureChoice(RecordKind.NOTE, RecordScope.USER, None),
        CaptureChoice(RecordKind.PREFERENCE, RecordScope.USER, None),
    ]
    if project_id is not None and Scope.MEMORY_NOTE in scopes:
        choices.append(CaptureChoice(RecordKind.NOTE, RecordScope.PROJECT, project_id))
    return tuple(choices)


#: How the agent proposes a capture, at the end of its reply (``request.chat_memory_context``).
_CAPTURE_BLOCK = re.compile(r"<memory-capture>(.*?)</memory-capture>", re.DOTALL)


@dataclass(frozen=True)
class ProposedCapture:
    """What the agent proposed: the text and the kind, and the scope it suggests. The card's choices
    are the person's, never the agent's."""

    text: str
    kind: str
    scope: str


def proposed_capture(reply: str) -> tuple[ProposedCapture | None, str]:
    """The first well-formed capture the reply proposes, and the reply without any capture block. A
    malformed block is dropped from the reply and proposes nothing."""
    proposal = None
    for raw in _CAPTURE_BLOCK.findall(reply):
        if proposal is not None:
            break
        try:
            doc = json.loads(raw.strip())
        except ValueError:
            continue
        if not isinstance(doc, dict):
            continue
        text, kind = str(doc.get("text") or "").strip(), doc.get("kind")
        scope = doc.get("scope") or RecordScope.USER
        if text and kind in (RecordKind.NOTE, RecordKind.PREFERENCE) and scope in _CAPTURE_SCOPES:
            proposal = ProposedCapture(text, str(kind), str(scope))
    shown = _CAPTURE_BLOCK.sub("", reply).rstrip()
    return proposal, shown


_CAPTURE_SCOPES = frozenset({RecordScope.USER, RecordScope.PROJECT})


def failure_notice(unavailable: Iterable[str]) -> str:
    """The reply's first line when a section of its context couldn't be read (§3.5: disclosed in the
    reply, never swallowed)."""
    names = ", ".join(u.replace("_", " ") for u in unavailable)
    return f"_Memory: your {names} could not be read for this reply, so it was answered without them._\n\n"


_HEADINGS = {
    SectionKind.PROJECT_INSTRUCTIONS.value: "Project instructions in force",
    SectionKind.TASK_INSTRUCTIONS.value: "Task instructions for the cycles you named",
    SectionKind.PREFERENCES.value: "Your preferences",
    SectionKind.NOTES.value: "Notes",
}


def memory_lines(handed: Mapping[str, Any]) -> str:
    """The turn's memory context as the agent shows it (``request.chat_memory_context``): each section
    with its records, what was left out for space, and what couldn't be read."""
    project_id = handed.get("project_id")
    lines = [
        f"This conversation is bound to the project {project_id}."
        if project_id
        else "This conversation isn't bound to a project: only your own notes and preferences."
    ]
    for section in handed.get("sections") or ():
        lines.append(f"\n{_HEADINGS.get(section['kind'], section['kind'])}:")
        for n, entry in enumerate(section.get("entries") or (), start=1):
            lines.append(f"{n}. {_label(section['kind'], entry)}{entry['text']}")
        if section.get("omitted"):
            lines.append(f"({section['omitted']} more left out for space.)")
    if len(lines) == 1:
        lines.append("\nNothing is recorded for this conversation yet.")
    unavailable = handed.get("unavailable") or ()
    if unavailable:
        names = ", ".join(u.replace("_", " ") for u in unavailable)
        lines.append(
            f"\nCouldn't be read for this turn: {names}. Say so if it matters to the answer."
        )
    return "\n".join(lines)


def _label(kind: str, entry: Mapping[str, Any]) -> str:
    if kind == SectionKind.TASK_INSTRUCTIONS.value:
        return f"{entry.get('cycle_id')}, {', '.join(entry.get('task_types') or ())}: "
    if kind == SectionKind.NOTES.value:
        whose = "project" if entry.get("scope") == RecordScope.PROJECT else "yours"
        return f"({whose}, a suggestion) " if entry.get("suggestion") else f"({whose}) "
    return ""
