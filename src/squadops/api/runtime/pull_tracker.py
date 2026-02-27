"""
In-memory pull job tracker for model pull operations (SIP-0075 §2.1).

V1: In-memory only. Runtime restart clears all pull job tracking.
Clients should treat unknown pull_id after restart as expired/lost state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

_pull_jobs: dict[str, PullJob] = {}


@dataclass
class PullJob:
    pull_id: str
    model_name: str
    status: str = "pending"  # pending | pulling | complete | failed
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


def create_pull_job(model_name: str) -> PullJob:
    """Create a new pull job and register it in the tracker."""
    job = PullJob(pull_id=str(uuid.uuid4()), model_name=model_name, status="pulling")
    _pull_jobs[job.pull_id] = job
    return job


def get_pull_job(pull_id: str) -> PullJob | None:
    """Look up a pull job by ID. Returns None if not found or expired."""
    return _pull_jobs.get(pull_id)


def complete_pull_job(pull_id: str) -> None:
    """Mark a pull job as successfully completed."""
    job = _pull_jobs.get(pull_id)
    if job:
        job.status = "complete"
        job.completed_at = datetime.now(UTC)


def fail_pull_job(pull_id: str, error: str) -> None:
    """Mark a pull job as failed with an error message."""
    job = _pull_jobs.get(pull_id)
    if job:
        job.status = "failed"
        job.error = error
        job.completed_at = datetime.now(UTC)


def clear_jobs() -> None:
    """Clear all tracked jobs (for testing)."""
    _pull_jobs.clear()
