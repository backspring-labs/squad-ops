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
from squadops.memory.exposures import Exposure
from squadops.memory.lessons import Approval, PatternRevision, _tokens
from squadops.memory.records import (
    MemoryRecord,
    RecordKind,
    RecordScope,
    retrieved,
)

logger = logging.getLogger(__name__)

#: A cycle a turn names, by its id: the cycles whose task instructions the turn sees (§3.5).
NAMED_CYCLE = re.compile(r"\bcyc_[0-9a-f]{12}\b")
#: A turn that asks about lessons: it says "lesson", or names one by its pattern or revision (#2181).
NAMED_LESSON = re.compile(r"\bpat_[0-9a-f]{16}(?:@\d+)?\b")
_ASKS_ABOUT_LESSONS = re.compile(r"\blessons?\b", re.IGNORECASE)

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


@dataclass(frozen=True)
class LessonsLoaded:
    """A project's lessons as the lessons API reads them (``memory:read``), with the exposures that
    supplied them, or why they couldn't be read (#2181)."""

    revisions: tuple[PatternRevision, ...] = ()
    approvals: tuple[Approval, ...] = ()
    exposures: tuple[Exposure, ...] = ()
    failure: str | None = None


def named_cycles(text: str) -> frozenset[str]:
    return frozenset(NAMED_CYCLE.findall(text))


def asks_about_lessons(text: str) -> bool:
    return bool(_ASKS_ABOUT_LESSONS.search(text) or NAMED_LESSON.search(text))


def _inspected(lessons: LessonsLoaded, *, text: str) -> list[dict[str, Any]]:
    """The approved lessons in force for the project, each as its record shows it: the text, what it
    targets and cites, what it is approved for and by whom, the replay check, and how many dispatches
    were supplied it. A lesson the turn names comes first."""
    revisions = {r.revision_id: r for r in lessons.revisions}
    named = set(NAMED_LESSON.findall(text))
    entries = []
    for approval in lessons.approvals:
        revision = revisions.get(approval.revision_id)
        if revision is None or approval.revoked_at is not None:
            continue
        applicability = approval.applicability.to_dict()
        applicability.pop("project_id", None)
        entries.append(
            {
                "revision_id": revision.revision_id,
                "target_behavior": revision.target_behavior,
                "text": revision.text,
                "applicability": applicability,
                "cited_observations": list(revision.cited_observations),
                "approval": {
                    "approval_id": approval.approval_id,
                    "approved_by": approval.approved_by,
                    "approved_at": approval.approved_at.isoformat(),
                    "ruling": approval.ruling,
                    "replay_check": dict(approval.replay_check),
                },
                "supplied_in": sum(
                    any(
                        i.get("revision_id") == revision.revision_id
                        for i in e.recalled.get("intervention") or ()
                    )
                    for e in lessons.exposures
                ),  # fmt: skip
            }
        )
    return sorted(
        entries,
        key=lambda e: not (e["revision_id"] in named or e["revision_id"].split("@")[0] in named),
    )


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
    lessons: LessonsLoaded | None = None,
) -> tuple[tuple[Section, ...], dict[str, Any]]:
    """The turn's sections and what its agent is handed. Pure: ``reads`` gives each section the records
    its read returned, or its failure. The sections fill in ``CHAT_SECTIONS``'s order from one token
    budget, each record whole or omitted and listed; notes are also bounded by count (§3.10). The
    project's approved lessons come last, when the turn asked about them (``lessons``), to inspect:
    the lesson section a task holds is never a chat turn's (#2181)."""
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
    sections.append(
        _inspected_section(lessons, turn=turn, project_id=project_id, left=left, limits=limits,
                           handed=handed, unavailable=unavailable)
    )  # fmt: skip
    # §3.5: a lesson never reaches chat as guidance.
    sections.append(Section(SectionKind.LESSONS, Need.OPTIONAL, Disposition.NOT_APPLICABLE))
    return tuple(sections), {
        "project_id": project_id,
        "sections": handed,
        "unavailable": unavailable,
    }


def _inspected_section(
    lessons: LessonsLoaded | None,
    *,
    turn: ChatTurn,
    project_id: str | None,
    left: int,
    limits: ChatLimits,
    handed: list[dict[str, Any]],
    unavailable: list[str],
) -> Section:
    """The inspected lessons' section, adding what the agent is handed. Not applicable to an unbound
    turn, or one that didn't ask (no lessons were read for it)."""
    kind = SectionKind.INSPECTED_LESSONS
    if lessons is None or project_id is None:
        return Section(kind, Need.OPTIONAL, Disposition.NOT_APPLICABLE)
    if lessons.failure is not None:
        unavailable.append(kind.value)
        return Section(kind, Need.OPTIONAL, Disposition.FAILED)
    supplied: list[dict[str, Any]] = []
    omitted: list[tuple[RecordRef, str]] = []
    for entry in _inspected(lessons, text=turn.text):
        cost = _tokens(json.dumps(entry))
        if cost > left:
            omitted.append((RecordRef.of_revision_id(entry["revision_id"]), OMITTED_BY_TOKENS))
        else:
            supplied.append(entry)
            left -= cost
    if supplied or omitted:
        handed.append({"kind": kind.value, "entries": supplied, "omitted": len(omitted)})
    disposition = (
        Disposition.SUPPLIED
        if supplied
        else Disposition.OMITTED_BY_BUDGET
        if omitted
        else Disposition.NONE_ELIGIBLE
    )
    return Section(
        kind,
        Need.OPTIONAL,
        disposition,
        supplied=tuple(RecordRef.of_revision_id(e["revision_id"]) for e in supplied),
        omitted=tuple(omitted),
        effective_budget=limits.max_tokens,
    )


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
        if self.scope == RecordScope.TASK:
            return (
                "for the named cycle's selected tasks from their next dispatch, as an intervention: "
                "refused once one of them has dispatched"
            )
        if self.kind == RecordKind.INSTRUCTION:
            return (
                f"for {self.project_id}'s cycles and campaigns admitted from now, on the tasks its "
                "applicability covers; running ones keep their snapshot"
            )
        if self.scope == RecordScope.PROJECT:
            return (
                f"in chats bound to {self.project_id} from their next turn; no task receives a note"
            )
        return "in your chats from your next turn; no task receives it"


def capture_choices(
    *, scopes: Collection[str], project_id: str | None
) -> tuple[CaptureChoice, ...]:
    """What a card offers this person in this session: a private note or a preference always; on a
    bound session, a project note with ``memory:note``, a project instruction with
    ``memory:instruct``, and a task instruction with ``cycles:write`` or ``campaigns:supervise``
    (stage B, #2180). A task instruction names an admitted cycle, so it is an intervention (§3.5):
    which of the two its cycle needs is checked when it is confirmed."""
    choices = [
        CaptureChoice(RecordKind.NOTE, RecordScope.USER, None),
        CaptureChoice(RecordKind.PREFERENCE, RecordScope.USER, None),
    ]
    if project_id is not None and Scope.MEMORY_NOTE in scopes:
        choices.append(CaptureChoice(RecordKind.NOTE, RecordScope.PROJECT, project_id))
    if project_id is not None and Scope.MEMORY_INSTRUCT in scopes:
        choices.append(CaptureChoice(RecordKind.INSTRUCTION, RecordScope.PROJECT, project_id))
    if project_id is not None and {Scope.CYCLES_WRITE, Scope.CAMPAIGNS_SUPERVISE} & set(scopes):
        choices.append(CaptureChoice(RecordKind.INSTRUCTION, RecordScope.TASK, project_id))
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
    #: A conversational claim, kept as a hypothesis: never a lesson's citation (§3.5, T5).
    suggestion: bool = False
    #: A project instruction's applicability as the agent proposes it (task types, roles, stacks), a
    #: field left out or malformed empty; ``None`` for a note or a preference. The card shows it, and
    #: the person fills, confirms or changes it.
    applicability: Mapping[str, tuple[str, ...]] | None = None
    #: A task instruction's target as the agent proposes it: the cycle (``""`` when left out) and its
    #: task types, which the person fills, confirms or changes on the card. ``None`` for anything else.
    target: Mapping[str, Any] | None = None
    #: The lesson revision a task instruction applies ("apply lesson X to this task"), named as its
    #: provenance. A lessons-disabled unit refuses one (§3.7's guarantee).
    lesson_revision: str | None = None


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
        if not isinstance(kind, str) or not isinstance(scope, str):
            # An unhashable kind or scope (a list) proposes nothing, never ends the stream (the second
            # read of PR #2525).
            continue
        if text and kind in (RecordKind.NOTE, RecordKind.PREFERENCE) and scope in _CAPTURE_SCOPES:
            suggestion = doc.get("suggestion") is True and kind == RecordKind.NOTE
            proposal = ProposedCapture(text, str(kind), str(scope), suggestion)
        elif text and kind == RecordKind.INSTRUCTION and doc.get("scope") == RecordScope.TASK:
            # A task instruction stays one: never widened into a project instruction (§3.5).
            lesson = doc.get("lesson")
            proposal = ProposedCapture(
                text, RecordKind.INSTRUCTION, RecordScope.TASK,
                target=_proposed_target(doc.get("target")),
                # Kept as named, malformed or not: dropping one would drop the check it carries, so
                # the card shows it and the capture refuses a malformed one (the second read).
                lesson_revision=lesson.strip() if isinstance(lesson, str) and lesson.strip()
                else None,
            )  # fmt: skip
        elif (
            text
            and kind == RecordKind.INSTRUCTION
            and (doc.get("scope") or RecordScope.PROJECT) == RecordScope.PROJECT
        ):
            proposal = ProposedCapture(
                text, RecordKind.INSTRUCTION, RecordScope.PROJECT,
                applicability=_proposed_applicability(doc.get("applicability")),
            )  # fmt: skip
    shown = _CAPTURE_BLOCK.sub("", reply).rstrip()
    return proposal, shown


_CAPTURE_SCOPES = frozenset({RecordScope.USER, RecordScope.PROJECT})
_APPLICABILITY_FIELDS = ("task_types", "roles", "stacks")


def offered_target(target: Mapping[str, Any], said: str) -> dict[str, Any]:
    """The proposed target as the card offers it: its cycle blanked unless the person's own message
    named it. The agent may only repeat a cycle, never pick one (the second read of #2180)."""
    cycle = target.get("cycle_id") or ""
    return {
        "cycle_id": cycle if cycle in named_cycles(said) else "",
        "task_types": list(target.get("task_types") or ()),
    }


def _proposed_target(raw: Any) -> dict[str, Any]:
    """The target cycle and task types an agent proposed. A cycle left out or malformed is ``""``,
    and task types the same as an applicability's: empty, for the person to fill. The card keeps the
    cycle only when the person named it (``offered_target``): an instruction for the wrong cycle
    would bind that cycle's work."""
    raw = raw if isinstance(raw, dict) else {}
    cycle = raw.get("cycle_id")
    types = raw.get("task_types")
    return {
        "cycle_id": cycle.strip()
        if isinstance(cycle, str) and NAMED_CYCLE.fullmatch(cycle.strip())
        else "",
        "task_types": tuple(str(t).strip() for t in types if str(t).strip())
        if isinstance(types, list)
        else (),
    }


def _proposed_applicability(raw: Any) -> dict[str, tuple[str, ...]]:
    """The applicability an agent proposed, each field the names it gave. A field it left out, or
    gave malformed, is empty, never ``*``: an unknown never means everywhere (§A.3.2), so the card
    shows it blank and the capture is refused until the person fills it ('*' for any is theirs to
    choose)."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for name in _APPLICABILITY_FIELDS:
        values = raw.get(name)
        out[name] = (
            tuple(str(v).strip() for v in values if str(v).strip())
            if isinstance(values, list)
            else ()
        )
    return out


#: The reply's first line when the agent couldn't render the context it was handed (the second read of PR
#: #2517): the runtime's exposure records what it handed, and the reply says the agent didn't show it.
RENDER_FAILURE_NOTICE = (
    "_Memory: your records couldn't be shown to the agent for this reply, so it was answered "
    "without them._\n\n"
)


def used_line(handed: Mapping[str, Any]) -> str:
    """The reply's closing line naming the records its context supplied, by id and revision
    (§A.3.11: "a short line naming the records it used"), an inspected lesson by its revision id
    (#2181), or ``""`` when it supplied none."""
    used = [
        entry["revision_id"]
        if "revision_id" in entry
        else f"{entry['record_id']}@{entry['revision']}"
        for section in handed.get("sections") or ()
        for entry in section.get("entries") or ()
    ]
    return f"\n\n_Memory used: {', '.join(used)}._" if used else ""


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
    SectionKind.INSPECTED_LESSONS.value: (
        "The project's approved lessons, to explain when asked (they guide the squad's tasks, "
        "never this conversation)"
    ),
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
            if section["kind"] == SectionKind.INSPECTED_LESSONS.value:
                lines.append(f"{n}. {_lesson_line(entry)}")
            else:
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


def _lesson_line(entry: Mapping[str, Any]) -> str:
    """One inspected lesson, its evidence and approval cited by id (#2181)."""
    applies = "; ".join(
        f"{name.replace('_', ' ')} {', '.join(values)}"
        for name, values in entry["applicability"].items()
        if isinstance(values, list)
    )
    approval = entry["approval"]
    replay = approval["replay_check"]
    return (
        f"{entry['revision_id']}, for {entry['target_behavior']}: {entry['text']}\n"
        f"   Applies to {applies}. Cites {', '.join(entry['cited_observations']) or 'nothing'}.\n"
        f"   Approved by {approval['approved_by']} at {approval['approved_at']} "
        f"({approval['approval_id']}){': ' + approval['ruling'] if approval['ruling'] else ''}. "
        f"Replay check: {replay.get('result', replay) if replay else 'none recorded'}. "
        f"Supplied to {entry['supplied_in']} task dispatch(es)."
    )


def _label(kind: str, entry: Mapping[str, Any]) -> str:
    if kind == SectionKind.TASK_INSTRUCTIONS.value:
        return f"{entry.get('cycle_id')}, {', '.join(entry.get('task_types') or ())}: "
    if kind == SectionKind.NOTES.value:
        whose = "project" if entry.get("scope") == RecordScope.PROJECT else "yours"
        return f"({whose}, a suggestion) " if entry.get("suggestion") else f"({whose}) "
    return ""
