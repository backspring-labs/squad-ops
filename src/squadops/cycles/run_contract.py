"""Run Contract model — durable execution contract for implementation runs (SIP-0079 §7.1).

The run contract captures objective, acceptance criteria, non-goals, time budget,
stop conditions, and required artifacts. Stored as a run-level artifact of type
``run_contract`` and referenced by all pulse checks and correction decisions.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunContract:
    """Durable execution contract for an implementation run."""

    objective: str
    acceptance_criteria: tuple[str, ...]
    non_goals: tuple[str, ...]
    time_budget_seconds: int
    stop_conditions: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    plan_artifact_ref: str
    source_gate_decision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON transport / artifact storage."""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunContract:
        """Deserialize from dict.

        Converts list fields to tuples for frozen dataclass compatibility.
        """
        coerced = dict(data)
        for field_name in (
            "acceptance_criteria",
            "non_goals",
            "stop_conditions",
            "required_artifacts",
        ):
            if field_name in coerced and isinstance(coerced[field_name], list):
                coerced[field_name] = tuple(coerced[field_name])
        return cls(**coerced)
