"""The typed memory records (SIP-0110 Appendix A, §A.3.2–§A.3.4, §A.3.8; #2177).

Three kinds, beside SIP-0110's observations and lessons:
- **a note:** something a person asked to keep. A ``suggestion`` is a note marked as a claim about how
  work should be done. A note never reaches a task (§A.3.2): it becomes an instruction only by an
  explicit, confirmed conversion;
- **a preference:** how a person wants to be worked with. It is always that person's own;
- **an instruction:** a directive the squad's work receives, binding.
  - **A project instruction** carries an applicability.
  - **A task instruction** carries a target cycle and a task selector, and never a snapshot owner (§A.3.7).

**Every record is revisions over one identity** (§A.3.8). A correction is a new revision naming the one
it supersedes; a withdrawal is a status change. Nothing is rewritten, and a withdrawn record is no
longer retrieved.

**References to authoritative records are references, never copies** (§A.3.2). A reference names its
target and the revision it means (``manifest:decision:<id>@<revision>``), and whether the record
requires it. Restating an authoritative fact inline would make memory a second copy that drifts, so a
reference that carries content is refused, naming where the fact is changed.

Pure: the store holds these records (``MemoryRecordsPort``), and the routes call these rules.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from squadops.auth.models import Scope


class RecordKind:
    NOTE = "note"
    PREFERENCE = "preference"
    INSTRUCTION = "instruction"
    ALL = frozenset({NOTE, PREFERENCE, INSTRUCTION})


class RecordScope:
    #: The signed-in person's own: read by them, and by chats they own.
    USER = "user"
    #: A project's: read with ``memory:read``, and by chats bound to the project.
    PROJECT = "project"
    #: Selected tasks of one target cycle (§A.3.7).
    TASK = "task"
    ALL = frozenset({USER, PROJECT, TASK})


#: Which scopes each kind may take (§A.3.2's table).
KIND_SCOPES: Mapping[str, frozenset[str]] = {
    RecordKind.NOTE: frozenset({RecordScope.USER, RecordScope.PROJECT}),
    RecordKind.PREFERENCE: frozenset({RecordScope.USER}),
    RecordKind.INSTRUCTION: frozenset({RecordScope.PROJECT, RecordScope.TASK}),
}


class RecordStatus:
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    ALL = frozenset({ACTIVE, WITHDRAWN})


class SourceKind:
    """Where a record came from (§A.3.4)."""

    CHAT_MESSAGE = "chat_message"
    GATE_DECISION = "gate_decision"
    CYCLE_REQUEST = "cycle_request"
    API_CALL = "api_call"
    CONVERSION = "conversion"
    ALL = frozenset({CHAT_MESSAGE, GATE_DECISION, CYCLE_REQUEST, API_CALL, CONVERSION})


#: ``<family>:<kind>:<id>@<revision>``: a reference to an authoritative record (§A.3.2).
_REFERENCE = re.compile(r"^[a-z][a-z_]*(:[a-z][a-z_]*)+:[^@\s]+@[^@\s]+$")
#: Where an authoritative fact is changed, by the reference's family (§A.3.2).
CHANGE_PATHS: Mapping[str, str] = {
    "manifest": "the manifest's operator edit (SIP-0103 §5c.5)",
    "decision": "a decision record (#950)",
}
_ANY = "*"


class RecordRefused(ValueError):
    """A record, revision or withdrawal the rules refuse, with why. Raised before anything is
    stored."""


class NotPermitted(PermissionError):
    """The caller doesn't hold what the record's kind and scope need (§A.3.3)."""


@dataclass(frozen=True)
class Reference:
    """An authoritative record, by reference (§A.3.2, §A.3.6)."""

    ref: str
    required: bool

    def __post_init__(self) -> None:
        if not _REFERENCE.match(self.ref):
            raise RecordRefused(
                f"a reference names its record and revision, <family>:<kind>:<id>@<revision>: "
                f"{self.ref!r}"
            )

    @property
    def family(self) -> str:
        return self.ref.split(":", 1)[0]


def reference_of(doc: Mapping[str, Any]) -> Reference:
    """A submitted reference. One that carries the target's content is refused, naming where
    that fact is changed: memory keeps a reference, never a second copy."""
    if "content" in doc or "value" in doc:
        ref = str(doc.get("ref", ""))
        path = CHANGE_PATHS.get(ref.split(":", 1)[0], "the record's own owner")
        raise RecordRefused(
            f"{ref or 'a reference'} is stored as a reference, never a copy: to change what it says, "
            f"use {path}"
        )
    return Reference(str(doc.get("ref", "")), bool(doc.get("required", False)))


@dataclass(frozen=True)
class InstructionApplicability:
    """Where a project instruction applies: every field explicit, ``*`` for any (an unknown never
    means everywhere, as a lesson's applicability)."""

    task_types: tuple[str, ...]
    roles: tuple[str, ...]
    stacks: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("task_types", "roles", "stacks"):
            values = getattr(self, name)
            if not values or any(not str(v).strip() for v in values):
                raise RecordRefused(
                    f"an instruction's applicability names its {name} ('*' for any)"
                )

    def covers(self, *, task_type: str, role: str, stack: str | None) -> bool:
        def fits(values: tuple[str, ...], value: str | None) -> bool:
            return _ANY in values or (value is not None and value in values)

        return (
            fits(self.task_types, task_type) and fits(self.roles, role) and fits(self.stacks, stack)
        )


@dataclass(frozen=True)
class TaskTarget:
    """A task instruction's target (§A.3.7): one cycle, and the tasks within it by type."""

    cycle_id: str
    task_types: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.cycle_id.strip() or not self.task_types:
            raise RecordRefused("a task instruction names its target cycle and its tasks")


@dataclass(frozen=True)
class Source:
    """Where a record came from (§A.3.4), typed, with the ids that locate it."""

    kind: str
    ids: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in SourceKind.ALL:
            raise RecordRefused(f"a source is one of {sorted(SourceKind.ALL)}, not {self.kind!r}")


@dataclass(frozen=True)
class Revision:
    """One immutable revision of a record. ``supersedes`` names the revision it replaces."""

    number: int
    body: str
    author: str
    created_at: datetime
    source: Source
    confirmed_by: str | None = None
    supersedes: int | None = None
    suggestion: bool = False
    applicability: InstructionApplicability | None = None
    target: TaskTarget | None = None
    references: tuple[Reference, ...] = ()


@dataclass(frozen=True)
class StatusChange:
    status: str
    by: str
    at: datetime
    why: str


@dataclass(frozen=True)
class MemoryRecord:
    """A record: its identity, its kind and scope, and every revision and status change."""

    record_id: str
    kind: str
    scope: str
    project_id: str | None
    owner_id: str
    revisions: tuple[Revision, ...]
    status_changes: tuple[StatusChange, ...] = ()

    @property
    def current(self) -> Revision:
        return self.revisions[-1]

    @property
    def status(self) -> str:
        return self.status_changes[-1].status if self.status_changes else RecordStatus.ACTIVE


def required_scope(kind: str, scope: str, *, campaign_cycle: bool = False) -> str | None:
    """The scope a caller needs to create, revise or withdraw a record of ``kind`` and
    ``scope`` (§A.3.3). ``None`` for a user-private record: only its owner may, for themselves."""
    if scope == RecordScope.USER:
        return None
    if kind == RecordKind.NOTE:
        return Scope.MEMORY_NOTE
    if scope == RecordScope.PROJECT:
        return Scope.MEMORY_INSTRUCT
    return Scope.CAMPAIGNS_SUPERVISE if campaign_cycle else Scope.CYCLES_WRITE


def authorize_write(
    kind: str,
    scope: str,
    *,
    actor_id: str,
    actor_scopes: Collection[str],
    owner_id: str,
    campaign_cycle: bool = False,
) -> None:
    """Refused unless the actor may write this record (§A.3.3), the same rule through chat and
    the API."""
    needed = required_scope(kind, scope, campaign_cycle=campaign_cycle)
    if needed is None:
        if actor_id != owner_id:
            raise NotPermitted("a user-private record is written by its owner, for themselves")
        return
    if needed not in actor_scopes:
        raise NotPermitted(f"a {scope} {kind} needs {needed}")


def visible(
    record: MemoryRecord,
    *,
    viewer_id: str,
    viewer_scopes: Collection[str],
    project_id: str | None,
) -> bool:
    """Whether a query bound to ``project_id`` (``None``: unbound) answers with ``record`` (T4).
    A user-private record answers its owner only. A project's or a task's answers ``memory:read``
    on a query bound to that project. An unbound query gets only its owner's private records."""
    if record.scope == RecordScope.USER:
        return record.owner_id == viewer_id
    if project_id is None or record.project_id != project_id:
        return False
    return Scope.MEMORY_READ in viewer_scopes


def retrieved(records: Collection[MemoryRecord], **who: Any) -> list[MemoryRecord]:
    """What a query answers: the visible, active records. A withdrawn record is never retrieved,
    though its history is kept."""
    return [r for r in records if r.status == RecordStatus.ACTIVE and visible(r, **who)]


def shown_source(
    record: MemoryRecord, revision: Revision, *, viewer_id: str, session_deleted: bool = False
) -> dict[str, Any]:
    """A revision's source as ``viewer_id`` may see it (§A.3.4). A record that came from a chat
    turn shows that turn's ids only to the turn's author; anyone else sees who and when. A record
    confirmed from a session its owner since deleted stays, marked so (§A.8 Q29, #2180)."""
    source = revision.source
    deleted = {"session_deleted": True} if session_deleted else {}
    if source.kind == SourceKind.CHAT_MESSAGE and viewer_id != revision.author:
        return {
            "kind": source.kind,
            "summary": f"converted from a private chat turn by {revision.author}, "
            f"{revision.created_at.isoformat()}",
            **deleted,
        }
    return {"kind": source.kind, "ids": dict(source.ids), **deleted}


def new_record(
    *,
    record_id: str,
    kind: str,
    scope: str,
    project_id: str | None,
    owner_id: str,
    revision: Revision,
) -> MemoryRecord:
    """A record's first revision, checked against §A.3.2's kinds and scopes."""
    if kind not in RecordKind.ALL:
        raise RecordRefused(f"a record is one of {sorted(RecordKind.ALL)}, not {kind!r}")
    if scope not in KIND_SCOPES[kind]:
        raise RecordRefused(f"a {kind} takes scope {sorted(KIND_SCOPES[kind])}, not {scope!r}")
    if scope != RecordScope.USER and not project_id:
        raise RecordRefused(f"a {scope} {kind} names its project")
    _check_revision(kind, scope, revision)
    return MemoryRecord(record_id, kind, scope, project_id, owner_id, (revision,))


def _check_revision(kind: str, scope: str, revision: Revision) -> None:
    if not revision.body.strip():
        raise RecordRefused("a record says something: its body is empty")
    if revision.suggestion and kind != RecordKind.NOTE:
        raise RecordRefused("a suggestion is a note marked as a claim")
    if kind == RecordKind.INSTRUCTION:
        if scope == RecordScope.PROJECT and revision.applicability is None:
            raise RecordRefused("a project instruction names its applicability")
        if scope == RecordScope.TASK and revision.target is None:
            raise RecordRefused("a task instruction names its target cycle and its tasks")
        if any(r.ref.endswith("@current") for r in revision.references):
            # #2178, #2179: an instruction's references are bound to a concrete revision when the
            # unit binds them (§3.7): a task instruction's with its cycle's inputs, a project
            # instruction's in the snapshot that pins it. Resolving ``@current`` at that binding is
            # each one's second stage; a pin that kept it unresolved could never be bound after.
            raise RecordRefused(
                f"a {scope} instruction's reference names its revision; @current isn't bound yet"
            )
        if revision.confirmed_by is None:
            raise RecordRefused("an instruction binds the work, so it is confirmed")
    elif revision.applicability is not None or revision.target is not None:
        raise RecordRefused(f"a {kind} reaches no task, so it has no applicability or target")


def revised(record: MemoryRecord, revision: Revision) -> MemoryRecord:
    """``record`` with ``revision`` as its new current one. It supersedes the current revision,
    which is kept. A withdrawn record is not revised: it stays withdrawn, and a new record is made."""
    if record.status == RecordStatus.WITHDRAWN:
        raise RecordRefused(f"{record.record_id} is withdrawn, and a withdrawal isn't undone")
    numbered = replace(revision, number=record.current.number + 1, supersedes=record.current.number)
    _check_revision(record.kind, record.scope, numbered)
    before, after = record.current.target, numbered.target
    if before is not None and after is not None and before.cycle_id != after.cycle_id:
        # §3.5: a task instruction is authoritative for its target cycle only. Moving it would
        # withdraw it from one cycle and add it to another, unrecorded on either (#2178).
        raise RecordRefused(
            f"a task instruction's cycle is fixed ({before.cycle_id}): withdraw it, and give "
            f"{after.cycle_id} its own"
        )
    return replace(record, revisions=(*record.revisions, numbered))


def withdrawn(record: MemoryRecord, *, by: str, at: datetime, why: str) -> MemoryRecord:
    """``record``, withdrawn: no longer retrieved, every revision kept."""
    if record.status == RecordStatus.WITHDRAWN:
        raise RecordRefused(f"{record.record_id} is already withdrawn")
    if not why.strip():
        raise RecordRefused("a withdrawal says why")
    change = StatusChange(RecordStatus.WITHDRAWN, by, at, why)
    return replace(record, status_changes=(*record.status_changes, change))


def revision_document(revision: Revision) -> dict[str, Any]:
    """A revision as it is stored: every field, references kept as references."""
    return {
        "number": revision.number,
        "body": revision.body,
        "author": revision.author,
        "created_at": revision.created_at.isoformat(),
        "source": {"kind": revision.source.kind, "ids": dict(revision.source.ids)},
        "confirmed_by": revision.confirmed_by,
        "supersedes": revision.supersedes,
        "suggestion": revision.suggestion,
        "applicability": (
            {
                "task_types": list(revision.applicability.task_types),
                "roles": list(revision.applicability.roles),
                "stacks": list(revision.applicability.stacks),
            }
            if revision.applicability
            else None
        ),
        "target": (
            {"cycle_id": revision.target.cycle_id, "task_types": list(revision.target.task_types)}
            if revision.target
            else None
        ),
        "references": [{"ref": r.ref, "required": r.required} for r in revision.references],
    }


def revision_from_document(doc: Mapping[str, Any]) -> Revision:
    """A stored revision, read back as it was written."""
    applicability = doc.get("applicability")
    target = doc.get("target")
    return Revision(
        number=int(doc["number"]),
        body=doc["body"],
        author=doc["author"],
        created_at=datetime.fromisoformat(doc["created_at"]),
        source=Source(doc["source"]["kind"], dict(doc["source"].get("ids") or {})),
        confirmed_by=doc.get("confirmed_by"),
        supersedes=doc.get("supersedes"),
        suggestion=bool(doc.get("suggestion")),
        applicability=(
            InstructionApplicability(
                tuple(applicability["task_types"]),
                tuple(applicability["roles"]),
                tuple(applicability["stacks"]),
            )
            if applicability
            else None
        ),
        target=TaskTarget(target["cycle_id"], tuple(target["task_types"])) if target else None,
        references=tuple(
            Reference(r["ref"], bool(r["required"])) for r in doc.get("references", [])
        ),
    )


@dataclass(frozen=True)
class PinnedInstruction:
    """A project instruction's revision as a unit pinned it at admission (Appendix A §3.7; #2179).
    Self-contained, as the rest of a snapshot is: the pin never depends on rows read later, so a
    unit keeps the revision it pinned however the record changes after."""

    record_id: str
    revision: int
    text: str
    applicability: InstructionApplicability
    references: tuple[Reference, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "revision": self.revision,
            "text": self.text,
            "applicability": {
                "task_types": list(self.applicability.task_types),
                "roles": list(self.applicability.roles),
                "stacks": list(self.applicability.stacks),
            },
            "references": [{"ref": r.ref, "required": r.required} for r in self.references],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PinnedInstruction:
        a = data["applicability"]
        return cls(
            record_id=str(data["record_id"]),
            revision=int(data["revision"]),
            text=str(data["text"]),
            applicability=InstructionApplicability(
                tuple(a["task_types"]), tuple(a["roles"]), tuple(a["stacks"])
            ),
            references=tuple(
                Reference(r["ref"], bool(r["required"])) for r in data.get("references", [])
            ),
        )


@dataclass(frozen=True)
class Rebinding:
    """One re-binding of a running unit (Appendix A §3.7; #2179): the project instruction's revision
    the unit bound, replaced by the record's current revision, or by nothing when the record is
    withdrawn. An intervention, recorded with who, when and why. The snapshot keeps every
    re-binding, so what the unit bound at admission is still read."""

    record_id: str
    replaced: PinnedInstruction
    replacement: PinnedInstruction | None
    by: str
    at: datetime
    why: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "replaced": self.replaced.to_dict(),
            "replacement": self.replacement.to_dict() if self.replacement else None,
            "by": self.by,
            "at": self.at.isoformat(),
            "why": self.why,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Rebinding:
        replacement = data.get("replacement")
        return cls(
            record_id=str(data["record_id"]),
            replaced=PinnedInstruction.from_dict(data["replaced"]),
            replacement=PinnedInstruction.from_dict(replacement) if replacement else None,
            by=str(data["by"]),
            at=datetime.fromisoformat(str(data["at"])),
            why=str(data["why"]),
        )


def pinned_of(record: MemoryRecord) -> PinnedInstruction:
    """A project instruction's current revision, as a unit binds it."""
    current = record.current
    if current.applicability is None:
        raise RecordRefused(f"{record.record_id} is not a project instruction")
    return PinnedInstruction(
        record.record_id, current.number, current.body, current.applicability, current.references
    )


def in_force(records: Collection[MemoryRecord]) -> tuple[PinnedInstruction, ...]:
    """The project instructions in force now, as a unit admitted now pins them: active, confirmed,
    each at its current revision, in the order they were recorded."""
    pinned = []
    for record in records:
        if (
            record.kind != RecordKind.INSTRUCTION
            or record.scope != RecordScope.PROJECT
            or record.status != RecordStatus.ACTIVE
        ):
            continue
        current = record.current
        if current.applicability is None or current.confirmed_by is None:
            continue
        pinned.append(pinned_of(record))
    return tuple(pinned)
