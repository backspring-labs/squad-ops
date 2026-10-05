"""A campaign starts: its calibration cycle is launched by the cycle-create path (SIP-0109 §11,
§12b, §17; #1709).

Entered at ``POST /api/v1/campaigns/{id}/start``, with the real launch service over the memory
campaign and cycle registries, the config project and squad-profile registries, and the real
request profiles; the executor is a recorder. What the launch leaves is read back: the cycle, its
first run, and what was started.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.factory import create_project_registry, create_squad_profile_port
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.api.campaign_launch import CampaignLaunchService
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.campaigns import campaigns_router
from squadops.api.routes.cycles.cycles import CreationPorts
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.models import CampaignState, ControlOperation, LaunchIntentState
from tests.unit.campaigns.builders import campaign, policy, quiet_box

pytestmark = pytest.mark.auth

CID = "cmp_start0000001"


class _Executor:
    def __init__(self) -> None:
        self.started: list[tuple[str, str, str]] = []
        self.reentered: list[tuple[str, str]] = []

    async def execute_cycle(
        self, cycle_id: str, run_id: str, squad_profile_id: str, *, reentry: bool = False
    ) -> None:
        if reentry:
            self.reentered.append((cycle_id, run_id))
            return
        self.started.append((cycle_id, run_id, squad_profile_id))


class _Deploys:
    async def latest(self):
        return None


class _World:
    def __init__(self, campaigns: MemoryCampaignRegistry | None = None) -> None:
        self.campaigns = campaigns or MemoryCampaignRegistry()
        self.cycles = MemoryCycleRegistry()
        self.executor = _Executor()
        self.launch = CampaignLaunchService(
            campaigns=self.campaigns,
            creation=CreationPorts(
                project_registry=create_project_registry("config"),
                squad_profile=create_squad_profile_port("config"),
                cycle_registry=self.cycles,
                deploy_registry=_Deploys(),
            ),
            flow_executor=self.executor,
            event_bus=MagicMock(),
            box_verdict=quiet_box,
        )
        self.seat = (Role.ADMIN, "owner")
        app = FastAPI()
        world = self

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                role, user = world.seat
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
        register_domain_error_handlers(app)
        app.state.campaign_registry = self.campaigns
        app.state.cycle_registry = self.cycles
        app.state.campaign_launch = self.launch
        app.state.authz_port = KeycloakAuthzAdapter()
        self.client = TestClient(app)

    def start(self, key: str = "start-1"):
        return self.client.post(
            f"/api/v1/campaigns/{CID}/start",
            json={"reason": "the 2.0 shakeout", "idempotency_key": key},
        )


@pytest.fixture(autouse=True)
def _sandbox_provider(monkeypatch):
    """#1568: the create-time sandbox preflight reads the provider from the process env, and the
    provider is required; compose sets it on the runtime API, as the create route's tests do."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


@pytest.fixture
async def world() -> _World:
    w = _World()
    await w.campaigns.create_campaign(
        campaign(CID, policy=policy(calibration_profile="framing", squad_profile="full-38")),
        actor="owner",
        actor_role="admin",
        reason="r",
        idempotency_key="create",
    )
    return w


async def test_a_start_launches_the_calibration_cycle_by_the_cycle_create_path(world):
    """§11, §12b. Bugs caught: a start that moves the campaign and launches nothing; a launched
    cycle that names no campaign (the decision at its end could not find its campaign); or a
    cycle record with no run, which the executor never starts."""
    resp = world.start()
    await asyncio.sleep(0)  # the started execution task runs

    body = resp.json()
    [intent] = await world.campaigns.launch_intents(CID)
    [cycle_id] = body["launched_cycles"]
    cycle = await world.cycles.get_cycle(cycle_id)
    [run] = await world.cycles.list_runs(cycle_id)
    assert resp.status_code == 200
    assert body["campaign"]["state"] == CampaignState.CALIBRATING
    assert (intent.state, intent.cycle_id) == (LaunchIntentState.LAUNCHED, cycle_id)
    assert (cycle.campaign_id, cycle.kind, cycle.request_profile) == (CID, "calibration", "framing")
    assert (cycle.squad_profile_id, cycle.created_by) == ("full-38", "campaign-launcher")
    assert (run.run_number, run.status, run.workload_type) == (1, "queued", "framing")
    assert world.executor.started == [(cycle_id, run.run_id, "full-38")]


async def test_the_supervisor_starts_a_campaign_and_its_row_names_the_supervisor(world):
    """#1940: the crew dispatches. Bug caught: the supervisor's start refused, or recorded under
    another actor than the token's. Entered at the start route, through the real launch service."""
    world.seat = (Role.CAMPAIGN_SUPERVISOR, "ripley")

    resp = world.start()
    await asyncio.sleep(0)

    [cycle_id] = resp.json()["launched_cycles"]
    [started] = [
        e for e in await world.campaigns.control_log(CID) if e.operation is ControlOperation.START
    ]
    assert resp.status_code == 200
    assert (started.actor, started.actor_role) == ("ripley", Role.CAMPAIGN_SUPERVISOR)
    assert world.executor.started[0][0] == cycle_id


async def test_a_repeated_start_and_a_second_drain_launch_nothing_more(world):
    """§12b: exactly one cycle per intent. Bug caught: a replayed start, or the startup drain
    after it, creating a second calibration cycle or starting its run twice."""
    world.start()
    again = world.start()
    await world.launch.drain()
    await asyncio.sleep(0)

    cycles = await world.cycles.list_cycles("group_run")
    assert again.json()["replayed"] is True
    assert len(cycles) == 1
    assert len(world.executor.started) == 1


async def test_a_campaign_that_is_not_a_draft_refuses_the_start(world):
    world.start()
    resp = world.start(key="start-2")

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["details"]["refusal"] == "stale_state"
    assert len(await world.campaigns.launch_intents(CID)) == 1


async def test_a_policy_naming_a_profile_that_does_not_exist_cannot_start():
    w = _World()
    await w.campaigns.create_campaign(
        campaign(CID, policy=policy(calibration_profile="no-such-profile")),
        actor="owner",
        actor_role="admin",
        reason="r",
        idempotency_key="create",
    )

    resp = w.start()

    assert resp.status_code == 422
    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.DRAFT


class _MarkFailsOnce(MemoryCampaignRegistry):
    """A crash after the cycle is created and before its intent is marked launched."""

    def __init__(self) -> None:
        super().__init__()
        self.failed = False

    async def mark_launch_intent_launched(self, launch_id, cycle_id, *, actor):
        if not self.failed:
            self.failed = True
            raise ConnectionError("the process died here")
        return await super().mark_launch_intent_launched(launch_id, cycle_id, actor=actor)


async def test_a_launch_interrupted_before_its_mark_is_finished_by_the_next_drain():
    """§12b, crash after the cycle exists and before the mark. Bug caught: the re-drain
    creating a second cycle, or the found cycle left without its first run."""
    w = _World(_MarkFailsOnce())
    await w.campaigns.create_campaign(
        campaign(CID, policy=policy(calibration_profile="framing", squad_profile="full-38")),
        actor="owner",
        actor_role="admin",
        reason="r",
        idempotency_key="create",
    )

    first = w.start()
    await w.launch.drain()
    await asyncio.sleep(0)

    [cycle] = await w.cycles.list_cycles("group_run")
    [intent] = await w.campaigns.launch_intents(CID)
    assert first.json()["launched_cycles"] == []
    assert (intent.state, intent.cycle_id) == (LaunchIntentState.LAUNCHED, cycle.cycle_id)
    assert len(await w.cycles.list_runs(cycle.cycle_id)) == 1
    assert len(w.executor.started) == 1


async def test_a_restarted_process_starts_a_first_run_left_queued(world):
    """§12b, crash after the first run is created and before it starts: a new process's drain
    starts it, once. Bug caught: a queued first run nobody ever starts — a campaign that waits
    for a cycle that will never move."""
    world.start()
    restarted = CampaignLaunchService(
        campaigns=world.campaigns,
        creation=world.launch._creation,
        flow_executor=world.executor,
        event_bus=MagicMock(),
        box_verdict=quiet_box,
    )

    await restarted.drain()
    await restarted.drain()
    await asyncio.sleep(0)

    [cycle] = await world.cycles.list_cycles("group_run")
    [run] = await world.cycles.list_runs(cycle.cycle_id)
    # Once by the process that died before its run moved, once by the restart, never again.
    assert world.executor.started == [(cycle.cycle_id, run.run_id, "full-38")] * 2


@pytest.mark.parametrize(
    ("left", "taken_up"),
    [
        (("running", "completed"), True),  # stopped at its gate: the poller died with the process
        (("running",), True),  # a run in flight: resumed from its checkpoint
        (("running", "failed"), False),  # the campaign's to decide, by the re-hearing
    ],
    ids=["at-its-gate", "run-in-flight", "failed"],
)
async def test_a_restart_takes_up_the_campaign_cycle_it_died_inside(world, left, taken_up):
    """SIP-0109 §12a (#1922), entered at ``main._resume_campaigns``, the startup the runtime
    runs. Bugs caught: a campaign cycle whose gate poller, or whose run, died with the process,
    left with nothing to move it but ``runs retry`` or ``runs resume`` outside the interface; or a
    failed run re-run behind the campaign's decision."""
    from types import SimpleNamespace

    from squadops.api.runtime.main import _resume_campaigns
    from squadops.cycles.models import RunStatus

    world.start()
    await asyncio.sleep(0)
    [cycle] = await world.cycles.list_cycles("group_run")
    [run] = await world.cycles.list_runs(cycle.cycle_id)
    for status in left:
        await world.cycles.update_run_status(run.run_id, RunStatus(status))
    restarted = CampaignLaunchService(
        campaigns=world.campaigns,
        creation=world.launch._creation,
        flow_executor=world.executor,
        event_bus=MagicMock(),
        box_verdict=quiet_box,
    )
    progress = SimpleNamespace(rehear_ended=AsyncMock(return_value=[]))

    await _resume_campaigns(SimpleNamespace(campaign_launch=restarted, campaign_progress=progress))
    await asyncio.sleep(0)

    assert world.executor.reentered == ([(cycle.cycle_id, run.run_id)] if taken_up else [])
