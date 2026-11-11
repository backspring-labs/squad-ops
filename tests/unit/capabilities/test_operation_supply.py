"""Who supplies a scenario's operation, and with which tool (#3044; SIP-0117 R4.4).

Entered at ``scenario_operation`` with a record and a catalog built as cycle creation builds
them (the shared skillset fixture). Plan expansion, the baseline step and Campaign delivery
each call it, so a defect here is one they would all share.
"""

from __future__ import annotations

import copy
import dataclasses

import pytest

from squadops.capabilities.capability_contracts import VerificationMode
from squadops.capabilities.operation_supply import (
    OperationSupplyError,
    scenario_operation,
    tool_request,
)
from squadops.capabilities.skillsets import SkillsetCapability, ToolRequest
from tests.unit.cycles.skillset_fixture import built, requiring_config, skillset
from tests.unit.cycles.skillset_fixture import catalog as fixture_catalog

pytestmark = [pytest.mark.domain_capabilities]

TOOL = ToolRequest("play_scenario", "fixture-editor", "worker")


def _catalog(*tools: ToolRequest) -> dict:
    """The fixture catalog, with the qa skillset's scenario capability requesting ``tools``."""
    skillsets = fixture_catalog()
    qa = skillsets["fixture-qa"]
    capabilities = tuple(
        dataclasses.replace(c, tools=tools) if c.contract == "fixture.scenario" else c
        for c in qa.capabilities
    )
    skillsets["fixture-qa"] = skillset("fixture-qa", "qa", capabilities, qa.skill_files)
    return skillsets


@pytest.fixture
def config(monkeypatch):
    return requiring_config(monkeypatch)


def test_a_scenario_runs_under_the_one_operation_its_cycles_record_offers(config):
    """Bug caught: the baseline step, the handler and delivery each finding the tool their own
    way, so a scenario passes under one provider and is judged under another."""
    catalog = _catalog(TOOL)
    record, _ = built(config, catalog)

    supplied = scenario_operation(record, catalog)

    assert (supplied.contract, supplied.mode, supplied.role) == ("fixture.scenario", "play", "qa")
    assert (supplied.skillset, supplied.skillset_digest) == (
        "fixture-qa",
        catalog["fixture-qa"].digest,
    )
    assert (supplied.provider, supplied.operation, supplied.location) == (
        "fixture-editor",
        "play_scenario",
        "worker",
    )


def test_two_suppliers_of_a_scenarios_operation_are_refused_never_chosen_between(config):
    """Bug caught: the first row taken, so which provider runs a scenario depends on the
    record's order."""
    catalog = _catalog(TOOL)
    record, _ = built(config, catalog)
    record = copy.deepcopy(record)
    extra = next(r for r in record["offered"] if r["contract"] == "fixture.scenario")
    record["offered"].append({**extra, "skillset": "fixture-web"})

    with pytest.raises(OperationSupplyError, match="more than one supplier"):
        scenario_operation(record, catalog)


@pytest.mark.parametrize(
    ("record", "says"),
    [
        (None, "offers no operation contract in `play` mode"),
        ({"offered": [], "assignment": []}, "offers no operation contract"),
    ],
)
def test_a_cycle_that_offers_no_scenario_operation_is_refused(record, says):
    """Bug caught: a missing record read as a supplier, or a scenario run under no tool."""
    with pytest.raises(OperationSupplyError, match=says):
        scenario_operation(record, _catalog(TOOL))


def test_a_supplier_whose_skillset_changed_since_the_cycle_was_created_is_refused(config):
    """Bug caught: a scenario run with a tool from a skillset other than the one the cycle
    recorded, after a redeploy edited it."""
    record, _ = built(config, _catalog(TOOL))
    redeployed = _catalog(ToolRequest("play_scenario", "other-editor", "worker"))
    redeployed["fixture-qa"] = dataclasses.replace(redeployed["fixture-qa"], digest="moved")

    with pytest.raises(OperationSupplyError, match="has changed since the cycle was created"):
        scenario_operation(record, redeployed)


@pytest.mark.parametrize(
    ("tools", "says"),
    [((), "requests 0 tools"), ((TOOL, ToolRequest("x", "y", "worker")), "requests 2 tools")],
)
def test_a_supplier_that_requests_no_single_tool_is_refused(tools, says):
    """Bug caught: the first of two tools run, or an operation asked of no provider."""
    capability = SkillsetCapability("fixture.scenario", (VerificationMode.PLAY,), (), tools)
    held = skillset("fixture-qa", "qa", (capability,), {})
    operation = {
        "skillset": "fixture-qa",
        "skillset_digest": held.digest,
        "contract": "fixture.scenario",
        "mode": "play",
    }

    with pytest.raises(OperationSupplyError, match=says):
        tool_request({"fixture-qa": held}, operation)
