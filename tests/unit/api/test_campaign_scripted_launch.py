"""A scripted Campaign's cycles, each answered from its own script (SIP-0109 §24dt, #2892).

Wiring, entered at ``CampaignLaunchService.drain()`` as the runtime's sweep calls it, over intents
the real builders wrote (``calibration_launch``, ``increment_launch``, ``bound_launch``). What the
launch binds is read where the agent reads it: the cycle's resolved config, as the task plan puts
it on each envelope (``resolved_config``), through ``LLMCallScope.from_envelope`` into the
scripted provider. So a Campaign of several increments can give each increment a different
change, and the one launch the policy has no script for is refused by name.
"""

from __future__ import annotations

import textwrap
from unittest.mock import MagicMock

import pytest

from adapters.cycles.factory import create_project_registry, create_squad_profile_port
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.llm.script_positions import InProcessScriptPositions
from adapters.llm.scripted import ScriptedLLMAdapter
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
    ControlOperation,
    CycleKind,
    LaunchIntentState,
)
from squadops.llm.call_scope import LLMCallScope, use_llm_call_scope
from squadops.llm.models import ChatMessage
from squadops.llm.script import ScriptLibrary, script_version
from squadops.tasks.models import TaskEnvelope
from tests.unit.campaigns.builders import campaign, move, policy, quiet_box

pytestmark = [pytest.mark.domain_orchestration]

S = CampaignState
CID = "cmp_scripted0001"


def _script(name: str, change: str) -> str:
    return textwrap.dedent(
        f"""\
        script: {name}
        description: one cycle of a scripted campaign, {change}
        answers:
          - task_type: development.develop
            occurrence: 1
            call: 1
            content: "{change}"
        """
    )


CHANGES = {"shelf-c1": "calibrate", "shelf-c2": "add search", "shelf-c3": "repair search"}


@pytest.fixture
def library(tmp_path, monkeypatch) -> ScriptLibrary:
    """The deploy's packaged library, holding the campaign's three scripts. The create-time
    preflight reads ``ScriptLibrary.packaged()``, so it is the packaged directory that moves."""
    for name, change in CHANGES.items():
        (tmp_path / f"{name}.yaml").write_text(_script(name, change))
    monkeypatch.setattr("squadops.llm.script.PACKAGED_SCRIPTS_DIR", tmp_path)
    return ScriptLibrary(tmp_path)


def _pinned(library: ScriptLibrary, name: str) -> str:
    return f"{name}@{script_version((library.directory / f'{name}.yaml').read_bytes())}"


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


@pytest.fixture(autouse=True)
def _sandbox_provider(monkeypatch):
    """#1568: the create-time sandbox preflight reads the provider from the process env."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


async def _scripted_campaign(scripts: list[str]):
    """A sample application's campaign on the shipped ``machinery`` squad, its accepted tree a
    cycle's, so each builder writes a launch it would write live."""
    reg = MemoryCampaignRegistry()
    created = campaign(
        CID,
        policy=policy(squad_profile="machinery", llm_scripts=scripts),
        accepted=AcceptedTree(identity="tree_base0001", cycle_id="cyc_base0001"),
    )
    await reg.create_campaign(
        created, actor="owner", actor_role="owner", reason="r", idempotency_key="create-1"
    )
    return reg, created


async def _answer(adapter: ScriptedLLMAdapter, cycle) -> str:
    """The first development answer of ``cycle``, asked as its agent asks: the scope read from an
    envelope carrying the cycle's resolved config (task_plan's ``resolved_config`` input)."""
    envelope = TaskEnvelope(
        task_id=f"task-{cycle.cycle_id}-m001-development.develop",
        agent_id="neo",
        cycle_id=cycle.cycle_id,
        pulse_id="p",
        project_id=cycle.project_id,
        task_type="development.develop",
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
        inputs={"resolved_config": cycle.resolved_config()},
    )
    with use_llm_call_scope(LLMCallScope.from_envelope(envelope)):
        reply = await adapter.chat([ChatMessage(role="user", content="build")], model="scripted")
    return reply.content


async def test_each_cycle_a_scripted_campaign_launches_is_answered_from_its_own_script(library):
    """Bug caught: every cycle of a scripted campaign answered from one script, which keys only by
    task type within a cycle, so each increment makes the first increment's change again (and is
    refused once its criterion already passes on the head). Or a repair taking its increment's
    script rather than its own place in the order, so it replays the failing build."""
    scripts = [_pinned(library, name) for name in CHANGES]
    campaigns, created = await _scripted_campaign(scripts)
    cycles = MemoryCycleRegistry()
    await campaigns.transition(
        CID, move(S.CALIBRATING, "k-cal", launch=calibration_launch(created))
    )
    increment = increment_launch(created, baseline_manifest="the accepted manifest")
    await campaigns.transition(CID, move(S.AT_PROPOSAL, "k-inc", launch=increment))
    block = increment.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    repair = bound_launch(
        created,
        CycleKind.REPAIR,
        {
            **{k: v for k, v in block.items() if k in CONTINUED_KEYS},
            "continues": "cyc_failed0001",
            "repair_of": "cyc_failed0001",
        },
        plan_artifact_refs=[],
        contract_ref=None,
    )
    await campaigns.transition(CID, move(S.AT_PROPOSAL, "k-rep", launch=repair))

    await _service(campaigns, cycles).drain()

    intents = await campaigns.launch_intents(CID)
    assert [(i.cycle_kind, i.state) for i in intents] == [
        (CycleKind.CALIBRATION, LaunchIntentState.LAUNCHED),
        (CycleKind.INCREMENT, LaunchIntentState.LAUNCHED),
        (CycleKind.REPAIR, LaunchIntentState.LAUNCHED),
    ]
    launched = [await cycles.get_cycle(i.cycle_id) for i in intents]
    assert [c.resolved_config()["llm_script"] for c in launched] == scripts
    adapter = ScriptedLLMAdapter(library, InProcessScriptPositions())
    assert [await _answer(adapter, c) for c in launched] == list(CHANGES.values())


async def test_a_launch_past_the_last_script_escalates_naming_it_and_creates_no_cycle(library):
    """The edge: a campaign that names one script launching its second cycle. Bug caught: the
    second cycle created with no script, or the first one's, so it answers from answers recorded
    for another cycle; or the gap found only at the first model call, hours into the run, instead
    of at the launch, by name."""
    campaigns, created = await _scripted_campaign([_pinned(library, "shelf-c1")])
    cycles = MemoryCycleRegistry()
    await campaigns.transition(
        CID, move(S.CALIBRATING, "k-cal", launch=calibration_launch(created))
    )
    await campaigns.transition(
        CID,
        move(
            S.AT_PROPOSAL,
            "k-inc",
            launch=increment_launch(created, baseline_manifest="the accepted manifest"),
        ),
    )

    await _service(campaigns, cycles).drain()

    calibration, increment = await campaigns.launch_intents(CID)
    assert (calibration.state, increment.state) == (
        LaunchIntentState.LAUNCHED,
        LaunchIntentState.PENDING,
    )
    assert len(await cycles.list_cycles("group_run")) == 1
    assert (await campaigns.get_campaign(CID)).state is CampaignState.ESCALATED
    escalation = [
        e
        for e in await campaigns.control_log(CID)
        if e.operation is ControlOperation.LAUNCH_REFUSED
    ]
    assert len(escalation) == 1
    assert "LLM_SCRIPT_MISSING" in escalation[0].reason
    assert f"campaign {CID}'s launch 2 has no script: its llm_scripts names 1" in (
        escalation[0].reason
    )


async def test_the_place_in_the_order_is_read_from_the_control_log_not_remembered(library):
    """Bug caught: the launch's place counted in the launching process, so after a restart of the
    runtime (the soak's controlled restart) the next increment takes the first script again and
    rebuilds the first increment's change."""
    scripts = [_pinned(library, name) for name in CHANGES]
    campaigns, created = await _scripted_campaign(scripts)
    cycles = MemoryCycleRegistry()
    await campaigns.transition(
        CID, move(S.CALIBRATING, "k-cal", launch=calibration_launch(created))
    )
    await _service(campaigns, cycles).drain()  # the process before the restart

    await campaigns.transition(
        CID,
        move(
            S.AT_PROPOSAL,
            "k-inc",
            launch=increment_launch(created, baseline_manifest="the accepted manifest"),
        ),
    )
    await _service(campaigns, cycles).drain()  # a fresh process, after it

    second = (await campaigns.launch_intents(CID))[1]
    assert second.state is LaunchIntentState.LAUNCHED
    assert (await cycles.get_cycle(second.cycle_id)).resolved_config()["llm_script"] == scripts[1]
