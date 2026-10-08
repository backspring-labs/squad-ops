"""Cross-cycle recall, the query (SIP-0110 §0.8; #1964 shipped the rails, #2096 the policy).

An authoring task asks, before it authors, which approved lessons its unit's pinned snapshot
supplies for it. The query carries the scope, taken from trusted execution context (the cycle, its
squad profile and its config), never from an agent-supplied value. The policy that answers it is
:func:`squadops.memory.lessons.recall`, behind ``FailurePatternRecallPort``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

#: The input a consuming task's supplied lessons ride on: ``{"snapshot", "lessons": [{"revision_id",
#: "text"}]}``, present only when a lesson is supplied, so a task handed none has the inputs it had
#: before memory existed (§0.9). The authoring envelope records it apart, in its ``memory`` block.
LESSONS_INPUT = "cross_cycle_lessons"


class UnitKind(StrEnum):
    """The two units that pin a snapshot (§0.7): a standalone cycle, or a campaign and all its
    proposals and cycles."""

    CYCLE = "cycle"
    CAMPAIGN = "campaign"


@dataclass(frozen=True)
class RecallQuery:
    """What an authoring task asks before it authors (§0.8): its project and task type, the role,
    stack and model family a lesson's applicability is matched against, and the unit whose pinned
    snapshot answers. An empty field matches no lesson: an unknown never means "everywhere" (§0.8
    step 3). A query that names no unit is answered as a failed recall."""

    project_id: str
    task_type: str
    role: str = ""
    stack: str = ""
    model_family: str = ""
    unit_kind: UnitKind | None = None
    unit_id: str = ""
