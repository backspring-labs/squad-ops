"""Plan Delta model — append-only record of plan modifications (SIP-0079 §7.6).

Plan deltas layer corrections on top of the original plan with full traceability.
The original plan is never mutated.

RC-7: Each entry in ``changes`` follows the format
``"{kind}: {target} — {description}"``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PlanDelta:
    """Append-only record of a plan modification during execution."""

    delta_id: str
    run_id: str
    correction_path: str  # continue | patch | rewind | abort
    trigger: str
    failure_classification: str
    analysis_summary: str
    decision_rationale: str
    changes: tuple[str, ...]
    affected_task_types: tuple[str, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        """Validate required fields are non-empty."""
        if not self.failure_classification:
            raise ValueError("failure_classification must be non-empty")
        if not self.analysis_summary:
            raise ValueError("analysis_summary must be non-empty")
        if not self.decision_rationale:
            raise ValueError("decision_rationale must be non-empty")
        if self.correction_path in ("patch", "rewind") and not self.changes:
            raise ValueError(
                f"changes must be non-empty for correction_path '{self.correction_path}'"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON transport / artifact storage."""
        d = dataclasses.asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanDelta:
        """Deserialize from dict.

        Converts list fields to tuples and ISO string to datetime.
        """
        coerced = dict(data)
        for field_name in ("changes", "affected_task_types"):
            if field_name in coerced and isinstance(coerced[field_name], list):
                coerced[field_name] = tuple(coerced[field_name])
        if isinstance(coerced.get("created_at"), str):
            coerced["created_at"] = datetime.fromisoformat(coerced["created_at"])
        return cls(**coerced)
