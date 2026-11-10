"""The skillset record (SIP-0116 §10, phase 1): its content, its digest, and that a cycle
keeps it through the registry and the read route."""

from __future__ import annotations

import copy
import dataclasses
from datetime import UTC, datetime

import pytest

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.api.routes.cycles.mapping import cycle_to_response
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.skillset_record import build_skillset_record, skillset_record_digest
from squadops.stacks import development_profiles
from squadops.stacks.requirements import (
    ContractNeed,
    PlatformTarget,
    ResponsibilityRequirement,
    SkillsetRequirement,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 11, 9, tzinfo=UTC)
PROFILE = SquadProfile(
    profile_id="fixture-squad",
    name="Fixture",
    description="",
    version=1,
    agents=(AgentProfileEntry("eve", "qa", "m", True, {}, ("qa",), ("fixture-qa",)),),
    created_at=NOW,
)


@pytest.fixture
def requiring_profile(monkeypatch):
    """A development profile with requirements. None is registered, so one is put in the
    registry for the test."""
    requires = (
        ResponsibilityRequirement(
            "qa",
            (
                SkillsetRequirement(
                    "fixture-qa", ">=2", (ContractNeed("fixture.unit_tests", "headless"),)
                ),
                SkillsetRequirement("fixture-qa-b"),
            ),
        ),
    )
    profile = dataclasses.replace(
        development_profiles.DEVELOPMENT_PROFILES["python_cli"],
        name="fixture_stack",
        platform=PlatformTarget("fixture", "local"),
        requires=requires,
    )
    monkeypatch.setitem(development_profiles.DEVELOPMENT_PROFILES, "fixture_stack", profile)
    return "fixture_stack"


def test_a_profiles_requirements_are_recorded_as_declared_with_its_platform(requiring_profile):
    record = build_skillset_record(PROFILE, "hash-1", {"development_profile": requiring_profile})

    assert record["development_profile"]["platform"] == {"id": "fixture", "variant": "local"}
    assert record["requirements"] == [
        {
            "role": "qa",
            "any_of": [
                {
                    "skillset": "fixture-qa",
                    "version": ">=2",
                    "needs": [{"contract": "fixture.unit_tests", "mode": "headless"}],
                },
                {"skillset": "fixture-qa-b", "version": "", "needs": []},
            ],
        }
    ]
    # Phase 1 records what was declared. Coverage assigns an agent in phase 2.
    assert record["assignment"] == []


def test_a_repository_backed_cycles_recorded_selection_gives_the_origin():
    config = {
        "development_profile": "node_vitest",
        "development_profile_selection": {"name": "node_vitest", "origin": "derived"},
    }

    record = build_skillset_record(PROFILE, "hash-1", config)

    assert record["development_profile"]["origin"] == "derived"


@pytest.mark.parametrize(
    "selection",
    [{"name": "python_api", "origin": "derived"}, {"name": "node_vitest"}],
    ids=["names another profile", "has no origin"],
)
def test_a_selection_that_is_not_this_profiles_pin_is_refused_rather_than_borrowed(selection):
    """Bug caught: the record saying a profile was ``derived`` from the product's runners
    because a selection for some other profile happened to be on the cycle."""
    config = {"development_profile": "node_vitest", "development_profile_selection": selection}

    with pytest.raises(ValueError, match="recorded development_profile_selection"):
        build_skillset_record(PROFILE, "hash-1", config)


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["squad"].__setitem__("roster_hash", "hash-2"),
        lambda r: r["base_set"].__setitem__("version", "base@2"),
        lambda r: r["requirements"].append({"role": "dev", "any_of": []}),
        lambda r: r.__setitem__("schema", "squadops.skillset-record/v2"),
    ],
    ids=["the squad", "the base set", "a requirement", "the schema"],
)
def test_any_change_to_the_record_no_longer_matches_its_digest(change):
    """Bug caught: a digest that covers part of the record, so a stored record edited after
    creation still reads as the one the cycle ran under."""
    record = build_skillset_record(PROFILE, "hash-1", {})
    assert skillset_record_digest(record) == record["digest"]

    edited = copy.deepcopy(record)
    change(edited)

    assert skillset_record_digest(edited) != record["digest"]


def test_the_same_inputs_give_the_same_digest_and_a_different_squad_another():
    one = build_skillset_record(PROFILE, "hash-1", {})
    two = build_skillset_record(PROFILE, "hash-1", {})
    other = build_skillset_record(PROFILE, "hash-2", {})

    assert one == two
    assert other["digest"] != one["digest"]


def test_an_unknown_development_profile_is_refused_rather_than_recorded():
    with pytest.raises(ValueError, match="Unknown development profile 'no_such_stack'"):
        build_skillset_record(PROFILE, "hash-1", {"development_profile": "no_such_stack"})


async def test_the_registry_and_the_read_route_return_the_record_a_cycle_was_created_with():
    """Bug caught: the record written at creation and lost by the registry's read or by the
    response mapper, so an operator can't see what a cycle ran under."""
    record = build_skillset_record(PROFILE, "hash-1", {})
    registry = MemoryCycleRegistry()
    await registry.create_cycle(
        Cycle(
            cycle_id="cyc_1",
            project_id="p",
            created_at=NOW,
            created_by="t",
            prd_ref=None,
            squad_profile_id="fixture-squad",
            squad_profile_snapshot_ref="hash-1",
            task_flow_policy=TaskFlowPolicy(mode="sequential", gates=()),
            build_strategy="fresh",
            skillset_record=record,
        )
    )

    stored = await registry.get_cycle("cyc_1")

    assert stored.skillset_record == record
    assert cycle_to_response(stored, []).skillset_record == record
