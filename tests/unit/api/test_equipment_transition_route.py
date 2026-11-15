"""``POST /api/v1/campaigns/{id}/equipment-transitions`` (SIP-0116 §10, phase 5, #3037), entered at
the route with the real authorization adapter and the runtime's error handlers: the owner's
recorded transition to the equipment a refused launch found.

The pin and the refused launch's rows are written as the launch service writes them; the launch
itself is ``test_campaign_equipment_pin.py``'s."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from squadops.auth.models import Role
from squadops.campaigns.equipment import equipment_digest
from squadops.campaigns.models import (
    CampaignState,
    CampaignTransition,
    ControlOperation,
    ControlOutcome,
)
from squadops.memory.lessons import UnitKind
from squadops.memory.pinning import pin_unit
from tests.unit.api.test_campaign_routes import _create, _identity, _World
from tests.unit.api.test_goal_delegation_routes import _complete

pytestmark = pytest.mark.auth

CID = "cmp_api000000001"
ROUTE = f"/api/v1/campaigns/{CID}/equipment-transitions"
PINNED = {"base_set": "base@1", "requirements": [], "assignment": [], "offered": [], "content": []}
FOUND = {**PINNED, "content": [{"skillset": "s", "skill": "play", "digest": "b" * 64}]}


class _Launches:
    """The launcher's lock, which the transition holds while it is written."""

    def __init__(self) -> None:
        self.lock = asyncio.Lock()

    def launches_held(self) -> asyncio.Lock:
        return self.lock


@pytest.fixture
def world() -> _World:
    world = _World()
    world.launches = _Launches()
    world.client.app.state.campaign_launch = world.launches
    world.store = InMemoryCrossCycleMemoryStore()
    world.client.app.state.memory_store = world.store
    assert _create(world).status_code == 201
    return world


async def _row(world, operation, key, binding) -> None:
    await world.campaigns.transition(
        CID,
        CampaignTransition(
            operation=operation, actor="campaign-launcher", actor_role="launcher",
            reason="as the launch service writes it", idempotency_key=key, next_state=None,
            target="launch-2", binding=binding,
        ),
    )  # fmt: skip


async def _pinned_and_refused(world) -> str:
    await _row(world, ControlOperation.EQUIPMENT_PINNED, "pin",
               {"digest": equipment_digest(PINNED), "equipment": PINNED, "cycle_id": "cyc_1"})  # fmt: skip
    found = equipment_digest(FOUND)
    await _row(world, ControlOperation.EQUIPMENT_CHANGED, "changed", {
        "launch_id": "launch-2", "pinned_digest": equipment_digest(PINNED), "found_digest": found,
        "equipment": FOUND, "parts": ["skill s/play: added"],
    })  # fmt: skip
    return found


def _transition(world, to_digest: str, key: str = "t-1", reason: str = "the revision is approved"):
    return world.client.post(
        ROUTE, json={"to_digest": to_digest, "reason": reason, "idempotency_key": key}
    )


def _code(resp) -> tuple[int, str]:
    return resp.status_code, resp.json()["detail"]["error"]["code"]


async def _transitions(world) -> list:
    return [
        e
        for e in await world.campaigns.control_log(CID)
        if e.operation is ControlOperation.EQUIPMENT_TRANSITION
        and e.outcome is ControlOutcome.APPLIED
    ]


async def test_the_owners_transition_accepts_exactly_what_the_refused_launch_found(world):
    """Bugs caught: a transition accepting equipment nobody saw (a digest other than the refused
    launch's), so a catalog that moved again is let through; a replay writing a second row; or
    the transition touching the Campaign's lesson snapshot."""
    snapshot = await pin_unit(
        world.store, unit_kind=UnitKind.CAMPAIGN, unit_id=CID, project_id="group_run",
        pinned_at=datetime(2026, 11, 15, tzinfo=UTC), disabled=False,
    )  # fmt: skip
    found = await _pinned_and_refused(world)

    mismatch = _transition(world, "sha256:" + "0" * 64)
    applied = _transition(world, found)
    replayed = _transition(world, found)

    assert _code(mismatch) == (409, "EQUIPMENT_DIGEST_MISMATCH")
    assert (applied.status_code, replayed.status_code) == (201, 201)
    [row] = await _transitions(world)
    assert row.binding == {
        "from_digest": equipment_digest(PINNED),
        "to_digest": found,
        "equipment": FOUND,
        "parts": ["skill s/play: added"],
    }
    assert (row.actor, row.reason) == ("owner", "the revision is approved")
    assert (await world.store.get_snapshot(UnitKind.CAMPAIGN, CID)).to_dict() == snapshot.to_dict()
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.DRAFT


@pytest.mark.parametrize(
    ("setup", "identity", "body", "expected"),
    [
        ("pinned only", Role.ADMIN, {}, (409, "EQUIPMENT_NOT_CHANGED")),
        ("refused", Role.CAMPAIGN_SUPERVISOR, {}, (403, None)),
        ("refused", Role.ADMIN, {"reason": " "}, (422, "VALIDATION_ERROR")),
        ("completed", Role.ADMIN, {}, (409, "CONTROL_OPERATION_REFUSED")),
    ],
    ids=["nothing changed", "not the owner", "no reason", "completed campaign"],
)
async def test_a_transition_with_nothing_to_accept_or_no_authority_is_refused(
    world, setup, identity, body, expected
):
    """Bugs caught: a transition recorded where no launch was refused; the operator's
    supervisor accepting equipment for itself; a transition with no reason; or one recorded on a
    campaign that has no launches left."""
    if setup == "pinned only":
        await _row(world, ControlOperation.EQUIPMENT_PINNED, "pin",
                   {"digest": equipment_digest(PINNED), "equipment": PINNED, "cycle_id": "c"})  # fmt: skip
        found = equipment_digest(FOUND)
    else:
        found = await _pinned_and_refused(world)
    if setup == "completed":
        await _complete(world)
    world.as_(_identity(identity))

    resp = world.client.post(
        ROUTE,
        json={"to_digest": found, "reason": "approved", "idempotency_key": "t-1", **body},
    )

    status, code = expected
    assert resp.status_code == status, resp.json()
    if code is not None:
        assert resp.json()["detail"]["error"]["code"] == code
    assert await _transitions(world) == []
