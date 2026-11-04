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
import json
import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.campaigns import campaigns_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.calibration_record import record_for
from squadops.campaigns.close_contribution import (
    NO_ACCEPTED_INCREMENT,
    CampaignContribution,
    accepted_on_branch,
    closing_row,
)
from squadops.campaigns.increment_tree import INCREMENT_EVALUATION_ARTIFACT_TYPE
from squadops.campaigns.launch_requests import start_transition
from squadops.campaigns.models import (
    CampaignOutcome,
    CampaignState,
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
    contribute_campaign,
    relocated_criterion_files,
)
from squadops.projects.source_context import parse_source_context
from squadops.projects.workspaces import capture_inherited_baseline
from tests.fixtures.shared_contract.repository import _git, recorded, tracked_files
from tests.unit.api.test_campaign_calibration_record import PROJECT
from tests.unit.campaigns.builders import T0, campaign, move, policy
from tests.unit.campaigns.test_campaign_branch import CID, NOW, REPORT, _added
from tests.unit.campaigns.test_campaign_branch import _World as _BranchWorld
from tests.unit.projects.test_workspaces import _LocalSandbox

TOKEN = "github_pat_inventedForTheTest0002"
BRANCH = f"squadops/{CID}"
URL = "https://forge.example.invalid/tally/pull/9"
CRITERION = "test_criterion_T1.py"
MOVED = f"tests/test_{CID}_T1.py"


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

    def __init__(self, tmp_path, *, tokens: dict[str, str] | None = None) -> None:
        self.forge = _Forge()
        self.book = _Contributions()
        super().__init__(tmp_path)
        self.projects.contributions = self.book.contributions
        self.projects.record_contribution = self.book.record_contribution
        self.contribution = CampaignContribution(
            campaigns=self.campaigns,
            projects=self.projects,
            repository=self.clones,
            forge=self.forge,
            tokens={PROJECT: TOKEN} if tokens is None else tokens,
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
            goal_sets=None,
            contribute_at_close=lambda campaign_id: self.contribution.at_close(campaign_id),
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

    async def accepted_with_criterion(self, cycle_id: str = "cyc_inc000000001") -> str:
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
            await self._stored(cycle, run, CRITERION, "source", b"def test_t1():\n    pass\n"),
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

    def client(self) -> TestClient:
        """The campaign routes, as the runtime mounts them, for the supervisor's seat."""
        app = FastAPI()

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = Identity(
                    user_id="supervisor",
                    display_name="supervisor",
                    roles=(Role.CAMPAIGN_SUPERVISOR,),
                    scopes=tuple(sorted(scopes_for_roles((Role.CAMPAIGN_SUPERVISOR,)))),
                    identity_type=IdentityType.HUMAN,
                )
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(campaigns_router)
        register_domain_error_handlers(app)
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
        ("test_criterion_T1.py", "tests/test_cmp_b498332d326e_T1.py"),
        # placed beside the runner's tests (#2858): renamed where it stands
        ("tests/test_criterion_T2.py", "tests/test_cmp_b498332d326e_T2.py"),
        # a vitest runner's pattern has no prefix
        ("frontend/src/criterion_T3.test.jsx", "frontend/src/cmp_b498332d326e_T3.test.jsx"),
    ],
)
def test_a_criterion_file_leaves_the_stem_and_the_root(placed, moved):
    """#2860's interim, made the rule. Bugs caught: a root file left at the root, where a later
    placement under ``tests/`` breaks pytest's collection (#2858); a name left in the stem, which
    §24cx then refuses to every later Campaign's criterion of that id; the runner's own prefix
    dropped, so the runner no longer collects the file."""
    assert relocated_criterion_files([placed], "cmp_b498332d326e028682987379") == {placed: moved}


def test_a_file_outside_the_stem_is_left_where_it_is():
    """Bug caught: a product test file the Campaign changed renamed as if it were a criterion's."""
    assert relocated_criterion_files(["tests/test_report.py", "README.md"], "cmp_x") == {}


async def test_a_campaign_closed_by_its_decision_opens_one_contribution_with_its_criteria_moved(
    tmp_path, caplog
):
    """The wiring, entered at the completion boundary. The increment's acceptance meets the
    objective, so its decision closes the Campaign, and the close opens the contribution. Bugs
    caught:
    - the close recording nothing due, or opening nothing (campaigns 4 and 6, by hand);
    - the open inside the close's transaction, so a refusal there undoes the close;
    - the root criterion file contributed as it was placed, where the next Campaign's placement
      collides with it (#2860);
    - the commit pushed or recorded off the branch's head, or its base wrong, so a sync reads the
      Campaign's change against the wrong commit;
    - a second request opened, or the token stored, returned or logged."""
    caplog.set_level(logging.DEBUG)
    world = _World(tmp_path)
    await world.started()

    captured = await world.accepted_with_criterion()

    stored = await world.campaigns.get_campaign(CID)
    closing = await world.closing()
    [contribution] = world.book.recorded
    pushed = world.remote()
    files = tracked_files(world.repo.path, pushed)
    assert (stored.state, stored.outcome) == (CampaignState.COMPLETED, CampaignOutcome.SUCCESS)
    assert closing.operation is ControlOperation.DECIDE
    assert closing.binding["contribution"] == {"due": True, "accepted": ["cyc_inc000000001"]}
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
    assert contribution.parent_commit == world.repo.second_commit  # the branch's base
    [request] = world.forge.opened
    assert (request["head"], request["base"], request["token"]) == (BRANCH, "main", TOKEN)
    assert f"- {CRITERION} -> {MOVED}" in request["body"]
    assert "Opened at the campaign's close" in request["body"]
    assert await world.failures() == []
    assert TOKEN not in repr(await world.campaigns.control_log(CID)) + caplog.text


async def test_a_failed_open_is_recorded_the_campaign_stays_closed_and_the_retry_opens_it(
    tmp_path,
):
    """The forge refuses at the close; the owner's abort closed the Campaign (the route the
    live loop takes). Bugs caught:
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
    closing = await world.closing()
    [failure] = await world.failures()
    stored = await world.campaigns.get_campaign(CID)
    assert closing.operation is ControlOperation.ABORT
    assert closing.binding["contribution"]["due"] is True
    assert (stored.state, stored.outcome) == (CampaignState.COMPLETED, CampaignOutcome.ABORTED)
    assert failure.outcome is ControlOutcome.APPLIED
    assert failure.binding["error"] == "ReviewRequestFailed"
    assert "503" in failure.binding["message"]
    assert world.book.recorded == []
    first_push = world.remote()  # the push landed before the forge refused

    world.forge.refuse = False
    retried = client.post(f"/api/v1/campaigns/{CID}/contributions", json={})
    again = client.post(f"/api/v1/campaigns/{CID}/contributions", json={})

    assert retried.status_code == 201, retried.text
    body = retried.json()
    assert (body["replayed"], body["contribution"]["campaign_id"]) == (False, CID)
    assert body["contribution"]["commit"] == first_push == world.remote()
    assert (again.json()["replayed"], len(world.book.recorded)) == (True, 1)
    assert len(world.forge.opened) == 1


async def test_with_no_token_the_close_records_why_and_the_supervisors_token_opens_it(tmp_path):
    """The deploy holds no token for the Project (§24ci (b): nothing is stored by default). Bugs
    caught: the close pushing without one, or failing silently; the supervisor's own token not
    reaching the push; the token kept anywhere."""
    world = _World(tmp_path, tokens={})
    await world.started()
    await world.accepted_with_criterion()

    [failure] = await world.failures()
    assert "no review-request token" in failure.binding["message"]
    assert world.remote() is None and world.forge.calls == 0

    opened = world.client().post(
        f"/api/v1/campaigns/{CID}/contributions", json={"token": "supervisor-own-token"}
    )

    assert opened.status_code == 201, opened.text
    assert world.forge.opened[0]["token"] == "supervisor-own-token"
    assert "supervisor-own-token" not in opened.text
    assert world.book.recorded[0].contributed_by == "supervisor"


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
    retried = client.post(f"/api/v1/campaigns/{CID}/contributions", json={})

    assert aborted.status_code == 200, aborted.text
    assert (await world.closing()).binding["contribution"] == {
        "due": False,
        "reason": NO_ACCEPTED_INCREMENT,
    }
    assert retried.status_code == 409
    assert retried.json()["detail"]["error"]["code"] == "CONTRIBUTION_REFUSED"
    assert world.forge.calls == 0 and world.remote() is None and world.book.recorded == []
    assert await world.failures() == []


async def test_a_running_campaign_and_an_unknown_one_are_refused(tmp_path):
    """Bugs caught: a contribution opened mid-Campaign, before its close; an unknown Campaign
    answered with anything but the standard 404."""
    world = _World(tmp_path)
    await world.started(target=2)
    client = world.client()

    running = client.post(f"/api/v1/campaigns/{CID}/contributions", json={})
    unknown = client.post("/api/v1/campaigns/cmp_nosuch000001/contributions", json={})

    assert running.status_code == 409
    assert "opened at its close" in running.json()["detail"]["error"]["message"]
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
