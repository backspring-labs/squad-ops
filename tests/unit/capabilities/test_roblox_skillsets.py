"""The packaged Roblox skillsets against the Studio provider they name (SIP-0118 R4.3; SIP-0117
R5.9; #3041).

The scenario a strategy task writes is frozen against the vocabulary the cycle keeps, from the QA
skillset that supplies ``game.scenario_verification``. It is then played by the worker's
``roblox-studio`` provider, which reads its own copy of that vocabulary and serves one operation.
Each test enters at the call the cycle makes: the kept copy and ``scenario_vocabulary_for`` for
the vocabulary, and ``tool_request`` for the tool a scenario's operation runs.
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

import pytest

from adapters.cycles.config_squad_profile import ConfigSquadProfile
from adapters.remote_execution.game_dev_roblox_studio import vocabulary as studio_vocabulary
from adapters.remote_execution.game_dev_roblox_studio.runner import OPERATION, PROVIDER
from squadops.capabilities.operation_supply import OperationSupplyError, tool_request
from squadops.capabilities.skillsets import SCENARIO_VOCABULARY_FILE, load_skillsets
from squadops.cycles.skillset_content import scenario_vocabulary_for
from squadops.cycles.skillset_coverage import Assignment, cycle_coverage
from squadops.stacks.development_profiles import DEVELOPMENT_PROFILES

QA = "roblox-studio-qa"
SCENARIO = "game.scenario_verification"
SQUAD = "game-dev-roblox"
SQUAD_PROFILES = Path(__file__).resolve().parents[3] / "config" / "squad-profiles.yaml"

#: The profile that says what a Roblox game's work requires (SIP-0118 R5.2), and a cycle's
#: configuration naming it, as an operator's request does.
ROBLOX = DEVELOPMENT_PROFILES["game_dev_roblox"]
NAMED = {"development_profile": "game_dev_roblox"}


@pytest.fixture(scope="module")
def catalog():
    return load_skillsets()


def test_every_skill_holding_a_vocabulary_holds_the_one_the_worker_reads(catalog):
    """Bug caught: the harness's vocabulary changed (an action added or renamed) and a skill's
    copy left behind, so strategy writes scenarios the worker refuses, or proposals are refused
    for actions the worker plays."""
    worker = (
        resources.files("adapters.remote_execution.game_dev_roblox_studio")
        .joinpath(studio_vocabulary.VOCABULARY_FILE)
        .read_text(encoding="utf-8")
    )
    holders = {
        f"{skillset.id}/{skill}": files[SCENARIO_VOCABULARY_FILE]
        for skillset in catalog.values()
        for skill, files in skillset.skill_files.items()
        if SCENARIO_VOCABULARY_FILE in files
    }

    assert sorted(holders) == [
        "roblox-increment-design/play-scenario-authoring",
        "roblox-studio-qa/studio-play-scenario",
    ]
    assert {where: text == worker for where, text in holders.items()} == dict.fromkeys(
        holders, True
    )


def test_a_cycle_keeping_the_qa_skillset_freezes_scenarios_against_the_workers_reader(catalog):
    """The path a proposal's scenario takes, entered at the kept copy a cycle writes and the call
    the proposal's rails read it through. Bug caught: a scenario frozen against no vocabulary (so
    every scenario criterion is refused as unverifiable) or against another reader than the one
    the worker registers."""
    from squadops.cycles.skillset_content import kept_document

    qa = catalog[QA]
    document = kept_document([Assignment("qa", "eve", QA, qa.version, qa.digest)], catalog)
    record = {"offered": [{"contract": SCENARIO, "mode": "play", "skillset": QA}]}

    vocabulary = scenario_vocabulary_for(document, record, SCENARIO)

    assert vocabulary == studio_vocabulary.VOCABULARY
    assert vocabulary.reader == "roblox-studio/1"


def test_a_scenarios_operation_runs_the_one_tool_the_worker_serves(catalog):
    """Bug caught: the QA skillset requesting a tool id or provider the worker doesn't serve, so
    every scenario's operation is queued for no worker and reads not executed."""
    qa = catalog[QA]
    operation = {"contract": SCENARIO, "mode": "play", "skillset": QA, "skillset_digest": qa.digest}

    tool = tool_request(catalog, operation)

    assert (tool.provider, tool.id, tool.location) == (PROVIDER, OPERATION, "worker")


def test_a_scenario_isnt_run_by_a_skillset_that_doesnt_supply_it(catalog):
    """Bug caught: the strategy skillset, which writes scenarios and holds the vocabulary as its
    model's reference, read as a supplier of the operation that plays them."""
    design = catalog["roblox-increment-design"]
    operation = {
        "contract": SCENARIO,
        "mode": "play",
        "skillset": design.id,
        "skillset_digest": design.digest,
    }

    with pytest.raises(OperationSupplyError):
        tool_request(catalog, operation)


def _worked_criteria(catalog) -> list[dict]:
    """Every criterion of every whole change-request example in the strategy skill: the fenced
    YAML blocks that hold ``criteria``. A fragment showing one action or assertion isn't one."""

    import yaml

    text = catalog["roblox-increment-design"].skill_files["play-scenario-authoring"]["SKILL.md"]
    examples = [yaml.safe_load(block) for block in re.findall(r"```yaml\n(.*?)```", text, re.S)]
    return [
        criterion
        for example in examples
        if isinstance(example, dict) and "criteria" in example
        for criterion in example["criteria"]
    ]


def test_every_worked_example_in_the_strategy_skill_is_one_the_rails_accept(catalog):
    """Bug caught: the vocabulary or the rails changing under the skill, or an example added
    that they refuse, so an example the strategy model copies from teaches a scenario every
    proposal is refused for (an action the reader no longer takes, a surface that isn't the
    named assertion's path, a scenario id that isn't its criterion's)."""
    from squadops.remote_execution.scenario import read_declaration

    scenarios = [c for c in _worked_criteria(catalog) if c["surface_kind"] == "scenario"]

    assert [c["id"] for c in scenarios] == ["S1", "S2", "S3"]
    for criterion in scenarios:
        declaration = read_declaration(criterion["scenario"], studio_vocabulary.VOCABULARY)
        named = next(
            a for a in declaration.assertions if a.assertion_id == declaration.named_assertion
        )
        assert declaration.scenario_id == criterion["id"]
        assert named.observe.arguments["path"] == criterion["surface"], criterion["id"]


def test_the_strategy_skills_examples_answer_the_self_review_it_asks_for(catalog):
    """#3199: the skill ends by asking each criterion's ``observable`` to say, in fixed words,
    whether it is played or headless, the wrong builds it fails on, a changing value's band,
    and what a headless criterion left unplayed. The model copies the examples. Bugs caught: an
    example that leaves an answer out, so the copied shape does too; the headless example
    declaring no gap; and the example of a changing value named by an exact match or a
    format-only check, the two shapes the 2.8 gate returned."""
    criteria = {c["id"]: c for c in _worked_criteria(catalog)}

    for criterion in criteria.values():
        kind = "Headless." if criterion["surface_kind"] == "package" else "Played."
        assert criterion["observable"].startswith(kind), criterion["id"]
        assert "Fails on:" in criterion["observable"], criterion["id"]
    assert "Band:" in criteria["S2"]["observable"]
    assert "Not played:" in criteria["P1"]["observable"]
    assert [c["surface_kind"] for c in criteria.values()].count("package") == 1
    # The changing value is waited for and then read as a band, and never moved to by a key.
    counting = criteria["S2"]["scenario"]
    [wait] = counting["steps"]
    [named] = [a for a in counting["assertions"] if a["id"] == counting["named_assertion"]]
    assert (wait["action"], wait["expect"], wait["observe"]) == (
        "wait_until", named["expect"], named["observe"],
    )  # fmt: skip
    assert named["expect"] == {"op": "contains", "value": "in 1"}
    # The played half of the two-part result fails on today's game: a missing warning fails equals.
    hidden = criteria["S3"]["scenario"]
    [named] = [a for a in hidden["assertions"] if a["id"] == hidden["named_assertion"]]
    assert named["expect"] == {"op": "equals", "value": False}


def test_the_strategy_skills_coverage_table_and_its_examples_quote_the_items_sentences(catalog):
    """#3199's first replay: an author restated the item without its second sentence and covered
    the restatement completely. The skill now has each criterion quote the sentence it reads
    after ``Reads:``, and its coverage table works the invented item one sentence at a time. Bugs
    caught: an example with no ``Reads:``, so the copied shape drops it; a sentence of the
    example item missing from the table, which is the omission itself; and the table naming one
    criterion for a sentence while that criterion's example quotes another."""
    text = catalog["roblox-increment-design"].skill_files["play-scenario-authoring"]["SKILL.md"]
    criteria = {c["id"]: c for c in _worked_criteria(catalog)}
    rule = text[text.index("### 1. Coverage") : text.index("### 2. Reachability")]
    item = " ".join(line[2:] for line in rule.splitlines() if line.startswith("> "))
    rows = re.findall(r'^\| "(.+?)" \| .+? \| `(\w+)`', rule, re.M)

    # Joined, the table's sentences are the item: none dropped, none reworded.
    assert " ".join(sentence for sentence, _ in rows) == item
    assert [reader for _, reader in rows] == ["P1", "S3"]
    for sentence, reader in rows:
        assert f'Reads: "{sentence}"' in " ".join(criteria[reader]["observable"].split())
    for criterion in criteria.values():
        assert re.search(r'Reads: ".+?\."', criterion["observable"]), criterion["id"]


def test_the_strategy_skill_keeps_its_stop_for_an_effect_nothing_can_observe(catalog):
    """`roblox-skills-v3`'s unobservable case answers with this stop, and #3199 adds a case
    beside it where a `package` criterion is right (a state no action reaches). Bug caught: the
    new rule read as lifting the stop, so a sound is "proved" by a headless test of its rule."""
    text = catalog["roblox-increment-design"].skill_files["play-scenario-authoring"]["SKILL.md"]
    stop = text.index("If the criterion's effect is one `roblox-studio/1` can't observe, stop.")
    no_way_round = text.index("A `package` criterion is no way round that.")
    unreachable = text.index("A state no action reaches is another case")

    assert stop < no_way_round < unreachable
    assert 'stops: ["no scenario:"]' in text.split("---")[1]


def test_the_roblox_profile_is_the_neutral_profile_with_a_platform_and_requirements():
    """The skills replay captured its tasks under ``product_neutral`` and handed them the skills a
    cycle requiring the skillsets would (SIP-0116 §17p). Bug caught: the profile gaining advice,
    a source filter or a test pattern of its own, so a cycle under it renders another prompt than
    the one the replay tested; or its requirements leaving its fingerprint, so a retry can't tell
    the work now asks something of the squad."""
    import dataclasses

    from squadops.stacks.development_profiles import development_profile_fingerprint
    from squadops.stacks.requirements import requirement_errors

    neutral = dataclasses.asdict(DEVELOPMENT_PROFILES["product_neutral"])
    roblox = dataclasses.asdict(ROBLOX)

    assert sorted(k for k in neutral if neutral[k] != roblox[k]) == ["name", "platform", "requires"]
    assert roblox["platform"] == {"id": "roblox", "variant": "studio-place"}
    assert requirement_errors(ROBLOX.platform, ROBLOX.requires) == []
    assert development_profile_fingerprint("game_dev_roblox") != development_profile_fingerprint(
        "product_neutral"
    )


async def test_the_roblox_squad_covers_what_the_first_milestone_requires(catalog):
    """Entered at the comparison cycle creation makes (``cycle_coverage``, on a configuration
    naming the profile as an operator's request does), on the squad as the
    deploy seeds it. Bug caught: a skillset id misspelt, or declared on an agent of another
    role. A squad profile seeds once and an edit never reaches the deploy, so either would refuse
    every Roblox cycle until a new profile is cloned."""
    squad = await ConfigSquadProfile(yaml_path=SQUAD_PROFILES).get_profile(SQUAD)

    coverage = cycle_coverage(squad, NAMED, catalog)

    assert coverage.findings == ()
    assert [(a.role, a.agent_id, a.skillset) for a in coverage.assignments] == [
        ("strat", "nat", "roblox-increment-design"),
        ("dev", "neo", "roblox-luau-dev"),
        ("qa", "eve", QA),
    ]
    assert [(o.contract, o.mode, o.agent_id) for o in coverage.offered] == [
        ("game.increment_design", "", "nat"),
        ("game.gameplay_implementation", "", "neo"),
        ("game.unit_tests", "headless", "eve"),
        (SCENARIO, "play", "eve"),
    ]


async def test_a_squad_without_the_roblox_skillsets_is_refused_by_name(catalog):
    """The edge the squad exists for. Bug caught: coverage reading a squad that carries none of
    the skillsets as covered, so a Roblox cycle on the wrong squad would author with no skills."""
    plain = await ConfigSquadProfile(yaml_path=SQUAD_PROFILES).get_profile("full-38-tf")

    coverage = cycle_coverage(plain, NAMED, catalog)

    assert coverage.assignments == ()
    (finding,) = coverage.findings
    assert "Selected squad: `full-38-tf`" in finding.message
    for skillset in ("roblox-increment-design", "roblox-luau-dev", QA):
        assert skillset in finding.message


async def test_the_roblox_squad_is_the_tensorfold_roster_without_its_builder():
    """Bug caught: the squad drifting from the roster the Spark serves (a model id TensorFold
    doesn't serve, or a completion budget of its own), which would make its cycles a different
    experiment from every other cycle on that box."""
    provider = ConfigSquadProfile(yaml_path=SQUAD_PROFILES)
    squad = await provider.get_profile(SQUAD)
    served = await provider.get_profile("full-38-tf")

    def roster(profile):
        return [
            (a.agent_id, a.role, a.model, a.enabled, a.config_overrides, a.serves_roles)
            for a in profile.agents
            if a.role != "builder"
        ]

    assert roster(squad) == roster(served)
    assert [a.agent_id for a in squad.agents if a.role == "builder"] == []
