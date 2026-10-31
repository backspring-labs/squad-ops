"""A greenfield product's first commit, at the destination its owner approved (SIP-0112 FR-01,
UC-B; E.4.6).

Entered at ``initialize_project``, the step ``POST /api/v1/projects/{id}/initializations`` runs,
through the real managed clone. The owner's empty repository is a bare repository under a
configured root, standing in for the forge's. Bugs caught:
- a layout other than the blueprint's, or a commit that doesn't reach the lifecycle after it;
- a branch that already has a commit overwritten, or pushed to at all;
- a retry, after a push that landed and a record that didn't, refused, so the Project is stuck;
- a Project initialized twice, or from a manifest that isn't for it or can't be scaffolded;
- a greenfield Development Configuration that doesn't name the blueprint it was started on.
"""

from __future__ import annotations

import dataclasses
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from adapters.tools.git_source import GitSourceRepository
from squadops.cycles.models import Project
from squadops.projects.configuration import configure_project
from squadops.projects.development_configuration import ConfigurationInvalid
from squadops.projects.initialization import (
    InitializationRefused,
    initial_tree,
    initialize_project,
    read_manifest,
)
from squadops.projects.models import ProjectLifecycleStatus, ProjectSource, SourceUnavailable
from squadops.projects.registration import LocatorPolicy
from squadops.projects.validation import validate_project
from tests.fixtures.shared_contract.repository import build_repository, recorded

pytestmark = [pytest.mark.domain_api]

_REPO_ROOT = Path(__file__).resolve().parents[3]
STACK = "fullstack_fastapi_react"
NOW = datetime(2026, 10, 20, 23, 0, tzinfo=UTC)


def _manifest(project_id: str = "shelfnote", **changes) -> str:
    """The group_run example's approved manifest, made this Project's."""
    doc = yaml.safe_load((_REPO_ROOT / "examples/03_group_run/interface_manifest.yaml").read_text())
    doc.update(project_id=project_id, **changes)
    return yaml.safe_dump(doc, sort_keys=False)


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return done.stdout.strip()


class _Registry:
    """Records as the registry would, and can fail its first initialization record."""

    def __init__(self, project, *, fail_first_record=False):
        self.project = project
        self.initialization = None
        self.configuration = None
        self.fail_first_record = fail_first_record

    async def get_project(self, project_id):
        return self.project

    async def get_initialization(self, project_id):
        return self.initialization

    async def record_initialization(self, initialization, *, idempotency_key, request_hash):
        if self.fail_first_record:
            self.fail_first_record = False
            raise ConnectionError("the database went away after the push")
        if self.initialization is not None:
            return self.initialization, True
        self.initialization = initialization
        return initialization, False

    async def record_validation(self, project_id, *, commit, diagnostic, actor, idempotency_key):
        status = (
            ProjectLifecycleStatus.READY if commit else ProjectLifecycleStatus.FAILED_REGISTRATION
        )
        self.project = dataclasses.replace(
            self.project, lifecycle_status=status, development_baseline_commit=commit
        )
        return self.project, False

    async def record_development_configuration(self, configuration, **kwargs):
        self.configuration = configuration
        return configuration, False


@pytest.fixture
def world(tmp_path):
    sources = tmp_path / "sources"
    remote = sources / "shelfnote.git"
    remote.mkdir(parents=True)
    _git(remote, "init", "--bare", "--quiet", "--initial-branch=main")
    clones = GitSourceRepository(
        tmp_path / "cache",
        LocatorPolicy.of([], [str(sources)]),
        timeout_seconds=60,
        committer_name="SquadOps",
        committer_email="squadops@squadops.invalid",
    )
    project = Project(
        project_id="shelfnote",
        name="Shelfnote",
        description="A shared reading list with notes",
        created_at=datetime(2026, 10, 20, 22, 0, tzinfo=UTC),
        lifecycle_status=ProjectLifecycleStatus.REGISTERING,
        source=ProjectSource(str(remote), "refs/heads/main", "review_request"),
    )
    return remote, clones, _Registry(project)


async def _initialize(registry, clones, manifest=None, *, tokens=None, key="init-1"):
    return await initialize_project(
        registry.project.project_id,
        manifest or _manifest(),
        registry=registry,
        repository=clones,
        tokens={"shelfnote": "owner-token"} if tokens is None else tokens,
        actor="owner",
        idempotency_key=key,
        now=NOW,
    )


def _greenfield_submission(stack):
    technical = dict(recorded("development_configuration", "valid")["configuration"]["technical"])
    technical["stack"] = stack
    return {"technical": technical}


async def test_a_greenfield_project_starts_on_its_blueprint_and_goes_on_through_the_lifecycle(
    world,
):
    """FR-01, UC-B: the empty branch's first commit is the blueprint's layout and nothing else,
    with no parent; validation then reaches READY at it, and the Development Configuration names
    the blueprint, recorded at that commit."""
    remote, clones, registry = world

    initialization, replayed = await _initialize(registry, clones)

    head = _git(remote, "rev-parse", "refs/heads/main")
    assert (initialization.commit, replayed) == (head, False)
    assert _git(remote, "rev-list", "--parents", "-n", "1", head) == head  # a root commit
    expected, executable = initial_tree(read_manifest("shelfnote", _manifest()))
    listing = _git(remote, "ls-tree", "-r", head).splitlines()
    assert {line.split("\t")[1] for line in listing} == set(expected) == set(initialization.files)
    modes = {line.split("\t")[1]: line.split()[0] for line in listing}
    assert {p for p, mode in modes.items() if mode == "100755"} == executable == {"start.sh"}
    assert (
        _git(remote, "show", f"{head}:backend/main.py")
        == expected["backend/main.py"].decode().strip()
    )

    project, _ = await validate_project(
        "shelfnote", registry=registry, repository=clones, actor="owner", idempotency_key="v-1"
    )
    assert (project.lifecycle_status, project.development_baseline_commit) == (
        ProjectLifecycleStatus.READY, head,
    )  # fmt: skip
    configuration, _ = await configure_project(
        "shelfnote", _greenfield_submission(STACK), expected_revision=0, registry=registry,
        repository=clones, actor="owner", idempotency_key="c-1",
    )  # fmt: skip
    assert (configuration.stack, configuration.validated_at_commit) == (STACK, head)


async def test_a_branch_that_has_a_commit_is_never_pushed_to(tmp_path):
    """The owner's repository wasn't empty: refused before any push, the branch untouched, and
    nothing recorded."""
    repo = build_repository(tmp_path / "sources" / "tally")
    clones = GitSourceRepository(
        tmp_path / "cache", LocatorPolicy.of([], [str(tmp_path / "sources")]),
        timeout_seconds=60, committer_name="SquadOps", committer_email="squadops@squadops.invalid",
    )  # fmt: skip
    registry = _Registry(
        Project(
            project_id="shelfnote",
            name="Shelfnote",
            description="",
            created_at=datetime(2026, 10, 20, tzinfo=UTC),
            lifecycle_status=ProjectLifecycleStatus.FAILED_REGISTRATION,
            source=ProjectSource(str(repo.path), "refs/heads/main", "review_request"),
        )  # fmt: skip
    )

    with pytest.raises(SourceUnavailable) as refused:
        await _initialize(registry, clones)

    assert refused.value.reason == "not_empty"
    assert _git(repo.path, "rev-parse", "refs/heads/main") == repo.second_commit
    assert registry.initialization is None


async def test_a_retry_after_the_push_landed_records_the_same_commit(world):
    """The push landed and the record didn't. The retry makes the same commit, finds the branch
    already at it, and records it, rather than refusing a branch it filled itself."""
    remote, clones, registry = world
    registry.fail_first_record = True
    with pytest.raises(ConnectionError):
        await _initialize(registry, clones, key="init-1")
    pushed = _git(remote, "rev-parse", "refs/heads/main")

    initialization, replayed = await _initialize(registry, clones, key="init-2")

    assert (initialization.commit, replayed) == (pushed, False)
    assert _git(remote, "rev-parse", "refs/heads/main") == pushed


async def test_a_project_initialized_already_is_answered_or_refused_by_its_manifest(world):
    remote, clones, registry = world
    first, _ = await _initialize(registry, clones)

    again, replayed = await _initialize(registry, clones, key="init-2")
    assert (again, replayed) == (first, True)
    with pytest.raises(InitializationRefused, match="from another manifest"):
        await _initialize(registry, clones, _manifest(scope="something else"), key="init-3")
    assert _git(remote, "rev-parse", "refs/heads/main") == first.commit


@pytest.mark.parametrize(
    ("change", "manifest", "tokens", "why"),
    [
        ({"source": None}, None, None, "sample application"),
        ({"lifecycle_status": ProjectLifecycleStatus.READY,
          "development_baseline_commit": "a" * 40}, None, None, "source reached"),
        ({}, _manifest("tally"), None, "is for 'tally'"),
        ({}, _manifest(stack="rails_hotwire"), None, "can't be scaffolded"),
        ({}, "kind: interface_manifest\n", None, "doesn't parse"),
        ({}, None, {}, "no token"),
    ],
    ids=["a-sample-application", "a-project-already-reached", "another-projects-manifest",
         "a-stack-with-no-blueprint", "a-manifest-that-doesnt-parse", "no-token"],
)  # fmt: skip
async def test_an_initialization_that_cant_be_made_pushes_nothing(
    world, change, manifest, tokens, why
):
    remote, clones, registry = world
    registry.project = dataclasses.replace(registry.project, **change)

    with pytest.raises(InitializationRefused, match=why):
        await _initialize(registry, clones, manifest, tokens=tokens)

    assert _git(remote, "for-each-ref") == ""
    assert registry.initialization is None


@pytest.mark.parametrize(
    ("stack", "why"),
    [("rails_hotwire", "not a SIP-0105 blueprint"), ("nextjs_ts", "initialized on the"),
     (None, "initialized on the")],
    ids=["no-such-blueprint", "another-blueprint", "none-named"],
)  # fmt: skip
async def test_a_greenfield_configuration_names_the_blueprint_it_was_started_on(world, stack, why):
    """§B.4.1: a greenfield Project names its blueprint in its Development Configuration."""
    _remote, clones, registry = world
    await _initialize(registry, clones)
    await validate_project(
        "shelfnote", registry=registry, repository=clones, actor="owner", idempotency_key="v-1"
    )

    with pytest.raises(ConfigurationInvalid, match=why):
        await configure_project(
            "shelfnote", _greenfield_submission(stack), expected_revision=0, registry=registry,
            repository=clones, actor="owner", idempotency_key="c-1",
        )  # fmt: skip
    assert registry.configuration is None
