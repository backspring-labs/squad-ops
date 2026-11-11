"""The skillset spec and the capability contracts it specializes (SIP-0116 §4, §6; phase 1).
Fixtures only: no skillset is shipped."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from squadops.capabilities.capability_contracts import (
    CapabilityContractDeclaration,
    VerificationMode,
    capability_contract,
    contract_errors,
)
from squadops.capabilities.skillsets import (
    PACKAGED_SKILLSETS_DIR,
    SkillsetError,
    ToolRequest,
    load_skillset,
    load_skillsets,
)
from squadops.tasks.task_types import TaskType

pytestmark = [pytest.mark.domain_capabilities]

CONTRACTS = {
    "fixture.scenario_verification": CapabilityContractDeclaration(
        id="fixture.scenario_verification",
        task_type=TaskType.QA_VALIDATE,
        evidence="one executed-passed, executed-failed or not-executed result per assertion",
        modes=(VerificationMode.PLAY, VerificationMode.MULTIPLAYER),
    ),
    "fixture.unit_tests": CapabilityContractDeclaration(
        id="fixture.unit_tests",
        task_type=TaskType.QA_TEST,
        evidence="one result per test",
        modes=(VerificationMode.HEADLESS,),
    ),
}

SPEC = """
    api_version: squadops.skillset/v1
    skillset:
      id: fixture-qa
      version: 2
      description: Verifies a fixture product
      roles: [qa]
      platform: {id: fixture, variants: [local]}
      prerequisites:
        - provider: fixture-runner
      capabilities:
        - contract: fixture.unit_tests
          modes: [headless]
          skills: [test-loader, shared/conventions]
        - contract: fixture.scenario_verification
          modes: [play]
          skills: [play-scenario]
          tools:
            - {id: play_scenario, provider: fixture-editor, location: worker}
"""

_SKILL = "---\nname: {name}\ndescription: How to {name}\n---\nDo the work.\n"


def _write_skill(directory: Path, name: str) -> None:
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(_SKILL.format(name=name))


@pytest.fixture
def root(tmp_path) -> Path:
    skillset = tmp_path / "fixture-qa"
    skillset.mkdir()
    (skillset / "skillset.yaml").write_text(textwrap.dedent(SPEC))
    _write_skill(skillset / "skills" / "test-loader", "test-loader")
    _write_skill(skillset / "skills" / "play-scenario", "play-scenario")
    _write_skill(tmp_path / "_shared" / "conventions", "conventions")
    return tmp_path


def _respec(root: Path, old: str, new: str) -> None:
    path = root / "fixture-qa" / "skillset.yaml"
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new))


def test_a_valid_directory_loads_with_its_contracts_modes_skills_and_tools(root):
    skillset = load_skillset(root / "fixture-qa", contracts=CONTRACTS)

    assert (skillset.id, skillset.version, skillset.roles) == ("fixture-qa", 2, ("qa",))
    assert (skillset.platform_id, skillset.platform_variants) == ("fixture", ("local",))
    assert skillset.prerequisites == ("fixture-runner",)
    scenario = skillset.capability_for("fixture.scenario_verification")
    assert scenario.modes == (VerificationMode.PLAY,)
    assert scenario.tools == (ToolRequest("play_scenario", "fixture-editor", "worker"),)
    assert skillset.capability_for("fixture.unit_tests").skills == (
        "test-loader",
        "shared/conventions",
    )
    assert sorted(skillset.skill_digests) == ["play-scenario", "shared/conventions", "test-loader"]
    assert skillset.capability_for("fixture.gameplay") is None


@pytest.mark.parametrize(
    "edit",
    [
        lambda root: _respec(root, "version: 2", "version: 3"),
        lambda root: (root / "fixture-qa/skills/play-scenario/SKILL.md").write_text(
            _SKILL.format(name="play-scenario") + "One more rule.\n"
        ),
        lambda root: (root / "_shared/conventions/SKILL.md").write_text(
            _SKILL.format(name="conventions") + "A shared rule changed.\n"
        ),
        lambda root: (root / "fixture-qa/skills/test-loader/loader.txt").write_bytes(b"\xff\x00"),
    ],
    ids=["the spec", "its own skill", "a shared skill it includes", "a skill's resource"],
)
def test_the_digest_moves_when_the_spec_or_any_skill_content_changes(root, edit):
    """Bug caught: a revised skill reaching a pinned Campaign unnoticed, because the digest
    covered the spec and not the content (or its own skills and not a shared one)."""
    before = load_skillset(root / "fixture-qa", contracts=CONTRACTS).digest
    edit(root)

    assert load_skillset(root / "fixture-qa", contracts=CONTRACTS).digest != before


def test_the_digest_is_the_same_for_the_same_content(root):
    one = load_skillset(root / "fixture-qa", contracts=CONTRACTS)
    two = load_skillset(root / "fixture-qa", contracts=CONTRACTS)

    assert one.digest == two.digest
    assert len(one.digest) == 64


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("squadops.skillset/v1", "squadops.skillset/v2", "api_version must be"),
        ("id: fixture-qa", "id: other", "id 'other' must be its directory's name, 'fixture-qa'"),
        ("version: 2", "version: 0", "version must be a positive integer, not 0"),
        ("version: 2", "version: true", "version must be a positive integer, not True"),
        ("roles: [qa]", "roles: []", "roles must name at least one"),
        ("variants: [local]", "variants: []", "platform.variants must name at least one"),
        (
            "modes: [play]",
            "modes: [editor]",
            "capability fixture.scenario_verification: the contract doesn't run in editor mode",
        ),
        (
            "modes: [headless]",
            "modes: [playing]",
            "capability fixture.unit_tests: 'playing' is not a verification mode",
        ),
        (
            "contract: fixture.unit_tests",
            "contract: fixture.undeclared",
            "capability fixture.undeclared: no such capability contract",
        ),
        (
            "location: worker",
            "location: cloud",
            "tool play_scenario: location 'cloud' is not one of agent, sandbox, worker",
        ),
        ("skills: [play-scenario]", "skills: [missing]", "skill missing: no SKILL.md in missing/"),
        (
            "skills: [test-loader, shared/conventions]",
            "skills: [shared/absent]",
            "skill shared/absent: no SKILL.md in absent/",
        ),
        ("roles: [qa]", "roles: [qa]\n  grants: [publish]", "unknown field: grants"),
        (
            "- provider: fixture-runner",
            "- provider: fixture-runner\n    - provider: fixture-runner",
            "prerequisites lists a provider more than once",
        ),
    ],
)
def test_a_defect_in_the_spec_is_refused_by_name(root, old, new, expected):
    _respec(root, old, new)

    with pytest.raises(SkillsetError) as refused:
        load_skillset(root / "fixture-qa", contracts=CONTRACTS)

    assert any(expected in e for e in refused.value.errors), refused.value.errors


def test_every_defect_is_reported_in_one_pass(root):
    """Bug caught: a loader that stops at the first defect, so an author fixes a skillset one
    refusal at a time."""
    _respec(root, "version: 2", "version: -1")
    _respec(root, "modes: [play]", "modes: [editor]")
    _respec(root, "skills: [play-scenario]", "skills: [missing]")

    with pytest.raises(SkillsetError) as refused:
        load_skillset(root / "fixture-qa", contracts=CONTRACTS)

    assert len(refused.value.errors) == 3
    assert refused.value.skillset == "fixture-qa"


def test_a_skill_without_its_name_and_description_is_refused(root):
    (root / "fixture-qa/skills/play-scenario/SKILL.md").write_text(
        "---\nname: play-scenario\n---\nDo the work.\n"
    )

    with pytest.raises(SkillsetError, match="front matter lacks description"):
        load_skillset(root / "fixture-qa", contracts=CONTRACTS)


def test_a_skillset_may_specialize_a_planned_task_type_as_its_own_contract(root):
    """§6.1: the three existing planned types are their own contracts. They carry no
    verification mode, so a skillset declares none for them."""
    _respec(root, "contract: fixture.unit_tests\n      modes: [headless]", "contract: qa.test")

    skillset = load_skillset(root / "fixture-qa", contracts=CONTRACTS)

    assert skillset.capability_for("qa.test").modes == ()


def test_the_catalog_reads_every_skillset_and_never_the_shared_directory(root):
    assert list(load_skillsets(root, contracts=CONTRACTS)) == ["fixture-qa"]


def test_one_invalid_skillset_fails_the_catalog_rather_than_vanishing_from_it(root):
    """Bug caught: a skipped skillset turning its author's typo into a coverage refusal on
    another operator's cycle, with nothing naming the typo."""
    (root / "broken").mkdir()

    with pytest.raises(SkillsetError, match="skillset broken: no skillset.yaml"):
        load_skillsets(root, contracts=CONTRACTS)


def test_no_skillset_is_shipped_and_a_missing_directory_is_an_empty_catalog(tmp_path):
    assert load_skillsets(tmp_path / "absent") == {}
    assert load_skillsets() == {}, f"phase 1 ships none; found one under {PACKAGED_SKILLSETS_DIR}"


def test_a_planned_task_type_resolves_as_its_own_contract_and_others_dont():
    develop = capability_contract("development.develop")

    assert develop == CapabilityContractDeclaration(
        "development.develop", TaskType.DEVELOPMENT_DEVELOP, ""
    )
    assert capability_contract("qa.validate") is None
    assert capability_contract("fixture.unit_tests") is None
    assert capability_contract("fixture.unit_tests", CONTRACTS).task_type is TaskType.QA_TEST


def test_declared_contracts_are_checked_for_ids_modes_and_evidence():
    declared = {
        "wrong.key": CONTRACTS["fixture.unit_tests"],
        "qa.test": CapabilityContractDeclaration("qa.test", TaskType.QA_TEST, "per test"),
        "fixture.twice": CapabilityContractDeclaration(
            "fixture.twice",
            TaskType.QA_TEST,
            " ",
            (VerificationMode.PLAY, VerificationMode.PLAY),
        ),
    }

    assert contract_errors(declared) == [
        "wrong.key: declared under a key that isn't its id (fixture.unit_tests)",
        "qa.test: a contract's id can't be a task type's; a plannable task type is already "
        "its own contract",
        "fixture.twice: a verification mode is listed more than once",
        "fixture.twice: a contract says what evidence it must produce",
    ]
    assert contract_errors(CONTRACTS) == []


GAME_SPEC = """
    api_version: squadops.skillset/v1
    skillset:
      id: fixture-game-qa
      version: 1
      description: Verifies a fixture game
      roles: [qa]
      platform: {id: fixture, variants: [local]}
      prerequisites:
        - provider: fixture-editor
      capabilities:
        - contract: game.unit_tests
          modes: [headless]
        - contract: game.scenario_verification
          modes: [play]
          tools:
            - {id: play_scenario, provider: fixture-editor, location: worker}
"""


def _game_skillset(tmp_path, spec: str = GAME_SPEC) -> Path:
    directory = tmp_path / "fixture-game-qa"
    directory.mkdir()
    (directory / "skillset.yaml").write_text(textwrap.dedent(spec))
    return directory


def test_a_skillset_specializes_the_registered_game_contracts(tmp_path):
    """SIP-0118 R4.2 with SIP-0116 §4: checked against the contracts the deployment declares,
    not a fixture table. Bug caught: the registry and the loader disagreeing on a contract's
    id or modes, so the first real skillset fails to load."""
    skillset = load_skillset(_game_skillset(tmp_path))

    assert [(c.contract, c.modes) for c in skillset.capabilities] == [
        ("game.unit_tests", (VerificationMode.HEADLESS,)),
        ("game.scenario_verification", (VerificationMode.PLAY,)),
    ]


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (
            "modes: [play]",
            "modes: [headless]",
            "capability game.scenario_verification: the contract doesn't run in headless mode",
        ),
        (
            "contract: game.unit_tests",
            "contract: game.build_verification",
            "capability game.build_verification: no such capability contract",
        ),
    ],
    ids=["a mode the contract lacks", "a contract nobody declared"],
)
def test_a_skillset_cannot_claim_what_the_registered_contracts_do_not_declare(
    tmp_path, old, new, expected
):
    """One mode never implies another, and a skillset specializes: it never defines."""
    with pytest.raises(SkillsetError) as refused:
        load_skillset(_game_skillset(tmp_path, GAME_SPEC.replace(old, new)))

    assert expected in refused.value.errors
