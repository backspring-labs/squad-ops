"""Run Checkpoint model — durable snapshot of run execution state (SIP-0079 §7.4).

Checkpoints are persisted at task boundaries after each successful task completion.
Only successfully completed tasks appear in ``completed_task_ids`` (RC-4).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RunCheckpoint:
    """Durable snapshot of run execution state at a task boundary."""

    run_id: str
    checkpoint_index: int
    completed_task_ids: tuple[str, ...]
    prior_outputs: dict[str, Any]
    artifact_refs: tuple[str, ...]
    plan_delta_refs: tuple[str, ...]
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON transport / persistence."""
        d = dataclasses.asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunCheckpoint:
        """Deserialize from dict.

        Converts list fields to tuples and ISO string to datetime.
        """
        coerced = dict(data)
        for field_name in ("completed_task_ids", "artifact_refs", "plan_delta_refs"):
            if field_name in coerced and isinstance(coerced[field_name], list):
                coerced[field_name] = tuple(coerced[field_name])
        if isinstance(coerced.get("created_at"), str):
            coerced["created_at"] = datetime.fromisoformat(coerced["created_at"])
        return cls(**coerced)
