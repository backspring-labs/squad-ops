"""Recording a Project's Development Configuration (SIP-0112 §B.5.1, E.4.2).

Entered at ``configure_project``, the step ``POST /api/v1/projects/{id}/development-configurations``
runs, with a recording registry and a managed clone that serves the shared fixture's tree.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest

from squadops.cycles.models import Project, ProjectStateConflictError
from squadops.projects.configuration import configure_project
from squadops.projects.models import (
    CheckoutTree,
    ProjectLifecycleStatus,
    ProjectSource,
    SourceUnavailable,
)
from tests.fixtures.shared_contract.repository import build_repository, recorded, tracked_files


@pytest.fixture
def fixture_tree(tmp_path):
    repo = build_repository(tmp_path / "tally")
    files = tracked_files(repo.path, repo.second_commit)
    return CheckoutTree(repo.second_commit, files, frozenset(), frozenset(), frozenset())


class _Registry:
    def __init__(self, status=ProjectLifecycleStatus.READY, commit=None):
        self.project = Project(
            project_id="prj-tally",
            name="Tally",
            description="",
            created_at=datetime(2026, 10, 18, tzinfo=UTC),
            lifecycle_status=status,
            source=ProjectSource(
                repo_uri="https://code.example.invalid/tally.git",
                base_ref="refs/heads/main",
                contribution_mode="review_request",
            ),
            development_baseline_commit=commit,
        )
        self.recorded = None

    async def get_project(self, project_id):
        return self.project

    async def get_initialization(self, project_id):
        return None  # an existing product, registered rather than initialized here

    async def record_development_configuration(self, configuration, **kwargs):
        self.recorded = (configuration, kwargs)
        return configuration, False


class _Clone:
    def __init__(self, tree, *, lost=False):
        self.tree, self.lost, self.synced = tree, lost, []

    async def tree_at(self, project_id, commit):
        if self.lost:
            raise SourceUnavailable("the managed clone does not exist yet", reason="not_cloned")
        return self.tree

    async def sync(self, project_id, locator, ref):
        self.synced.append((locator, ref))
        self.lost = False
        return self.tree.commit


def _submission():
    technical = copy.deepcopy(
        recorded("development_configuration", "valid")["configuration"]["technical"]
    )
    return {"technical": technical}


async def _configure(registry, clone, expected_revision=0):
    return await configure_project(
        "prj-tally",
        _submission(),
        expected_revision=expected_revision,
        registry=registry,
        repository=clone,
        actor="owner",
        idempotency_key="c-1",
    )


async def test_the_record_is_the_fixtures_at_the_baseline_commit(fixture_tree):
    """§B.5.1. Bugs caught: instruction sources read at a commit other than the one the
    commands are recorded against; a revision numbered other than the next."""
    registry = _Registry(commit=fixture_tree.commit)

    await _configure(registry, _Clone(fixture_tree), expected_revision=0)

    configuration, kwargs = registry.recorded
    assert configuration.to_document() == recorded("development_configuration", "valid")
    assert (kwargs["actor"], kwargs["idempotency_key"]) == ("owner", "c-1")


async def test_a_lost_clone_is_fetched_again_before_its_tree_is_read(fixture_tree):
    """§B.3: the managed clone is a cache, gone with its container. Bug caught: a configuration
    refused after a restart because the cache was empty."""
    registry, clone = _Registry(commit=fixture_tree.commit), _Clone(fixture_tree, lost=True)

    await _configure(registry, clone)

    assert clone.synced == [("https://code.example.invalid/tally.git", "refs/heads/main")]
    assert registry.recorded[0].instruction_sources[0].path == "CONTRIBUTING.md"


@pytest.mark.parametrize(
    ("status", "commit"),
    [
        (ProjectLifecycleStatus.REGISTERING, None),
        (ProjectLifecycleStatus.FAILED_REGISTRATION, None),
    ],
)
async def test_a_project_whose_source_was_never_reached_is_refused(fixture_tree, status, commit):
    registry = _Registry(status=status, commit=commit)

    with pytest.raises(ProjectStateConflictError, match=status.value):
        await _configure(registry, _Clone(fixture_tree))
    assert registry.recorded is None


async def test_the_request_hash_covers_the_expected_revision(fixture_tree):
    """Bug caught: a retry against a different expected revision replaying the first, so a
    concurrent recording slips past the version precondition."""
    first, second = _Registry(commit=fixture_tree.commit), _Registry(commit=fixture_tree.commit)

    await _configure(first, _Clone(fixture_tree), expected_revision=0)
    await _configure(second, _Clone(fixture_tree), expected_revision=1)

    assert first.recorded[1]["request_hash"] != second.recorded[1]["request_hash"]
    assert second.recorded[0].revision == 2
