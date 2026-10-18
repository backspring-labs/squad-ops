"""Validating a registered Project (SIP-0112 E.4.2, §B.6, R4).

Entered at ``validate_project``, the step ``POST /api/v1/projects/{id}/validate`` runs, with a
recording registry and a managed clone that answers as told.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.cycles.models import Project, ProjectStateConflictError
from squadops.projects.models import CheckoutTree, ProjectSource, SourceUnavailable
from squadops.projects.validation import validate_project

COMMIT = "c" * 40
SOURCE = ProjectSource(
    repo_uri="https://code.example.invalid/tally.git",
    base_ref="refs/heads/main",
    contribution_mode="review_request",
)


class _Registry:
    def __init__(self, source=SOURCE):
        self.project = Project(
            project_id="prj-tally",
            name="Tally",
            description="",
            created_at=datetime(2026, 10, 18, tzinfo=UTC),
            source=source,
        )
        self.recorded = None

    async def get_project(self, project_id):
        return self.project

    async def record_validation(self, project_id, **kwargs):
        self.recorded = kwargs
        return self.project, False


class _Clone:
    def __init__(self, *, fails=None, symlinks=frozenset()):
        self.fails, self.symlinks, self.calls = fails, symlinks, []

    async def sync(self, project_id, locator, ref):
        self.calls.append((project_id, locator, ref))
        if self.fails:
            raise self.fails
        return COMMIT

    async def tree_at(self, project_id, commit):
        return CheckoutTree(commit, {"a.py": b""}, frozenset(), self.symlinks, frozenset())


async def _validate(registry, clone):
    return await validate_project(
        "prj-tally", registry=registry, repository=clone, actor="owner", idempotency_key="v-1"
    )


async def test_a_reached_source_records_ready_at_the_base_refs_commit():
    registry, clone = _Registry(), _Clone()

    await _validate(registry, clone)

    assert clone.calls == [("prj-tally", SOURCE.repo_uri, SOURCE.base_ref)]
    assert registry.recorded == {
        "commit": COMMIT,
        "diagnostic": None,
        "actor": "owner",
        "idempotency_key": "v-1",
    }


@pytest.mark.parametrize(
    ("clone", "diagnostic"),
    [
        (
            _Clone(fails=SourceUnavailable("git clone failed: not found", reason="clone")),
            "clone: git clone failed: not found",
        ),
        (
            _Clone(symlinks=frozenset({"docs/link"})),
            "capability gap: the sandbox cannot carry tracked symlinks: docs/link",
        ),
    ],
    ids=["unreachable", "a-symlink"],
)
async def test_a_source_it_cannot_reach_or_carry_records_the_reason(clone, diagnostic):
    """R4, §8.2.1. Bugs caught: a Project READY whose source was never reached; a tree with a
    symlink called READY, so the first Cycle fails at seeding instead of registration naming it;
    the failure raised as a 500 rather than recorded for a retry."""
    registry = _Registry()

    await _validate(registry, clone)

    assert (registry.recorded["commit"], registry.recorded["diagnostic"]) == (None, diagnostic)


async def test_a_sample_application_has_nothing_to_validate():
    clone = _Clone()

    with pytest.raises(ProjectStateConflictError, match="sample application"):
        await _validate(_Registry(source=None), clone)
    assert clone.calls == []
