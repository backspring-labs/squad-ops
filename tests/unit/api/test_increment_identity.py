"""#2578 part 2: a campaign cycle's ``increment_id``, set by the launcher from the launch's own
binding, entering at ``CampaignLaunchService.drain()`` as the runtime's sweep calls it.

The column is a projection of the control log, which stays the campaign's source of truth (the
MacBook lane's G4, point 3): every launched cycle's ``increment_id`` is the proposal id its own
launch names, and a calibration's is empty.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from adapters.cycles.factory import create_project_registry, create_squad_profile_port
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.api.campaign_launch import CampaignLaunchService
from squadops.api.routes.cycles.cycles import CreationPorts
from squadops.campaigns.launch_requests import (
    CONTINUED_KEYS,
    bound_launch,
    calibration_launch,
    increment_launch,
)
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    CycleKind,
    LaunchIntentState,
    LaunchRequest,
)
from tests.unit.campaigns.builders import campaign, move, quiet_box

S = CampaignState
CID = "cmp_incident0001"


class _Executor:
    async def execute_cycle(self, *_args, **_kwargs) -> None:
        return None


class _Deploys:
    async def latest(self):
        return None


def _service(campaigns: MemoryCampaignRegistry, cycles: MemoryCycleRegistry):
    return CampaignLaunchService(
        campaigns=campaigns,
        creation=CreationPorts(
            project_registry=create_project_registry("config"),
            squad_profile=create_squad_profile_port("config"),
            cycle_registry=cycles,
            deploy_registry=_Deploys(),
        ),
        flow_executor=_Executor(),
        event_bus=MagicMock(),
        box_verdict=quiet_box,
    )


def _block(request: LaunchRequest) -> dict:
    return request.cycle_request["body"]["execution_overrides"]["campaign_proposal"]


@pytest.fixture(autouse=True)
def _sandbox_provider(monkeypatch):
    """#1568: the create-time sandbox preflight reads the provider from the process env, and the
    provider is required; compose sets it on the runtime API, as the create route's tests do."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


@pytest.fixture
async def campaigns() -> MemoryCampaignRegistry:
    reg = MemoryCampaignRegistry()
    await reg.create_campaign(
        campaign(CID), actor="owner", actor_role="owner", reason="r", idempotency_key="create-1"
    )
    return reg


async def test_each_launched_cycle_names_the_increment_its_own_launch_binds(campaigns):
    """Entry: ``drain()``, over intents the real builders wrote (``calibration_launch``,
    ``increment_launch``, ``bound_launch`` with part 1's allow-list). Bug caught: the column
    left empty on a campaign's increment, set on its calibration, or a repair's naming another
    increment than the one its binding continues, so a reader grouping cycles by increment
    reads the wrong set."""
    cycles = MemoryCycleRegistry()
    service = _service(campaigns, cycles)
    at_base = campaign(
        CID, accepted=AcceptedTree(identity="tree_base0001", cycle_id="cyc_base0001")
    )

    await campaigns.transition(
        CID, move(S.CALIBRATING, "k-cal", launch=calibration_launch(at_base))
    )
    increment = increment_launch(at_base, baseline_manifest="the accepted manifest")
    await campaigns.transition(CID, move(S.AT_PROPOSAL, "k-inc", launch=increment))
    continued = {k: v for k, v in _block(increment).items() if k in CONTINUED_KEYS}
    repair = bound_launch(
        at_base,
        CycleKind.REPAIR,
        {**continued, "continues": "cyc_failed0001", "repair_of": "cyc_failed0001"},
        plan_artifact_refs=[],
        contract_ref=None,
    )
    await campaigns.transition(CID, move(S.AT_PROPOSAL, "k-rep", launch=repair))

    await service.drain()

    intents = await campaigns.launch_intents(CID)
    assert [i.state for i in intents] == [LaunchIntentState.LAUNCHED] * 3
    named = {i.cycle_kind: (await cycles.get_cycle(i.cycle_id)).increment_id for i in intents}
    proposal_id = _block(increment)["proposal_id"]
    assert named == {
        CycleKind.CALIBRATION: None,
        CycleKind.INCREMENT: proposal_id,
        CycleKind.REPAIR: proposal_id,
    }
    # The projection, as the G4 asks: each column equals the proposal its launch row names.
    for intent in intents:
        block = intent.cycle_request["body"]["execution_overrides"].get("campaign_proposal")
        expected = block["proposal_id"] if block else None
        assert (await cycles.get_cycle(intent.cycle_id)).increment_id == expected


async def test_a_launch_whose_binding_names_no_proposal_escalates_and_creates_no_cycle(
    campaigns,
):
    """The edge: an increment intent whose block lost its ``proposal_id``. Bug caught: its cycle
    created belonging to no increment, silently, or the fault repeating on every drain instead
    of escalating the campaign, since no re-drain can supply what the intent lacks."""
    cycles = MemoryCycleRegistry()
    service = _service(campaigns, cycles)
    at_base = campaign(
        CID, accepted=AcceptedTree(identity="tree_base0001", cycle_id="cyc_base0001")
    )
    increment = increment_launch(at_base, baseline_manifest="the accepted manifest")
    del _block(increment)["proposal_id"]
    await campaigns.transition(CID, move(S.CALIBRATING, "k-cal"))
    await campaigns.transition(CID, move(S.AT_PROPOSAL, "k-inc", launch=increment))

    await service.drain()

    assert await cycles.list_cycles("group_run") == []
    assert (await campaigns.get_campaign(CID)).state is CampaignState.ESCALATED


@pytest.mark.parametrize("field", ["increment_id", "campaign_id", "kind"])
def test_a_standalone_create_cannot_name_an_increment_or_a_campaign(field):
    """The MacBook lane's G4, point 1: these are the launcher's keywords to ``prepare_cycle``,
    never a client's. Bug caught: the create request gaining the field, so a standalone cycle
    could claim to be some campaign's increment, and the column would no longer be the control
    log's projection."""
    import pydantic

    from squadops.api.cycle_schemas import CycleCreateRequest

    with pytest.raises(pydantic.ValidationError) as refused:
        CycleCreateRequest(**{field: "a value a client chose"})

    assert any(
        e["type"] == "extra_forbidden" and e["loc"] == (field,) for e in refused.value.errors()
    )
