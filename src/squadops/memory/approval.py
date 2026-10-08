"""Drafting, approving and revoking a lesson (SIP-0110 §0.4, §0.6–§0.7; slice 3d, #2096).

**A draft** is a pattern revision written by the frontier-model auditor (the 2.2 plan's D15), citing
the observations it rests on. A new draft of a target behavior is the pattern's next revision: a
new occurrence adds evidence and never resets or resurrects a lesson.

**An approval** binds one revision to a stated applicability, owner-given. It may narrow the
revision's applicability and never widens it. It records the ruling it rests on, the replay check
the draft was given, and the auditor's **combined check**: a task receives up to three lessons, so
the draft is checked together with every approved lesson that would be supplied beside it under the
same applicability (§0.6). An approval whose combined check did not cover that whole set, or found a
conflict, is refused: a conflicting set is revised, narrowed or withdrawn first.

**A revocation** reaches units admitted after it. The units already running with the lesson pinned
are named, so their work can be halted or restarted under a new snapshot and their measurements set
apart (§0.7, D9): nothing a running unit was handed changes silently.

Pure: the routes read and write the store.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from squadops.memory.lessons import (
    ANY_STACK,
    Applicability,
    Approval,
    PatternRevision,
    Snapshot,
    pattern_id_for,
)

#: The combined check's two verdicts (§0.6).
NO_CONFLICT = "no_conflict"
CONFLICT = "conflict"


class LessonRefused(ValueError):
    """A draft, an approval or a revocation the rules refuse, with the reason."""


@dataclass(frozen=True)
class CombinedCheck:
    """The auditor's check of a draft together with the approved lessons supplied beside it."""

    revision_ids: tuple[str, ...]
    verdict: str
    reference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_ids": list(self.revision_ids),
            "verdict": self.verdict,
            "reference": self.reference,
        }


def overlaps(a: Applicability, b: Applicability) -> bool:
    """Whether some task falls inside both: the same project, and a task type, a role, a stack and
    a model family in common (a stack-independent lesson meets every stack)."""
    stacks_meet = (
        ANY_STACK in a.stacks or ANY_STACK in b.stacks or bool(set(a.stacks) & set(b.stacks))
    )
    return (
        a.project_id == b.project_id
        and bool(set(a.task_types) & set(b.task_types))
        and bool(set(a.roles) & set(b.roles))
        and stacks_meet
        and bool(set(a.model_families) & set(b.model_families))
    )


def in_force(approval: Approval, at: datetime) -> bool:
    return approval.approved_at <= at and (approval.revoked_at is None or approval.revoked_at > at)


def supplied_together(
    applicability: Applicability,
    *,
    pattern_id: str,
    revisions: Iterable[PatternRevision],
    approvals: Iterable[Approval],
    at: datetime,
) -> tuple[str, ...]:
    """The approved revisions, in force at ``at``, that a task inside ``applicability`` could be
    supplied beside a revision of ``pattern_id``: every approval whose applicability overlaps, of
    another pattern (a pattern supplies one revision, its latest)."""
    pattern_of = {r.revision_id: r.pattern_id for r in revisions}
    return tuple(
        sorted(
            {
                a.revision_id
                for a in approvals
                if in_force(a, at)
                and pattern_of.get(a.revision_id) not in (None, pattern_id)
                and overlaps(applicability, a.applicability)
            }
        )
    )


def draft_revision(
    *,
    target_behavior: str,
    text: str,
    applicability: Applicability,
    template_id: str,
    template_version: str,
    drafter_model: str,
    drafter_version: str,
    cited_observations: Sequence[str],
    known_observations: Iterable[str],
    revisions: Iterable[PatternRevision],
    now: datetime,
) -> PatternRevision:
    """The auditor's draft, as the pattern's next revision. Its pattern is the project, the target
    behavior and the task types it covers; it cites observations the store holds."""
    for name, value in (
        ("target_behavior", target_behavior),
        ("text", text),
        ("template_id", template_id),
        ("template_version", template_version),
        ("drafter_model", drafter_model),
        ("drafter_version", drafter_version),
    ):
        if not str(value).strip():
            raise LessonRefused(f"a draft names its {name}")
    if not cited_observations:
        raise LessonRefused("a draft cites the observations it rests on")
    unknown = sorted(set(cited_observations) - set(known_observations))
    if unknown:
        raise LessonRefused(f"a draft cites only recorded observations; not recorded: {unknown}")
    pattern_id = pattern_id_for(
        applicability.project_id, target_behavior, "|".join(sorted(applicability.task_types))
    )
    latest = max((r.revision for r in revisions if r.pattern_id == pattern_id), default=0)
    return PatternRevision(
        pattern_id=pattern_id,
        revision=latest + 1,
        target_behavior=target_behavior,
        text=text,
        applicability=applicability,
        template_id=template_id,
        template_version=template_version,
        drafter_model=drafter_model,
        drafter_version=drafter_version,
        cited_observations=tuple(cited_observations),
        created_at=now,
    )


def approve(
    revision: PatternRevision,
    *,
    applicability: Applicability,
    approved_by: str,
    ruling: str,
    replay_check: Mapping[str, Any],
    combined_check: CombinedCheck,
    revisions: Iterable[PatternRevision],
    approvals: Iterable[Approval],
    now: datetime,
) -> Approval:
    """The owner's approval of ``revision`` for ``applicability``, or :class:`LessonRefused`."""
    if not applicability.within(revision.applicability):
        raise LessonRefused(
            "an approval may narrow its revision's applicability, never widen it: a wider one is "
            "a new revision, drafted and replay-checked for it (§0.6)"
        )
    if not ruling.strip():
        raise LessonRefused("an approval records the owner's ruling it rests on")
    if (
        not str(replay_check.get("reference") or "").strip()
        or not str(replay_check.get("result") or "").strip()
    ):
        raise LessonRefused("an approval records the replay check the draft was given (§0.6)")
    together = supplied_together(
        applicability,
        pattern_id=revision.pattern_id,
        revisions=revisions,
        approvals=approvals,
        at=now,
    )
    unchecked = sorted(set(together) - set(combined_check.revision_ids))
    if unchecked:
        raise LessonRefused(
            "the combined check did not cover every approved lesson supplied beside this one; "
            f"not covered: {unchecked} (§0.6)"
        )
    if combined_check.verdict != NO_CONFLICT:
        raise LessonRefused(
            f"the combined check found {combined_check.verdict!r}: a conflicting set is not "
            "approved as it stands; revise, narrow or withdraw a lesson first (§0.6)"
        )
    if not combined_check.reference.strip():
        raise LessonRefused("the combined check names where it is recorded")
    approval_id = (
        "apr_"
        + hashlib.sha256(f"{revision.revision_id}|{now.isoformat()}".encode()).hexdigest()[:16]
    )
    return Approval(
        approval_id=approval_id,
        revision_id=revision.revision_id,
        applicability=applicability,
        approved_by=approved_by,
        approved_at=now,
        replay_check=dict(replay_check),
        ruling=ruling.strip(),
        combined_check=combined_check.to_dict(),
    )


def revoke(approval: Approval, *, by: str, reason: str, now: datetime) -> Approval:
    """``approval`` revoked from ``now``: units admitted afterwards pin without it (§0.7)."""
    if approval.revoked_at is not None:
        raise LessonRefused(f"{approval.approval_id} was revoked at {approval.revoked_at}")
    if not reason.strip():
        raise LessonRefused("a revocation says why")
    return dataclasses.replace(
        approval, revoked_at=now, revoked_by=by, revocation_reason=reason.strip()
    )


def units_holding(approval_id: str, snapshots: Iterable[Snapshot]) -> list[Snapshot]:
    """The units whose pinned snapshot carries ``approval_id``: the work a revocation names, so it
    can be halted or restarted under a new snapshot and its measurements set apart (§0.7, D9)."""
    return [s for s in snapshots if any(e.approval.approval_id == approval_id for e in s.entries)]
