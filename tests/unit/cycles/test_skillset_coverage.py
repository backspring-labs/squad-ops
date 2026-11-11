"""Coverage on the routed agent (SIP-0116 §5.3, §9; phase 2). Fixtures only: no skillset,
contract or requiring profile is shipped."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.capabilities.capability_contracts import (
    CapabilityContractDeclaration,
    VerificationMode,
)
from squadops.capabilities.skillsets import Skillset, SkillsetCapability
from squadops.cycles.models import AgentProfileEntry, SquadProfile
from squadops.cycles.skillset_coverage import (
    COVERAGE,
    DECLARATION,
    Assignment,
    Coverage,
    OfferedContract,
    resolve_coverage,
)
from squadops.stacks.requirements import (
    ContractNeed,
    PlatformTarget,
    ResponsibilityRequirement,
    SkillsetRequirement,
)
from squadops.tasks.task_types import TaskType

pytestmark = [pytest.mark.domain_orchestration]

PLATFORM = PlatformTarget("fixture", "local")
CONTRACTS = {
    "fixture.scenario_verification": CapabilityContractDeclaration(
        "fixture.scenario_verification",
        TaskType.QA_VALIDATE,
        "one result per assertion",
        (VerificationMode.PLAY, VerificationMode.MULTIPLAYER),
    ),
    "fixture.unit_tests": CapabilityContractDeclaration(
        "fixture.unit_tests", TaskType.QA_TEST, "one result per test", (VerificationMode.HEADLESS,)
    ),
}


def _skillset(skillset_id="fixture-qa", *, version=2, roles=("qa",), capabilities=None, **over):
    fields = {
        "id": skillset_id,
        "version": version,
        "description": "fixture",
        "roles": roles,
        "platform_id": "fixture",
        "platform_variants": ("local",),
        "prerequisites": (),
        "capabilities": capabilities
        or (
            SkillsetCapability("fixture.unit_tests", (VerificationMode.HEADLESS,)),
            SkillsetCapability("fixture.scenario_verification", (VerificationMode.PLAY,)),
        ),
        "skill_digests": {},
        "digest": f"digest-of-{skillset_id}",
    }
    return Skillset(**{**fields, **over})


CATALOG = {"fixture-qa": _skillset(), "fixture-dev": _skillset("fixture-dev", roles=("dev",))}
QA_REQUIRES = ResponsibilityRequirement(
    "qa",
    (
        SkillsetRequirement(
            "fixture-qa",
            ">=2",
            (
                ContractNeed("fixture.unit_tests", "headless"),
                ContractNeed("fixture.scenario_verification", "play"),
            ),
        ),
    ),
)


def _squad(*agents: AgentProfileEntry) -> SquadProfile:
    return SquadProfile(
        "fixture-squad", "Fixture", "", 1, agents, datetime(2026, 11, 9, tzinfo=UTC)
    )


def _agent(agent_id, role, *skillsets, enabled=True, serves=None) -> AgentProfileEntry:
    return AgentProfileEntry(
        agent_id, role, "m", enabled, {}, tuple(serves or (role,)), tuple(skillsets)
    )


EVE = _agent("eve", "qa", "fixture-qa")
NEO = _agent("neo", "dev")


def _resolve(squad, requires=(QA_REQUIRES,), platform=PLATFORM, catalog=CATALOG):
    return resolve_coverage(squad, platform, requires, catalog, CONTRACTS)


def test_a_routed_agent_carrying_the_skillset_is_assigned_and_its_contracts_offered():
    coverage = _resolve(_squad(NEO, EVE))

    assert coverage.covered
    assert coverage.assignments == (
        Assignment("qa", "eve", "fixture-qa", 2, "digest-of-fixture-qa"),
    )
    assert coverage.offered == (
        OfferedContract(
            "fixture.unit_tests", "headless", TaskType.QA_TEST, "qa", "eve", "fixture-qa"
        ),
        OfferedContract(
            "fixture.scenario_verification", "play", TaskType.QA_VALIDATE, "qa", "eve", "fixture-qa"
        ),
    )


def test_work_that_requires_nothing_is_covered_by_any_squad():
    coverage = resolve_coverage(_squad(NEO, _agent("eve", "qa")), None, (), {}, {})

    assert coverage == Coverage()
    assert coverage.covered


def test_an_agent_elsewhere_in_the_roster_carrying_the_skillset_does_not_help():
    """§5.3: the agent the work routes to is the one checked. Bug caught: a squad passing
    preflight because *someone* carries the skillset, then dispatching the step to an agent
    that was never equipped for it."""
    spare = _agent("ada", "qa", "fixture-qa", enabled=False)
    wrong_role = _agent("neo", "dev", "fixture-qa")

    coverage = _resolve(_squad(wrong_role, _agent("eve", "qa"), spare))

    assert [f.kind for f in coverage.findings] == [COVERAGE]
    assert coverage.findings[0].message == (
        "Squad skillset requirements not met. Selected squad: `fixture-squad`. Missing: "
        "`fixture-qa` for `qa` (agent `eve`). Select or configure a squad with an eligible "
        "agent carrying each skillset."
    )
    assert coverage.assignments == ()


def test_the_first_enabled_agent_serving_the_role_is_the_routed_one():
    generalist = _agent("han", "generalist", serves=("dev", "qa"))

    coverage = _resolve(_squad(generalist, EVE))

    assert "`fixture-qa` for `qa` (agent `han`)" in coverage.findings[0].message


@pytest.mark.parametrize(
    ("squad", "constraint", "expected"),
    [
        (
            _squad(EVE),
            "3",
            "`fixture-qa` at version 3 for `qa` (agent `eve` carries version 2)",
        ),
        (
            _squad(EVE),
            ">=5",
            "`fixture-qa` at version >=5 for `qa` (agent `eve` carries version 2)",
        ),
        (_squad(NEO), ">=2", "`fixture-qa` for `qa` (no enabled agent serves that role)"),
    ],
)
def test_an_incompatible_version_and_an_unserved_role_are_coverage_refusals(
    squad, constraint, expected
):
    requires = (ResponsibilityRequirement("qa", (SkillsetRequirement("fixture-qa", constraint),)),)

    coverage = _resolve(squad, requires)

    assert [f.kind for f in coverage.findings] == [COVERAGE]
    assert expected in coverage.findings[0].message


def test_every_unmet_requirement_is_named_in_one_refusal():
    requires = (
        QA_REQUIRES,
        ResponsibilityRequirement("dev", (SkillsetRequirement("fixture-dev"),)),
    )

    coverage = _resolve(_squad(NEO, _agent("eve", "qa")), requires)

    (finding,) = coverage.findings
    assert (
        "Missing: `fixture-qa` for `qa` (agent `eve`), `fixture-dev` for `dev` (agent `neo`)."
        in (finding.message)
    )


def test_a_declared_alternative_satisfies_the_requirement_and_an_undeclared_one_never_does():
    either = ResponsibilityRequirement(
        "qa", (SkillsetRequirement("fixture-qa-b"), SkillsetRequirement("fixture-qa"))
    )
    catalog = {**CATALOG, "fixture-qa-b": _skillset("fixture-qa-b")}
    lookalike = _agent("eve", "qa", "fixture-qa-c")

    accepted = _resolve(_squad(EVE), (either,), catalog=catalog)
    refused = _resolve(
        _squad(lookalike), (either,), catalog={**catalog, "fixture-qa-c": _skillset("fixture-qa-c")}
    )

    assert accepted.assignments[0].skillset == "fixture-qa"
    assert "`fixture-qa-b` or `fixture-qa` for `qa` (agent `eve`)" in refused.findings[0].message


@pytest.mark.parametrize(
    ("requirement", "catalog", "expected"),
    [
        (
            SkillsetRequirement("fixture-unknown"),
            CATALOG,
            "Required skillset `fixture-unknown` is unknown to this deployment.",
        ),
        (
            SkillsetRequirement("fixture-qa", needs=(ContractNeed("fixture.capture", "capture"),)),
            CATALOG,
            "Required skillset `fixture-qa` doesn't specialize the contract `fixture.capture`.",
        ),
        (
            SkillsetRequirement(
                "fixture-qa", needs=(ContractNeed("fixture.scenario_verification", "multiplayer"),)
            ),
            CATALOG,
            "Required skillset `fixture-qa` doesn't support `fixture.scenario_verification` in "
            "`multiplayer` mode.",
        ),
        (
            SkillsetRequirement("fixture-qa"),
            {"fixture-qa": _skillset(platform_id="other")},
            "Required skillset `fixture-qa` applies to `other` (`local`), and the profile's "
            "platform is `fixture` (`local`).",
        ),
        (
            SkillsetRequirement("fixture-qa"),
            {"fixture-qa": _skillset(platform_variants=("cloud",))},
            "Required skillset `fixture-qa` applies to `fixture` (`cloud`), and the profile's "
            "platform is `fixture` (`local`).",
        ),
    ],
    ids=["unknown", "contract", "mode", "platform", "variant"],
)
def test_a_requirement_its_skillset_cannot_meet_is_a_declaration_refusal(
    requirement, catalog, expected
):
    """§5.1: a requirement is checked for consistency whatever squad is selected. Bug caught:
    a profile requiring a mode nothing declares reading as covered, so an unproven
    verification reads as passing."""
    coverage = _resolve(
        _squad(EVE), (ResponsibilityRequirement("qa", (requirement,)),), catalog=catalog
    )

    assert (DECLARATION, expected) in [(f.kind, f.message) for f in coverage.findings]


def test_a_skillset_the_agents_role_does_not_allow_is_a_declaration_refusal():
    requires = (ResponsibilityRequirement("qa", (SkillsetRequirement("fixture-dev"),)),)

    coverage = _resolve(_squad(_agent("eve", "qa", "fixture-dev")), requires)

    assert [(f.kind, f.message) for f in coverage.findings] == [
        (
            DECLARATION,
            "Agent `eve` declares skillset `fixture-dev` for `qa`, and that skillset is for `dev`.",
        )
    ]
    assert coverage.assignments == ()


def test_two_required_skillsets_adding_to_one_capability_are_refused_by_name():
    """Q62. Bug caught: two skillsets both loading skills for one role's ``qa.test`` tasks,
    with nothing saying which guidance wins."""
    second = _skillset(
        "fixture-qa-web",
        capabilities=(SkillsetCapability("qa.test"),),
    )
    requires = (
        QA_REQUIRES,
        ResponsibilityRequirement(
            "qa", (SkillsetRequirement("fixture-qa-web", needs=(ContractNeed("qa.test"),)),)
        ),
    )
    eve = _agent("eve", "qa", "fixture-qa", "fixture-qa-web")

    coverage = _resolve(_squad(eve), requires, catalog={**CATALOG, "fixture-qa-web": second})

    assert [(f.kind, f.message) for f in coverage.findings] == [
        (
            DECLARATION,
            "Required skillsets `fixture-qa`, `fixture-qa-web` both add to `qa.test` for `qa`. "
            "One skillset supplies a capability; the profile's author resolves it.",
        )
    ]


def test_a_skillset_an_agent_carries_but_the_work_does_not_require_offers_nothing():
    """§6.3. Bug caught: an equipped squad widening what an ordinary cycle's planner sees."""
    coverage = resolve_coverage(_squad(NEO, EVE), None, (), CATALOG, CONTRACTS)

    assert coverage.offered == ()
    assert coverage.covered


def test_the_routed_agent_is_the_one_dispatch_resolves_for_the_role():
    """Bug caught: coverage holding its own copy of the routing rule. If the two drift,
    preflight vouches for one agent and the step is sent to another."""
    from squadops.cycles.agent_config import resolve_agent_config
    from squadops.cycles.skillset_coverage import routed_agent

    squad = _squad(
        _agent("ada", "qa", enabled=False),
        _agent("han", "generalist", serves=("dev", "qa")),
        EVE,
    )

    for role in ("qa", "dev"):
        assert routed_agent(squad, role).agent_id == resolve_agent_config(role, squad).agent_id
    assert routed_agent(squad, "builder") is None


def test_a_profile_with_a_malformed_requirement_is_refused_at_the_cycle_not_half_checked(
    monkeypatch,
):
    import dataclasses

    from squadops.cycles.skillset_coverage import cycle_coverage
    from squadops.stacks import development_profiles

    broken = dataclasses.replace(
        development_profiles.DEVELOPMENT_PROFILES["python_cli"],
        name="broken_stack",
        requires=(QA_REQUIRES,),  # requires a skillset and declares no platform
    )
    monkeypatch.setitem(development_profiles.DEVELOPMENT_PROFILES, "broken_stack", broken)

    coverage = cycle_coverage(_squad(EVE), {"development_profile": "broken_stack"}, CATALOG)

    assert [(f.kind, f.message) for f in coverage.findings] == [
        (
            DECLARATION,
            "Development profile `broken_stack`: requires: a profile that requires skillsets "
            "declares its platform.",
        )
    ]
    assert coverage.assignments == ()


def test_coverage_for_an_unknown_profile_raises_rather_than_reading_as_covered():
    from squadops.cycles.skillset_coverage import cycle_coverage

    with pytest.raises(ValueError, match="Unknown development profile 'no_such_stack'"):
        cycle_coverage(_squad(EVE), {"development_profile": "no_such_stack"}, CATALOG)
