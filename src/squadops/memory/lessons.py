"""Lessons, approvals, the pinned snapshot and recall (SIP-0110 §0.2, §0.6–§0.8; slice 3c, #2096).

A **pattern revision** is one lesson's immutable text, drafted by the frontier-model auditor
(D15) with its applicability, template, drafter and the observations it cites. An **approval**
binds one revision to a stated applicability, owner-given, with the replay check it was given. A
**snapshot** is what a unit of execution (a standalone cycle, or a campaign and all its cycles)
pinned when it was admitted: the approved revisions then in force, and the recall policy. It
never changes while the unit runs (§0.7).

**Recall is deterministic** (§0.8): applicability filters first (an unknown never means
"everywhere"), then one revision per pattern, then a total order (approval time, then pattern),
then the budgets (at most three lessons, and a token budget; a lesson over budget is left out
whole, never cut). Five outcomes stay distinct: memory disabled, nothing eligible, supplied,
everything eligible omitted by the budget, and recall failed, which the caller records when the
recall itself raises.

Pure: the store holds these records, and the composers call :func:`recall`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from squadops.memory.recall import RecallQuery

#: A stack-independent lesson says so explicitly (§0.8 step 3): unknown never means everywhere.
ANY_STACK = "*"


class UnitKind(StrEnum):
    """The two units that pin a snapshot (§0.7)."""

    CYCLE = "cycle"
    CAMPAIGN = "campaign"


class RecallDisposition(StrEnum):
    """The outcomes recall keeps apart (§0.8)."""

    DISABLED = "memory_disabled"
    NONE_ELIGIBLE = "none_eligible"
    SUPPLIED = "supplied"
    OMITTED_BY_BUDGET = "omitted_by_budget"
    FAILED = "recall_failed"


@dataclass(frozen=True)
class Applicability:
    """Where a lesson applies (§0.6): every field names explicitly what it covers."""

    project_id: str
    task_types: tuple[str, ...]
    roles: tuple[str, ...]
    stacks: tuple[str, ...]
    model_families: tuple[str, ...]

    def covers(
        self, project_id: str, task_type: str, role: str, stack: str, model_family: str
    ) -> bool:
        return (
            self.project_id == project_id
            and task_type in self.task_types
            and role in self.roles
            and (stack in self.stacks or ANY_STACK in self.stacks)
            and model_family in self.model_families
        )

    def within(self, other: Applicability) -> bool:
        """Whether this applicability asks for no more than ``other`` grants: an approval may
        narrow a revision's applicability, never widen it (§0.6)."""
        return (
            self.project_id == other.project_id
            and set(self.task_types) <= set(other.task_types)
            and set(self.roles) <= set(other.roles)
            and (set(self.stacks) <= set(other.stacks) or ANY_STACK in other.stacks)
            and set(self.model_families) <= set(other.model_families)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "task_types": list(self.task_types),
            "roles": list(self.roles),
            "stacks": list(self.stacks),
            "model_families": list(self.model_families),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Applicability:
        return cls(
            project_id=str(data["project_id"]),
            task_types=tuple(data["task_types"]),
            roles=tuple(data["roles"]),
            stacks=tuple(data["stacks"]),
            model_families=tuple(data["model_families"]),
        )


def pattern_id_for(project_id: str, target_behavior: str, task_type: str) -> str:
    """A pattern's stable identity (§0.2): its project, target behavior and task type."""
    digest = hashlib.sha256(f"{project_id}|{target_behavior}|{task_type}".encode()).hexdigest()
    return f"pat_{digest[:16]}"


@dataclass(frozen=True)
class PatternRevision:
    """One lesson's immutable text and what it rests on (§0.2, §0.4)."""

    pattern_id: str
    revision: int
    target_behavior: str
    text: str
    applicability: Applicability
    template_id: str
    template_version: str
    drafter_model: str
    drafter_version: str
    cited_observations: tuple[str, ...]
    created_at: datetime

    @property
    def revision_id(self) -> str:
        return f"{self.pattern_id}@{self.revision}"


@dataclass(frozen=True)
class Approval:
    """The owner's authorization of one revision for a stated applicability (§0.6)."""

    approval_id: str
    revision_id: str
    applicability: Applicability
    approved_by: str
    approved_at: datetime
    #: The replay check the draft was given before approval: its reference and result (§0.6).
    replay_check: Mapping[str, Any] = field(default_factory=dict)
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class RecallPolicy:
    """The policy a snapshot pins with its lessons (§0.7, §0.8 step 6)."""

    version: int = 1
    max_lessons: int = 3
    token_budget: int = 600


@dataclass(frozen=True)
class SnapshotEntry:
    revision: PatternRevision
    approval: Approval


@dataclass(frozen=True)
class Snapshot:
    """What one unit pinned at admission (§0.7). Immutable while the unit runs."""

    snapshot_id: str
    unit_kind: UnitKind
    unit_id: str
    pinned_at: datetime
    disabled: bool
    entries: tuple[SnapshotEntry, ...] = ()
    policy: RecallPolicy = field(default_factory=RecallPolicy)


def pin(
    *,
    unit_kind: UnitKind,
    unit_id: str,
    pinned_at: datetime,
    disabled: bool,
    revisions: Sequence[PatternRevision],
    approvals: Sequence[Approval],
    policy: RecallPolicy | None = None,
) -> Snapshot:
    """The snapshot a unit pins: each approval in force at ``pinned_at`` (given before it, and not
    revoked by then) with the revision it binds. A unit that declares memory disabled pins
    nothing (§0.7)."""
    policy = policy or RecallPolicy()
    snapshot_id = (
        "snp_"
        + hashlib.sha256(
            f"{unit_kind.value}|{unit_id}|{pinned_at.isoformat()}".encode()
        ).hexdigest()[:16]
    )
    if disabled:
        return Snapshot(snapshot_id, unit_kind, unit_id, pinned_at, True, (), policy)
    by_id = {r.revision_id: r for r in revisions}
    entries = []
    for approval in approvals:
        revision = by_id.get(approval.revision_id)
        if revision is None or approval.approved_at > pinned_at:
            continue
        if approval.revoked_at is not None and approval.revoked_at <= pinned_at:
            continue
        if not approval.applicability.within(revision.applicability):
            continue  # an approval never widens what its revision states
        entries.append(SnapshotEntry(revision, approval))
    return Snapshot(snapshot_id, unit_kind, unit_id, pinned_at, False, tuple(entries), policy)


@dataclass(frozen=True)
class Recalled:
    """One recall's outcome, recorded with the authoring it fed (the exposure, §0.2)."""

    snapshot_id: str | None
    disposition: RecallDisposition
    supplied: tuple[SnapshotEntry, ...] = ()
    #: Each eligible lesson left out, and why (``budget`` or ``superseded``).
    omitted: tuple[tuple[str, str], ...] = ()

    def exposure(self) -> dict[str, Any]:
        """What the authoring envelope's ``memory`` block records."""
        return {
            "snapshot": self.snapshot_id,
            "disposition": self.disposition.value,
            "intervention": [
                {
                    "revision_id": e.revision.revision_id,
                    "approval_id": e.approval.approval_id,
                    "target_behavior": e.revision.target_behavior,
                }
                for e in self.supplied
            ],
            "omitted": [{"revision_id": r, "reason": why} for r, why in self.omitted],
        }


def _tokens(text: str) -> int:
    """A deterministic size estimate: a token per four characters, rounded up."""
    return -(-len(text) // 4)


def recall(snapshot: Snapshot | None, query: RecallQuery) -> Recalled:
    """The lessons ``query``'s task is supplied from its unit's snapshot (§0.8)."""
    if snapshot is None or snapshot.disabled:
        return Recalled(snapshot.snapshot_id if snapshot else None, RecallDisposition.DISABLED)
    eligible = [
        e
        for e in snapshot.entries
        if e.approval.applicability.covers(
            query.project_id, query.task_type, query.role, query.stack, query.model_family
        )
    ]
    if not eligible:
        return Recalled(snapshot.snapshot_id, RecallDisposition.NONE_ELIGIBLE)
    # One revision per pattern: the latest approved in the snapshot.
    latest: dict[str, SnapshotEntry] = {}
    omitted: list[tuple[str, str]] = []
    for entry in sorted(eligible, key=lambda e: (e.revision.pattern_id, e.revision.revision)):
        held = latest.get(entry.revision.pattern_id)
        if held is not None:
            omitted.append((held.revision.revision_id, "superseded"))
        latest[entry.revision.pattern_id] = entry
    ordered = sorted(latest.values(), key=lambda e: (e.approval.approved_at, e.revision.pattern_id))
    supplied: list[SnapshotEntry] = []
    spent = 0
    for entry in ordered:
        cost = _tokens(entry.revision.text)
        if (
            len(supplied) >= snapshot.policy.max_lessons
            or spent + cost > snapshot.policy.token_budget
        ):
            omitted.append((entry.revision.revision_id, "budget"))
            continue
        supplied.append(entry)
        spent += cost
    disposition = RecallDisposition.SUPPLIED if supplied else RecallDisposition.OMITTED_BY_BUDGET
    return Recalled(snapshot.snapshot_id, disposition, tuple(supplied), tuple(omitted))
