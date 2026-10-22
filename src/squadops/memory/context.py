"""Context assembly's types (SIP-0110 Appendix A §3.6; #2176, inert in 2.3).

What a consumer asks for, and what it is given, section by section. The consumer is typed, a task invocation at
a consuming seam or a chat turn, and so is its project binding, so a fabricated cycle or project cannot be
represented: a chat turn has no cycle, run or task, an unbound request has no project, and a task invocation
is always bound to a project.

In 2.3 the only section is SIP-0110's lessons, optional and answered by today's recall. 2.4 adds the binding
sections (#2178, #2179) and chat's own (#2180, ``squadops.memory.chat``): optional, since a chat turn executes no
work.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from squadops.memory.lessons import Recalled
from squadops.memory.recall import UnitKind


class Need(StrEnum):
    #: Task and project instructions, and the references they require: never omitted.
    BINDING = "binding"
    #: Lessons, notes, preferences and optional references: omitted whole, and disclosed.
    OPTIONAL = "optional"


class Disposition(StrEnum):
    """A section's outcome: SIP-0110 §0.8's, per section, and two that only sections have."""

    SUPPLIED = "supplied"
    NONE_ELIGIBLE = "none_eligible"
    #: Recall's own word for it (``RecallDisposition.DISABLED``), so a section and its exposure read the same.
    #: §3.6 writes "disabled"; that bare word would shadow unrelated config comparisons (#380's guard).
    DISABLED = "memory_disabled"
    #: The unit declared ``memory_context: none`` (§3.7): its project instructions and lessons are
    #: withheld, as recall words it (``RecallDisposition.CONTEXT_NONE``).
    CONTEXT_NONE = "memory_context_none"
    #: An optional section only.
    OMITTED_BY_BUDGET = "omitted_by_budget"
    INCOMPATIBLE = "incompatible"
    FAILED = "failed"
    #: A binding record not loaded, not resolved or not fitted: the task is held, undispatched.
    INCOMPLETE = "incomplete"
    #: A section that does not apply to its consumer, such as lessons on a chat turn.
    NOT_APPLICABLE = "not_applicable"


class SectionKind(StrEnum):
    TASK_INSTRUCTIONS = "task_instructions"
    PROJECT_INSTRUCTIONS = "project_instructions"
    REFERENCES = "references"
    LESSONS = "lessons"
    NOTES = "notes"
    PREFERENCES = "preferences"
    #: A project's approved lessons shown to a chat turn that asks about them, to explain, never as
    #: guidance (§3.5, #2181): that is ``LESSONS``, which a chat turn never holds.
    INSPECTED_LESSONS = "inspected_lessons"


@dataclass(frozen=True)
class UnitRef:
    """A unit that pins a snapshot (§0.7): a standalone cycle, or a campaign."""

    kind: UnitKind
    unit_id: str


@dataclass(frozen=True)
class RecordRef:
    """A record and the revision supplied or omitted."""

    record_id: str
    revision: str

    @classmethod
    def of_revision_id(cls, revision_id: str) -> RecordRef:
        """A lesson's ``pattern@revision`` id."""
        record, _, revision = revision_id.rpartition("@")
        return cls(record or revision_id, revision if record else "")


@dataclass(frozen=True)
class ProjectBound:
    #: From the envelope, or a chat session's stored binding.
    project_id: str


@dataclass(frozen=True)
class Unbound:
    """A chat session opened with no project: its owner's private records only."""


@dataclass(frozen=True)
class TaskInvocation:
    """An authoring invocation at a consuming seam (SIP-0110 §0.9)."""

    run_id: str
    task_id: str
    attempt: int
    #: The cycle this task belongs to: what task instructions match (§3.7).
    target_cycle_id: str
    #: The cycle itself, or its campaign: whose snapshot answers (§3.7). Never used to match instructions.
    snapshot_owner: UnitRef
    task_type: str
    role: str
    stack: str
    model_family: str
    agent_id: str
    #: Tokens: the model's window less the completion reserve and the task's own inputs (§3.6 Budgets);
    #: ``-1`` when the model's window is unknown, which never means room.
    prompt_budget: int


@dataclass(frozen=True)
class ChatTurn:
    """One chat turn. It has no cycle, run or task; its owner and agent are already checked (§3.3)."""

    session_id: str
    message_id: str
    user_id: str
    agent_id: str
    #: What the person said: the notes are ranked by it, and the cycles it names select task
    #: instructions (§3.10, #2180).
    text: str = ""
    #: The person's scopes, from their identity: what of a bound project they may read (§3.3).
    viewer_scopes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ContextRequest:
    binding: ProjectBound | Unbound
    consumer: TaskInvocation | ChatTurn

    def __post_init__(self) -> None:
        if isinstance(self.consumer, TaskInvocation) and not isinstance(self.binding, ProjectBound):
            raise TypeError("a task invocation is always bound to a project (§3.6)")


@dataclass(frozen=True)
class Section:
    kind: SectionKind
    need: Need
    disposition: Disposition
    supplied: tuple[RecordRef, ...] = ()
    #: Optional sections only: each record left out, and the limit or reason that left it out.
    omitted: tuple[tuple[RecordRef, str], ...] = ()
    #: Optional sections: what the section could spend. None for a binding section.
    effective_budget: int | None = None
    #: Binding sections only: what could not be loaded, resolved or fitted.
    unresolved: tuple[tuple[RecordRef, str], ...] = ()
    #: Binding sections only: incomplete because the store didn't answer, so nothing an operator
    #: gave can be judged. Otherwise an incomplete section is the operator's input: over its
    #: budget, or naming a reference its cycle couldn't bind. A held run ends by which (#2178).
    store_failed: bool = False


@dataclass(frozen=True)
class ContextBundle:
    request: ContextRequest
    sections: tuple[Section, ...]
    #: False when any binding section is incomplete: the task is then held, undispatched.
    complete: bool
    #: The lesson section's answer as recall gave it: what the task is handed, and what its exposure records.
    #: The section rendered is exactly the set recall returned (§3.6), so it is carried, never rebuilt.
    #: None for a consumer recall does not answer.
    recalled: Recalled | None = None
    #: What the task is handed on ``TASK_INSTRUCTIONS_INPUT`` (#2178), carried as recall's answer is:
    #: ``None`` when no task instruction applies.
    task_instructions: Mapping[str, Any] | None = None
    #: What the task is handed on ``PROJECT_INSTRUCTIONS_INPUT`` (#2179): ``None`` when none applies.
    project_instructions: Mapping[str, Any] | None = None
    #: What a chat turn's agent is handed (#2180): its sections' records, and the sections that failed.
    #: ``None`` for a task, and for a chat turn with no records store.
    chat: Mapping[str, Any] | None = None

    def section(self, kind: SectionKind) -> Section | None:
        return next((s for s in self.sections if s.kind == kind), None)
