"""A Project's upstream read against its approved baseline (SIP-0112 FR-21, FR-06; E.4.4).

Against the shared fixture's product through the real managed clone. An outside developer
changes the repository, and the squad's earlier contribution is taken in, or not. The one
stand-in is the forge, which answers a review request's state. Bugs caught:
- an outside change to how the product is checked or instructed not named, so the next unit
  relies on evidence validated against an older tree;
- a contribution the product took left pending, or one it closed read as taken;
- a squash merge, which makes a new commit, never recognized as integration;
- a sync that moves the approved baseline by itself.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime

import pytest

from adapters.tools.git_source import GitSourceRepository
from squadops.cycles.models import Project
from squadops.ports.projects.review_request import ReviewRequestState
from squadops.projects.contribution import Contribution, capture_ref
from squadops.projects.development_configuration import parse_configuration
from squadops.projects.drift import (
    COMMAND_INPUTS,
    CONTRIBUTION_POLICY,
    DEPENDENCIES,
    INSTRUCTIONS,
    SOURCE,
    TOOLCHAIN,
    drift_between,
)
from squadops.projects.models import ProjectSource
from squadops.projects.registration import LocatorPolicy
from squadops.projects.sync import sync_project
from tests.fixtures.shared_contract.repository import build_repository, recorded, tracked_files

ENV = {
    "GIT_AUTHOR_NAME": "o",
    "GIT_AUTHOR_EMAIL": "o@example.invalid",
    "GIT_COMMITTER_NAME": "o",
    "GIT_COMMITTER_EMAIL": "o@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
}


def _git(repo, *args):
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=repo, env=ENV, capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip


def _commit(repo, files, message):
    for path, content in files.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


class _Registry:
    def __init__(self, project, configuration):
        self.project, self.configuration = project, configuration
        self.contributions_held: list[Contribution] = []
        self.syncs: list[dict] = []

    async def get_project(self, project_id):
        return self.project

    async def get_development_configuration(self, project_id, revision=None):
        return self.configuration

    async def contributions(self, project_id):
        return list(self.contributions_held)

    async def record_contribution_state(self, project_id, cycle_id, run_id, **change):
        actor = change.pop("actor")
        assert actor == "owner"
        [held] = [c for c in self.contributions_held if c.run_id == run_id]
        updated = Contribution(**{**held.__dict__, **change})
        self.contributions_held = [updated]
        return updated

    async def record_sync(self, document, **kwargs):
        self.syncs.append(document)
        return document, False


class _Forge:
    def __init__(self, state):
        self.state = state

    async def review_request_state(self, *, url, token):
        return self.state


@pytest.fixture
def world(tmp_path):
    repo = build_repository(tmp_path / "sources" / "tally")
    clones = GitSourceRepository(
        tmp_path / "cache",
        LocatorPolicy.of([], [str(tmp_path / "sources")]),
        timeout_seconds=60,
        committer_name="SquadOps",
        committer_email="squadops@squadops.invalid",
    )
    project = Project(
        project_id="prj-tally",
        name="Tally",
        description="",
        created_at=datetime(2026, 10, 19, tzinfo=UTC),
        source=ProjectSource(str(repo.path), "refs/heads/main", "review_request"),
        development_baseline_commit=repo.second_commit,
    )
    configuration = parse_configuration(recorded("development_configuration", "valid"))
    return repo, clones, _Registry(project, configuration)


async def _sync(clones, registry, forge=None):
    return await sync_project(
        "prj-tally",
        registry=registry,
        repository=clones,
        forge=forge,
        tokens={"prj-tally": "t0ken"},
        actor="owner",
        idempotency_key="s-1",
    )


async def _contributed(repo, clones, registry):
    """A pending review request for a captured change, pushed as squadops/cyc_1."""
    await clones.sync("prj-tally", str(repo.path), "refs/heads/main")
    files = tracked_files(repo.path, repo.second_commit)
    files["tally/report.py"] += b"\n# summary line\n"
    commit = await clones.commit_tree(
        "prj-tally", parent=repo.second_commit, files=files, executable=(),
        ref=capture_ref("cyc_1", "run_1"), message="squad\n",
    )  # fmt: skip
    await clones.push_capture(
        "prj-tally", str(repo.path), ref=capture_ref("cyc_1", "run_1"),
        branch="squadops/cyc_1", token="t0ken",
    )  # fmt: skip
    registry.contributions_held = [
        Contribution(
            project_id="prj-tally",
            cycle_id="cyc_1",
            run_id="run_1",
            commit=commit,
            parent_commit=repo.second_commit,
            mode="review_request",
            state="pending",
            branch="squadops/cyc_1",
            review_url="https://github.com/o/tally/pull/7",
            contributed_by="owner",
            contributed_at=datetime(2026, 10, 19, tzinfo=UTC),
        )  # fmt: skip
    ]
    return commit


def test_each_changed_path_is_named_by_the_evidence_it_invalidates():
    """Bug caught: a changed check script, instruction or toolchain pin filed as ordinary
    source, so the evidence validated against the old tree is relied on."""
    configuration = parse_configuration(recorded("development_configuration", "valid"))
    old = {"tally/report.py": b"a", "tools/build.py": b"a", "CONTRIBUTING.md": b"a"}
    new = {
        "tally/report.py": b"b",
        "tools/build.py": b"b",  # named by the build check's argv
        "CONTRIBUTING.md": b"b",
        "requirements-dev.txt": b"b",
        ".python-version": b"3.13\n",
        ".github/workflows/ci.yml": b"b",
    }

    drift = drift_between("p", "a" * 40, "b" * 40, old, new, configuration)

    assert drift.changed == {
        SOURCE: ("tally/report.py",),
        COMMAND_INPUTS: ("tools/build.py",),
        INSTRUCTIONS: ("CONTRIBUTING.md",),
        DEPENDENCIES: ("requirements-dev.txt",),
        TOOLCHAIN: (".python-version",),
        CONTRIBUTION_POLICY: (".github/workflows/ci.yml",),
    }
    assert drift.relevant == [
        INSTRUCTIONS, COMMAND_INPUTS, DEPENDENCIES, TOOLCHAIN, CONTRIBUTION_POLICY
    ]  # fmt: skip


async def test_an_outside_change_is_named_and_the_baseline_stays_where_it_was(world):
    repo, clones, registry = world
    head = _commit(
        repo.path,
        {"CONTRIBUTING.md": "Run the checks first.\n", "tally/notes.py": "NOTES = []\n"},
        "outside",
    )

    document, _ = await _sync(clones, registry)

    assert (document["baseline_commit"], document["upstream_commit"]) == (
        repo.second_commit,
        head,
    )
    assert document["drift"]["changed"] == {
        INSTRUCTIONS: ["CONTRIBUTING.md"],
        SOURCE: ["tally/notes.py"],
    }
    assert document["drift"]["relevant"] == [INSTRUCTIONS]
    assert registry.project.development_baseline_commit == repo.second_commit


async def test_an_unmoved_upstream_has_no_drift(world):
    repo, clones, registry = world

    document, _ = await _sync(clones, registry)

    assert document["drift"] is None and document["upstream_commit"] == repo.second_commit


@pytest.mark.parametrize(
    ("merge", "forge_state", "expected"),
    [("fast-forward", None, "integrated"), ("squash", "merged", "integrated"),
     (None, "closed", "closed"), (None, "open", "pending")],
    ids=["its-commit-taken", "squash-merged", "closed-unmerged", "still-open"],
)  # fmt: skip
async def test_a_contribution_stands_as_the_product_took_it(world, merge, forge_state, expected):
    repo, clones, registry = world
    commit = await _contributed(repo, clones, registry)
    merged = None
    if merge == "fast-forward":
        _git(repo.path, "merge", "-q", "--ff-only", "squadops/cyc_1")
        merged = commit
    elif merge == "squash":
        _git(repo.path, "merge", "-q", "--squash", "squadops/cyc_1")
        _git(repo.path, "commit", "-q", "-m", "the squad's change, squashed")
        merged = _git(repo.path, "rev-parse", "HEAD")
    forge = _Forge(ReviewRequestState(forge_state, merged)) if forge_state else None

    document, _ = await _sync(clones, registry, forge)

    [standing] = document["contributions"]
    assert (standing["state"], standing["integrated_commit"]) == (expected, merged)


async def test_a_reference_reads_the_pinned_commit_never_the_branch_head(world):
    """Contract 6's resolver. Bugs caught: an instruction read at the branch's head, so a
    unit's instructions and the commands it pinned come from different commits; a digest that
    isn't the one discovery recorded for that commit; a missing source passed over silently."""
    from squadops.projects.references import ReferenceUnresolved, resolve_repository_reference
    from squadops.projects.source_context import parse_source_context

    repo, clones, _registry = world
    await clones.sync("prj-tally", str(repo.path), "refs/heads/main")
    _commit(repo.path, {"CONTRIBUTING.md": "changed upstream\n"}, "outside")
    await clones.sync("prj-tally", str(repo.path), "refs/heads/main")
    context = parse_source_context(recorded("project_source_context", "valid"))
    recorded_source = recorded("development_configuration", "valid")["configuration"][
        "instruction_sources"
    ][0]

    reference = await resolve_repository_reference(
        context.__class__(**{**context.__dict__, "project_id": "prj-tally"}),
        "CONTRIBUTING.md",
        repository=clones,
    )

    assert reference.commit == repo.second_commit
    assert reference.digest == recorded_source["digest"]
    with pytest.raises(ReferenceUnresolved, match="AGENTS.md"):
        await resolve_repository_reference(
            context.__class__(**{**context.__dict__, "project_id": "prj-tally"}),
            "AGENTS.md",
            repository=clones,
        )
