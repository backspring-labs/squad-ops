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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.cycles.factory import create_squad_profile_port
from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.tools.git_source import GitSourceRepository
from squadops.api.campaign_launch import CampaignLaunchService
from squadops.api.routes.campaigns import campaigns as campaign_routes
from squadops.campaigns.calibration_record import BINDING_KEY
from squadops.campaigns.campaign_branch import CampaignBranch, campaign_ref
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
from squadops.projects.models import (
    CheckoutTree,
    ProjectLifecycleStatus,
    ProjectSource,
    SourceUnavailable,
)
from squadops.projects.registration import LocatorPolicy
from squadops.projects.workspaces import SEEDED, SourceMapping, capture_inherited_baseline
from tests.fixtures.shared_contract.repository import build_repository, product_files, recorded
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
#: §24bv point 5: the objective's requirements source, a file in the product read at the head.
REQUIREMENTS = "repo:file:README.md@current"


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


class _Clone:
    """The managed clone's one read the start makes (the size preflight, #2889): ``files`` as the
    tree at any commit, or ``refusal`` raised as the read's."""

    def __init__(self, files: dict[str, bytes], refusal: Exception | None = None) -> None:
        self.files, self.refusal = files, refusal

    async def tree_at(self, project_id: str, commit: str) -> CheckoutTree:
        if self.refusal is not None:
            raise self.refusal
        return CheckoutTree(commit, dict(self.files), frozenset(), frozenset(), frozenset())


def _never_assessed(cycle_id: str):
    raise AssertionError(f"a calibration record is never assessed as a cycle ({cycle_id})")


def _progress(world: _World, vault_dir, branch: CampaignBranch | None = None) -> CampaignProgress:
    return CampaignProgress(
        campaigns=world.campaigns,
        cycles=world.cycles,
        vault=FilesystemArtifactVault(vault_dir),
        assess=_never_assessed,
        launch=world.launch.drain,
        evaluate_outcome=None,
        evaluate_baseline=None,
        outcome_section=None,
        intervention_section=None,
        campaign_branch=branch,
        goal_sets=None,
    )


async def _world(
    projects,
    tmp_path,
    campaigns: MemoryCampaignRegistry | None = None,
    branch: CampaignBranch | None = None,
    proposal_profile: str = "campaign-increment-source",
    repository=None,
    squad_profile: str = "full-38",
    squad_profiles=None,
) -> _World:
    """``repository`` is the managed clone the start's size preflight reads (#2889): the fixture's
    product by default. A sample application's world is given none, so a start that reached the
    preflight for it would fail."""
    world = _World(campaigns, project_registry=projects)
    world.progress = _progress(world, tmp_path / "vault", branch)
    world.client.app.state.campaign_progress = world.progress
    world.client.app.state.artifact_vault = FilesystemArtifactVault(tmp_path / "vault")
    world.client.app.state.squad_profile = squad_profiles or create_squad_profile_port("config")
    repository_backed = isinstance(world.projects, _Projects)
    if repository_backed:
        world.client.app.state.source_repository = repository or _Clone(product_files())
    await world.campaigns.create_campaign(
        campaign(
            CID,
            project_id=world.projects.project.project_id if repository_backed else "group_run",
            objective=dataclasses.replace(
                campaign().objective,
                requirements=REQUIREMENTS if repository_backed else None,
            ),
            policy=policy(
                calibration_profile="validated-fullstack",
                squad_profile=squad_profile,
                proposal_profile=proposal_profile,
            ),
        ),
        actor="owner",
        actor_role="admin",
        reason="r",
        idempotency_key="create",
    )
    return world


async def test_a_start_writes_the_record_and_row_5_launches_a_proposal_on_the_branch(tmp_path):
    """§24bv point 1, the wiring: the start route over Tally with its baseline really captured.
    Bugs caught: a repository-backed start that launches a calibration cycle (IR-2's, which fails
    at provisioning for want of a plan); a record that names anything but the capture's commit,
    revision, checks, disclosed gaps and the commit's own tree; an accepted tree that names a cycle,
    or none; a campaign branch (§24bv point 2) not started at the record's commit, so the first
    increment's capture has no head to follow; or a record never decided, so the campaign sits
    calibrating with nothing to end it.
    §24bv point 5: row 5's proposal launches, on the campaign branch, through the launcher's
    drain and ``prepare_cycle``. Bugs caught: the record's proposal escalated as unbuilt; its block
    carrying a manifest or a vault cycle a repository-backed tree has none of, or no basis, so
    every increment seam reads it as no increment; its tree not the record's; its requirements
    source dropped; its cycle not pinned at the head."""
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
    world = await _world(
        projects,
        tmp_path,
        branch=CampaignBranch(projects=projects, repository=clones),
        repository=clones,
    )

    resp = world.start()

    log = await world.campaigns.control_log(CID)
    [start, promote, decide, launched] = [
        e for e in log if e.operation is not ControlOperation.CREATE
    ]
    record = start.binding[BINDING_KEY]
    stored = await world.campaigns.get_campaign(CID)
    assert resp.status_code == 200, resp.json()
    assert [e.operation for e in log] == [
        ControlOperation.CREATE,
        ControlOperation.START,
        ControlOperation.PROMOTE,
        ControlOperation.DECIDE,
        ControlOperation.MARK_LAUNCHED,
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
    assert stored.accepted == AcceptedTree(
        TREE, calibration_record_id=record["record_id"], commit=repo.second_commit
    )
    assert promote.binding["commit"] == repo.second_commit
    # §24bv point 2: the campaign's branch starts at the record's commit.
    assert await clones.ref_commit(PROJECT, campaign_ref(CID)) == repo.second_commit
    assert (decide.target, decide.binding["row"], decide.binding["action"]) == (
        record["record_id"],
        5,
        "propose",
    )
    assert decide.binding["guard"] == "proceed"
    assert "unbuilt" not in decide.binding
    assert stored.state is CampaignState.AT_PROPOSAL
    [intent] = await world.campaigns.launch_intents(CID)
    [cycle] = await world.cycles.list_cycles(PROJECT)
    assert (intent.cycle_id, launched.target) == (cycle.cycle_id, intent.launch_id)
    block = cycle.resolved_config()["campaign_proposal"]
    assert block["basis"] == "campaign_branch"
    assert block["baseline_tree"] == TREE  # bound at drain, the record's tree
    assert not {"baseline_manifest", "accepted_cycle_id"} & set(block)
    assert block["objective"]["requirements"] == REQUIREMENTS
    context = cycle.source_context
    assert (context.pinned_commit, context.pinned_from) == (repo.second_commit, "campaign_branch")
    assert [s[0] for s in world.executor.started] == [cycle.cycle_id]


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
        ControlOperation.MARK_LAUNCHED,  # §24bv point 5: row 5's proposal, launched once
    ]
    assert stored.accepted is not None and stored.accepted.calibration_record_id is not None
    assert stored.state is CampaignState.AT_PROPOSAL


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
    the owner's propose answers as a missing cycle instead of naming why it can't launch; or the
    ledger reading every decision as a cycle's, so its read fails from the campaign's start on.
    Since §24bv point 5 a record's proposal launches, so the escalation is a proposal profile the
    deploy doesn't hold."""
    world = await _world(_recorded_projects(), tmp_path, proposal_profile="no-such-profile")
    # #2889: the start's size preflight refuses a proposal profile it can't load
    # (``test_a_proposal_profile_the_deploy_doesnt_hold_refuses_the_start``); the profile here is
    # one the deploy stopped holding after the preflight read it, so the launch is what fails.
    with patch.object(campaign_routes, "size_preflight", AsyncMock(return_value=())):
        world.start()

    resumed = world.client.post(
        f"/api/v1/campaigns/{CID}/resume",
        json={"reason": "propose", "idempotency_key": "r-1", "action": "propose"},
    )
    ledger = world.client.get(f"/api/v1/campaigns/{CID}/ledger")

    error = resumed.json()["detail"]["error"]
    assert (resumed.status_code, error["code"]) == (422, "VALIDATION_ERROR")
    assert "proposal profile cannot be loaded" in error["message"]
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.ESCALATED
    assert (ledger.status_code, ledger.json()) == (200, [])


async def test_a_sample_applications_start_still_launches_its_calibration_cycle(tmp_path):
    """§11, unchanged by §24bv. Bug caught: a Project with no source taken down the record path,
    so a sample application's campaign builds nothing and proposes on a tree it never built.
    #2889: nor is it measured by the size preflight, which reads a product's tree: its world holds
    no managed clone, so a start that reached the preflight would fail here."""
    world = await _world(None, tmp_path)

    resp = world.start()

    [start] = [
        e for e in await world.campaigns.control_log(CID) if e.operation is ControlOperation.START
    ]
    [cycle_id] = resp.json()["launched_cycles"]
    assert BINDING_KEY not in start.binding
    assert (await world.cycles.get_cycle(cycle_id)).kind == "calibration"
    assert (await world.campaigns.get_campaign(CID)).accepted is None


# --- the size preflight (#2889, SIP-0109 §24db) -------------------------------------------------

#: The squad on the 65,536-token window the 2.5 demonstrations ran on (#2805, #2810).
_TF_SQUAD = "full-38-tf"


def _module(name: str, tokens: int) -> bytes:
    """An invented Python module of about ``tokens`` tokens (four characters each)."""
    line = f"def {name}_total(entries):  # sums the entries of one account\n"
    return (line * (tokens * 4 // len(line) + 1)).encode()


def _product(**packages: int) -> dict[str, bytes]:
    """Each named top-level package, holding four modules of the given total tokens."""
    return {
        f"{package}/part_{i}.py": _module(f"{package}_{i}", tokens // 4)
        for package, tokens in packages.items()
        for i in range(4)
    }


async def test_a_product_larger_than_the_window_whose_tasks_fit_starts_unaffected(tmp_path, caplog):
    """The wiring for a product that fits (#2889), entered at the start route on the window #2805
    and #2810 were found on: about 92,000 tokens of product in four packages beside Tally's own
    small ones, larger than the 65,536-token window and inside 2.4's 384 KB limit. Every task the Campaign dispatches is
    measured and fits, as #2807 and #2812 made it, so the start writes its record as it did.
    Bugs caught: a preflight that counts the whole tree for a task that is shown a part of it
    (the #2805 and #2810 class), refusing a product that fits; or one that measures nothing (no
    binding logged) and passes every product."""
    files = {
        **product_files(),
        **_product(ledger=23_000, notify=23_000, parse=23_000, server=23_000),
    }
    world = await _world(
        _recorded_projects(), tmp_path, repository=_Clone(files), squad_profile=_TF_SQUAD
    )

    with caplog.at_level("INFO", logger="squadops.execution.size_preflight"):
        resp = world.start()

    measured = {r.args[1] for r in caplog.records if r.msg.startswith("size_preflight")}
    assert resp.status_code == 200, resp.json()
    assert {"qa.test", "development.develop", "development.correction_repair"} <= measured
    assert BINDING_KEY in (await world.campaigns.control_log(CID))[1].binding


@pytest.mark.parametrize(
    "package_tokens",
    [90_000, 40_000],
    ids=["past-the-window", "inside-the-window-but-not-with-its-reserve"],
)
async def test_a_task_that_cant_fit_on_the_product_is_a_blocking_gap_named_before_anything(
    tmp_path, package_tokens
):
    """A product whose source is one package: every plan's ``qa.test`` is shown that package
    (``package_scoped``). At about 90,000 tokens it is past the 65,536-token window; at about
    40,000 the prompt (about 59,000 tokens, its JSON escapes counted) is inside it, but not with
    the 12,288 tokens its completion reserves. The start is refused (409) as a
    ``prompt_over_window`` blocking gap naming the binding, its size and its window, and nothing is
    written. Bugs caught: the preflight not wired to the start, so
    the Campaign learns it an hour into its first increment as #2805 did; the reserve left out of
    the fit; a refusal that names no task type or size; or one that writes the start and leaves
    the Campaign calibrating."""
    files = {
        **{p: c for p, c in product_files().items() if not p.endswith(".py")},
        **_product(app=package_tokens),
    }
    world = await _world(
        _recorded_projects(), tmp_path, repository=_Clone(files), squad_profile=_TF_SQUAD
    )

    resp = world.start()

    error = resp.json()["detail"]["error"]
    over = {b["task_type"]: b for b in error["details"]["bindings"]}
    log = await world.campaigns.control_log(CID)
    assert (resp.status_code, error["code"]) == (409, "CALIBRATION_REFUSED")
    assert (error["details"]["cause"], error["details"]["gaps"]) == (
        "blocking_gap",
        ["prompt_over_window"],
    )
    qa = over["qa.test"]
    assert (qa["role"], qa["model"], qa["window"]) == ("qa", "qwen3.8-27b-tf-nvfp4", 65_536)
    assert qa["prompt_tokens"] + qa["completion_reserve"] > 65_536
    assert qa["prompt_tokens"] > package_tokens  # the package, shown whole
    assert (
        f"qa.test (qa, on qwen3.8-27b-tf-nvfp4): its prompt is {qa['prompt_tokens']}"
        in (error["message"])
    )
    assert [e.operation for e in log] == [ControlOperation.CREATE]
    assert await world.campaigns.launch_intents(CID) == []


class _Squads:
    """The squad profile port, serving ``full-38-tf`` with its qa agent on ``model``."""

    def __init__(self, model: str | None) -> None:
        self.model = model

    async def get_profile(self, profile_id):
        profile = await create_squad_profile_port("config").get_profile(_TF_SQUAD)
        agents = [
            dataclasses.replace(a, model=self.model) if a.agent_id == "eve" else a
            for a in profile.agents
        ]
        return dataclasses.replace(profile, agents=type(profile.agents)(agents))


@pytest.mark.parametrize(
    ("squads", "repository", "proposal_profile", "named"),
    [
        (_Squads("a-model-nobody-registered"), None, "campaign-increment-source", "qa.test (qa"),
        (_Squads(None), None, "campaign-increment-source", "on no model"),
        (
            None,
            _Clone({**product_files(), **_product(app=120_000)}),
            "campaign-increment-source",
            "(too_large): 477 KB of source and config, past the 384 KB",
        ),
        (
            None,
            _Clone({}, SourceUnavailable("the clone timed out reading it", reason="timeout")),
            "campaign-increment-source",
            "(timeout): the clone timed out reading it",
        ),
        (None, None, "no-such-profile", "can't load proposal profile 'no-such-profile'"),
    ],
    ids=[
        "window-unknown",
        "no-model",
        "tree-too-large-to-read",
        "tree-unreadable",
        "proposal-profile-not-held",
    ],
)
async def test_a_size_nobody_could_measure_refuses_the_start(
    tmp_path, squads, repository, proposal_profile, named
):
    """Require, don't default (#2889): a binding whose model has no window the registry knows, or
    no model at all; a tree too large to read (past 2.4's limit, ``CheckoutTooLarge``) or one the
    clone can't read; a proposal profile the deploy doesn't hold.
    Each refuses the start (409 ``size_unmeasured``) naming what, and writes nothing. Bugs caught:
    an unknown window or an unread tree read as fitting, so the Campaign starts on a size nobody
    measured; or a crash (500) where the owner is owed a reason."""
    world = await _world(
        _recorded_projects(),
        tmp_path,
        repository=repository,
        squad_profile=_TF_SQUAD,
        squad_profiles=squads,
        proposal_profile=proposal_profile,
    )

    resp = world.start()

    error = resp.json()["detail"]["error"]
    assert (resp.status_code, error["details"]["cause"]) == (409, "size_unmeasured")
    assert named in error["message"]
    assert [e.operation for e in await world.campaigns.control_log(CID)] == [
        ControlOperation.CREATE
    ]
