"""IR-3 (SIP-0112 §8.4, as amendment H.3 restates it under SIP-0110 §5ad and #2610): a Campaign is
admitted on an external Project with a project instruction citing a repository instruction source,
and an outside commit then changes that source.

Entered where the runtime enters: the Campaign launcher builds each cycle
(``CampaignLaunchService._build_cycle``), a standalone cycle is prepared by ``prepare_cycle`` and
pinned by ``pin_standalone_cycle``, and the drift is read by ``sync_project``. It enters below the
drain: a refused launch leaves the Campaign escalated with its intent pending, and the next cycle
launches after reconciliation and the owner's resume. This shows what each launch binds, not that
escalation and resume. The product is the
shared fixture's Tally, a real repository read through the managed clone, and the references are
bound by the repository family's own resolver.

What bugs would these catch?
- a Campaign's next cycle launched on the evidence an outside instruction change invalidated, or a
  standalone cycle created on it;
- the Campaign's snapshot moved by an upstream change, which only a re-binding may do;
- a cycle already launched re-bound to the new content behind its back;
- a cycle launched after reconciliation still bound to the old content, at the Campaign's admission
  rather than at its own pinned commit;
- a standalone cycle created afterwards bound to anything but the new content.

The re-binding half of IR-3 (a Campaign changes what it bound only as a recorded intervention) is
the re-binding route's: ``tests/unit/api/test_rebinding.py`` (a campaign's row read as an
intervention) and ``tests/unit/memory/test_campaign_cycle_bindings.py``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import subprocess
from datetime import UTC, datetime

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.records import InMemoryMemoryRecords
from adapters.tools.git_source import GitSourceRepository
from adapters.tools.repository_references import RepositoryReferenceResolver
from squadops.api.campaign_launch import LaunchRefused
from squadops.api.cycle_schemas import CycleCreateRequest
from squadops.api.routes.cycles.cycles import prepare_cycle
from squadops.campaigns.launch_requests import start_transition
from squadops.cycles.models import Project, StaleSourcePreconditionError
from squadops.memory.lessons import UnitKind
from squadops.memory.pinning import pin_campaign, pin_standalone_cycle
from squadops.memory.records import Reference
from squadops.projects.baseline import parse_baseline
from squadops.projects.development_configuration import parse_configuration
from squadops.projects.models import ProjectLifecycleStatus, ProjectSource
from squadops.projects.registration import LocatorPolicy
from squadops.projects.sync import sync_project
from tests.fixtures.shared_contract.repository import build_repository, recorded
from tests.unit.api.test_campaign_start import CID, _sandbox_provider, _World  # noqa: F401
from tests.unit.campaigns.builders import campaign, policy
from tests.unit.memory.test_project_instructions import DESIGN, T0, _instruction

pytestmark = [pytest.mark.domain_memory]

PROJECT = "prj-tally"
REF = "repo:file:CONTRIBUTING.md@current"
NOW = datetime(2026, 10, 21, tzinfo=UTC)
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


class _Projects:
    """The registry's record of Tally, as validation, configuration and the baseline capture leave
    it: ``reconcile`` moves all three to a new commit, as those three commands do."""

    def __init__(self, repo_path: str, commit: str) -> None:
        self.repo_path, self.syncs = repo_path, []
        self.configuration = parse_configuration(recorded("development_configuration", "valid"))
        self.reconcile(commit, revision=1)

    def reconcile(self, commit: str, *, revision: int) -> None:
        self.commit, self.revision = commit, revision

    async def get_project(self, project_id):
        return Project(
            project_id=PROJECT, name="Tally", description="", created_at=NOW,
            lifecycle_status=ProjectLifecycleStatus.READY, record_version=self.revision,
            source=ProjectSource(self.repo_path, "refs/heads/main", "review_request"),
            development_configuration_revision=self.revision,
            development_baseline_commit=self.commit, integrated_upstream_commit=self.commit,
        )  # fmt: skip

    async def get_inherited_baseline(self, project_id):
        return parse_baseline(
            {**recorded("inherited_baseline", "valid"), "commit": self.commit,
             "development_configuration_revision": self.revision}
        )  # fmt: skip

    async def get_development_configuration(self, project_id, revision=None):
        return self.configuration

    async def contributions(self, project_id):
        return []

    async def source_syncs(self, project_id):
        return list(self.syncs)

    async def record_sync(self, document, **kwargs):
        self.syncs.append(document)
        return document, False


@pytest.fixture
async def world(tmp_path):
    repo = build_repository(tmp_path / "sources" / "tally")
    clones = GitSourceRepository(
        tmp_path / "cache",
        LocatorPolicy.of([], [str(tmp_path / "sources")]),
        timeout_seconds=60,
        committer_name="SquadOps",
        committer_email="squadops@squadops.invalid",
    )
    await clones.sync(PROJECT, str(repo.path), "refs/heads/main")
    projects = _Projects(str(repo.path), repo.second_commit)
    resolvers = {"repo": RepositoryReferenceResolver(clones, projects)}
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await records.create(
        dataclasses.replace(
            _instruction("mrec_contrib", DESIGN, references=(Reference(REF, True),)),
            project_id=PROJECT,
        )
    )
    w = _World(project_registry=projects)
    w.launch._creation = dataclasses.replace(
        w.launch._creation, memory_store=store, memory_records=records,
        reference_resolvers=resolvers,
    )  # fmt: skip
    admitted = campaign(
        CID, project_id=PROJECT,
        policy=policy(calibration_profile="implementation", squad_profile="full-38"),
    )  # fmt: skip
    await w.campaigns.create_campaign(
        admitted, actor="owner", actor_role="admin", reason="r", idempotency_key="create"
    )
    await pin_campaign(store, admitted, now=T0, records=records, resolvers=resolvers)
    await w.campaigns.transition(
        CID, start_transition(admitted, actor="owner", actor_role="admin", reason="r",
                              idempotency_key="start")
    )  # fmt: skip
    [intent] = await w.campaigns.launch_intents(CID)
    return repo, clones, projects, resolvers, store, records, w, intent


async def _bound_digest(store, cycle_id: str) -> str:
    """The digest a campaign cycle bound its one reference to, at its launch (§5ad)."""
    [instruction] = (await store.get_cycle_binding(cycle_id)).instructions
    [reference] = instruction.references
    return reference.digest


def _digest(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()


async def test_an_outside_instruction_change_holds_new_cycles_and_each_binds_its_own_commit(world):
    repo, clones, projects, resolvers, store, records, w, intent = world
    before = (repo.path / "CONTRIBUTING.md").read_text()
    snapshot = await store.get_snapshot(UnitKind.CAMPAIGN, CID)

    first = await w.launch._build_cycle(intent)
    changed = before + "Every change states which check covers it.\n"
    (repo.path / "CONTRIBUTING.md").write_text(changed)
    _git(repo.path, "commit", "-q", "-am", "an outside instruction change")
    upstream = _git(repo.path, "rev-parse", "HEAD")
    document, _ = await sync_project(
        PROJECT, registry=projects, repository=clones, forge=None, tokens={}, actor="owner",
        idempotency_key="sync-1",
    )  # fmt: skip

    # Until the Project is reconciled, the Campaign's next launch and a standalone cycle are held.
    with pytest.raises(LaunchRefused, match="STALE_SOURCE_PRECONDITION"):
        await w.launch._build_cycle(intent)
    with pytest.raises(StaleSourcePreconditionError, match="with instructions changed"):
        await prepare_cycle(
            w.launch._creation, PROJECT, CycleCreateRequest(squad_profile_id="full-38")
        )
    held_snapshot = await store.get_snapshot(UnitKind.CAMPAIGN, CID)
    held_first = await _bound_digest(store, first.cycle_id)

    projects.reconcile(upstream, revision=2)
    later = await w.launch._build_cycle(intent)
    standalone = await prepare_cycle(
        w.launch._creation, PROJECT, CycleCreateRequest(squad_profile_id="full-38")
    )
    pinned = await pin_standalone_cycle(
        store, standalone.cycle, now=NOW, records=records, resolvers=resolvers
    )

    assert document["drift"]["changed"] == {"instructions": ["CONTRIBUTING.md"]}
    assert document["drift"]["relevant"] == ["instructions"]
    assert held_snapshot == snapshot, "an upstream change moved the Campaign's snapshot"
    assert held_first == _digest(before), "a launched cycle was re-bound behind its back"
    assert first.source_context.development_baseline_commit == repo.second_commit
    assert later.source_context.development_baseline_commit == upstream
    assert await _bound_digest(store, later.cycle_id) == _digest(changed)
    [instruction] = pinned.instructions
    [reference] = instruction.references
    assert reference.digest == _digest(changed)
