"""``/api/v1/campaigns`` (SIP-0109 §13, #1799), with the real authorization adapter.

Entered at the HTTP surface, over the memory registries the runtime's Postgres twins mirror, with
the identity injected as the auth middleware would set it. Each test names the bug it catches:
a scope the owner's ruling withholds granted anyway, an actor taken from the request body, a
refusal not recorded, a resume to the wrong state, an abort that leaves a launched cycle running.
"""

from __future__ import annotations

import dataclasses

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.campaigns import campaigns_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.launcher import CampaignLauncher
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    ControlOperation,
    CycleKind,
    LaunchRequest,
)
from tests.unit.campaigns.builders import cycle_for, move, quiet_box

pytestmark = pytest.mark.auth

_POLICY = dict(
    max_cycles=6,
    max_elapsed_s=43200,
    budget_tokens=2_000_000,
    max_repair_cycles_per_increment=1,
    max_retry_cycles_per_increment=1,
    max_proposal_run_retries=1,
    max_proposal_revisions=2,
    max_rejected_proposals_in_row=2,
    max_unaccepted_increments=2,
    ruling_bound_s=1800,
    lease_expiry_s=3600,
    launch_blocked_interval_s=300,
    launch_blocked_attempts=6,
    calibration_profile="validated-fullstack",
    proposal_profile="campaign-increment",
    squad_profile="full-38",
)


class _Audit:
    def __init__(self) -> None:
        self.events = []

    def record(self, event) -> None:
        self.events.append(event)


def _identity(*roles: str, user: str = "owner", kind: str = IdentityType.HUMAN) -> Identity:
    return Identity(
        user_id=user,
        display_name=user,
        roles=roles,
        scopes=tuple(sorted(scopes_for_roles(roles))),
        identity_type=kind,
    )


class _World:
    def __init__(self) -> None:
        self.campaigns = MemoryCampaignRegistry()
        self.cycles = MemoryCycleRegistry()
        self.audit = _Audit()
        self.identity: Identity | None = _identity(Role.ADMIN)
        app = FastAPI()
        world = self

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                if world.identity is not None:
                    request.state.identity = world.identity
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(campaigns_router)
        register_domain_error_handlers(app)
        app.state.campaign_registry = self.campaigns
        app.state.cycle_registry = self.cycles
        app.state.authz_port = KeycloakAuthzAdapter()
        app.state.audit_port = self.audit
        self.client = TestClient(app)

    def as_(self, identity: Identity | None) -> _World:
        self.identity = identity
        return self


@pytest.fixture
def world() -> _World:
    return _World()


def _create(world: _World, key: str = "create-1", **overrides):
    body = {
        "project_id": "group_run",
        "objective": {
            "statement": "evolve group_run toward its PRD's expansion scope",
            "allowed_scope": ["backend", "frontend"],
            "measurement": "two accepted increments",
            "target_accepted_increments": 2,
        },
        "policy": _POLICY,
        "reason": "the 2.0 shakeout",
        "idempotency_key": key,
        "campaign_id": "cmp_api000000001",
    }
    body.update(overrides)
    return world.client.post("/api/v1/campaigns", json=body)


def _control(world: _World, op: str, key: str, **extra):
    return world.client.post(
        f"/api/v1/campaigns/cmp_api000000001/{op}",
        json={"reason": f"{op} it", "idempotency_key": key, **extra},
    )


# --- the owner's ruling, scope by scope ----------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "create", "pause", "resume", "abort", "read"),
    [
        (Role.ADMIN, 200, 200, 200, 200, 200),
        (Role.CAMPAIGN_SUPERVISOR, 200, 200, 200, 200, 200),
        (Role.CAMPAIGN_TRIAGE, 403, 403, 403, 403, 200),
        (Role.OPERATOR, 403, 403, 403, 403, 200),
    ],
)
async def test_each_role_holds_exactly_the_operations_the_ruling_gives_it(
    world, role, create, pause, resume, abort, read
):
    """Bug caught: the supervisor unable to manage a campaign it was given (#1940: create, its
    own pause's resume, abort), or the read-only seats able to steer. The owner's ruling of
    2026-10-02, as #1940 revised it, route by route. The resume here lifts the caller's own
    pause; the owner's holds are the next tests'."""
    assert _create(world.as_(_identity(role, user="x"))).status_code == create
    world.as_(_identity(Role.ADMIN))
    if create != 200:
        assert _create(world).status_code == 200
    await world.campaigns.transition("cmp_api000000001", move(CampaignState.CALIBRATING, "k-run"))
    world.as_(_identity(role, user="x"))
    assert world.client.get("/api/v1/campaigns/cmp_api000000001").status_code == read
    assert _control(world, "pause", "k-pause").status_code == pause
    if pause != 200:
        world.as_(_identity(Role.ADMIN))
        assert _control(world, "pause", "k-pause").status_code == 200
        world.as_(_identity(role, user="x"))
    assert _control(world, "resume", "k-resume").status_code == resume
    assert _control(world, "abort", "k-abort").status_code == abort


@pytest.mark.parametrize("role", [Role.CAMPAIGN_TRIAGE, Role.OPERATOR, Role.VIEWER])
async def test_only_the_managing_seats_start_a_campaign(world, role):
    """Starting a campaign launches cycles: the owner's and, since #1940, the supervisor's
    (campaigns:manage). Bug caught: a read-only seat able to launch a campaign."""
    _create(world)
    world.as_(_identity(role, user="x"))

    assert _control(world, "start", "k-start").status_code == 403
    assert (await world.campaigns.get_campaign("cmp_api000000001")).state is CampaignState.DRAFT


async def test_the_supervisor_cannot_lift_the_owners_own_pause(world):
    """#1940: the supervisor lifts its own pause, not the owner's. Bug caught: the manage scope
    letting the supervisor resume a campaign the owner held. Refused before anything is written."""
    _create(world)
    await world.campaigns.transition("cmp_api000000001", move(CampaignState.CALIBRATING, "k-run"))
    assert _control(world, "pause", "k-owner-pause").status_code == 200
    rows = len(await world.campaigns.control_log("cmp_api000000001"))
    world.as_(_identity(Role.CAMPAIGN_SUPERVISOR, user="ripley"))

    refused = _control(world, "resume", "k-sup-resume")

    error = refused.json()["detail"]["error"]
    assert (refused.status_code, error["code"]) == (403, "OWNER_AUTHORITY_REQUIRED")
    assert "paused by the owner" in error["message"]
    assert len(await world.campaigns.control_log("cmp_api000000001")) == rows
    world.as_(_identity(Role.ADMIN))
    assert _control(world, "resume", "k-owner-resume").status_code == 200


def test_no_identity_is_refused_once_authorization_is_configured(world):
    assert _create(world.as_(None)).status_code == 401


# --- the control log -----------------------------------------------------------------------------


async def test_the_actor_and_role_on_the_row_come_from_the_token(world):
    """Bug caught: a caller naming itself in the body — the actor is the token's, always."""
    _create(world)
    await world.campaigns.transition("cmp_api000000001", move(CampaignState.CALIBRATING, "k-run"))
    world.as_(_identity(Role.CAMPAIGN_SUPERVISOR, user="ripley", kind=IdentityType.SERVICE))

    resp = world.client.post(
        "/api/v1/campaigns/cmp_api000000001/pause",
        json={"reason": "watching", "idempotency_key": "k-1", "actor": "owner"},
    )

    entry = resp.json()["entry"]
    assert (entry["actor"], entry["actor_role"]) == ("ripley", "campaign-supervisor")
    paused = world.audit.events[-1]
    assert (paused.action, paused.actor_id, paused.actor_type) == (
        "campaign.pause",
        "ripley",
        "service",
    )


async def test_a_refused_operation_is_a_409_naming_its_recorded_row(world):
    """§12a: refused and recorded. Bug caught: a refusal that leaves no row, or a 500."""
    _create(world)
    await world.campaigns.transition("cmp_api000000001", move(CampaignState.CALIBRATING, "k-run"))
    _control(world, "pause", "k-1")

    resp = _control(world, "pause", "k-1", reason="a different reason")

    detail = resp.json()["detail"]["error"]
    log = world.client.get("/api/v1/campaigns/cmp_api000000001/control-log").json()
    assert (resp.status_code, detail["code"]) == (409, "CONTROL_OPERATION_REFUSED")
    assert detail["details"]["entry_id"] == log[-1]["entry_id"]
    assert (log[-1]["outcome"], log[-1]["refusal"]) == ("refused", "conflicting_idempotency_key")
    assert world.audit.events[-1].result == "denied"


async def test_a_repeated_operation_replays_without_a_second_row_or_audit_event(world):
    _create(world)
    await world.campaigns.transition("cmp_api000000001", move(CampaignState.CALIBRATING, "k-run"))
    first = _control(world, "pause", "k-1").json()
    audited = len(world.audit.events)

    again = _control(world, "pause", "k-1").json()

    assert again["replayed"] and again["entry"] == first["entry"]
    assert len(world.audit.events) == audited
    assert len(world.client.get("/api/v1/campaigns/cmp_api000000001/control-log").json()) == 3


# --- pause, resume, abort ------------------------------------------------------------------------


async def test_resume_returns_the_campaign_to_the_state_it_was_paused_from(world):
    """Bug caught: a resume that moves a paused building campaign anywhere but building."""
    _create(world)
    for to, key in ((CampaignState.CALIBRATING, "a"), (CampaignState.AT_PROPOSAL, "b")):
        await world.campaigns.transition("cmp_api000000001", move(to, key))
    _control(world, "pause", "k-pause")

    resumed = _control(world, "resume", "k-resume").json()

    assert resumed["campaign"]["state"] == "at_proposal"
    assert (resumed["entry"]["prior_state"], resumed["entry"]["next_state"]) == (
        "paused",
        "at_proposal",
    )


async def test_the_campaign_read_carries_its_accepted_tree(world):
    """§7.1: the tree every increment is proposed against and every ruling binds to is readable
    by the supervisor. Bug caught: the response mapping leaving it out, so a ruling's binding
    cannot be built from a read."""
    _create(world)
    await world.campaigns.transition("cmp_api000000001", move(CampaignState.CALIBRATING, "a"))
    before = world.client.get("/api/v1/campaigns/cmp_api000000001").json()
    await world.campaigns.transition(
        "cmp_api000000001",
        move(
            CampaignState.CALIBRATING,
            "promote",
            operation=ControlOperation.PROMOTE,
            accepted=AcceptedTree("sha-cal", "cyc_cal000000001"),
        ),
    )

    after = world.as_(_identity(Role.CAMPAIGN_SUPERVISOR)).client.get(
        "/api/v1/campaigns/cmp_api000000001"
    )

    assert before["accepted"] is None
    assert after.json()["accepted"] == {"identity": "sha-cal", "cycle_id": "cyc_cal000000001"}


async def test_a_resume_after_the_gate_opened_during_the_pause_returns_to_the_gate(world):
    """§9.2: a proposal submitted while the campaign was paused waits for its ruling after the
    resume. Bug caught: the resume returning to at_proposal, where no ruling is legal, so the
    submitted proposal could never be ruled on."""
    from squadops.campaigns.gate import submission
    from squadops.campaigns.models import ProposalBinding, SubmittedProposal

    _create(world)
    for to, key in ((CampaignState.CALIBRATING, "a"), (CampaignState.AT_PROPOSAL, "b")):
        await world.campaigns.transition("cmp_api000000001", move(to, key))
    _control(world, "pause", "k-pause")
    await world.campaigns.transition(
        "cmp_api000000001",
        submission(
            CampaignState.PAUSED,
            SubmittedProposal(ProposalBinding("p", 1, "h", "t"), "cyc_1", "run_p"),
        ),
    )

    resumed = _control(world, "resume", "k-resume").json()

    assert resumed["campaign"]["state"] == "awaiting_ruling"


def test_resuming_a_campaign_that_is_not_paused_is_refused_as_stale(world):
    _create(world)
    resp = _control(world, "resume", "k-resume")
    assert resp.json()["detail"]["error"]["details"]["refusal"] == "stale_state"


async def test_abort_cancels_the_launched_cycle_by_the_existing_path(world):
    """§12a: an abort is terminal and the running cycle is cancelled by the existing path.
    Bug caught: an aborted campaign whose launched cycle keeps running."""
    _create(world)
    await world.campaigns.transition(
        "cmp_api000000001",
        move(
            CampaignState.CALIBRATING,
            "k-start",
            launch=LaunchRequest(CycleKind.CALIBRATION),
        ),
    )

    async def build(intent):
        return cycle_for(intent)

    [launched] = await CampaignLauncher(
        world.campaigns, world.cycles, build, actor="l1", box_verdict=quiet_box
    ).drain()

    resp = _control(world, "abort", "k-abort").json()

    assert resp["cancelled_cycles"] == [launched.cycle_id]
    assert (await world.cycles.get_cycle(launched.cycle_id)).cancelled
    assert (resp["campaign"]["state"], resp["campaign"]["outcome"]) == ("completed", "aborted")


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"max_cycles": 0}, "max_cycles must be >= 1"),
        # A campaign whose launches could never be built is refused at its creation.
        ({"proposal_profile": "no-such-profile"}, "policy.proposal_profile"),
        ({"calibration_profile": "no-such-profile"}, "policy.calibration_profile"),
        # Or whose increments could never be ruled: the proposal workload alone (#1705 step b).
        ({"proposal_profile": "campaign-proposal"}, "must open with the proposal workload"),
    ],
)
async def test_an_invalid_policy_is_a_422_not_a_500_and_creates_nothing(world, override, message):
    """Bugs caught: a policy the domain refuses surfacing as a crash, or a campaign created
    whose first launch can only fail."""
    resp = _create(world, policy={**_POLICY, **override})
    assert resp.status_code == 422
    assert message in resp.json()["detail"]["error"]["message"]
    assert world.client.get("/api/v1/campaigns/cmp_api000000001").status_code == 404


def test_an_unknown_campaign_is_a_404(world):
    resp = world.client.get("/api/v1/campaigns/cmp_missing")
    assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (404, "CAMPAIGN_NOT_FOUND")


class _Bus:
    def __init__(self, fail: bool = False) -> None:
        self.emitted = []
        self.fail = fail

    def emit(self, event_type, **kwargs) -> None:
        if self.fail:
            raise RuntimeError("the bus is down")
        self.emitted.append((event_type, kwargs))


async def test_each_applied_row_is_projected_as_one_event_and_a_replay_as_none(world):
    """§13's event projection. Bug caught: a replay re-announcing a transition, or a row
    projected without its operation and states."""
    bus = _Bus()
    world.client.app.state.cycle_event_bus = bus
    _create(world)
    await world.campaigns.transition("cmp_api000000001", move(CampaignState.CALIBRATING, "k-run"))

    _control(world, "pause", "k-1")
    _control(world, "pause", "k-1")

    assert [(t, k["payload"]["operation"], k["payload"]["next_state"]) for t, k in bus.emitted] == [
        ("campaign.transitioned", "create", "draft"),
        ("campaign.transitioned", "pause", "paused"),
    ]


async def test_a_failing_event_bus_fails_no_operation(world):
    world.client.app.state.cycle_event_bus = _Bus(fail=True)
    _create(world)
    await world.campaigns.transition("cmp_api000000001", move(CampaignState.CALIBRATING, "k-run"))

    resp = _control(world, "pause", "k-1")

    assert resp.status_code == 200 and resp.json()["campaign"]["state"] == "paused"


def test_a_campaign_whose_measurement_has_no_reader_is_refused(world):
    """§24ah. Bug caught: a campaign created with no target, which row 3 can never stop in
    success, so it proposes past its objective until a limit stops it, and reads exhausted."""
    body_objective = {
        "statement": "evolve group_run",
        "allowed_scope": ["backend"],
        "measurement": "two accepted increments",
        "target_accepted_increments": None,
    }

    response = _create(world, objective=body_objective)

    assert response.status_code == 422
    assert "target_accepted_increments is required" in response.json()["detail"]["error"]["message"]


# --- the box lease (SIP-0109 §9.3; #1802) ---------------------------------------------------------


async def _at_the_gate(world: _World) -> None:
    assert _create(world).status_code == 200
    for i, state in enumerate(("calibrating", "at_proposal", "awaiting_ruling")):
        await world.campaigns.transition("cmp_api000000001", move(CampaignState(state), f"g{i}"))


async def test_the_supervisor_takes_and_returns_the_box_through_its_routes(world):
    """Bug caught: a lease route that changes nothing, an acquire past the policy's expiry, or
    a lease change that never reaches the security audit."""
    from tests.unit.campaigns.builders import QuietBox

    world.client.app.state.box_reader = QuietBox()
    await _at_the_gate(world)
    world.as_(_identity(Role.CAMPAIGN_SUPERVISOR, user="crew"))
    url = "/api/v1/campaigns/cmp_api000000001/lease"

    too_long = world.client.post(
        url, json={"reason": "r", "idempotency_key": "l0", "expires_in_s": 3601}
    )
    taken = world.client.post(
        url, json={"reason": "review", "idempotency_key": "l1", "expires_in_s": 900}
    )
    read = world.client.get(url)
    returned = world.client.post(f"{url}/release", json={"reason": "done", "idempotency_key": "l2"})

    assert too_long.status_code == 422
    assert taken.status_code == 200
    assert (taken.json()["lease"]["held_by"], taken.json()["lease"]["supervisor_holds"]) == (
        "crew",
        True,
    )
    assert read.json()["supervisor_holds"] is True
    assert (returned.json()["lease"]["holder"], returned.json()["lease"]["supervisor_holds"]) == (
        "squad",
        False,
    )
    assert [e.action for e in world.audit.events if "lease" in e.action] == [
        "campaign.lease_acquire",
        "campaign.lease_release",
    ]


async def test_a_lease_asked_for_while_a_run_is_in_flight_is_refused_with_its_reason(world):
    """Bug caught: the supervisor taking the box while a cycle's run is still executing."""

    class Busy:
        async def runs_in_flight(self):
            return ("run_live",)

    world.client.app.state.box_reader = Busy()
    await _at_the_gate(world)
    resp = world.client.post(
        "/api/v1/campaigns/cmp_api000000001/lease",
        json={"reason": "review", "idempotency_key": "l1", "expires_in_s": 900},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["details"]["refusal"] == "run_in_flight"
    assert await world.campaigns.box_lease() is None


async def test_the_owners_resume_of_a_blocked_launch_escalation_retries_the_launch(world):
    """Bug caught: an escalation over a blocked launch that the owner can only resume by naming
    an action, which would write a second intent beside the one still pending."""
    from squadops.campaigns.box import LaunchRefusal, LaunchVerdict
    from squadops.campaigns.launch_blocking import first_refusal
    from squadops.campaigns.models import CycleKind, LaunchRequest

    assert _create(world).status_code == 200
    cid = "cmp_api000000001"
    await world.campaigns.transition(cid, move(CampaignState.CALIBRATING, "c"))
    intent = (
        await world.campaigns.transition(
            cid, move(CampaignState.AT_PROPOSAL, "d", launch=LaunchRequest(CycleKind.INCREMENT))
        )
    ).intent
    blocked = first_refusal(
        await world.campaigns.get_campaign(cid),
        intent,
        LaunchVerdict(LaunchRefusal.SUPERVISOR_HOLDS_THE_BOX, ("held",)),
        actor="launcher",
    )
    await world.campaigns.transition(
        cid,
        dataclasses.replace(blocked, next_state=CampaignState.ESCALATED, idempotency_key="esc"),
    )

    resp = _control(world, "resume", "r1")

    assert resp.status_code == 200
    assert resp.json()["campaign"]["state"] == "launch_blocked"
    assert [i.state.value for i in await world.campaigns.launch_intents(cid)] == ["pending"]
