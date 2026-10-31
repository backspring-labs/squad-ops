"""A Project's upstream read against its approved baseline (SIP-0112 FR-21, FR-06; E.4.4).

Against the shared fixture's product through the real managed clone. An outside developer
changes the repository, and the squad's earlier contribution is taken in, or not. The one
stand-in is the forge, which answers a review request's state. Bugs caught:
- an outside change to how the product is checked or instructed not named, so the next unit
  relies on evidence validated against an older tree;
- a contribution the product took left pending, or one it closed read as taken;
- a squash merge, which makes a new commit, never recognized as integration;
- a sync that moves the approved baseline by itself;
- an instruction's repository reference bound at the branch's head, not the unit's pinned commit.
"""

from __future__ import annotations

import dataclasses
import subprocess
from datetime import UTC, datetime

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from adapters.memory.reference_resolvers import create_reference_resolvers
from adapters.tools.factory import create_repository_reference_resolver
from adapters.tools.git_source import GitSourceRepository
from adapters.tools.repository_references import REPOSITORY_FAMILY, RepositoryReferenceResolver
from squadops.cycles.models import Project, ProjectNotFoundError
from squadops.memory.pinning import pin_standalone_cycle
from squadops.memory.records import Reference
from squadops.memory.reference_reading import Unread, read_references
from squadops.ports.memory.references import BindingContext, BoundReference, ReferenceUnresolved
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
from squadops.projects.models import ProjectSource, SourceUnavailable
from squadops.projects.registration import LocatorPolicy
from squadops.projects.source_context import parse_source_context
from squadops.projects.sync import sync_project
from tests.fixtures.shared_contract.repository import build_repository, recorded, tracked_files
from tests.unit.cycles.test_failure_recall import _framing_cycle
from tests.unit.memory.test_project_instructions import DESIGN, T0, _instruction

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


@pytest.mark.parametrize("merge", ["merge-commit", "squash"])
async def test_an_integrated_contribution_is_named_apart_from_what_changed_outside(world, merge):
    """#2606, the brownfield demonstration's stage 4 replayed: the squad's change merged, then an
    outside commit on top. Bugs caught: the squad's own merged files filed as outside source drift
    beside the outside developer's; a squash merge, which takes no commit of ours, losing them."""
    repo, clones, registry = world
    commit = await _contributed(repo, clones, registry)
    if merge == "merge-commit":
        _git(
            repo.path, "merge", "-q", "--no-ff", "-m", "merge the squad's change", "squadops/cyc_1"
        )
        forge = None
    else:
        _git(repo.path, "merge", "-q", "--squash", "squadops/cyc_1")
        _git(repo.path, "commit", "-q", "-m", "the squad's change, squashed")
        forge = _Forge(ReviewRequestState("merged", _git(repo.path, "rev-parse", "HEAD")))
    _commit(
        repo.path,
        {"CONTRIBUTING.md": "Run the checks first.\n", "tally/notes.py": "NOTES = []\n"},
        "outside",
    )

    document, _ = await _sync(clones, registry, forge)

    drift = document["drift"]
    assert drift["schema"] == "source-drift/v2"
    assert drift["changed"] == {INSTRUCTIONS: ["CONTRIBUTING.md"], SOURCE: ["tally/notes.py"]}
    assert drift["integrated"] == [
        {"cycle_id": "cyc_1", "run_id": "run_1", "commit": commit,
         "changed": {SOURCE: ["tally/report.py"]}},
    ]  # fmt: skip
    assert drift["relevant"] == [INSTRUCTIONS]
    assert document["contributions"][0]["state"] == "integrated"


async def test_a_file_changed_outside_after_the_contribution_is_outside_drift(world):
    """#2606. Bug caught: a path the squad changed and an outside developer changed again since,
    credited to the squad, so the outside change goes unnamed."""
    repo, clones, registry = world
    await _contributed(repo, clones, registry)
    _git(repo.path, "merge", "-q", "--ff-only", "squadops/cyc_1")
    report = (repo.path / "tally/report.py").read_text()
    _commit(repo.path, {"tally/report.py": report + "# an outside edit\n"}, "outside")

    document, _ = await _sync(clones, registry)

    drift = document["drift"]
    assert drift["changed"] == {SOURCE: ["tally/report.py"]}
    assert drift["integrated"] == []


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


async def test_a_repository_reference_binds_the_pinned_commit_never_the_branch_head(world):
    """Contract 6's resolver, on the T16 port. Bugs caught: an instruction bound at the branch's
    head, so a unit's instructions and the commands it pinned come from different commits; a digest
    that isn't the one discovery recorded for that commit; a read that hands back content the
    binding never saw; a missing source, or a unit with no source commit, bound to something."""
    repo, clones, _registry = world
    await clones.sync("prj-tally", str(repo.path), "refs/heads/main")
    _commit(repo.path, {"CONTRIBUTING.md": "changed upstream\n"}, "outside")
    await clones.sync("prj-tally", str(repo.path), "refs/heads/main")
    resolver = RepositoryReferenceResolver(clones, _registry)
    pinned = BindingContext("prj-tally", "cycle", "cyc_1", repo.second_commit)
    [discovered] = recorded("development_configuration", "valid")["configuration"][
        "instruction_sources"
    ]

    bound = await resolver.bind("repo:file:CONTRIBUTING.md@current", pinned)

    assert bound == BoundReference(
        f"repo:file:CONTRIBUTING.md@{repo.second_commit}", repo.second_commit, discovered["digest"]
    )
    assert "changed upstream" not in await resolver.read(bound, pinned)
    tampered = BoundReference(bound.ref, bound.revision, "sha256:" + "0" * 64)
    with pytest.raises(ReferenceUnresolved, match="no longer matches"):
        await resolver.read(tampered, pinned)
    with pytest.raises(ReferenceUnresolved, match="AGENTS.md"):
        await resolver.bind("repo:file:AGENTS.md@current", pinned)
    with pytest.raises(ReferenceUnresolved, match="pins no source commit"):
        await resolver.bind(
            "repo:file:CONTRIBUTING.md@current", BindingContext("prj-tally", "campaign", "cmp_1")
        )


async def test_a_clone_that_times_out_is_a_fault_never_a_reference_kept_unbound(world, tmp_path):
    """SIP-0110 §5ae, through the real managed clone with git's own bound cut short. Bug caught:
    git's timeout turned into ``ReferenceUnresolved``, so a campaign cycle launched while the clone
    was slow keeps a required reference unbound for its life, holding every task it applies to,
    where a fault would have had the next drain bind it."""
    repo, clones, _registry = world
    await clones.sync("prj-tally", str(repo.path), "refs/heads/main")
    pinned = BindingContext("prj-tally", "cycle", "cyc_1", repo.second_commit)
    bound = await RepositoryReferenceResolver(clones, _registry).bind(
        "repo:file:CONTRIBUTING.md@current", pinned
    )
    slow = GitSourceRepository(
        tmp_path / "cache",
        LocatorPolicy.of([], [str(tmp_path / "sources")]),
        timeout_seconds=1e-6,
        committer_name="SquadOps",
        committer_email="squadops@squadops.invalid",
    )
    resolver = RepositoryReferenceResolver(slow, _registry)

    for call in (resolver.bind(bound.ref.replace(repo.second_commit, "current"), pinned),
                 resolver.read(bound, pinned)):  # fmt: skip
        with pytest.raises(SourceUnavailable) as raised:
            await call
        assert raised.value.reason == "timeout"


async def test_a_clone_moved_aside_holds_a_read_as_the_store_failing_and_names_the_clone(
    world, tmp_path
):
    """#2672, entered where a dispatch reads its references (``read_references`` through
    ``SnapshotRecall``), with this resolver registered under its bound as the runtime registers it.
    Bugs caught: a clone moved aside answering "git is not installed here", which sends an
    operator after a git binary; and a fix that made a missing clone a refusal of the reference,
    so the task waits on the operator's re-binding instead of releasing once the clone is back."""
    repo, clones, registry = world
    await clones.sync("prj-tally", str(repo.path), "refs/heads/main")
    pinned = BindingContext("prj-tally", "cycle", "cyc_1", repo.second_commit)
    bound = await RepositoryReferenceResolver(clones, registry).bind(
        "repo:file:CONTRIBUTING.md@current", pinned
    )
    resolvers = create_reference_resolvers(30.0)
    resolvers.register(create_repository_reference_resolver(clones, registry))
    recall = SnapshotRecall(InMemoryCrossCycleMemoryStore(), resolvers=resolvers)
    dispatch = BindingContext("prj-tally", "cycle", "cyc_1")
    clone = tmp_path / "cache" / "prj-tally.git"
    clone.rename(tmp_path / "cache" / "moved-aside.git")

    read = await read_references(
        [Reference(bound.ref, True, digest=bound.digest)],
        lambda reference: recall.read_reference(reference, dispatch),
    )

    assert read.unread == {
        bound.ref: Unread(
            "its repo resolver failed (SourceUnavailable: the managed clone is missing: "
            f"{clone} does not exist)",
            store_failed=True,
        )
    }


async def test_a_standalone_cycle_pins_a_project_instruction_at_its_source_context(world):
    """The wiring, entered where a standalone cycle is admitted (``pin_standalone_cycle``), with a
    real ``Cycle`` carrying its pinned source context and this resolver registered for ``repo``, as
    the runtime registers it. Bugs caught: the cycle's source commit not reaching the resolver, so
    the snapshot binds another commit, or none; a non-text file bound and refused only at read."""
    repo, clones, _registry = world
    await clones.sync("prj-tally", str(repo.path), "refs/heads/main")
    _commit(repo.path, {"CONTRIBUTING.md": "changed upstream\n"}, "outside")
    await clones.sync("prj-tally", str(repo.path), "refs/heads/main")
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    references = (
        Reference("repo:file:CONTRIBUTING.md@current", True),
        Reference("repo:file:assets/mark.png@current", False),
    )
    instruction = _instruction("mrec_contrib", DESIGN, references=references)
    await records.create(dataclasses.replace(instruction, project_id="prj-tally"))
    context = parse_source_context(recorded("project_source_context", "valid"))
    pinned_source = dataclasses.replace(
        context, project_id="prj-tally", development_baseline_commit=repo.second_commit
    )
    cycle = _framing_cycle(project_id="prj-tally", source_context=pinned_source)

    snapshot = await pin_standalone_cycle(
        store, cycle, now=T0, records=records,
        resolvers={REPOSITORY_FAMILY: create_repository_reference_resolver(clones, _registry)},
    )  # fmt: skip

    [pinned] = snapshot.instructions
    assert [r.ref for r in pinned.references] == [
        f"repo:file:CONTRIBUTING.md@{repo.second_commit}",
        "repo:file:assets/mark.png@current",
    ]
    [(unbound, why)] = pinned.unbound
    assert unbound == "repo:file:assets/mark.png@current" and "not text" in why


@pytest.mark.parametrize(
    ("project_id", "why"),
    [("prj-tally", None), ("group_run", "it is a sample application, with no source repository"),
     ("prj-nowhere", "no Project prj-nowhere is registered")],
    ids=["an-external-product-not-yet-cloned", "a-sample-application", "an-unknown-project"],
)  # fmt: skip
async def test_the_family_binds_nothing_only_where_there_is_no_repository(world, project_id, why):
    """SIP-0110 §5ac, which the records ask at write. Bugs caught: an instruction for a sample
    application accepted, so every unit pins it unbound and a required one holds every task it
    applies to; a registered external product refused because its clone doesn't exist yet."""
    _repo, clones, registry = world  # never synced: no clone on disk
    sample = dataclasses.replace(registry.project, project_id="group_run", source=None)

    class _Projects:
        async def get_project(self, pid):
            held = {"prj-tally": registry.project, "group_run": sample}
            if pid not in held:
                raise ProjectNotFoundError(pid)
            return held[pid]

    resolver = create_repository_reference_resolver(clones, _Projects())

    assert await resolver.binds_nothing_for(project_id) == why
