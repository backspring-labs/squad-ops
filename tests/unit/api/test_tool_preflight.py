"""A cycle's tools, checked at creation (SIP-0116 §8, §9; phase 4, #3036).

§14's proof: three fixtures, three distinct refusals, and an offline worker read as availability,
never as a missing skillset. Entered at ``_run_create_preflight``, which cycle creation and a
campaign's launch both call. The squad, record and catalog are the shared skillset fixture's,
with the qa skillset's scenario capability requesting a worker tool; the worker registry is the
real one on a memory store. The fixtures live in tests only.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

import pytest

from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.api.routes.cycles import cycles as route
from squadops.capabilities.skillsets import ToolRequest
from squadops.capabilities.tool_checks import AgentRemoteExecution
from squadops.cycles.skillset_coverage import cycle_coverage
from squadops.ports.tool_authority import BrokenRule
from squadops.remote_execution import leasing
from squadops.remote_execution.registry import WorkerRegistry
from tests.unit.capabilities.test_operation_supply import _catalog
from tests.unit.cycles.skillset_fixture import CONTRACTS, PROFILE, requiring_config
from tests.unit.remote_execution.registry_contract import Clock, registration

TOOL = ToolRequest("play_scenario", "fixture-editor", "worker")


class _Allows:
    async def broken_rules(self, tool, *, project_id, config, product) -> list[BrokenRule]:
        return []


class _RefusesScripts:
    """A provider whose compatibility check refuses a product with tagged scripts."""

    async def broken_rules(self, tool, *, project_id, config, product) -> list[BrokenRule]:
        return [BrokenRule("no-tagged-scripts", f"{project_id} tags 3 of its scripts")]


@pytest.fixture
def config(monkeypatch) -> dict:
    """A cycle whose work requires the fixture skillsets, the qa one requesting ``TOOL``."""
    catalog = _catalog(TOOL)
    monkeypatch.setattr(route, "packaged_skillsets", lambda: catalog)
    monkeypatch.setattr(
        route,
        "cycle_coverage",
        lambda profile, cfg, cat: cycle_coverage(profile, cfg, cat, CONTRACTS),
    )
    return {**requiring_config(monkeypatch), "required_checks": []}


async def _registry(*, online: bool) -> WorkerRegistry:
    clock = Clock()
    registry = WorkerRegistry(MemoryWorkerRegistryStore(), clock=clock)
    await registry.register(registration())
    if not online:
        clock.advance(leasing.SESSION_SILENT_SECONDS + 1)
    return registry


#: A runtime that binds remote execution: the port's presence is all the check reads (#3159).
BOUND = object()

HEARD_AT = datetime(2026, 11, 26, 15, 0)


def _agents_say(provider: str | None = "runtime_api", *, fresh: bool = True):
    """Every agent's own report of the remote execution it binds (#3235): the provider it last
    said, at a named build, heard at ``HEARD_AT``."""

    async def report(agent_id: str) -> AgentRemoteExecution:
        return AgentRemoteExecution(provider, "3f2a91c", HEARD_AT, fresh)

    return report


async def _agents_are_silent(agent_id: str) -> None:
    return None


async def _preflight(config: dict, **tools: Any) -> tuple[str, ...]:
    """Each refusal's code and message for ``config`` with ``tools``; ``()`` when created. The
    runtime binds remote execution unless a test says otherwise."""
    decision = await route._tool_preflight_decision(
        PROFILE,
        config,
        route.ToolPreflight(
            project_id="prj-1",
            **{"remote_execution": BOUND, "agent_report": _agents_say(), **tools},
        ),
    )
    return tuple(f"{f.code}: {f.message}" for f in decision.blocking)


async def test_a_tool_no_authority_governs_is_refused_as_authorization(config):
    """Bug caught: carrying a skillset read as authorizing its tool's operation."""
    [refusal] = await _preflight(config, worker_registry=await _registry(online=True))

    assert refusal.startswith("skillset_authorization: tool play_scenario (fixture-editor")
    assert "no authority governs provider fixture-editor" in refusal


async def test_a_tool_its_providers_rule_refuses_is_refused_naming_the_rule(config):
    """Bug caught: a provider's compatibility check (Studio's eligibility rules, SIP-0117 R4.6)
    asked nothing at creation, so the product fails at the first operation."""
    [refusal] = await _preflight(
        config,
        authorities={"fixture-editor": _RefusesScripts()},
        worker_registry=await _registry(online=True),
    )

    assert refusal.startswith("skillset_authorization:")
    assert "fixture-editor's rule no-tagged-scripts: prj-1 tags 3 of its scripts" in refusal


@pytest.mark.parametrize(
    ("registry", "says"),
    [
        ("offline", "fixture-editor/play_scenario and is offline"),
        ("none_serves", "no registered worker serves fixture-editor/play_scenario"),
        ("no_registry", "this runtime holds no worker registry"),
        ("unbound", "this runtime binds no remote execution (remote_execution.provider none)"),
    ],
)
async def test_a_tool_no_worker_can_run_is_refused_as_availability_never_coverage(
    config, registry, says
):
    """§14: an offline worker reads as availability, never as a missing skillset. Bugs caught:
    the squad told to carry a skillset it carries; a cycle created that stalls at its first
    operation; and a cycle created on a runtime that binds no remote execution because a worker
    is registered and online, whose every scenario then reads not executed (#3159)."""
    registries = {
        "offline": lambda: _registry(online=False),
        "none_serves": lambda: _empty_registry(),
        "no_registry": None,
        "unbound": lambda: _registry(online=True),
    }
    worker_registry = await registries[registry]() if registries[registry] else None

    [refusal] = await _preflight(
        config,
        authorities={"fixture-editor": _Allows()},
        worker_registry=worker_registry,
        remote_execution=None if registry == "unbound" else BOUND,
    )

    assert refusal.startswith("skillset_availability:")
    assert says in refusal
    assert "The squad still carries fixture-qa" in refusal


async def _empty_registry() -> WorkerRegistry:
    return WorkerRegistry(MemoryWorkerRegistryStore(), clock=Clock())


_SAID = "at revision 3f2a91c, last heard at 2026-11-26T15:00:00"


@pytest.mark.parametrize(
    ("agent_report", "says"),
    [
        (
            _agents_say("none"),
            "agent eve, which runs it, binds no remote execution: expected a provider, and it "
            f"reports remote_execution.provider none ({_SAID}). This runtime binds one, so the "
            "agent wasn't recreated when the provider was set",
        ),
        (
            _agents_say(None),
            f"agent eve, which runs it, doesn't say what remote execution it binds ({_SAID}): "
            "it was built before agents reported it",
        ),
        (
            _agents_say(fresh=False),
            f"agent eve, which runs it, isn't being heard from ({_SAID})",
        ),
        (
            _agents_are_silent,
            "agent eve, which runs it, has sent this runtime no heartbeat, so whether it binds "
            "remote execution can't be read",
        ),
        (None, "this runtime keeps no record of what its agents report, so none can be read"),
    ],
    ids=["binds-none", "built-before-it-reported", "not-heard-from", "no-heartbeat", "no-reports"],
)
async def test_a_tool_its_own_agent_cant_ask_for_is_refused_naming_the_agent(
    config, agent_report, says
):
    """#3235, 2026-11-19: the runtime was switched to ``runtime_api`` and rebuilt, the QA agent
    still bound no port, and the cycle was created. Its in-run evaluation then read "no remote
    execution port" as an unverified check on the candidate, while the Campaign's own plays
    ran. Bug caught: reading the agent's capability from the runtime's provider, with a worker
    online and every other check passing."""
    [refusal] = await _preflight(
        config,
        authorities={"fixture-editor": _Allows()},
        worker_registry=await _registry(online=True),
        agent_report=agent_report,
    )

    assert refusal.startswith("skillset_availability: tool play_scenario (fixture-editor")
    assert says in refusal


async def test_the_cycle_is_created_once_its_agent_is_recreated_with_the_provider(config):
    """The recovery. Bug caught: a refusal that outlives its cause, read from anything but the
    agent's newest report."""
    said = {"provider": "none"}

    async def report(agent_id: str) -> AgentRemoteExecution:
        return AgentRemoteExecution(said["provider"], "3f2a91c", HEARD_AT, True)

    tools = {
        "authorities": {"fixture-editor": _Allows()},
        "worker_registry": await _registry(online=True),
        "agent_report": report,
    }
    before = await _preflight(config, **tools)
    said["provider"] = "runtime_api"
    after = await _preflight(config, **tools)

    assert len(before) == 1 and "binds no remote execution" in before[0]
    assert after == ()


async def test_an_authorized_tool_with_an_online_worker_creates_the_cycle(config):
    """Bug caught: a ready deployment refused, so no cycle that needs a tool can be created."""
    assert (
        await _preflight(
            config,
            authorities={"fixture-editor": _Allows()},
            worker_registry=await _registry(online=True),
        )
        == ()
    )


@pytest.mark.parametrize(
    ("tool", "client", "says"),
    [
        (ToolRequest("shell", "sandbox", "sandbox"), object(), "sandbox's typed operations"),
        (ToolRequest("run_backend_tests", "sandbox", "sandbox"), None, "binds no sandbox client"),
    ],
)
async def test_a_sandbox_tool_is_held_to_its_typed_operations_and_a_bound_client(
    monkeypatch, tool, client, says
):
    """Bug caught: a sandbox tool outside its typed operations authorized, or one run where no
    sandbox is bound."""
    catalog = _catalog(tool)
    monkeypatch.setattr(route, "packaged_skillsets", lambda: catalog)
    monkeypatch.setattr(
        route, "cycle_coverage", lambda p, c, cat: cycle_coverage(p, c, cat, CONTRACTS)
    )

    [refusal] = await _preflight(requiring_config(monkeypatch), sandbox_client=client)

    assert says in refusal


async def test_a_cycle_whose_work_requires_no_tool_is_checked_for_nothing():
    """Every existing stack's cycle. Bug caught: a cycle with no tools refused on a runtime with
    no worker registry, no authority and no sandbox client."""
    assert await _preflight({"development_profile": "fullstack_fastapi_react"}) == ()


def test_creation_and_a_campaigns_launch_read_the_same_tool_ports():
    """Bug caught: a campaign's launch building ``CreationPorts`` without the tool ports, so its
    cycles skip the checks every operator-created cycle passes."""
    fields = {f.name for f in dataclasses.fields(route.CreationPorts)}

    assert {"tool_authorities", "worker_registry", "sandbox_client", "remote_execution"} <= fields


@pytest.mark.parametrize(
    ("online", "remote_execution", "says"),
    [
        (False, BOUND, "fixture-editor/play_scenario and is offline"),
        (True, None, "this runtime binds no remote execution (remote_execution.provider none)"),
    ],
    ids=["a worker offline", "no remote execution bound"],
)
async def test_the_create_preflight_refuses_the_cycle_with_the_tool_and_its_location(
    config, online, remote_execution, says
):
    """The wiring, entered at ``_run_create_preflight``, the call cycle creation makes with the
    ports it gathered. Bugs caught: the tool checks computed and never combined into the
    preflight, so the cycle is created and its operation reads not executed mid-run; and the
    runtime's own binding never reaching the check, so a worker online is enough (#3159)."""
    from squadops.cycles.models import PreflightRejectedError

    with pytest.raises(PreflightRejectedError) as refused:
        await route._run_create_preflight(
            None,
            PROFILE,
            config,
            campaign_cycle=False,
            tools=route.ToolPreflight(
                authorities={"fixture-editor": _Allows()},
                worker_registry=await _registry(online=online),
                agent_report=_agents_say(),
                remote_execution=remote_execution,
                project_id="prj-1",
            ),
        )

    assert "tool play_scenario (fixture-editor, at worker)" in str(refused.value)
    assert "has no provider available" in str(refused.value)
    assert says in str(refused.value)


def test_creation_reads_the_runtimes_binding_from_the_request():
    """The other end of the wiring: ``CreationPorts.of_request`` reads the port the runtime put
    on its state. Bug caught: the field declared and never filled, so every cycle that needs a
    worker is refused, or (filled with the registry) none is."""
    from types import SimpleNamespace

    def request(**state):
        base = dict.fromkeys(
            ("project_registry", "squad_profile", "cycle_registry", "deploy_registry",
             "memory_records", "reference_resolvers", "tool_authorities", "worker_registry",
             "sandbox_client"),
            object(),
        )  # fmt: skip
        return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(**{**base, **state})))

    assert route.CreationPorts.of_request(request(remote_execution=BOUND)).remote_execution is BOUND
    assert route.CreationPorts.of_request(request()).remote_execution is None
    # #3235: and the agents' own reports, from the health checker that keeps their heartbeats.
    checker = SimpleNamespace(agent_remote_execution=_agents_say("none"))
    assert (
        route.CreationPorts.of_request(request(health_checker=checker)).agent_report
        is checker.agent_remote_execution
    )
    assert route.CreationPorts.of_request(request()).agent_report is None


# ---------------------------------------------------------------- at dispatch (part 2)


def _operation_task(skillset_digest: str):
    from squadops.tasks.models import TaskEnvelope

    return TaskEnvelope(
        task_id="task-op", agent_id="eve", cycle_id="cyc_1", pulse_id="p", project_id="prj-1",
        task_type="qa.run_remote_operation", correlation_id="c", causation_id="c",
        trace_id="t", span_id="s",
        inputs={
            "operation": {
                "contract": "fixture.scenario", "mode": "play", "role": "qa",
                "skillset": "fixture-qa", "skillset_digest": skillset_digest,
            }
        },
    )  # fmt: skip


@pytest.mark.parametrize(
    ("online", "bound", "agent_says", "says"),
    [
        (True, True, "runtime_api", None),
        (False, True, "runtime_api", "fixture-editor/play_scenario and is offline"),
        (
            True,
            False,
            "runtime_api",
            "this runtime binds no remote execution (remote_execution.provider none)",
        ),
        # #3235: the capability lost during the run. The agent was recreated without the
        # provider after the cycle was created, and its task isn't sent to it.
        (True, True, "none", "agent eve, which runs it, binds no remote execution"),
        # And an agent that is only late with a heartbeat is sent its task: it keeps what it
        # last said. Bug caught: a busy agent refused, and its increment retried for it.
        (True, True, "late", None),
    ],
    ids=[
        "available",
        "a worker offline",
        "no remote execution bound",
        "its agent binds none",
        "its agent is late with a heartbeat",
    ],
)
async def test_an_operation_tasks_tool_is_read_available_again_as_it_is_dispatched(
    monkeypatch, online, bound, agent_says, says
):
    """§8, entered at the executor's ``_require_tool_available``, which runs after a task's
    preconditions. Bugs caught: a worker that went offline after creation leaving the operation
    to run to an unverified verdict that names no tool; or the ending classified in words the
    Campaign's relaunch budget (#3045) would have to parse."""
    from types import SimpleNamespace

    from squadops.cycles.failure_attribution import WORKER_UNAVAILABLE, TerminalKind
    from squadops.execution import dispatched_flow_executor as executor_module
    from squadops.execution.execution_errors import _ExecutionError

    catalog = _catalog(TOOL)
    monkeypatch.setattr(executor_module, "packaged_skillsets", lambda: catalog)
    executor = SimpleNamespace(
        _worker_registry=await _registry(online=online),
        _sandbox=None,
        _remote_execution=BOUND if bound else None,
        _agent_report=(
            _agents_say("runtime_api", fresh=False)
            if agent_says == "late"
            else _agents_say(agent_says)
        ),
    )
    method = executor_module.DispatchedFlowExecutor._require_tool_available
    task = _operation_task(catalog["fixture-qa"].digest)

    if says is None:
        await method(executor, task)
        return
    with pytest.raises(_ExecutionError) as ended:
        await method(executor, task)

    terminal = ended.value.terminal
    assert (terminal.kind, terminal.failure_classification, terminal.task_id) == (
        TerminalKind.INFRASTRUCTURE_FAILED,
        WORKER_UNAVAILABLE,
        "task-op",
    )
    assert "tool play_scenario (fixture-editor, at worker)" in str(ended.value)
    assert says in terminal.termination_reason


async def test_a_task_that_runs_no_operation_is_never_asked_for_a_tool():
    """Bug caught: every task of every cycle held to a worker registry it never uses."""
    from types import SimpleNamespace

    from squadops.execution import dispatched_flow_executor as executor_module
    from squadops.tasks.models import TaskEnvelope

    develop = TaskEnvelope(
        task_id="t", agent_id="neo", cycle_id="c", pulse_id="p", project_id="prj-1",
        task_type="development.develop", correlation_id="c", causation_id="c", trace_id="t",
        span_id="s",
    )  # fmt: skip
    executor = SimpleNamespace(_worker_registry=None, _sandbox=None, _remote_execution=None)

    await executor_module.DispatchedFlowExecutor._require_tool_available(executor, develop)


async def test_a_product_its_authority_cant_be_shown_refuses_creation_naming_why(config):
    """SIP-0116 §17n (#3042). Bugs caught: a source-backed cycle whose tree can't be read (here,
    a runtime with no managed clone) handed to its authority as a sample application's
    ``None``, which a provider might pass; or the refusal not naming why."""
    from types import SimpleNamespace

    asked = _Records()
    context = SimpleNamespace(project_id="prj-1", pinned_commit="c" * 40)

    [refusal] = await _preflight(
        config,
        authorities={"fixture-editor": asked},
        worker_registry=await _registry(online=True),
        source_context=context,
        source_repository=None,
    )

    assert refusal.startswith("skillset_authorization: the product's authorities can't be asked")
    assert f"Project prj-1's tree at {'c' * 40} can't be read" in refusal
    assert "no managed clone" in refusal
    assert asked.shown == []


async def test_a_cycle_on_no_repository_backed_product_shows_its_authority_none(config):
    """§17n. Bug caught: a sample application's cycle given a view of an empty tree, which reads
    as a product with nothing in it rather than none at all."""
    asked = _Records()

    assert (
        await _preflight(
            config,
            authorities={"fixture-editor": asked},
            worker_registry=await _registry(online=True),
        )
        == ()
    )
    assert asked.shown == [None]


class _Records:
    def __init__(self) -> None:
        self.shown: list = []

    async def broken_rules(self, tool, *, project_id, config, product) -> list[BrokenRule]:
        self.shown.append(product)
        return []
