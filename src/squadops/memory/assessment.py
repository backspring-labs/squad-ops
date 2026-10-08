"""Assessment: whether an authored output avoided a lesson's target (SIP-0110 §0.10; slice 3d, #2096).

An assessment attaches to **one exposure and one target**: the exact output the task authored, judged
by the target's template rubric. Not to the next gate event or check: a gate's silence about a
target is not evidence the target is absent. The output may be refused for another defect, carry
several and record one, be approved without the target being checked, or avoid the defect by
omitting meaningful work.

Each target is **present**, **absent after assessment**, **not applicable**, or **unassessed**.
An absence counts only where the output did its required work (§0.15 quality): a target avoided by
leaving the work out is not an absence. A target is assessed whether or not its lesson was supplied,
so the memory-off series and the memory-on series are read by one rubric.

``target_absence_rate`` is over applicable, assessed exposures. It is observational, not a causal
estimate of memory's benefit, and unassessed or inapplicable exposures earn no credit. There is no
automatic decay (§0.10): deprecation is the owner's decision on assessed evidence.

Assessments are append-only: a reassessment is a new record, and the latest per exposure and
target is the one read.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class TargetState(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    NOT_APPLICABLE = "not_applicable"
    UNASSESSED = "unassessed"


class AssessmentRefused(ValueError):
    """An assessment the rules refuse, with the reason."""


@dataclass(frozen=True)
class Assessment:
    """One target's state in one exposure's authored output."""

    project_id: str
    exposure_id: str
    pattern_id: str
    state: TargetState
    #: Whether the output did the work its task required. An absence requires it (§0.15 quality).
    required_work_done: bool | None
    #: Whether the target's lesson was supplied to this exposure (the memory-on series).
    supplied: bool
    rubric: str
    evidence: str
    assessed_by: str
    assessed_at: datetime

    @property
    def assessment_id(self) -> str:
        key = f"{self.exposure_id}|{self.pattern_id}|{self.assessed_at.isoformat()}"
        return "asm_" + hashlib.sha256(key.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "project_id": self.project_id,
            "exposure_id": self.exposure_id,
            "pattern_id": self.pattern_id,
            "state": self.state.value,
            "required_work_done": self.required_work_done,
            "supplied": self.supplied,
            "rubric": self.rubric,
            "evidence": self.evidence,
            "assessed_by": self.assessed_by,
            "assessed_at": self.assessed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Assessment:
        return cls(
            project_id=str(data["project_id"]),
            exposure_id=str(data["exposure_id"]),
            pattern_id=str(data["pattern_id"]),
            state=TargetState(data["state"]),
            required_work_done=data.get("required_work_done"),
            supplied=bool(data["supplied"]),
            rubric=str(data["rubric"]),
            evidence=str(data["evidence"]),
            assessed_by=str(data["assessed_by"]),
            assessed_at=datetime.fromisoformat(str(data["assessed_at"])),
        )


def supplied_to(intervention: Iterable[Mapping[str, Any]] | None, pattern_id: str) -> bool:
    """Whether an exposure's intervention carried a revision of ``pattern_id``."""
    return any(
        str(item.get("revision_id", "")).rsplit("@", 1)[0] == pattern_id
        for item in intervention or ()
    )


def assess(
    *,
    project_id: str,
    exposure_id: str,
    pattern_id: str,
    state: TargetState,
    required_work_done: bool | None,
    supplied: bool,
    rubric: str,
    evidence: str,
    assessed_by: str,
    now: datetime,
) -> Assessment:
    """A target's assessment, or :class:`AssessmentRefused`."""
    for name, value in (("rubric", rubric), ("evidence", evidence), ("assessed_by", assessed_by)):
        if not str(value).strip():
            raise AssessmentRefused(f"an assessment names its {name}")
    if state is TargetState.ABSENT and required_work_done is not True:
        raise AssessmentRefused(
            "a target is absent only where the output did its required work: one avoided by "
            "leaving the work out is not an absence (SIP-0110 §0.10); assess it as unassessed"
        )
    return Assessment(
        project_id=project_id,
        exposure_id=exposure_id,
        pattern_id=pattern_id,
        state=state,
        required_work_done=required_work_done,
        supplied=supplied,
        rubric=rubric,
        evidence=evidence,
        assessed_by=assessed_by,
        assessed_at=now,
    )


def latest(assessments: Iterable[Assessment]) -> dict[tuple[str, str], Assessment]:
    """The assessment read for each exposure and target: its most recent."""
    held: dict[tuple[str, str], Assessment] = {}
    for a in sorted(assessments, key=lambda a: (a.assessed_at, a.assessment_id)):
        held[(a.exposure_id, a.pattern_id)] = a
    return held


@dataclass(frozen=True)
class AbsenceRate:
    """``target_absence_rate`` for one target and one series (supplied or not)."""

    pattern_id: str
    supplied: bool
    absent: int
    assessed: int
    not_applicable: int
    unassessed: int

    @property
    def rate(self) -> float | None:
        """Absent over applicable, assessed exposures; ``None`` when there are none."""
        return self.absent / self.assessed if self.assessed else None


def target_absence_rates(assessments: Iterable[Assessment]) -> list[AbsenceRate]:
    """Per target, the memory-on and memory-off series apart, over the latest assessments."""
    counts: dict[tuple[str, bool], dict[str, int]] = {}
    for a in latest(assessments).values():
        c = counts.setdefault((a.pattern_id, a.supplied), dict.fromkeys(TargetState, 0))
        c[a.state] += 1
    return [
        AbsenceRate(
            pattern_id=pattern_id,
            supplied=supplied,
            absent=c[TargetState.ABSENT],
            assessed=c[TargetState.ABSENT] + c[TargetState.PRESENT],
            not_applicable=c[TargetState.NOT_APPLICABLE],
            unassessed=c[TargetState.UNASSESSED],
        )
        for (pattern_id, supplied), c in sorted(counts.items())
    ]
