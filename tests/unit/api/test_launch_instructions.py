"""A campaign launch's task instructions are its cycle's admitted inputs (SIP-0110 Appendix A §3.5;
#2178), stored by the cycle-create path a launch shares with the route (``prepare_cycle``).

Entered where the launcher builds a cycle (``CampaignLaunchService._build_cycle``), from the intent
a campaign's start writes, with its request carrying task instructions. What bugs would these
catch? A launch whose instructions the route would store dropped because only the route stored
them; an instruction stored as an intervention though the cycle was created with it; a launch with
nowhere to store them launched without them.
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest

from adapters.cycles.factory import create_project_registry, create_squad_profile_port
from adapters.memory.records import InMemoryMemoryRecords
from squadops.api.campaign_launch import CampaignLaunchService
from squadops.api.routes.cycles.cycles import CreationPorts
from squadops.memory.task_instructions import is_intervention
from tests.unit.api.test_campaign_start import (  # noqa: F401
    _Deploys,
    _Executor,
    _sandbox_provider,
    world,
)
from tests.unit.campaigns.builders import quiet_box

pytestmark = pytest.mark.auth

INSTRUCTION = {"text": "Name each run by its route.", "task_types": ["development.design_plan"]}


def _service(w, records) -> CampaignLaunchService:
    return CampaignLaunchService(
        campaigns=w.campaigns,
        creation=CreationPorts(
            project_registry=create_project_registry("config"),
            squad_profile=create_squad_profile_port("config"),
            cycle_registry=w.cycles,
            deploy_registry=_Deploys(),
            memory_records=records,
        ),
        flow_executor=_Executor(),
        event_bus=MagicMock(),
        box_verdict=quiet_box,
    )


async def _instructed_intent(w):
    """The calibration intent a start writes, its request carrying one task instruction."""
    w.start()
    [intent] = await w.campaigns.launch_intents("cmp_start0000001")
    body = {**intent.cycle_request["body"], "task_instructions": [INSTRUCTION]}
    return dataclasses.replace(intent, cycle_request={**intent.cycle_request, "body": body})


async def test_a_launchs_task_instructions_are_stored_as_its_cycles_admitted_inputs(world):  # noqa: F811
    records = InMemoryMemoryRecords()
    intent = await _instructed_intent(world)

    cycle = await _service(world, records)._build_cycle(intent)

    [record] = await records.list_project(cycle.project_id)
    assert record.current.target.cycle_id == cycle.cycle_id
    assert record.current.body == INSTRUCTION["text"]
    assert not is_intervention(record)
    assert record.current.confirmed_by == "campaign-launcher"


async def test_a_launch_with_instructions_and_no_store_is_a_fault_the_drain_repeats(world):  # noqa: F811
    """Bug caught: the launch going ahead without the instructions it was given, the cycle's
    first run built as if it had none."""
    intent = await _instructed_intent(world)

    with pytest.raises(RuntimeError, match="no store holds them"):
        await _service(world, None)._build_cycle(intent)


@pytest.mark.parametrize("resolver", [None, "fake"], ids=["no-resolver", "a-resolver"])
async def test_a_launchs_current_reference_is_bound_with_its_cycle_or_the_launch_refused(
    world,  # noqa: F811
    resolver,
):
    """T16's task part, entered at the launcher (the second read). Bugs caught: a campaign's
    launch storing ``@current`` as written, or launching without the instruction when it can't
    be bound, rather than refused so the campaign escalates; the launcher's ports lacking the
    resolvers the route has."""
    from squadops.campaigns.launcher import LaunchRefused
    from tests.unit.memory.test_reference_binding import _Resolver

    records = InMemoryMemoryRecords()
    given = {**INSTRUCTION, "references": [{"ref": "fake:doc:spec@current", "required": False}]}
    w = world
    w.start()
    [intent] = await w.campaigns.launch_intents("cmp_start0000001")
    body = {**intent.cycle_request["body"], "task_instructions": [given]}
    intent = dataclasses.replace(intent, cycle_request={**intent.cycle_request, "body": body})
    service = _service(w, records)
    if resolver:
        service._creation = dataclasses.replace(
            service._creation, reference_resolvers={resolver: _Resolver()}
        )
        cycle = await service._build_cycle(intent)
        [record] = await records.list_project(cycle.project_id)
        assert [r.ref for r in record.current.references] == ["fake:doc:spec@r1"]
    else:
        with pytest.raises(LaunchRefused, match="no resolver binds the fake family"):
            await service._build_cycle(intent)
        assert await records.list_project("group_run") == []
