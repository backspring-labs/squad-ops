"""The Project registry's writes, kept as the Postgres registry keeps them, over a test's records.

``KeyedProjectWrites`` gives a test's Project registry stand-in the writes the integration check
makes (SIP-0112 H.30): a contribution's state, a sync and a validation. Each obeys the port's
contract as ``adapters.cycles.postgres_project_registry`` does, which
``validation_record_contract`` holds on both:
- **a key replays** what it recorded, membership by key alone: a sync answers its stored document,
  a validation the Project as it is now, each with ``True``. A key with other content is refused;
- **a validation is fenced** on the baseline its caller read: a baseline that moved since, and isn't
  the commit, raises ``ProjectBaselineMovedError`` and writes nothing. One already at the commit is
  answered as it stands.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from squadops.cycles.models import (
    ProjectBaselineMovedError,
    ProjectStateConflictError,
    RegistrationKeyConflictError,
)
from squadops.projects.models import ProjectLifecycleStatus


class KeyedProjectWrites:
    """Installs the three writes on ``projects`` (which holds ``project`` and ``syncs``), over
    ``contributions``, a list of the Project's contribution records."""

    def __init__(self, projects: Any, contributions: list) -> None:
        self.projects, self.contributions = projects, contributions
        self.keys: dict[str, tuple[str, Any]] = {}
        #: Each commit a validation adopted, in order.
        self.validations: list[str] = []
        projects.record_contribution_state = self.record_contribution_state
        projects.record_sync = self.record_sync
        projects.record_validation = self.record_validation

    def _prior(self, key: str, digest: str) -> tuple[bool, Any]:
        if key not in self.keys:
            return False, None
        held_digest, stored = self.keys[key]
        if held_digest != digest:
            raise RegistrationKeyConflictError(
                f"idempotency key {key!r} recorded another operation"
            )
        return True, stored

    async def record_contribution_state(
        self, project_id, cycle_id, run_id, *, state, integrated_commit, actor
    ):
        [held] = [c for c in self.contributions if (c.cycle_id, c.run_id) == (cycle_id, run_id)]
        updated = dataclasses.replace(held, state=state, integrated_commit=integrated_commit)
        self.contributions[self.contributions.index(held)] = updated
        return updated

    async def record_sync(self, document, *, actor, idempotency_key, request_hash):
        seen, stored = self._prior(idempotency_key, request_hash)
        if seen:
            return stored, True
        self.projects.syncs.append(document)
        self.keys[idempotency_key] = (request_hash, document)
        return document, False

    async def record_validation(
        self, project_id, *, commit, diagnostic, actor, idempotency_key, expected_baseline
    ):
        if (commit is None) == (diagnostic is None):
            raise ValueError("a validation records a commit or a diagnostic, never both")
        seen, _ = self._prior(idempotency_key, f"validate:{project_id}")
        project = self.projects.project
        if seen:
            return project, True
        held = project.development_baseline_commit
        if commit is not None and held == commit:
            return project, False
        if held != expected_baseline:
            raise ProjectBaselineMovedError(
                f"Project {project_id}'s baseline moved to {held}", held=held
            )
        if project.lifecycle_status is ProjectLifecycleStatus.READY and commit is None:
            raise ProjectStateConflictError(
                f"Project {project_id} is READY: a failure isn't recorded"
            )
        self.validations.append(commit)
        self.projects.project = dataclasses.replace(
            project,
            lifecycle_status=ProjectLifecycleStatus.READY,
            development_baseline_commit=commit,
            integrated_upstream_commit=commit,
            record_version=project.record_version + 1,
        )
        self.keys[idempotency_key] = (f"validate:{project_id}", None)
        return self.projects.project, False


async def validation_record_contract(registry: Any, project_id: str, *, baseline: str) -> None:
    """The port's validation contract, on a READY Project at ``baseline``: each step's answer and
    what the Project holds after it. Bugs it catches in a registry: a replay that adopts; a stale
    validation that moves a newer adoption back; a key whose replay is read as an adoption."""
    import pytest

    u1, u2 = "1" * 40, "2" * 40

    def at(project) -> tuple:
        return (project.development_baseline_commit, project.integrated_upstream_commit)

    adopted, replayed = await registry.record_validation(
        project_id, commit=u1, diagnostic=None, actor="a", idempotency_key="c-1",
        expected_baseline=baseline,
    )  # fmt: skip
    assert (at(adopted), replayed) == ((u1, u1), False)
    version = adopted.record_version

    again, replayed = await registry.record_validation(
        project_id, commit=u1, diagnostic=None, actor="a", idempotency_key="c-1",
        expected_baseline=baseline,
    )  # fmt: skip
    assert (at(again), replayed, again.record_version) == ((u1, u1), True, version)

    with pytest.raises(ProjectBaselineMovedError) as moved:
        await registry.record_validation(
            project_id, commit=u2, diagnostic=None, actor="a", idempotency_key="c-2",
            expected_baseline=baseline,
        )  # fmt: skip
    assert moved.value.held == u1
    held = await registry.get_project(project_id)
    assert (at(held), held.record_version) == ((u1, u1), version)

    # The key was used, for another commit: replayed, and nothing adopted.
    spent, replayed = await registry.record_validation(
        project_id, commit=u2, diagnostic=None, actor="a", idempotency_key="c-1",
        expected_baseline=u1,
    )  # fmt: skip
    assert (at(spent), replayed) == ((u1, u1), True)

    current, replayed = await registry.record_validation(
        project_id, commit=u1, diagnostic=None, actor="a", idempotency_key="c-3",
        expected_baseline=baseline,
    )  # fmt: skip
    assert (at(current), replayed, current.record_version) == ((u1, u1), False, version)

    moved_on, replayed = await registry.record_validation(
        project_id, commit=u2, diagnostic=None, actor="a", idempotency_key="c-4",
        expected_baseline=u1,
    )  # fmt: skip
    assert (at(moved_on), replayed, moved_on.record_version) == ((u2, u2), False, version + 1)
