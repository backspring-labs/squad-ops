"""API routes — group_run reference fill (SIP-0098 §6.2 winnability oracle).

A known-good implementation of the scaffold-owned route signatures: an in-memory
store plus the join/leave logic the PRD's behaviors require. This is the "reference
fill" the contract's reference-fill CI gate runs against — no criterion may enter the
contract that this correct fill does not already satisfy. Fill-only: the scaffold owns
the imports, ``router``, and every decorator/signature below; only the bodies are ours.
"""

import uuid

from fastapi import APIRouter

from .errors import ApiError
from .models import Participant, ParticipantName, RunEvent, RunEventCreate

router = APIRouter()

# In-memory store: run id -> RunEvent (persistence: in_memory).
_RUNS: dict[str, RunEvent] = {}


def _get_run(run_id: str) -> RunEvent:
    run = _RUNS.get(run_id)
    if run is None:
        raise ApiError("run_not_found", f"run {run_id!r} does not exist")
    return run


@router.get("/runs", response_model=list[RunEvent])
def get_runs():
    """list runs."""
    return list(_RUNS.values())


@router.post("/runs", response_model=RunEvent, status_code=201)
def post_runs(payload: RunEventCreate):
    """create run."""
    run = RunEvent(id=uuid.uuid4().hex, participants=[], **payload.model_dump())
    _RUNS[run.id] = run
    return run


@router.get("/runs/{id}", response_model=RunEvent)
def get_runs_id(id: str):
    """run details."""
    return _get_run(id)


@router.post("/runs/{id}/join", response_model=RunEvent)
def post_runs_id_join(id: str, payload: ParticipantName):
    """join run by participant name."""
    run = _get_run(id)
    # Case-insensitive uniqueness; the stored name is NOT normalized (manifest decisions).
    if any(p.name.casefold() == payload.name.casefold() for p in run.participants):
        raise ApiError("duplicate_participant", f"{payload.name!r} has already joined")
    run.participants.append(Participant(id=uuid.uuid4().hex, name=payload.name))
    return run


@router.post("/runs/{id}/leave", response_model=RunEvent)
def post_runs_id_leave(id: str, payload: ParticipantName):
    """leave run by participant name."""
    run = _get_run(id)
    match = next(
        (p for p in run.participants if p.name.casefold() == payload.name.casefold()), None
    )
    if match is None:
        raise ApiError("participant_not_found", f"{payload.name!r} is not in this run")
    run.participants.remove(match)
    return run
