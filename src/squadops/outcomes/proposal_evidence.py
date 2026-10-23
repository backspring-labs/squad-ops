"""What a campaign's proposal run is shown of its accepted tree's outcomes (SIP-0113 §4.5; §10t).

The strategy role chooses the next increment. Beside the PRD's expansion scope it is shown each
goal of the campaign's pinned suite with its result on the accepted tree, each quality measure's
move against the calibration baseline, and the accepted increments' ``prd_delta`` folded by section
(§10t ruling 2). A goal's steps, checks and values are never read, so they can never be shown.

**One task's inputs carry it** (§10t ruling 1): ``PROPOSAL_EVIDENCE_INPUT`` on the proposal run's
``strategy.propose_increment``, composed at dispatch (``squadops.execution.proposal_evidence``). A
cycle's resolved config is stored, served, copied into retries and repairs and released with the
campaign's records, so the evidence never enters it.

Nothing here imports ``squadops.scenarios``: the executor reaches this module, and the squad's
packages never load the held-out store (``test_proposal_evidence_stays_on_its_task.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

#: The proposal task's input that carries its evidence. Composed by the executor alone, and read by
#: the proposal's handler alone.
PROPOSAL_EVIDENCE_INPUT = "proposal_evidence"


class GoalResult(StrEnum):
    """A goal's result as the proposer is shown it. ``blocked_unverified`` is ``not verified``
    without its reason, since a reason such as ``surface_absent`` names a held-out surface, and a
    ``not_applicable`` goal isn't shown (§10t ruling 2)."""

    PASSED = "passed"
    FAILED = "failed"
    NOT_VERIFIED = "not verified"


@dataclass(frozen=True)
class GoalEvidence:
    goal_id: str
    statement: str
    result: GoalResult


@dataclass(frozen=True)
class QualityMove:
    """One measure against the calibration baseline, with no detail, seed or URL."""

    measure: str
    before: float | int
    after: float | int


@dataclass(frozen=True)
class AcceptedSection:
    """A PRD section as the accepted increments left it, folded by id: what is accepted now, not
    its history."""

    section_id: str
    text: str


@dataclass(frozen=True)
class ProposalEvidence:
    goals: tuple[GoalEvidence, ...] = ()
    quality: tuple[QualityMove, ...] = ()
    accepted_prd: tuple[AcceptedSection, ...] = ()
    #: Goals held back for carrying one of the suite's markers (§10t ruling 3): a count, never text.
    held_back: int = 0

    def is_empty(self) -> bool:
        """Nothing to show. The task is then composed without the key, so its inputs are the ones
        it had before §4.5."""
        return not (self.goals or self.quality or self.accepted_prd or self.held_back)

    def to_inputs(self) -> dict[str, Any]:
        """The wire form: plain values, as every task input is."""
        return {
            "goals": [
                {"goal_id": g.goal_id, "statement": g.statement, "result": g.result.value}
                for g in self.goals
            ],
            "quality": [
                {"measure": q.measure, "before": q.before, "after": q.after} for q in self.quality
            ],
            "accepted_prd": [{"id": s.section_id, "text": s.text} for s in self.accepted_prd],
            "held_back": self.held_back,
        }
