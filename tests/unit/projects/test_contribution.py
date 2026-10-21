"""A run's verified change, contributed through the product's own process (SIP-0112 FR-06;
E.4.3).

Against the shared fixture's product, through the real managed clone. The product is a local
repository under a configured root, which stands in for the forge's remote. The one stand-in is
the forge, whose pull request is recorded rather than opened. Bugs caught:
- a change pushed or a review request opened that the product's own checks never accepted;
- a second contribution of one run pushing or opening again;
- a token-less or direct-push contribution leaving the deploy;
- a branch the product already holds with other history overwritten.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime

import pytest

from adapters.tools.git_source import GitSourceRepository
from squadops.cycles.models import Project
from squadops.projects.contribution import (
    ContributionRefused,
    capture_ref,
    contribute,
)
from squadops.projects.models import ProjectSource, SourceUnavailable
from squadops.projects.registration import LocatorPolicy
from squadops.projects.workspaces import SourceMapping
from tests.fixtures.shared_contract.repository import build_repository

CYCLE, RUN = "cyc_2407a0000002", "run_src000000001"


class _Registry:
    def __init__(self, project):
        self.project = project
        self.mappings: list[SourceMapping] = []
        self.recorded = []

    async def get_project(self, project_id):
        return self.project

    async def source_mappings(self, project_id, *, workspace_id=None):
        return list(self.mappings)

    async def contributions(self, project_id):
        return list(self.recorded)

    async def record_contribution(self, contribution, *, idempotency_key, request_hash):
        self.recorded.append(contribution)
        return contribution, False


class _Forge:
    def __init__(self):
        self.opened = []

    async def open_review_request(self, **request):
        self.opened.append(request)
        return "https://github.com/owner/tally/pull/7"


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
        created_at=datetime(2026, 10, 18, tzinfo=UTC),
        source=ProjectSource(str(repo.path), "refs/heads/main", "review_request"),
    )
    return repo, clones, _Registry(project), _Forge()


async def _captured(repo, clones, registry):
    """A run's accepted change, as source delivery leaves it: a commit under the run's capture
    ref, and the seeded and captured mappings of its workspace."""
    commit = await clones.sync("prj-tally", str(repo.path), "refs/heads/main")
    tree = await clones.tree_at("prj-tally", commit)
    files = {**tree.files, "tally/report.py": tree.files["tally/report.py"] + b"\n# --json\n"}
    captured = await clones.commit_tree(
        "prj-tally",
        parent=commit,
        files=files,
        executable=tree.executable,
        ref=capture_ref(CYCLE, RUN),
        message=f"SquadOps cycle {CYCLE}: tally/report.py\n\nThe product's own checks: accepted.\n",
    )
    workspace = f"src-{RUN}-0123456789ab"
    registry.mappings += [
        SourceMapping("prj-tally", workspace, "seeded", commit, "a" * 64, "b" * 64, CYCLE),
        SourceMapping("prj-tally", workspace, "captured", captured, "c" * 64, "d" * 64, CYCLE),
    ]
    return commit, captured


async def _contribute(clones, registry, forge, tokens=None):
    return await contribute(
        "prj-tally",
        CYCLE,
        RUN,
        registry=registry,
        repository=clones,
        forge=forge,
        tokens={"prj-tally": "t0ken"} if tokens is None else tokens,
        actor="owner",
        idempotency_key="c-1",
    )


def _branch(repo, name):
    done = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", name], cwd=repo.path, capture_output=True,
        text=True,
    )  # fmt: skip
    return done.stdout.strip() or None


async def test_a_review_request_pushes_the_captured_commit_and_opens_one_request(world):
    repo, clones, registry, forge = world
    parent, captured = await _captured(repo, clones, registry)

    contribution, replayed = await _contribute(clones, registry, forge)
    again, again_replayed = await _contribute(clones, registry, forge)

    assert _branch(repo, f"refs/heads/squadops/{CYCLE}") == captured
    assert [(r["head"], r["base"], r["title"], r["body"], r["token"]) for r in forge.opened] == [
        (
            f"squadops/{CYCLE}",
            "main",
            f"SquadOps cycle {CYCLE}: tally/report.py",
            "The product's own checks: accepted.",
            "t0ken",
        )
    ]
    assert (contribution.commit, contribution.parent_commit, contribution.state) == (
        captured,
        parent,
        "pending",
    )
    assert contribution.review_url == "https://github.com/owner/tally/pull/7"
    assert (replayed, again_replayed, again) == (False, True, contribution)


async def test_a_patch_export_records_the_run_and_nothing_leaves(world):
    repo, clones, registry, forge = world
    registry.project = Project(
        **{
            **registry.project.__dict__,
            "source": ProjectSource(str(repo.path), "refs/heads/main", "patch_export"),
        }
    )
    _, captured = await _captured(repo, clones, registry)

    contribution, _ = await _contribute(clones, registry, forge, tokens={})

    assert (contribution.mode, contribution.commit, contribution.branch) == (
        "patch_export",
        captured,
        None,
    )
    assert forge.opened == [] and _branch(repo, f"refs/heads/squadops/{CYCLE}") is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("uncaptured", "captured no accepted change"),
        ("no-token", "no review-request token for Project prj-tally"),
        ("direct-push", "which is integration"),
        ("tag-base", "targets a branch"),
    ],
)
async def test_what_cannot_be_contributed_is_refused_before_anything_leaves(world, change, message):
    repo, clones, registry, forge = world
    await _captured(repo, clones, registry)
    tokens = None
    if change == "uncaptured":
        registry.mappings = [m for m in registry.mappings if m.direction == "seeded"]
    elif change == "no-token":
        tokens = {}
    else:
        mode, base = (
            ("direct_push", "refs/heads/main") if change == "direct-push" else
            ("review_request", "refs/tags/v1")
        )  # fmt: skip
        registry.project = Project(
            **{**registry.project.__dict__, "source": ProjectSource(str(repo.path), base, mode)}
        )

    with pytest.raises(ContributionRefused, match=message):
        await _contribute(clones, registry, forge, tokens=tokens)

    assert forge.opened == [] and registry.recorded == []
    assert _branch(repo, f"refs/heads/squadops/{CYCLE}") is None


async def test_a_branch_the_product_holds_with_other_history_is_never_overwritten(world):
    repo, clones, registry, forge = world
    await _captured(repo, clones, registry)
    # someone else's commit on the branch name, off the first commit: not an ancestor of ours
    theirs = subprocess.run(
        ["git", "commit-tree", f"{repo.first_commit}^{{tree}}", "-p", repo.first_commit,
         "-m", "theirs"],
        cwd=repo.path, capture_output=True, text=True, check=True,
        env={"GIT_AUTHOR_NAME": "o", "GIT_AUTHOR_EMAIL": "o@example.invalid",
             "GIT_COMMITTER_NAME": "o", "GIT_COMMITTER_EMAIL": "o@example.invalid",
             "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    ).stdout.strip()  # fmt: skip
    subprocess.run(["git", "branch", f"squadops/{CYCLE}", theirs], cwd=repo.path, check=True)

    with pytest.raises(SourceUnavailable, match="git push failed"):
        await _contribute(clones, registry, forge)

    assert _branch(repo, f"refs/heads/squadops/{CYCLE}") == theirs
    assert forge.opened == [] and registry.recorded == []
