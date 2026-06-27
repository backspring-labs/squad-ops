"""Assignment routes (SIP-0089 §2.7).

REST surface for duty `Assignment`s on the versioned resource lane (`/api/v1`),
per the runtime-api prefix standard (#218): authenticated, managed resources
live under `/api/v1`; `/health` is reserved for read-only, unauthenticated
probes, so a writable resource must not live there. The CLI cannot import the
Postgres adapter directly (D26 forbidden-imports), so the ``squadops assignment
...`` commands reach assignments through these routes — mirroring how Phase-1
``agent state`` reads runtime-state over HTTP.

Serialization lives here in the DTO layer (DTO-purity): timedeltas cross the
wire as integer seconds (`*_seconds`), `DutyWindow` as a nested object, and the
`allowed_off_window_modes` tuple as a list.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from squadops.runtime.models import (
    Assignment,
    AssignmentType,
    DutyWindow,
    MissedWindowPolicy,
    RecallPolicy,
    RuntimeMode,
    Strictness,
    default_reserve_before_window,
)

router = APIRouter(prefix="/api/v1", tags=["assignments"])


def _get_assignment_port():
    from squadops.api.runtime.deps import get_assignment_port

    return get_assignment_port()


def _not_found(assignment_id: str) -> HTTPException:
    """404 in the resource-lane error envelope the CLI client parses."""
    return HTTPException(
        status_code=404,
        detail={
            "error": {
                "code": "ASSIGNMENT_NOT_FOUND",
                "message": f"No assignment with id={assignment_id}",
                "details": None,
            }
        },
    )


class DutyWindowDTO(BaseModel):
    """Wire form of `runtime.models.DutyWindow` (§10.3)."""

    start: datetime
    end: datetime
    timezone: str


class AssignmentResponse(BaseModel):
    """Wire form of `runtime.models.Assignment` (§10.2).

    `timedelta` fields are serialized as integer seconds; the reserve buffers and
    graceful window are minute-granularity policy, so seconds are lossless.
    """

    assignment_id: str
    agent_id: str
    assignment_type: AssignmentType
    assigned_role: str
    priority: int
    strictness: Strictness
    active_window: DutyWindowDTO
    reserve_before_window_seconds: int
    reserve_after_window_seconds: int
    recall_policy: RecallPolicy
    graceful_window_seconds: int
    missed_window_policy: MissedWindowPolicy
    allowed_off_window_modes: list[RuntimeMode]
    active: bool

    @classmethod
    def from_domain(cls, a: Assignment) -> AssignmentResponse:
        return cls(
            assignment_id=a.assignment_id,
            agent_id=a.agent_id,
            assignment_type=a.assignment_type,
            assigned_role=a.assigned_role,
            priority=a.priority,
            strictness=a.strictness,
            active_window=DutyWindowDTO(
                start=a.active_window.start,
                end=a.active_window.end,
                timezone=a.active_window.timezone,
            ),
            reserve_before_window_seconds=int(a.reserve_before_window.total_seconds()),
            reserve_after_window_seconds=int(a.reserve_after_window.total_seconds()),
            recall_policy=a.recall_policy,
            graceful_window_seconds=int(a.graceful_window.total_seconds()),
            missed_window_policy=a.missed_window_policy,
            allowed_off_window_modes=list(a.allowed_off_window_modes),
            active=a.active,
        )


class AssignmentCreate(BaseModel):
    """Create-request body for `POST /api/v1/assignments`.

    EXPERIMENTAL/INTERNAL in v1.1 (plan §2.7) — not a public operator command.
    Reserve fields are optional: when omitted, the D7/§11.4 strictness defaults
    are applied (15m before-window for hard duty, 0 for soft; 0 after-window
    always). Every persisted Assignment still carries explicit reserve values.
    """

    agent_id: str
    assigned_role: str
    window_start: datetime
    window_end: datetime
    timezone: str = "UTC"
    assignment_id: str | None = None
    assignment_type: AssignmentType = "duty"
    priority: int = 0
    strictness: Strictness = "hard"
    reserve_before_window_seconds: int | None = None
    reserve_after_window_seconds: int | None = None
    recall_policy: RecallPolicy = "graceful"
    graceful_window_seconds: int = 0
    missed_window_policy: MissedWindowPolicy = "skip"
    allowed_off_window_modes: list[RuntimeMode] = Field(default_factory=list)
    active: bool = True

    @model_validator(mode="after")
    def _check_window(self) -> AssignmentCreate:
        # Half-open [start, end): an empty or inverted window is never valid and
        # the DB CHECK (§2.2 / D3) would reject it — surface it as 422 here.
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        if (
            self.reserve_before_window_seconds is not None
            and self.reserve_before_window_seconds < 0
        ):
            raise ValueError("reserve_before_window_seconds must be non-negative")
        if self.reserve_after_window_seconds is not None and self.reserve_after_window_seconds < 0:
            raise ValueError("reserve_after_window_seconds must be non-negative")
        return self

    def to_domain(self) -> Assignment:
        reserve_before = (
            timedelta(seconds=self.reserve_before_window_seconds)
            if self.reserve_before_window_seconds is not None
            else default_reserve_before_window(self.strictness)
        )
        reserve_after = (
            timedelta(seconds=self.reserve_after_window_seconds)
            if self.reserve_after_window_seconds is not None
            else timedelta()
        )
        return Assignment(
            assignment_id=self.assignment_id or str(uuid4()),
            agent_id=self.agent_id,
            assignment_type=self.assignment_type,
            assigned_role=self.assigned_role,
            priority=self.priority,
            strictness=self.strictness,
            active_window=DutyWindow(
                start=self.window_start,
                end=self.window_end,
                timezone=self.timezone,
            ),
            reserve_before_window=reserve_before,
            reserve_after_window=reserve_after,
            recall_policy=self.recall_policy,
            graceful_window=timedelta(seconds=self.graceful_window_seconds),
            missed_window_policy=self.missed_window_policy,
            allowed_off_window_modes=tuple(self.allowed_off_window_modes),
            active=self.active,
        )


@router.get("/agents/{agent_id}/assignments", response_model=list[AssignmentResponse])
async def list_agent_assignments(agent_id: str) -> list[AssignmentResponse]:
    """List every assignment held by an agent (active and inactive), window-start order."""
    port = _get_assignment_port()
    assignments = await port.list_assignments_for_agent(agent_id)
    return [AssignmentResponse.from_domain(a) for a in assignments]


@router.get("/assignments/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(assignment_id: str) -> AssignmentResponse:
    """Show one assignment by id; 404 if no row exists."""
    port = _get_assignment_port()
    assignment = await port.get_assignment(assignment_id)
    if assignment is None:
        raise _not_found(assignment_id)
    return AssignmentResponse.from_domain(assignment)


@router.post("/assignments", response_model=AssignmentResponse, status_code=201)
async def create_assignment(body: AssignmentCreate) -> AssignmentResponse:
    """Create (upsert) an assignment. EXPERIMENTAL/INTERNAL in v1.1 — not a
    public operator command. Applies the D7/§11.4 reserve-buffer defaults when
    the reserve fields are omitted, then persists via the AssignmentPort.
    """
    port = _get_assignment_port()
    saved = await port.upsert_assignment(body.to_domain())
    return AssignmentResponse.from_domain(saved)
