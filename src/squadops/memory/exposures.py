"""Exposures: what each authoring task was supplied, or why nothing (SIP-0110 §0.2, §0.8 step 7).

An exposure is recorded for every task at a consuming seam (§0.9), a memory-disabled one included,
when its inputs are composed. It names the query the task asked with (the scope taken from trusted
context), the snapshot that answered, the disposition, the lessons supplied and those left out with
the reason. It is joined to the task's authoring by run and task. The assessment of the authored
output against each supplied lesson's target attaches to it later (§0.10, slice 3d).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from squadops.memory.lessons import Recalled
from squadops.memory.recall import RecallQuery, UnitKind


def exposure_id_for(run_id: str, task_id: str) -> str:
    """One exposure per task of a run: composing the task again records nothing new."""
    return "exp_" + hashlib.sha256(f"{run_id}|{task_id}".encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Exposure:
    """One consuming task's recall, as it was answered."""

    run_id: str
    task_id: str
    cycle_id: str
    seam: str
    query: RecallQuery
    #: ``Recalled.exposure()``: the snapshot, the disposition, the intervention and the omitted.
    recalled: Mapping[str, Any]
    recorded_at: datetime
    exposure_id: str = field(default="")

    def __post_init__(self) -> None:
        if not self.exposure_id:
            object.__setattr__(self, "exposure_id", exposure_id_for(self.run_id, self.task_id))

    @classmethod
    def of(
        cls,
        *,
        run_id: str,
        task_id: str,
        cycle_id: str,
        seam: str,
        query: RecallQuery,
        recalled: Recalled,
        recorded_at: datetime,
    ) -> Exposure:
        return cls(run_id, task_id, cycle_id, seam, query, recalled.exposure(), recorded_at)

    @property
    def disposition(self) -> str:
        return str(self.recalled["disposition"])

    def to_dict(self) -> dict[str, Any]:
        q = self.query
        return {
            "exposure_id": self.exposure_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "cycle_id": self.cycle_id,
            "seam": self.seam,
            "query": {
                "project_id": q.project_id,
                "task_type": q.task_type,
                "role": q.role,
                "stack": q.stack,
                "model_family": q.model_family,
                "unit_kind": q.unit_kind.value if q.unit_kind else None,
                "unit_id": q.unit_id,
            },
            "recalled": dict(self.recalled),
            "recorded_at": self.recorded_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Exposure:
        q = dict(data["query"])
        unit_kind = q.pop("unit_kind", None)
        return cls(
            run_id=str(data["run_id"]),
            task_id=str(data["task_id"]),
            cycle_id=str(data["cycle_id"]),
            seam=str(data["seam"]),
            query=RecallQuery(**q, unit_kind=UnitKind(unit_kind) if unit_kind else None),
            recalled=dict(data["recalled"]),
            recorded_at=datetime.fromisoformat(str(data["recorded_at"])),
            exposure_id=str(data["exposure_id"]),
        )
