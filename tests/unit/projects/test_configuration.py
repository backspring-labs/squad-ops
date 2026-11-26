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


async def _configure_with_roots(registry, clone, roots):
    submission = _submission()
    submission["technical"]["package_roots"] = roots
    return await configure_project(
        "prj-tally",
        submission,
        expected_revision=0,
        registry=registry,
        repository=clone,
        actor="owner",
        idempotency_key="c-roots",
    )


async def test_declared_package_roots_are_recorded_and_read_back(fixture_tree):
    """SIP-0112 H.33 (#3134). Bugs caught: the roots dropped between the submission and the
    stored document, or not read back by ``parse_configuration``, so the derivation never sees
    them and a Luau product still offers no surface."""
    from squadops.projects.development_configuration import parse_configuration

    registry = _Registry(commit=fixture_tree.commit)

    await _configure_with_roots(registry, _Clone(fixture_tree), ["tally", "checks"])

    configuration, _ = registry.recorded
    document = configuration.to_document()
    assert document["configuration"]["technical"]["package_roots"] == ["tally", "checks"]
    assert parse_configuration(document).package_roots == ("tally", "checks")


@pytest.mark.parametrize(
    ("roots", "field", "says"),
    [
        (["gone"], "technical.package_roots[0]", "no directory at the baseline commit"),
        # A file, not a directory: nothing is under it.
        (["README.md"], "technical.package_roots[0]", "no directory at the baseline commit"),
        (["/tally"], "technical.package_roots[0]", "not a directory inside the repository"),
        (["../tally"], "technical.package_roots[0]", "not a directory inside the repository"),
        (["tally/"], "technical.package_roots[0]", "a repository directory"),
        ("tally", "technical.package_roots", "a list of repository directories"),
        (["tally", "tools/tally"], "technical.package_roots", "two roots name one package"),
    ],
    ids=[
        "absent",
        "a-file",
        "absolute",
        "leaves",
        "trailing-slash",
        "not-a-list",
        "one-name-twice",
    ],
)
async def test_a_package_root_nothing_could_import_is_refused_naming_the_entry(
    fixture_tree, roots, field, says
):
    """H.33, require, don't default. Bugs caught: a root that isn't in the tree recorded, so a
    criterion is admitted on a package that can't be required; a path leaving the repository;
    or two roots one name, so a criterion's package is ambiguous."""
    from squadops.projects.development_configuration import ConfigurationInvalid

    registry = _Registry(commit=fixture_tree.commit)

    with pytest.raises(ConfigurationInvalid) as raised:
        await _configure_with_roots(registry, _Clone(fixture_tree), roots)

    assert raised.value.field == field
    assert says in str(raised.value)
    assert registry.recorded is None


# --- H.35 (#3155): the paths the product's owner reserves from a cycle's change ------------------


async def _configure_reserving(registry, clone, reserved):
    submission = _submission()
    submission["technical"]["reserved_paths"] = reserved
    return await configure_project(
        "prj-tally",
        submission,
        expected_revision=0,
        registry=registry,
        repository=clone,
        actor="owner",
        idempotency_key="c-reserved",
    )


async def test_declared_reserved_paths_are_recorded_and_read_back(fixture_tree):
    """Entered at ``configure_project``, the call the configuration route makes. Bugs caught:
    the entries dropped between the submission and the stored document, or not read back by
    ``parse_configuration``, so the derivation and delivery both read "nothing reserved"."""
    from squadops.projects.development_configuration import parse_configuration

    registry = _Registry(commit=fixture_tree.commit)
    reserved = ["tally/report.py", "checks", "**/*.md"]

    await _configure_reserving(registry, _Clone(fixture_tree), reserved)

    configuration, _ = registry.recorded
    document = configuration.to_document()
    assert document["configuration"]["technical"]["reserved_paths"] == reserved
    assert parse_configuration(document).reserved_paths == tuple(reserved)


async def test_a_configuration_reserving_nothing_is_stored_as_it_was_before(fixture_tree):
    """The edge every existing product is: none declared. Bug caught: an empty list written to
    every stored configuration, moving its digest and reading as a declaration."""
    registry = _Registry(commit=fixture_tree.commit)

    await _configure_reserving(registry, _Clone(fixture_tree), [])

    configuration, _ = registry.recorded
    assert configuration.reserved_paths == ()
    assert "reserved_paths" not in configuration.to_document()["configuration"]["technical"]


@pytest.mark.parametrize(
    ("reserved", "field", "says"),
    [
        (["tally/reprot.py"], "technical.reserved_paths[0]", "reserves no file at the baseline"),
        (["tally", "gone/**"], "technical.reserved_paths[1]", "reserves no file at the baseline"),
        (["**"], "technical.reserved_paths[0]", "reserves every file"),
        (["./"], "technical.reserved_paths[0]", "reserves every file"),
        (["/tally"], "technical.reserved_paths[0]", "not a path inside the repository"),
        (["tally/../checks"], "technical.reserved_paths[0]", "not a path inside the repository"),
        (["tally", "tally"], "technical.reserved_paths[1]", "declared twice"),
        ([""], "technical.reserved_paths[0]", "a repository path or glob"),
        ([" tally"], "technical.reserved_paths[0]", "a repository path or glob"),
        ("tally", "technical.reserved_paths", "a list of repository paths or globs"),
    ],
    ids=[
        "a misspelt file",
        "a glob matching nothing",
        "everything",
        "the root",
        "absolute",
        "leaves",
        "twice",
        "empty",
        "padded",
        "not-a-list",
    ],
)
async def test_a_reservation_that_would_protect_nothing_or_everything_is_refused_naming_the_entry(
    fixture_tree, reserved, field, says
):
    """Require, don't default. Bugs caught: a misspelt entry recorded, so the file the owner
    meant is unprotected and nothing says so; an entry that reserves the whole product, which
    refuses every cycle at its end; a path outside the repository."""
    from squadops.projects.development_configuration import ConfigurationInvalid

    registry = _Registry(commit=fixture_tree.commit)

    with pytest.raises(ConfigurationInvalid) as raised:
        await _configure_reserving(registry, _Clone(fixture_tree), reserved)

    assert raised.value.field == field
    assert says in str(raised.value)
    assert registry.recorded is None
