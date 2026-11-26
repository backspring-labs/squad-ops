"""A task's equipment under a skillset, built for the replay as a cycle builds it (SIP-0116 §17p;
#3041). The packaged tests compare it with what the cycle's own record and kept copy hand the
same task, so the replay tests the skills a cycle would load and no others.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.cycles.config_squad_profile import ConfigSquadProfile
from squadops.capabilities.skillsets import load_skillsets
from squadops.cycles.skillset_content import kept_document, skills_for, skills_input
from squadops.cycles.skillset_coverage import resolve_coverage
from squadops.cycles.skillset_replay import task_equipment
from squadops.stacks.requirements import (
    ContractNeed,
    PlatformTarget,
    ResponsibilityRequirement,
    SkillsetRequirement,
)

pytestmark = [pytest.mark.domain_orchestration]

_SQUAD_PROFILES = Path(__file__).resolve().parents[3] / "config" / "squad-profiles.yaml"
_REQUIRES = (
    ResponsibilityRequirement(
        "strat",
        (
            SkillsetRequirement(
                "roblox-increment-design", needs=(ContractNeed("game.increment_design"),)
            ),
        ),
    ),
    ResponsibilityRequirement(
        "dev",
        (
            SkillsetRequirement(
                "roblox-luau-dev", needs=(ContractNeed("game.gameplay_implementation"),)
            ),
        ),
    ),
    ResponsibilityRequirement(
        "qa",
        (
            SkillsetRequirement(
                "roblox-studio-qa",
                needs=(
                    ContractNeed("game.unit_tests", "headless"),
                    ContractNeed("game.scenario_verification", "play"),
                ),
            ),
        ),
    ),
)


@pytest.fixture(scope="module")
def catalog():
    return load_skillsets()


@pytest.mark.parametrize(
    ("skillset", "role", "agent", "task_type"),
    [
        ("roblox-increment-design", "strat", "nat", "strategy.propose_increment"),
        ("roblox-luau-dev", "dev", "neo", "development.develop"),
        ("roblox-studio-qa", "qa", "eve", "qa.test"),
    ],
)
async def test_the_replays_equipment_is_what_a_cycle_on_the_roblox_squad_would_hand(
    catalog, skillset, role, agent, task_type
):
    """Entered on the cycle's side at the comparison creation makes (``resolve_coverage`` on the
    seeded squad), its kept copy and ``skills_for``. Bug caught: the replay handing a task
    another set of skills than its cycle would (a shared skill left out, another capability's
    skill added), so a skill passes a test of something a cycle never loads."""
    squad = await ConfigSquadProfile(yaml_path=_SQUAD_PROFILES).get_profile("game-dev-roblox")
    coverage = resolve_coverage(squad, PlatformTarget("roblox", "studio-place"), _REQUIRES, catalog)
    record = {
        "offered": [
            {
                "agent_id": o.agent_id,
                "contract": o.contract,
                "task_type": o.task_type.value,
                "skillset": o.skillset,
            }
            for o in coverage.offered
        ]
    }
    cycles = skills_input(
        skills_for(
            kept_document(coverage.assignments, catalog),
            record,
            task_type=task_type,
            agent_id=agent,
        )
    )

    equipment = task_equipment(
        catalog, skillset=skillset, role=role, agent_id=agent, task_type=task_type
    )

    assert cycles, "the cycle hands this task at least one skill"
    assert equipment.skills == cycles
    assert equipment.scenario_vocabulary is None
    assert equipment.digests() == {f"{s['skillset']}/{s['skill']}": s["digest"] for s in cycles}


def test_the_proposals_vocabulary_is_the_one_the_scenario_supplier_holds(catalog):
    """Bug caught: a proposal replayed with no vocabulary, so every scenario criterion its skill
    writes is refused as unverifiable and the skill reads as failing."""
    from adapters.remote_execution.game_dev_roblox_studio import vocabulary as studio

    equipment = task_equipment(
        catalog,
        skillset="roblox-increment-design",
        role="strat",
        agent_id="nat",
        task_type="strategy.propose_increment",
        vocabulary_skillset="roblox-studio-qa",
    )

    assert equipment.scenario_vocabulary == studio.VOCABULARY.to_document()


@pytest.mark.parametrize(
    ("change", "says"),
    [
        ({"skillset": "roblox-lua-dev"}, "holds no skillset roblox-lua-dev"),
        ({"role": "qa"}, "is for dev, not qa"),
        ({"task_type": "qa.test"}, "loads no skill for a qa.test task"),
        ({"vocabulary_skillset": "roblox-luau-dev"}, "holds 0 scenario vocabularies"),
        ({"vocabulary_skillset": "absent"}, "holds no skillset absent"),
    ],
    ids=["unknown", "wrong-role", "no-skill-for-the-task", "no-vocabulary", "unknown-supplier"],
)
def test_equipment_that_cant_be_built_as_asked_is_refused_by_name(catalog, change, says):
    """Bug caught: a mistyped case handing its task no skills, and its skills arm running as a
    second baseline that the record calls a test of the skill."""
    asked = {
        "skillset": "roblox-luau-dev",
        "role": "dev",
        "agent_id": "neo",
        "task_type": "development.develop",
        **change,
    }

    with pytest.raises(ValueError, match=says):
        task_equipment(catalog, **asked)
