"""``/api/v1/campaigns`` (SIP-0109 §13, #1799), with the real authorization adapter.

Entered at the HTTP surface, over the memory registries the runtime's Postgres twins mirror, with
the identity injected as the auth middleware would set it. Each test names the bug it catches:
a scope the owner's ruling withholds granted anyway, an actor taken from the request body, a
refusal not recorded, a resume to the wrong state, an abort that leaves a launched cycle running.
"""

from __future__ import annotations

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
from squadops.campaigns.models import CampaignState, CycleKind, LaunchRequest
from tests.unit.campaigns.builders import cycle_for, move

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
    crew_ruling_bound_s=1800,
    owner_ruling_bound_s=43200,
    lease_expiry_s=3600,
    launch_blocked_interval_s=300,
    launch_blocked_attempts=6,
    calibration_profile="validated-fullstack",
    proposal_profile="group-run-proposal",
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
        (Role.CAMPAIGN_SUPERVISOR, 403, 200, 403, 403, 200),
        (Role.CAMPAIGN_TRIAGE, 403, 403, 403, 403, 200),
        (Role.OPERATOR, 403, 403, 403, 403, 200),
    ],
)
async def test_each_role_holds_exactly_the_operations_the_ruling_gives_it(
    world, role, create, pause, resume, abort, read
):
    """Bug caught: the crew's supervisor able to create, resume after a limit, or abort — or
    the read-only seats able to steer. The owner's ruling of 2026-10-02, route by route."""
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

    [launched] = await CampaignLauncher(world.campaigns, world.cycles, build, actor="l1").drain()

    resp = _control(world, "abort", "k-abort").json()

    assert resp["cancelled_cycles"] == [launched.cycle_id]
    assert (await world.cycles.get_cycle(launched.cycle_id)).cancelled
    assert (resp["campaign"]["state"], resp["campaign"]["outcome"]) == ("completed", "aborted")


def test_an_invalid_policy_is_a_422_not_a_500(world):
    """Bug caught: a policy the domain refuses (a zero cycle limit) surfacing as a crash."""
    resp = _create(world, policy={**_POLICY, "max_cycles": 0})
    assert resp.status_code == 422
    assert "max_cycles must be >= 1" in resp.json()["detail"]["error"]["message"]


def test_an_unknown_campaign_is_a_404(world):
    resp = world.client.get("/api/v1/campaigns/cmp_missing")
    assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (404, "CAMPAIGN_NOT_FOUND")
