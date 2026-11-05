"""A Campaign that closes with an accepted increment opens one contribution to the product
(SIP-0109 §24dc, #2861).

Entered where the live loop closes a Campaign: its terminal decision at
``CampaignProgress.cycle_ended`` (the completion boundary's call), and the owner's
``POST /api/v1/campaigns/{id}/abort``. Over ``test_campaign_branch``'s world: the shared fixture's
Tally, a real managed clone, real deliveries. The product the contribution is pushed to is the
fixture's own repository, the Project's locator. The forge is a recorder, and the token invented.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import time
from fnmatch import fnmatch
from pathlib import PurePosixPath

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.factory import create_project_registry
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.campaigns import campaigns_router
from squadops.api.routes.cycles.projects import router as projects_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.calibration_record import record_for
from squadops.campaigns.close_contribution import (
    NO_ACCEPTED_INCREMENT,
    CampaignContribution,
    accepted_on_branch,
    closing_binding,
    closing_row,
)
from squadops.campaigns.increment_tree import INCREMENT_EVALUATION_ARTIFACT_TYPE
from squadops.campaigns.launch_requests import start_transition
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignOutcome,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
    CycleKind,
    LaunchIntent,
    LaunchIntentState,
    LaunchRequest,
)
from squadops.campaigns.progress import CampaignProgress
from squadops.cycles.cycle_end import CycleStopReason
from squadops.cycles.models import Cycle, Project, Run, TaskFlowPolicy
from squadops.execution.source_delivery import deliver_source_change
from squadops.ports.projects.review_request import ReviewRequestFailed
from squadops.projects.contribution import (
    CAMPAIGN_RUN,
    ContributionRefused,
    campaign_contribution_ref,
    contribute_campaign,
    relocated_criterion_files,
)
from squadops.projects.derived_profile import parse_profile
from squadops.projects.source_context import parse_source_context
from squadops.projects.workspaces import capture_inherited_baseline
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import WorkspaceStore
from tests.fixtures.goal_set import GoalSetStore
from tests.fixtures.shared_contract.repository import _git, recorded, tracked_files
from tests.unit.api.test_campaign_calibration_record import PROJECT
from tests.unit.campaigns.builders import T0, campaign, move, policy
from tests.unit.campaigns.test_branch_rebase import _with_pytest_runner
from tests.unit.campaigns.test_campaign_branch import CID, NOW, REPORT, _added
from tests.unit.campaigns.test_campaign_branch import _World as _BranchWorld
from tests.unit.campaigns.test_runner_acceptance_sandbox import _ReadingBackend
from tests.unit.projects.test_workspaces import _LocalSandbox

TOKEN = "github_pat_inventedForTheTest0002"
BRANCH = f"squadops/{CID}"
URL = "https://forge.example.invalid/tally/pull/9"
CRITERION = "test_criterion_T1.py"
LIVE = "cmp_b498332d326e028682987379"


def _tag(campaign_id: str) -> str:
    """What a Campaign's id reads as in a file name, computed here apart from the code's."""
    return "campaign_" + hashlib.sha256(campaign_id.encode()).hexdigest()[:16]


MOVED = f"tests/test_{_tag(CID)}_T1.py"


@pytest.fixture(autouse=True)
def _sandbox_provider(monkeypatch):
    """#1568: the create-time sandbox preflight reads the provider from the process env."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


class _Forge:
    """The review-request port, recorded: an open request of one head against one base is
    returned rather than opened again, as the port's contract says. ``refuse`` makes it answer
    as a forge that refused."""

    def __init__(self, *, refuse: bool = False) -> None:
        self.opened: list[dict] = []
        self.calls = 0
        self.refuse = refuse

    async def open_review_request(self, **request) -> str:
        self.calls += 1
        if self.refuse:
            raise ReviewRequestFailed("the forge answered 503")
        if not self.opened:
            self.opened.append(request)
        return URL


class _Contributions:
    """The project registry's contributions, as the Postgres registry keeps them: one per
    (cycle, run), a second record answered with the first."""

    def __init__(self) -> None:
        self.recorded: list = []

    async def contributions(self, project_id):
        return list(self.recorded)

    async def record_contribution(self, contribution, *, idempotency_key, request_hash):
        for held in self.recorded:
            if (held.cycle_id, held.run_id) == (contribution.cycle_id, contribution.run_id):
                return held, True
        self.recorded.append(contribution)
        return contribution, False


class _World(_BranchWorld):
    """A Campaign on Tally whose first accepted increment meets its objective, so that
    increment's decision closes it; its contribution opened as ``main`` wires it."""

    def __init__(self, tmp_path) -> None:
        self.forge = _Forge()
        self.book = _Contributions()
        self.goal_sets = GoalSetStore()
        super().__init__(tmp_path)
        # No identity from the host: git's guess from the box's hostname works here and exits 128
        # on CI's runner, so every commit these tests make names its own.
        _git(self.repo.path, "config", "user.useConfigOnly", "true")
        self.projects.contributions = self.book.contributions
        self.projects.record_contribution = self.book.record_contribution
        store = WorkspaceStore(tmp_path / "reading-sandbox")
        self.reading_sandbox = SandboxService(
            store=store,
            journal=OperationEvidenceJournal(tmp_path / "reading-sandbox"),
            backend=_ReadingBackend(store),
        )
        self.contribution = self.contributing(sandbox=self.reading_sandbox)

    def contributing(self, *, sandbox) -> CampaignContribution:
        """The service as ``main`` wires it."""
        return CampaignContribution(
            campaigns=self.campaigns,
            projects=self.projects,
            repository=self.clones,
            forge=self.forge,
            sandbox=sandbox,
        )

    def progress_on(self, repository) -> CampaignProgress:
        progress = super().progress_on(repository)
        return CampaignProgress(
            campaigns=self.campaigns,
            cycles=self.cycles,
            vault=self.vault,
            assess=self._assess,
            launch=progress._launch,
            evaluate_outcome=None,
            evaluate_baseline=None,
            outcome_section=None,
            intervention_section=None,
            campaign_branch=progress._campaign_branch,
            goal_sets=self.goal_sets,
        )

    async def started(self, *, target: int = 1) -> None:
        """As ``test_campaign_branch``'s start, with the objective met by ``target`` accepted
        increments."""
        await capture_inherited_baseline(
            PROJECT,
            registry=self.projects,
            repository=self.clones,
            sandbox=_LocalSandbox(self.tmp_path / "baseline"),
            actor="owner",
            idempotency_key="b-1",
        )
        base = campaign(CID)
        draft = campaign(
            CID,
            project_id=PROJECT,
            objective=dataclasses.replace(base.objective, target_accepted_increments=target),
            policy=policy(
                calibration_profile="validated-fullstack",
                squad_profile="full-38",
                proposal_profile="no-such-profile",
            ),
        )
        await self.campaigns.create_campaign(
            draft, actor="owner", actor_role="admin", reason="r", idempotency_key="create"
        )
        record = await record_for(self.projects, self.projects.project, campaign_id=CID)
        await self.campaigns.transition(
            CID,
            start_transition(
                draft,
                actor="owner",
                actor_role="admin",
                reason="go",
                idempotency_key="start",
                record=record,
            ),
        )
        await self.progress.calibration_recorded(CID)
        self.runner_rooted_at(".")

    def runner_rooted_at(self, *roots: str) -> None:
        """The derived profile at the pin, with a pytest runner under ``roots`` beside Tally's
        unittest one, reading its tests by id."""
        held = self.projects.profile
        document = _with_pytest_runner(recorded("derived_profile", "valid"))
        document["test_runners"][-1]["roots"] = list(roots)
        document["commit"] = held.commit
        document["development_configuration_revision"] = held.development_configuration_revision
        self.projects.profile = parse_profile(document)

    async def accepted_with_criterion(
        self,
        cycle_id: str = "cyc_inc000000001",
        *,
        criterion: bytes = b"def test_t1():\n    pass\n",
        beside: dict[str, bytes] | None = None,
    ) -> str:
        """An increment that adds a function to the report module and its criterion's own test
        file at the product's root, as campaign 4's were placed: delivered for real, its
        evaluation freezing the criterion at that path. Its end is heard. Returns its capture."""
        result = await self.campaigns.transition(
            CID,
            move(
                CampaignState.BUILDING,
                f"launch-{cycle_id}",
                operation=ControlOperation.RESUME,
                launch=LaunchRequest(CycleKind.INCREMENT, {}),
            ),
        )
        await self.campaigns.mark_launch_intent_launched(
            result.intent.launch_id, cycle_id, actor="launcher"
        )
        context = parse_source_context(recorded("project_source_context", "valid"))
        cycle = Cycle(
            cycle_id=cycle_id,
            project_id=PROJECT,
            created_at=NOW,
            created_by="campaign-launcher",
            prd_ref=None,
            squad_profile_id="full-38",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            source_context=dataclasses.replace(context, repo_uri=str(self.repo.path)),
            campaign_id=CID,
            kind="increment",
        )
        run = Run(
            run_id=f"run_{cycle_id.removeprefix('cyc_')}",
            cycle_id=cycle_id,
            run_number=1,
            status="completed",
            initiated_by="system",
            resolved_config_hash="cfg",
            workload_type="implementation",
        )
        await self.cycles.create_cycle(cycle)
        await self.cycles.create_run(run)
        original = tracked_files(self.repo.path, self.repo.second_commit)[REPORT]
        emitted = [
            await self._stored(cycle, run, REPORT, "source", original + _added("total")),
            await self._stored(cycle, run, CRITERION, "source", criterion),
            *[await self._stored(cycle, run, p, "source", c) for p, c in (beside or {}).items()],
        ]
        delivery = await deliver_source_change(
            cycle,
            run.run_id,
            emitted,
            vault=self.vault,
            registry=self.projects,
            repository=self.clones,
            sandbox=self.sandbox,
        )
        assert delivery.captured_commit is not None, delivery.verification.to_document()
        bundle = {"address": "addr-T1", "test_path": CRITERION, "files": {}, "invocation": []}
        evaluation = {"verdict": "accepted", "new_bundles": {"T1": bundle}}
        await self._stored(
            cycle,
            run,
            "increment_evaluation.json",
            INCREMENT_EVALUATION_ARTIFACT_TYPE,
            json.dumps(evaluation).encode(),
        )
        await self.progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)
        return delivery.captured_commit

    def remote(self) -> str | None:
        listed = _git(self.repo.path, "branch", "--list", BRANCH).strip()
        return _git(self.repo.path, "rev-parse", f"refs/heads/{BRANCH}").strip() if listed else None

    async def closing(self) -> ControlLogEntry:
        row = closing_row(await self.campaigns.control_log(CID))
        assert row is not None
        return row

    async def failures(self) -> list[ControlLogEntry]:
        return [
            e
            for e in await self.campaigns.control_log(CID)
            if e.operation is ControlOperation.CONTRIBUTION_FAILED
        ]

    def client(self, role: str = Role.CAMPAIGN_SUPERVISOR) -> TestClient:
        """The campaign routes, as the runtime mounts them, for the supervisor's seat, or
        ``role``'s."""
        user = "supervisor" if role == Role.CAMPAIGN_SUPERVISOR else str(role)
        app = FastAPI()

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = Identity(
                    user_id=user,
                    display_name=user,
                    roles=(role,),
                    scopes=tuple(sorted(scopes_for_roles((role,)))),
                    identity_type=IdentityType.HUMAN,
                )
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(campaigns_router)
        app.include_router(projects_router)
        register_domain_error_handlers(app)
        app.state.goal_set_registry = self.goal_sets
        app.state.campaign_registry = self.campaigns
        app.state.cycle_registry = self.cycles
        app.state.project_registry = self.projects
        app.state.source_repository = self.clones
        app.state.review_requests = self.forge
        app.state.campaign_progress = self.progress
        app.state.campaign_contribution = self.contribution
        app.state.authz_port = KeycloakAuthzAdapter()
        return TestClient(app)


@pytest.mark.parametrize(
    ("placed", "moved"),
    [
        # campaign 4's root files: moved under tests/, out of the stem
        ("test_criterion_T1.py", f"tests/test_{_tag(LIVE)}_T1.py"),
        # placed beside the runner's tests (#2858): renamed where it stands
        ("tests/test_criterion_T2.py", f"tests/test_{_tag(LIVE)}_T2.py"),
        # a vitest runner's pattern has no prefix
        ("frontend/src/criterion_T3.test.jsx", f"frontend/src/{_tag(LIVE)}_T3.test.jsx"),
    ],
)
def test_a_criterion_file_leaves_the_stem_and_the_root(placed, moved):
    """#2860's interim, made the rule. Bugs caught: a root file left at the root, where a later
    placement under ``tests/`` breaks pytest's collection (#2858); a name left in the stem, which
    §24cx then refuses to every later Campaign's criterion of that id; the runner's own prefix
    dropped, so the runner no longer collects the file."""
    assert relocated_criterion_files([placed], LIVE) == {placed: moved}


def test_two_campaigns_never_take_one_name_and_each_name_is_a_valid_test_module():
    """PR #2920's review, finding 5. ``cmp_product_feature_a`` and ``_b`` shared 16 characters, so
    the second Campaign's file took the first's name, and pytest refuses two modules of one name
    (#2858). Bugs caught: a truncated id; an id's ``-`` reaching a module name, which no import
    can name; the runner's own patterns no longer matching."""
    ids = ("cmp_product_feature_a", "cmp_product_feature_b", "cmp-product-feature-a")
    moved = [
        relocated_criterion_files(["test_criterion_T1.py", "criterion_T1.test.jsx"], i) for i in ids
    ]

    python = [m["test_criterion_T1.py"] for m in moved]
    assert len(set(python)) == len(ids)
    for path in python:
        name = PurePosixPath(path)
        assert name.stem.isidentifier() and fnmatch(name.name, "test_*.py")
        assert "criterion_" not in name.name
    for m in moved:
        assert fnmatch(m["criterion_T1.test.jsx"], "*.test.*")


def test_a_file_outside_the_stem_is_left_where_it_is():
    """Bug caught: a product test file the Campaign changed renamed as if it were a criterion's."""
    assert relocated_criterion_files(["tests/test_report.py", "README.md"], "cmp_x") == {}


@pytest.mark.parametrize("close", ["decision", "abort"])
async def test_the_close_records_what_is_due_and_acts_on_nothing_outside(tmp_path, close):
    """The owner's ruling of 2026-11-04, keeping §24ci (b): a close never pushes or opens a request,
    even on a deploy that holds a token for the Project (``app.state.review_request_tokens``, the
    run contribution's fallback). Entered at the completion boundary and at the abort route. Bugs
    caught: an automatic open returning; a stored token read on this path; a failure row written
    for a token nobody was asked for; the closing row silent about what is due."""
    world = _World(tmp_path)
    await world.started(target=1 if close == "decision" else 2)
    client = world.client()
    client.app.state.review_request_tokens = {PROJECT: TOKEN}

    await world.accepted_with_criterion()
    if close == "abort":
        aborted = client.post(
            f"/api/v1/campaigns/{CID}/abort", json={"reason": "stop", "idempotency_key": "a-1"}
        )
        assert aborted.status_code == 200, aborted.text

    closing = await world.closing()
    held = await world.clones.ref_commit(PROJECT, campaign_contribution_ref(CID))
    assert closing.binding["contribution"] == {"due": True, "accepted": ["cyc_inc000000001"]}
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.COMPLETED
    assert world.forge.calls == 0 and world.remote() is None and held is None
    assert world.book.recorded == [] and await world.failures() == []


async def test_the_supervisors_request_opens_one_contribution_with_its_criteria_moved(
    tmp_path, caplog
):
    """The wiring: the increment's decision closes the Campaign at the completion boundary, and
    ``POST …/contributions`` with the supervisor's token opens what the close said was due. Bugs
    caught:
    - the root criterion file contributed as it was placed, where the next Campaign's placement
      collides with it (#2860);
    - the commit pushed or recorded off the branch's head, or its base wrong, so a sync reads the
      Campaign's change against the wrong commit;
    - a second request opened, or the token stored, returned or logged."""
    caplog.set_level(logging.DEBUG)
    world = _World(tmp_path)
    await world.started()
    captured = await world.accepted_with_criterion()

    opened = world.client().post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})

    assert opened.status_code == 201, opened.text
    [contribution] = world.book.recorded
    pushed = world.remote()
    files = tracked_files(world.repo.path, pushed)
    assert pushed == contribution.commit != captured
    assert _git(world.repo.path, "rev-parse", f"{pushed}^").strip() == captured
    assert CRITERION not in files and files[MOVED] == b"def test_t1():\n    pass\n"
    assert files[REPORT].endswith(_added("total"))
    assert (contribution.campaign_id, contribution.run_id) == (CID, CAMPAIGN_RUN)
    assert (contribution.state, contribution.branch, contribution.review_url) == (
        "pending",
        BRANCH,
        URL,
    )
    assert contribution.contributed_by == "supervisor"
    assert contribution.parent_commit == world.repo.second_commit  # the branch's base
    [request] = world.forge.opened
    assert (request["head"], request["base"], request["token"]) == (BRANCH, "main", TOKEN)
    assert f"- {CRITERION} -> {MOVED}" in request["body"]
    assert "Opened by the campaign's supervisor after its close" in request["body"]
    assert await world.failures() == []
    assert TOKEN not in repr(await world.campaigns.control_log(CID)) + caplog.text + opened.text


#: A criterion that reads a file beside it: at the root it passes, and moved under ``tests/`` the
#: fixture isn't beside it any more (the review's finding 1).
_READS_ITS_SIBLING = b"""from pathlib import Path


def test_t1():
    assert Path(__file__).with_name("seed.json").read_text() == "{}"
"""


async def test_a_criterion_the_move_breaks_opens_nothing_and_says_which(tmp_path):
    """PR #2920's review, finding 1. Moving a root criterion under ``tests/`` changes where it
    runs, so the moved tree is run on the product's runner before anything leaves. Bugs caught:
    the moved tree pushed unverified, so the review request fails on the owner's desk; a failure
    written nowhere; the branch left pushed."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted_with_criterion(criterion=_READS_ITS_SIBLING, beside={"seed.json": b"{}"})

    refused = world.client().post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})

    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["error"]["code"] == "CONTRIBUTION_REFUSED"
    [failure] = await world.failures()
    assert "T1" in failure.binding["message"] and MOVED in failure.binding["message"]
    assert world.forge.calls == 0 and world.remote() is None and world.book.recorded == []


async def test_a_moved_file_no_runner_holds_opens_nothing(tmp_path):
    """The runner's placement requirements hold after the move. The product's runner is rooted at
    ``crit``, so nothing would collect a file under ``tests/``. Bug caught: a criterion contributed
    where the product never runs it, which reads as a green suite."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted_with_criterion()
    world.runner_rooted_at("crit")

    refused = world.client().post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})

    assert refused.status_code == 409, refused.text
    [failure] = await world.failures()
    assert "no runner" in failure.binding["message"] and MOVED in failure.binding["message"]
    assert world.forge.calls == 0 and world.remote() is None


async def test_a_moved_file_another_runner_would_take_opens_nothing(tmp_path):
    """The placement requirement's other half: a runner rooted at ``tests`` takes the file the root
    runner placed. Bug caught: a criterion judged by another runner than the one that accepted it."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted_with_criterion()
    held = world.projects.profile
    document = _with_pytest_runner(recorded("derived_profile", "valid"))
    document["commit"] = held.commit
    document["development_configuration_revision"] = held.development_configuration_revision
    rooted = document["test_runners"][-1]
    document["test_runners"] = [
        document["test_runners"][0],
        {**rooted, "runner": "jest", "roots": ["tests"]},
        {**rooted, "roots": ["."]},
    ]
    world.projects.profile = parse_profile(document)

    refused = world.client().post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})

    assert refused.status_code == 409, refused.text
    assert world.forge.calls == 0 and world.remote() is None


async def test_a_criterion_no_reader_can_read_opens_nothing(tmp_path):
    """Only ``held`` passes: §24ci (a)'s rule. Under a runner with no test-id reader a clean exit
    is ``blocked_unverified``, never evidence. Bug caught: anything short of broken let through."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted_with_criterion()
    held = world.projects.profile
    document = _with_pytest_runner(recorded("derived_profile", "valid"))
    document["commit"] = held.commit
    document["development_configuration_revision"] = held.development_configuration_revision
    document["test_runners"][-1].update(roots=["."], test_ids=None)
    world.projects.profile = parse_profile(document)

    refused = world.client().post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})

    assert refused.status_code == 409, refused.text
    [failure] = await world.failures()
    assert "blocked_unverified" in failure.binding["message"]
    assert world.forge.calls == 0 and world.remote() is None


def test_a_campaign_with_a_branch_is_repository_backed_whatever_the_caller_read():
    """Finding 6's other side. The abort's Project lookup found nothing, and the log says a branch
    exists. Bug caught: accepted work closed with no record of what is due, because of a lookup."""
    log = [
        _row(1, ControlOperation.PROMOTE, {
            "calibration_record_id": "rec", "commit": "c0", "development_configuration_revision": 1,
        }),
        _row(2, ControlOperation.PROMOTE, {"cycle_id": "cyc_a", "commit": "a1"}),
    ]  # fmt: skip
    closing = move(
        CampaignState.COMPLETED, "k", operation=ControlOperation.ABORT,
        outcome=CampaignOutcome.ABORTED, repository_backed=False,
    )  # fmt: skip

    assert closing_binding(closing, log, [_intent("cyc_a", CycleKind.INCREMENT)]) == {
        "contribution": {"due": True, "accepted": ["cyc_a"]}
    }


@pytest.mark.parametrize("missing", ["sandbox", "profile"])
async def test_with_nothing_to_run_them_on_the_moved_criteria_open_nothing(tmp_path, missing):
    """Require, don't default. Bugs caught: no sandbox wired, or no derived profile at the pin,
    read as nothing to verify, so the moved tree leaves unverified."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted_with_criterion()
    if missing == "sandbox":
        world.contribution = world.contributing(sandbox=None)
    else:
        world.projects.profile = None

    refused = world.client().post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})

    assert refused.status_code == 409, refused.text
    [failure] = await world.failures()
    assert missing in failure.binding["message"]
    assert world.forge.calls == 0 and world.remote() is None and world.book.recorded == []


async def test_a_retired_criterion_moves_and_isnt_run(tmp_path):
    """A retired criterion stays on the branch, and may fail by design: a later increment replaced
    what it asserted. Bug caught: it refusing the contribution forever."""
    world = _World(tmp_path)
    await world.started(target=2)
    await world.accepted_with_criterion(criterion=b"def test_t1():\n    assert False\n")
    held = await world.campaigns.get_campaign(CID)
    await world.campaigns.transition(
        CID,
        move(
            held.state, "k-retire", operation=ControlOperation.PROMOTE, accepted=held.accepted,
            binding={"cycle_id": "cyc_inc000000001", "commit": held.accepted.commit,
                     "identity": held.accepted.identity, "retired_criteria": ["T1"]},
        ),
    )  # fmt: skip
    client = world.client()
    client.post(f"/api/v1/campaigns/{CID}/abort", json={"reason": "s", "idempotency_key": "a-r"})

    opened = client.post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})

    assert opened.status_code == 201, opened.text
    assert MOVED in tracked_files(world.repo.path, world.remote())


async def test_a_failed_open_is_recorded_the_campaign_stays_closed_and_the_retry_opens_it(
    tmp_path, monkeypatch
):
    """The owner's abort closes the Campaign; the supervisor's first request meets a forge that
    refuses. Bugs caught:
    - a failure lost: nothing on the Campaign says the contribution wasn't opened;
    - a failure that reopens or unwinds the close;
    - a retry that pushes a second commit, so the branch the first attempt left is refused as
      other history, or opens a second request;
    - the retry answered with a new record when one is held."""
    world = _World(tmp_path)
    await world.started(target=2)
    await world.accepted_with_criterion()
    world.forge.refuse = True
    client = world.client()
    aborted = client.post(
        f"/api/v1/campaigns/{CID}/abort",
        json={"reason": "the crew's deadline", "idempotency_key": "a-1"},
    )
    assert aborted.status_code == 200, aborted.text

    refused = client.post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})

    assert refused.status_code == 502, refused.text
    assert refused.json()["detail"]["error"]["code"] == "CONTRIBUTION_FAILED"
    closing = await world.closing()
    [failure] = await world.failures()
    stored = await world.campaigns.get_campaign(CID)
    assert closing.operation is ControlOperation.ABORT
    assert closing.binding["contribution"]["due"] is True
    assert (stored.state, stored.outcome) == (CampaignState.COMPLETED, CampaignOutcome.ABORTED)
    assert failure.outcome is ControlOutcome.APPLIED
    assert failure.actor == "supervisor"
    assert failure.binding["error"] == "ReviewRequestFailed"
    assert "503" in failure.binding["message"]
    assert world.book.recorded == []
    first_push = world.remote()  # the push landed before the forge refused

    world.forge.refuse = False
    # A minute later: a commit made again would differ from the first by its committer date.
    later = time.time() + 60
    monkeypatch.setattr("adapters.tools.git_source.time.time", lambda: later)
    retried = client.post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})
    again = client.post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})

    assert retried.status_code == 201, retried.text
    body = retried.json()
    assert (body["replayed"], body["contribution"]["campaign_id"]) == (False, CID)
    assert body["contribution"]["commit"] == first_push == world.remote()
    assert (again.json()["replayed"], len(world.book.recorded)) == (True, 1)
    assert len(world.forge.opened) == 1


async def test_a_request_with_no_token_is_refused_and_no_stored_one_stands_in(tmp_path):
    """§24ci (b): the token comes with the request alone. Bug caught: the route falling back on the
    deploy's token for the Project, which is the automatic path by another door."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted_with_criterion()
    client = world.client()
    client.app.state.review_request_tokens = {PROJECT: TOKEN}

    refused = client.post(f"/api/v1/campaigns/{CID}/contributions", json={})

    assert refused.status_code == 422, refused.text
    assert world.forge.calls == 0 and world.remote() is None and await world.failures() == []


async def test_a_campaign_with_no_accepted_increment_opens_nothing_and_says_so(tmp_path):
    """Aborted after its calibration, before any increment. Bugs caught: an empty branch pushed
    as a review request; a close record silent about why nothing was opened; a retry that opens
    one anyway."""
    world = _World(tmp_path)
    await world.started(target=2)
    client = world.client()

    aborted = client.post(
        f"/api/v1/campaigns/{CID}/abort", json={"reason": "stop", "idempotency_key": "a-1"}
    )
    retried = client.post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})

    assert aborted.status_code == 200, aborted.text
    assert (await world.closing()).binding["contribution"] == {
        "due": False,
        "reason": NO_ACCEPTED_INCREMENT,
    }
    assert retried.status_code == 409
    assert retried.json()["detail"]["error"]["code"] == "CONTRIBUTION_REFUSED"
    assert world.forge.calls == 0 and world.remote() is None and world.book.recorded == []
    assert await world.failures() == []


def _promotes_first(world: _World, operation: ControlOperation, cycle_id: str, commit: str) -> None:
    """A PROMOTE that commits in the instant before ``operation``'s row: after anything read for
    the row outside the registry's lock, and before its own write."""
    real = world.campaigns.transition

    async def racing(campaign_id, transition):
        if transition.operation is operation:
            held = await world.campaigns.get_campaign(campaign_id)
            await real(
                campaign_id,
                move(
                    held.state, f"promote-{cycle_id}", operation=ControlOperation.PROMOTE,
                    accepted=AcceptedTree("tree-late", cycle_id, commit=commit),
                    binding={"cycle_id": cycle_id, "commit": commit, "identity": "tree-late"},
                ),
            )  # fmt: skip
        return await real(campaign_id, transition)

    world.campaigns.transition = racing


async def test_a_promotion_racing_the_abort_is_on_the_closing_rows_record(tmp_path):
    """PR #2920's review, finding 3, entered at the abort route. The promotion commits after the
    route's reads and before the abort's row. Bug caught: ``due: false`` over accepted work, which
    no request can then open: stranded on the branch."""
    world = _World(tmp_path)
    await world.started(target=2)
    cycle, _run, captured = await world.delivered("cyc_late00000001", _added("total"))
    _promotes_first(world, ControlOperation.ABORT, cycle.cycle_id, captured)

    aborted = world.client().post(
        f"/api/v1/campaigns/{CID}/abort", json={"reason": "stop", "idempotency_key": "a-1"}
    )

    assert aborted.status_code == 200, aborted.text
    assert (await world.closing()).binding["contribution"] == {
        "due": True,
        "accepted": ["cyc_late00000001"],
    }


async def test_a_promotion_racing_a_terminal_decision_is_on_the_closing_rows_record(tmp_path):
    """Finding 3's other door, entered at the completion boundary: a promotion that commits after
    the hearing's last read of the log. Bug caught: the terminal decision's record missing an
    increment the branch holds."""
    world = _World(tmp_path)
    await world.started()
    late = "cyc_race00000003"
    held = (await world.campaigns.get_campaign(CID)).state
    launched = await world.campaigns.transition(
        CID,
        move(
            CampaignState.BUILDING, "launch-race", operation=ControlOperation.RESUME,
            launch=LaunchRequest(CycleKind.INCREMENT, {}),
        ),
    )  # fmt: skip
    await world.campaigns.mark_launch_intent_launched(
        launched.intent.launch_id, late, actor="launcher"
    )
    await world.campaigns.transition(CID, move(CampaignState.ESCALATED, "held-again"))
    assert held is CampaignState.ESCALATED
    real = world.campaigns.transition

    async def racing(campaign_id, transition):
        if transition.next_state is CampaignState.COMPLETED:
            state = (await world.campaigns.get_campaign(campaign_id)).state
            await real(
                campaign_id,
                move(
                    state, "promote-race", operation=ControlOperation.PROMOTE,
                    accepted=AcceptedTree("tree-race", late, commit="d" * 40),
                    binding={"cycle_id": late, "commit": "d" * 40, "identity": "tree-race"},
                ),
            )  # fmt: skip
        return await real(campaign_id, transition)

    world.campaigns.transition = racing
    await world.accepted_with_criterion()

    closing = await world.closing()
    assert closing.operation is ControlOperation.DECIDE
    assert closing.binding["contribution"]["accepted"] == ["cyc_inc000000001", late]


async def test_an_abort_stored_before_this_rule_replays_and_stays_as_it_was(tmp_path):
    """PR #2920's review, finding 4. An abort committed before the upgrade has no ``contribution``
    on its row, and its client's retry arrives after it. The key is the server's derivation, never
    the caller's content. Bugs caught: the retry's hash differing, so a replay reads as an
    idempotency conflict; a retry rewriting the stored row; such a Campaign contributed."""
    world = _World(tmp_path)
    await world.started(target=2)
    await world.accepted_with_criterion()
    stored = await world.campaigns.transition(
        CID,
        CampaignTransition(
            operation=ControlOperation.ABORT,
            actor="supervisor",
            actor_role=Role.CAMPAIGN_SUPERVISOR,
            reason="stop",
            idempotency_key="a-old",
            next_state=CampaignState.COMPLETED,
            outcome=CampaignOutcome.ABORTED,
        ),
    )
    assert "contribution" not in stored.entry.binding
    client = world.client()

    retried = client.post(
        f"/api/v1/campaigns/{CID}/abort", json={"reason": "stop", "idempotency_key": "a-old"}
    )
    asked = client.post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})

    assert retried.status_code == 200, retried.text
    assert retried.json()["replayed"] is True
    assert retried.json()["entry"]["entry_id"] == stored.entry.entry_id
    assert "contribution" not in (await world.closing()).binding
    assert asked.status_code == 409 and world.forge.calls == 0


async def test_a_draft_on_an_unknown_project_stays_abortable(tmp_path):
    """PR #2920's review, finding 6. A Campaign with no branch has no contribution, so nothing about
    one can block its abort. Bug caught: the Project's lookup answering 404 for the abort."""
    world = _World(tmp_path)
    draft = campaign("cmp_orphan000001", project_id="prj-gone")
    await world.campaigns.create_campaign(
        draft, actor="owner", actor_role="admin", reason="r", idempotency_key="create-orphan"
    )
    client = world.client()
    client.app.state.project_registry = create_project_registry("config")

    aborted = client.post(
        "/api/v1/campaigns/cmp_orphan000001/abort",
        json={"reason": "stop", "idempotency_key": "a-orphan"},
    )

    assert aborted.status_code == 200, aborted.text
    assert aborted.json()["campaign"]["state"] == "completed"


async def test_a_running_campaign_and_an_unknown_one_are_refused(tmp_path):
    """Bugs caught: a contribution opened mid-Campaign, before its close; an unknown Campaign
    answered with anything but the standard 404."""
    world = _World(tmp_path)
    await world.started(target=2)
    client = world.client()

    running = client.post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})
    unknown = client.post("/api/v1/campaigns/cmp_nosuch000001/contributions", json={"token": TOKEN})

    assert running.status_code == 409
    assert "opened after its close" in running.json()["detail"]["error"]["message"]
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["error"]["code"] == "CAMPAIGN_NOT_FOUND"


async def test_a_sample_application_has_nothing_to_contribute_to():
    """Bug caught: a Project with no repository reaching the clone or the forge."""
    project = Project(project_id="group_run", name="g", description="", created_at=T0)
    book = _Contributions()
    forge = _Forge()

    with pytest.raises(ContributionRefused, match="sample application"):
        await contribute_campaign(
            project,
            "cmp_sample000001",
            head="a" * 40,
            base="b" * 40,
            criterion_paths=(),
            title="t",
            body="b",
            registry=book,
            repository=None,
            forge=forge,
            token=TOKEN,
            actor="squadops",
            idempotency_key="k",
            verify=None,
        )
    assert forge.calls == 0 and book.recorded == []


def _row(seq: int, operation: ControlOperation, binding: dict) -> ControlLogEntry:
    return ControlLogEntry(
        entry_id=f"e{seq}",
        campaign_id=CID,
        seq=seq,
        operation=operation,
        actor="squadops",
        actor_role="completion",
        reason="r",
        target=None,
        idempotency_key=f"k{seq}",
        request_hash="h",
        binding=binding,
        outcome=ControlOutcome.APPLIED,
        refusal=None,
        prior_state=CampaignState.EVALUATING,
        next_state=CampaignState.EVALUATING,
        committed_at=NOW,
    )


def _intent(cycle_id: str, kind: CycleKind) -> LaunchIntent:
    return LaunchIntent(
        f"l-{cycle_id}", CID, "d", kind, {}, LaunchIntentState.LAUNCHED, NOW, cycle_id=cycle_id
    )


def test_an_increment_is_followed_through_each_rebase_and_a_dropped_one_is_upstreams():
    """Bugs caught: the accepted set read from promotions alone, so a rebased increment names a
    commit no branch holds; a calibration counted as an increment; an increment upstream already
    took (dropped by the rebase) still read as the Campaign's own."""
    log = [
        _row(1, ControlOperation.PROMOTE, {"calibration_record_id": "rec", "commit": "c0"}),
        _row(2, ControlOperation.PROMOTE, {"cycle_id": "cyc_a", "commit": "a1"}),
        _row(3, ControlOperation.PROMOTE, {"cycle_id": "cyc_b", "commit": "b1"}),
        _row(4, ControlOperation.BRANCH_REBASED, {"replayed": [["b1", "b2"]], "dropped": ["a1"]}),
        _row(5, ControlOperation.PROMOTE, {"cycle_id": "cyc_c", "commit": "c1"}),
    ]
    intents = [
        _intent("cyc_a", CycleKind.INCREMENT),
        _intent("cyc_b", CycleKind.REPAIR),
        _intent("cyc_c", CycleKind.INCREMENT),
        _intent("cyc_cal", CycleKind.CALIBRATION),
    ]

    assert accepted_on_branch(log, intents) == (("cyc_a", None), ("cyc_b", "b2"), ("cyc_c", "c1"))
