"""A repository-backed Project's Campaign calibrates by a record, not a cycle (SIP-0109 §24bv point
1, §24cc; SIP-0112 H.4 point 4, H.6).

Entered at ``POST /api/v1/campaigns/{id}/start``, through the real launch service and the real
completion path (``CampaignProgress``) over the memory campaign and cycle registries. The Project
is the shared fixture's Tally:
- for the wiring test, its baseline really captured: the real managed clone
  (``GitSourceRepository``) and the real workspace store, its checks run as local processes by
  ``test_workspaces``' sandbox stand-in, and what the capture records kept by a registry that
  holds it;
- for the refusals and the re-hearing, the records the fixture recorded, each changed only where a
  case says.

A sample application's Campaign is entered the same way, and still launches its calibration cycle.
"""

from __future__ import annotations

import dataclasses
import re
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.tools.git_source import GitSourceRepository
from squadops.api.campaign_launch import CampaignLaunchService
from squadops.campaigns.calibration_record import BINDING_KEY
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    ControlOperation,
    ControlOutcome,
)
from squadops.campaigns.progress import CampaignProgress
from squadops.cycles.models import (
    DerivedProfileNotFoundError,
    InheritedBaselineNotFoundError,
    Project,
)
from squadops.projects.baseline import parse_baseline
from squadops.projects.derived_profile import BLOCKING, Gap, parse_profile
from squadops.projects.development_configuration import parse_configuration
from squadops.projects.models import ProjectLifecycleStatus, ProjectSource
from squadops.projects.registration import LocatorPolicy
from squadops.projects.workspaces import SEEDED, SourceMapping, capture_inherited_baseline
from tests.fixtures.shared_contract.repository import build_repository, recorded
from tests.unit.api.test_campaign_start import _World
from tests.unit.campaigns.builders import campaign, policy, quiet_box
from tests.unit.projects.test_workspaces import _LocalSandbox

pytestmark = pytest.mark.auth

CID = "cmp_start0000001"
PROJECT = "prj-tally"
CONTEXT = recorded("project_source_context", "valid")
COMMIT = CONTEXT["development_baseline_commit"]
#: The fixture's own record of the tree at the baseline commit (contract 4), an oracle independent
#: of the code under test.
TREE = next(
    e["tree_identity"]
    for e in recorded("workspace_commit_mapping", "valid")["entries"]
    if e["commit"] == COMMIT
)


@pytest.fixture(autouse=True)
def _sandbox_provider(monkeypatch):
    """#1568: the create-time sandbox preflight reads the provider from the process env."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


class _Projects:
    """The project registry's reads a start makes, over real records: the Project, its syncs, and
    what its baseline capture recorded (a capture writes through ``record_*`` here)."""

    def __init__(self, project: Project, configuration) -> None:
        self.project, self.configuration = project, configuration
        self.mappings: list[SourceMapping] = []
        self.baseline = None
        self.profile = None
        self.syncs: list[dict] = []

    async def list_projects(self):
        return [self.project]

    async def get_project(self, project_id):
        assert project_id == self.project.project_id
        return self.project

    async def get_development_configuration(self, project_id, revision=None):
        return self.configuration

    async def record_source_mapping(self, mapping):
        self.mappings.append(mapping)

    async def source_mappings(self, project_id, *, workspace_id=None):
        return [m for m in self.mappings if workspace_id in (None, m.workspace_id)]

    async def record_inherited_baseline(self, baseline, *, derived_profile=None, **_):
        self.baseline, self.profile = baseline, derived_profile
        return baseline, False

    async def get_inherited_baseline(self, project_id):
        if self.baseline is None:
            raise InheritedBaselineNotFoundError(f"no baseline for {project_id}")
        return self.baseline

    async def get_derived_profile(self, project_id, *, at=None):
        """As the port reads it (SIP-0112 H.8): the latest capture's, or the one at ``at``."""
        held = self.profile
        if held is None or (
            at is not None and (held.commit, held.development_configuration_revision) != at
        ):
            raise DerivedProfileNotFoundError(f"no profile for {project_id} at {at}")
        return held

    async def source_syncs(self, project_id):
        return list(self.syncs)

    async def get_initialization(self, project_id):
        return None


def _tally(repo_uri: str = CONTEXT["repo_uri"], **overrides) -> Project:
    fields = dict(
        project_id=PROJECT,
        name="Tally",
        description="the shared fixture",
        created_at=datetime(2026, 10, 18, tzinfo=UTC),
        lifecycle_status=ProjectLifecycleStatus.READY,
        source=ProjectSource(repo_uri, "refs/heads/main", "review_request"),
        development_configuration_revision=CONTEXT["development_configuration_revision"],
        development_baseline_commit=COMMIT,
    )
    return Project(**{**fields, **overrides})


def _recorded_projects(**project) -> _Projects:
    """Tally as the fixture recorded its capture: the baseline, the profile and the seeded tree."""
    projects = _Projects(
        _tally(**project), parse_configuration(recorded("development_configuration", "valid"))
    )
    projects.baseline = parse_baseline(recorded("inherited_baseline", "valid"))
    projects.profile = parse_profile(recorded("derived_profile", "valid"))
    projects.mappings.append(
        SourceMapping(PROJECT, f"baseline-{PROJECT}-{COMMIT[:12]}", SEEDED, COMMIT, "rev", TREE)
    )
    return projects


def _never_assessed(cycle_id: str):
    raise AssertionError(f"a calibration record is never assessed as a cycle ({cycle_id})")


def _progress(world: _World, vault_dir) -> CampaignProgress:
    return CampaignProgress(
        campaigns=world.campaigns,
        cycles=world.cycles,
        vault=FilesystemArtifactVault(vault_dir),
        assess=_never_assessed,
        launch=world.launch.drain,
        evaluate_outcome=None,
        outcome_section=None,
        intervention_section=None,
    )


async def _world(projects, tmp_path, campaigns: MemoryCampaignRegistry | None = None) -> _World:
    world = _World(campaigns, project_registry=projects)
    world.progress = _progress(world, tmp_path / "vault")
    world.client.app.state.campaign_progress = world.progress
    world.client.app.state.artifact_vault = FilesystemArtifactVault(tmp_path / "vault")
    await world.campaigns.create_campaign(
        campaign(
            CID,
            project_id=world.projects.project.project_id
            if isinstance(world.projects, _Projects)
            else "group_run",
            policy=policy(calibration_profile="validated-fullstack", squad_profile="full-38"),
        ),
        actor="owner",
        actor_role="admin",
        reason="r",
        idempotency_key="create",
    )
    return world


async def test_a_start_writes_the_record_launches_nothing_and_row_5_proposes(tmp_path):
    """§24bv point 1, the wiring: the start route over Tally with its baseline really captured.
    Bugs caught: a repository-backed start that launches a calibration cycle (IR-2's, which fails
    at provisioning for want of a plan); a record that names anything but the capture's commit,
    revision, checks, disclosed gaps and the commit's own tree; an accepted tree that names a cycle,
    or none; or a record never decided, so the campaign sits calibrating with nothing to end it.
    Row 5 proposes, and its launch is the proposal input point 5 has yet to build: it escalates,
    naming it, which is where this lane's half stops."""
    repo = build_repository(tmp_path / "sources" / "tally")
    projects = _Projects(
        _tally(str(repo.path)), parse_configuration(recorded("development_configuration", "valid"))
    )
    clones = GitSourceRepository(
        tmp_path / "cache",
        LocatorPolicy.of([], [str(tmp_path / "sources")]),
        timeout_seconds=60,
        committer_name="SquadOps",
        committer_email="squadops@squadops.invalid",
    )
    await capture_inherited_baseline(
        PROJECT,
        registry=projects,
        repository=clones,
        sandbox=_LocalSandbox(tmp_path / "cycles"),
        actor="owner",
        idempotency_key="b-1",
    )
    world = await _world(projects, tmp_path)

    resp = world.start()

    log = await world.campaigns.control_log(CID)
    [start, promote, decide] = [e for e in log if e.operation is not ControlOperation.CREATE]
    record = start.binding[BINDING_KEY]
    stored = await world.campaigns.get_campaign(CID)
    assert resp.status_code == 200, resp.json()
    assert [e.operation for e in log] == [
        ControlOperation.CREATE,
        ControlOperation.START,
        ControlOperation.PROMOTE,
        ControlOperation.DECIDE,
    ]
    assert (record["commit"], record["development_configuration_revision"]) == (
        repo.second_commit,
        1,
    )
    assert record["tree_identity"] == TREE
    assert [(c["id"], c["result"]) for c in record["baseline"]["checks"]] == [
        (c["id"], c["result"]) for c in recorded("inherited_baseline", "valid")["checks"]
    ]
    assert re.fullmatch(r"[0-9a-f]{64}", record["baseline"]["digest"])
    assert [g["id"] for g in record["disclosed_gaps"]] == [
        "missing_environment",
        "no_test_id_reader",
    ]
    assert stored.accepted == AcceptedTree(TREE, calibration_record_id=record["record_id"])
    assert promote.binding["commit"] == repo.second_commit
    assert (decide.target, decide.binding["row"], decide.binding["action"]) == (
        record["record_id"],
        5,
        "propose",
    )
    assert decide.binding["guard"] == "proceed"
    assert "§24bv point 5" in decide.binding["unbuilt"]
    assert stored.state is CampaignState.ESCALATED
    assert resp.json()["campaign"]["state"] == "escalated"
    assert await world.campaigns.launch_intents(CID) == []
    assert await world.cycles.list_cycles(PROJECT) == []
    assert world.executor.started == []


def _blocking(gap_id: str, paths: tuple[str, ...]) -> Gap:
    return Gap(gap_id, BLOCKING, None, paths, f"{gap_id}, as derived", "what its id names")


def _with_gap(projects: _Projects, gap: Gap) -> None:
    projects.profile = dataclasses.replace(projects.profile, gaps=(*projects.profile.gaps, gap))


def _unreconciled(projects: _Projects) -> None:
    projects.syncs = [
        {
            "baseline_commit": COMMIT,
            "upstream_commit": "f" * 40,
            "drift": {"relevant": ["instructions"], "changed": {"instructions": ["CLAUDE.md"]}},
        }
    ]


def _no_baseline(projects: _Projects) -> None:
    projects.baseline = None


def _baseline_elsewhere(projects: _Projects) -> None:
    projects.baseline = parse_baseline(recorded("inherited_baseline", "stale_commit"))


def _no_tree(projects: _Projects) -> None:
    projects.mappings = []


def _no_profile(projects: _Projects) -> None:
    projects.profile = None


def _stale_profile(projects: _Projects) -> None:
    projects.profile = parse_profile(recorded("derived_profile", "stale_commit"))


@pytest.mark.parametrize(
    ("project", "change", "cause"),
    [
        ({"lifecycle_status": ProjectLifecycleStatus.REGISTERING}, None, "project_not_ready"),
        ({"development_configuration_revision": None}, None, "project_not_ready"),
        ({}, _unreconciled, "drift_unreconciled"),
        ({}, _no_baseline, "no_baseline"),
        ({}, _baseline_elsewhere, "no_baseline"),
        ({}, _no_tree, "no_baseline"),
        ({}, _no_profile, "no_profile"),
        # H.8: a profile of another commit is none at the pin, never read in its place.
        ({}, _stale_profile, "no_profile"),
        (
            {},
            lambda p: _with_gap(p, _blocking("test_files_unclassed", ("legacy",))),
            "blocking_gap",
        ),
        ({}, lambda p: _with_gap(p, _blocking("no_check_ran", ("**",))), "blocking_gap"),
        (
            {},
            lambda p: _with_gap(p, _blocking("missing_toolchain", ("web",))),
            "blocking_gap",
        ),
    ],
    ids=[
        "registering",
        "unconfigured",
        "drift-unreconciled",
        "never-captured",
        "captured-at-another-commit",
        "no-tree-at-the-commit",
        "no-profile",
        "a-profile-of-another-commit",
        "test-files-unclassed",
        "no-check-ran",
        "toolchain-missing",
    ],
)
async def test_a_start_that_cant_write_its_record_is_refused_and_writes_nothing(
    tmp_path, project, change, cause
):
    """§24bv point 1, §24cc, SIP-0112 H.6: each cause refuses the start (409, naming it), and
    nothing is written: no start row, no record, no launch and no cycle, so ``prepare_cycle``'s
    own blocking-gap refusal (SIP-0112 H.8) is never reached and the start is refused once. Bugs
    caught: a cause missed, so a Campaign calibrates on drift nobody reconciled, on a baseline of
    another commit, on a profile of another tree (read in place of none at the pin), or past a
    blocking gap, including ``test_files_unclassed``, which H.6 makes a stop for a Campaign and not
    only for its feature and fix increments; or a refusal that writes the start and leaves the
    campaign calibrating."""
    projects = _recorded_projects(**project)
    if change is not None:
        change(projects)
    world = await _world(projects, tmp_path)

    resp = world.start()

    error = resp.json()["detail"]["error"]
    log = await world.campaigns.control_log(CID)
    assert (resp.status_code, error["code"]) == (409, "CALIBRATION_REFUSED")
    assert error["details"]["cause"] == cause
    assert [e.operation for e in log] == [ControlOperation.CREATE]
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.DRAFT
    assert await world.campaigns.launch_intents(CID) == []
    assert await world.cycles.list_cycles(PROJECT) == []


async def test_a_blocking_gaps_refusal_names_each_gap(tmp_path):
    """H.6: what would close it is the owner's to act on. Bug caught: a refusal naming only that
    a gap stands, so the owner can't tell which of the product's parts to fix."""
    projects = _recorded_projects()
    _with_gap(projects, _blocking("test_files_unclassed", ("legacy",)))
    _with_gap(projects, _blocking("no_check_ran", ("**",)))
    world = await _world(projects, tmp_path)

    error = world.start().json()["detail"]["error"]

    assert error["details"]["gaps"] == ["test_files_unclassed", "no_check_ran"]
    assert "closes by what its id names" in error["message"]


class _DiesBefore(MemoryCampaignRegistry):
    """The process dies before ``operation``'s first write commits."""

    def __init__(self, operation: ControlOperation) -> None:
        super().__init__()
        self.operation, self.died = operation, False

    async def transition(self, campaign_id, transition):
        if transition.operation is self.operation and not self.died:
            self.died = True
            raise ConnectionError("the process died here")
        return await super().transition(campaign_id, transition)


@pytest.mark.parametrize(
    "dies_before", [ControlOperation.PROMOTE, ControlOperation.DECIDE], ids=["promote", "decide"]
)
async def test_a_record_a_restart_left_undecided_is_heard_once_at_startup(tmp_path, dies_before):
    """§12a for a record (§24cc), entered at ``main._resume_campaigns``, the startup the runtime
    runs. The start committed its record, and the process died before its promotion, or between
    its promotion and its decision. Bugs caught: the campaign left calibrating with no cycle to
    end and nothing to hear it; a second promotion row, or a promotion refused as a conflicting
    key so the decision is never written; or a decision written twice by a second restart."""
    from squadops.api.runtime.main import _resume_campaigns

    world = await _world(_recorded_projects(), tmp_path, campaigns=_DiesBefore(dies_before))
    with pytest.raises(ConnectionError):
        world.start()
    restarted = CampaignLaunchService(
        campaigns=world.campaigns,
        creation=world.launch._creation,
        flow_executor=world.executor,
        event_bus=MagicMock(),
        box_verdict=quiet_box,
    )
    state = SimpleNamespace(
        campaign_launch=restarted, campaign_progress=_progress(world, tmp_path / "vault")
    )

    await _resume_campaigns(state)
    await _resume_campaigns(state)

    applied = [
        e.operation
        for e in await world.campaigns.control_log(CID)
        if e.outcome is ControlOutcome.APPLIED
    ]
    stored = await world.campaigns.get_campaign(CID)
    assert applied == [
        ControlOperation.CREATE,
        ControlOperation.START,
        ControlOperation.PROMOTE,
        ControlOperation.DECIDE,
    ]
    assert stored.accepted is not None and stored.accepted.calibration_record_id is not None
    assert stored.state is CampaignState.ESCALATED


async def test_a_record_campaigns_package_reads_its_record(tmp_path):
    """§14, §24cc: the abort closes the campaign and materializes its package from the records.
    Bugs caught: the digest reading every promotion as a cycle's (a ``cycle_id`` key error), so a
    repository-backed campaign's package is never written; or the record's promotion read as a
    partial one because it has no vault tree, so its safety guarantees never all hold."""
    world = await _world(_recorded_projects(), tmp_path)
    world.start()

    world.client.post(
        f"/api/v1/campaigns/{CID}/abort", json={"reason": "the read", "idempotency_key": "a-1"}
    )
    digest = world.client.get(f"/api/v1/campaigns/{CID}/package").json()["digest"]

    [start] = [
        e for e in await world.campaigns.control_log(CID) if e.operation is ControlOperation.START
    ]
    record_id = start.binding[BINDING_KEY]["record_id"]
    assert f"- calibration record `{record_id}`: commit `{COMMIT[:12]}`" in digest
    assert "- held: no partial promotion" in digest


async def test_the_owners_word_and_the_ledger_read_a_records_decision(tmp_path):
    """§10's owner's word and §9.4's ledger after a record's decision escalated (§24cc). Bugs
    caught: the resume looking the record's id up as a cycle (the latest decision's target), so
    the owner's propose answers as a missing cycle instead of naming what isn't built; or the
    ledger reading every decision as a cycle's, so its read fails from the campaign's start on."""
    world = await _world(_recorded_projects(), tmp_path)
    world.start()

    resumed = world.client.post(
        f"/api/v1/campaigns/{CID}/resume",
        json={"reason": "propose", "idempotency_key": "r-1", "action": "propose"},
    )
    ledger = world.client.get(f"/api/v1/campaigns/{CID}/ledger")

    error = resumed.json()["detail"]["error"]
    assert (resumed.status_code, error["code"]) == (422, "VALIDATION_ERROR")
    assert "§24bv point 5" in error["message"]
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.ESCALATED
    assert (ledger.status_code, ledger.json()) == (200, [])


async def test_a_sample_applications_start_still_launches_its_calibration_cycle(tmp_path):
    """§11, unchanged by §24bv. Bug caught: a Project with no source taken down the record path,
    so a sample application's campaign builds nothing and proposes on a tree it never built."""
    world = await _world(None, tmp_path)

    resp = world.start()

    [start] = [
        e for e in await world.campaigns.control_log(CID) if e.operation is ControlOperation.START
    ]
    [cycle_id] = resp.json()["launched_cycles"]
    assert BINDING_KEY not in start.binding
    assert (await world.cycles.get_cycle(cycle_id)).kind == "calibration"
    assert (await world.campaigns.get_campaign(CID)).accepted is None
