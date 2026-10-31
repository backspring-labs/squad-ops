"""Exposures: what each authoring task was supplied, or why nothing (SIP-0110 §0.2, §0.8 step 7).

An exposure is recorded for every authoring invocation at a consuming seam (§0.9), a memory-disabled
one included: when the task's inputs are composed, and again each time the loop dispatches the task
once more (a correction round's re-take, an emission retry, #2162). It names the query the task
asked with (the scope taken from trusted context), the snapshot that answered, the disposition, the
lessons supplied and those left out with the reason. It is joined to its authoring by run, task and
attempt, which the captured envelope carries (#1304's ``prior_attempts`` plus one). The assessment
of the authored output against each supplied lesson's target attaches to it later (§0.10, slice 3d).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from squadops.memory.context import Disposition
from squadops.memory.lessons import Recalled
from squadops.memory.recall import RecallQuery, UnitKind

#: What a held task's exposure id ends with (#2178).
HELD_SUFFIX = ":held"

#: The exposure fields a record is handed through (#2178, #2179): a task's binding sections.
INSTRUCTION_SECTIONS = ("task_instructions", "project_instructions")


def exposure_id_for(run_id: str, task_id: str, attempt: int = 1) -> str:
    """One exposure per authoring invocation (§0.2): composing the same attempt again records
    nothing new, and each re-dispatch is its own. A first attempt keeps the id it had before the
    attempt was part of it, so the exposures already stored still join to their envelopes."""
    key = f"{run_id}|{task_id}" if attempt == 1 else f"{run_id}|{task_id}|{attempt}"
    return "exp_" + hashlib.sha256(key.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Exposure:
    """One authoring invocation's recall, as it was answered."""

    run_id: str
    task_id: str
    cycle_id: str
    #: The agent that ran the task, kept apart from its role (§0.15 identity, §6): a role can be
    #: reassigned to another agent, and a record keyed only by role would follow the role.
    agent_id: str
    seam: str
    query: RecallQuery
    #: ``Recalled.exposure()``: the snapshot, the disposition, the intervention and the omitted.
    recalled: Mapping[str, Any]
    recorded_at: datetime
    #: Which dispatch of the task this was: 1 for the first, one more for each re-dispatch.
    attempt: int = 1
    exposure_id: str = field(default="")
    #: The task instructions' binding section (#2178): its disposition, each revision supplied and
    #: each that couldn't be. ``None`` when the dispatch's composer read no instructions.
    task_instructions: Mapping[str, Any] | None = None
    #: The project instructions' binding section (#2179), kept as the task instructions' is.
    project_instructions: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.exposure_id:
            exposure_id = exposure_id_for(self.run_id, self.task_id, self.attempt)
            # #2178: a held task's answer is its own record, so the dispatch after its release
            # records the attempt's exposure rather than finding this one in its place.
            object.__setattr__(self, "exposure_id", exposure_id + HELD_SUFFIX * self.held)

    @property
    def incomplete_sections(self) -> tuple[str, ...]:
        """The binding sections that couldn't be completed. Any one holds the task undispatched
        (§3.6: the bundle is held), so nothing in its sections reached the model."""
        return tuple(
            name
            for name in INSTRUCTION_SECTIONS
            if (getattr(self, name) or {}).get("disposition") == Disposition.INCOMPLETE.value
        )

    @property
    def held(self) -> bool:
        """Whether the task was held, not dispatched: it counts as no dispatch (#2178)."""
        return bool(self.incomplete_sections)

    @classmethod
    def of(
        cls,
        *,
        run_id: str,
        task_id: str,
        cycle_id: str,
        agent_id: str,
        seam: str,
        query: RecallQuery,
        recalled: Recalled,
        recorded_at: datetime,
        attempt: int = 1,
        task_instructions: Mapping[str, Any] | None = None,
        project_instructions: Mapping[str, Any] | None = None,
    ) -> Exposure:
        return cls(
            run_id,
            task_id,
            cycle_id,
            agent_id,
            seam,
            query,
            recalled.exposure(),
            recorded_at,
            attempt,
            task_instructions=task_instructions,
            project_instructions=project_instructions,
        )

    @property
    def disposition(self) -> str:
        return str(self.recalled["disposition"])

    def to_dict(self) -> dict[str, Any]:
        q = self.query
        return {
            "exposure_id": self.exposure_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "attempt": self.attempt,
            "cycle_id": self.cycle_id,
            "agent_id": self.agent_id,
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
            # Only when instructions were read, so an exposure from before #2178 is unchanged.
            **(
                {"task_instructions": dict(self.task_instructions)}
                if self.task_instructions is not None
                else {}
            ),
            **(
                {"project_instructions": dict(self.project_instructions)}
                if self.project_instructions is not None
                else {}
            ),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Exposure:
        q = dict(data["query"])
        unit_kind = q.pop("unit_kind", None)
        return cls(
            run_id=str(data["run_id"]),
            task_id=str(data["task_id"]),
            cycle_id=str(data["cycle_id"]),
            agent_id=str(data["agent_id"]),
            seam=str(data["seam"]),
            query=RecallQuery(**q, unit_kind=UnitKind(unit_kind) if unit_kind else None),
            recalled=dict(data["recalled"]),
            recorded_at=datetime.fromisoformat(str(data["recorded_at"])),
            # An exposure stored before the attempt was recorded is its task's first (#2162).
            attempt=int(data.get("attempt") or 1),
            exposure_id=str(data["exposure_id"]),
            task_instructions=data.get("task_instructions"),
            project_instructions=data.get("project_instructions"),
        )
