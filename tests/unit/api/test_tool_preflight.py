"""A cycle's tools, checked at creation (SIP-0116 §8, §9; phase 4, #3036).

§14's proof: three fixtures, three distinct refusals, and an offline worker read as availability,
never as a missing skillset. Entered at ``_run_create_preflight``, which cycle creation and a
campaign's launch both call. The squad, record and catalog are the shared skillset fixture's,
with the qa skillset's scenario capability requesting a worker tool; the worker registry is the
real one on a memory store. The fixtures live in tests only.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.api.routes.cycles import cycles as route
from squadops.capabilities.skillsets import ToolRequest
from squadops.cycles.skillset_coverage import cycle_coverage
from squadops.ports.tool_authority import BrokenRule
from squadops.remote_execution import leasing
from squadops.remote_execution.registry import WorkerRegistry
from tests.unit.capabilities.test_operation_supply import _catalog
from tests.unit.cycles.skillset_fixture import CONTRACTS, PROFILE, requiring_config
from tests.unit.remote_execution.registry_contract import Clock, registration

TOOL = ToolRequest("play_scenario", "fixture-editor", "worker")


class _Allows:
    def broken_rules(self, tool, *, project_id, config) -> list[BrokenRule]:
        return []


class _RefusesScripts:
    """A provider whose compatibility check refuses a product with tagged scripts."""

    def broken_rules(self, tool, *, project_id, config) -> list[BrokenRule]:
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


async def _preflight(config: dict, **tools: Any) -> tuple[str, ...]:
    """Each refusal's code and message for ``config`` with ``tools``; ``()`` when created."""
    decision = await route._tool_preflight_decision(
        PROFILE, config, route.ToolPreflight(project_id="prj-1", **tools)
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
    ],
)
async def test_a_tool_no_worker_can_run_is_refused_as_availability_never_coverage(
    config, registry, says
):
    """§14: an offline worker reads as availability, never as a missing skillset. Bug caught:
    the squad told to carry a skillset it carries, or a cycle created that stalls at its first
    operation."""
    registries = {
        "offline": lambda: _registry(online=False),
        "none_serves": lambda: _empty_registry(),
        "no_registry": None,
    }
    worker_registry = await registries[registry]() if registries[registry] else None

    [refusal] = await _preflight(
        config, authorities={"fixture-editor": _Allows()}, worker_registry=worker_registry
    )

    assert refusal.startswith("skillset_availability:")
    assert says in refusal
    assert "The squad still carries fixture-qa" in refusal


async def _empty_registry() -> WorkerRegistry:
    return WorkerRegistry(MemoryWorkerRegistryStore(), clock=Clock())


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

    assert {"tool_authorities", "worker_registry", "sandbox_client"} <= fields


async def test_the_create_preflight_refuses_the_cycle_with_the_tool_and_its_location(config):
    """The wiring, entered at ``_run_create_preflight``, the call cycle creation makes with the
    ports it gathered. Bug caught: the tool checks computed and never combined into the
    preflight, so the cycle is created and its operation reads not executed mid-run."""
    from squadops.cycles.models import PreflightRejectedError

    with pytest.raises(PreflightRejectedError) as refused:
        await route._run_create_preflight(
            None,
            PROFILE,
            config,
            campaign_cycle=False,
            tools=route.ToolPreflight(
                authorities={"fixture-editor": _Allows()},
                worker_registry=await _registry(online=False),
                project_id="prj-1",
            ),
        )

    assert "tool play_scenario (fixture-editor, at worker)" in str(refused.value)
    assert "has no provider available" in str(refused.value)
