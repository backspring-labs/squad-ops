"""``/api/v1/box/lease``: the operator's lease on the box, outside every campaign (SIP-0109
§24dw; #2287). Entered at the HTTP surface with the real authorization adapter, over the memory
registry the runtime's Postgres twin mirrors, with the identity injected as the auth middleware
sets it. Each test names the bug it catches."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.box import router
from squadops.auth.models import Role
from squadops.campaigns.box import LeaseHolder
from squadops.campaigns.models import CampaignState, CampaignTransition, ControlOperation
from tests.unit.api.test_campaign_routes import _Audit, _identity
from tests.unit.campaigns.builders import campaign, move

pytestmark = pytest.mark.auth

URL = "/api/v1/box/lease"


class _Box:
    """The box reader: the runs running or queued on it, set by the test."""

    def __init__(self) -> None:
        self.runs: tuple[str, ...] = ()

    async def runs_running_or_queued(self) -> tuple[str, ...]:
        return self.runs


class _World:
    def __init__(self) -> None:
        self.campaigns = MemoryCampaignRegistry()
        self.audit = _Audit()
        self.box = _Box()
        self.identity = _identity(Role.ADMIN, user="ada")
        app = FastAPI()
        world = self

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = world.identity
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(router)
        register_domain_error_handlers(app)
        app.state.campaign_registry = self.campaigns
        app.state.box_reader = self.box
        app.state.authz_port = KeycloakAuthzAdapter()
        app.state.audit_port = self.audit
        self.client = TestClient(app)

    def take(self, key: str, *, reason: str = "local model session", expires_in_s: int = 1800):
        return self.client.post(
            URL, json={"reason": reason, "idempotency_key": key, "expires_in_s": expires_in_s}
        )

    def give_back(self, key: str):
        return self.client.post(
            f"{URL}/release", json={"reason": "session over", "idempotency_key": key}
        )


@pytest.fixture
def world() -> _World:
    return _World()


def test_the_operator_takes_the_box_renews_it_and_gives_it_back_with_every_row_kept(world):
    """Bugs caught: a lease route that changes nothing; a renewal that restarts the lease's
    acquisition; a retry under the same key acting twice, or a key reused for another change
    taken as a retry; another admin giving back a box the operator holds; a change that never
    reaches the security audit."""
    taken = world.take("t1")
    renewed = world.take("t2", expires_in_s=3600)
    retried = world.take("t2", expires_in_s=3600)
    reused = world.take("t2", reason="another session")
    world.identity = _identity(Role.ADMIN, user="grace")
    not_hers = world.give_back("g1")
    world.identity = _identity(Role.ADMIN, user="ada")
    given = world.give_back("r1")
    read = world.client.get(URL)

    assert taken.status_code == 200, taken.json()
    lease = taken.json()["lease"]
    assert (lease["holder"], lease["held_by"], lease["campaign_id"], lease["operator_holds"]) == (
        "operator", "ada", None, True
    )  # fmt: skip
    assert renewed.json()["lease"]["acquired_at"] == lease["acquired_at"]
    assert renewed.json()["lease"]["expires_at"] > lease["expires_at"]
    assert (retried.status_code, retried.json()["replayed"]) == (200, True)
    assert reused.status_code == 409
    assert reused.json()["detail"]["error"]["details"]["refusal"] == "conflicting_idempotency_key"
    assert not_hers.status_code == 409
    assert not_hers.json()["detail"]["error"]["details"]["refusal"] == "not_lease_holder"
    assert (given.json()["lease"]["holder"], given.json()["lease"]["operator_holds"]) == (
        "squad", False
    )  # fmt: skip
    body = read.json()
    assert body["lease"]["holder"] == "squad"
    assert [(e["seq"], e["operation"], e["outcome"], e["refusal"]) for e in body["log"]] == [
        (4, "release", "applied", None),
        (3, "release", "refused", "not_lease_holder"),
        (2, "acquire", "applied", None),
        (1, "acquire", "applied", None),
    ]
    assert [(e.action, e.result) for e in world.audit.events] == [
        ("box.lease_acquire", "success"),
        ("box.lease_acquire", "success"),
        ("box.lease_acquire", "denied"),
        ("box.lease_release", "denied"),
        ("box.lease_release", "success"),
    ]


async def _supervisor_holds(world: _World) -> None:
    await world.campaigns.create_campaign(
        campaign("cmp_gate00000001"), actor="o", actor_role="o", reason="r", idempotency_key="c"
    )
    for i, state in enumerate(("calibrating", "at_proposal", "awaiting_ruling")):
        await world.campaigns.transition("cmp_gate00000001", move(CampaignState(state), f"g{i}"))
    await world.campaigns.change_box_lease(
        "cmp_gate00000001",
        CampaignTransition(
            operation=ControlOperation.LEASE_ACQUIRE, actor="sup", actor_role="campaign-supervisor",
            reason="gate", idempotency_key="sup", next_state=None,
            binding={"held_by": "sup", "expires_in_s": 900},
        ),
        runs_in_flight=(),
    )  # fmt: skip
    # Paused at its gate, so only the supervisor's lease refuses the operator.
    await world.campaigns.transition("cmp_gate00000001", move(CampaignState.PAUSED, "p"))


async def _live(world: _World, state: str) -> None:
    await world.campaigns.create_campaign(
        campaign("cmp_live00000001"), actor="o", actor_role="o", reason="r", idempotency_key="l"
    )
    path = {"calibrating": ("calibrating",), "paused": ("calibrating", "paused"),
            "escalated": ("calibrating", "escalated")}[state]  # fmt: skip
    for i, s in enumerate(path):
        await world.campaigns.transition("cmp_live00000001", move(CampaignState(s), f"m{i}"))


@pytest.mark.parametrize(
    ("setup", "refusal", "read"),
    [
        ("queued", "run_in_flight", ["run run_queued"]),
        ("calibrating", "campaign_live", ["campaign cmp_live00000001 is calibrating"]),
        ("supervisor", "box_held", ["the supervisor (sup) holds the box until"]),
        ("paused", None, []),
        ("escalated", None, []),
    ],
)
async def test_the_box_is_taken_only_when_nothing_could_run_on_it(world, setup, refusal, read):
    """Bugs caught: the operator taking the box under a queued run, which starts the moment the
    lease ends; or beside a live campaign, which launches into it; or from a supervisor at its
    gate. A campaign held for a person launches nothing, so it doesn't refuse it."""
    if setup == "queued":
        world.box.runs = ("run_queued",)
    elif setup == "supervisor":
        await _supervisor_holds(world)
    else:
        await _live(world, setup)

    response = world.take("t1")

    if refusal is None:
        assert response.status_code == 200, response.json()
        assert response.json()["lease"]["operator_holds"] is True
        return
    assert response.status_code == 409
    details = response.json()["detail"]["error"]["details"]
    assert (details["refusal"], details["seq"]) == (refusal, 1)
    assert [r[: len(w)] for r, w in zip(details["reasons"], read, strict=True)] == read
    lease = await world.campaigns.box_lease()
    assert lease is None or lease.holder is not LeaseHolder.OPERATOR


@pytest.mark.parametrize(
    ("role", "expires_in_s", "status"),
    [(Role.OPERATOR, 900, 403), (Role.CAMPAIGN_SUPERVISOR, 900, 403), (Role.ADMIN, 3601, 422)],
    ids=["an operator role without box:operate", "a campaign's supervisor", "past an hour"],
)
async def test_a_change_without_box_operate_or_past_an_hour_is_refused_before_anything_is_written(
    world, role, expires_in_s, status
):
    """Bugs caught: the lease granted by campaigns:supervise, which is a campaign's; a person
    without box:operate taking the box; a lease longer than the bound, so a crashed operator
    holds the box for good."""
    world.identity = _identity(role, user="someone")

    response = world.take("t1", expires_in_s=expires_in_s)

    assert response.status_code == status
    assert (await world.campaigns.operator_lease_log(), await world.campaigns.box_lease()) == (
        [], None
    )  # fmt: skip
