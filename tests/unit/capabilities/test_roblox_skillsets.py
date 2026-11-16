"""The packaged Roblox skillsets against the Studio provider they name (SIP-0118 R4.3; SIP-0117
R5.9; #3041).

The scenario a strategy task writes is frozen against the vocabulary the cycle keeps, from the QA
skillset that supplies ``game.scenario_verification``. It is then played by the worker's
``roblox-studio`` provider, which reads its own copy of that vocabulary and serves one operation.
Each test enters at the call the cycle makes: the kept copy and ``scenario_vocabulary_for`` for
the vocabulary, and ``tool_request`` for the tool a scenario's operation runs.
"""

from __future__ import annotations

from importlib import resources

import pytest

from adapters.remote_execution.game_dev_roblox_studio import vocabulary as studio_vocabulary
from adapters.remote_execution.game_dev_roblox_studio.runner import OPERATION, PROVIDER
from squadops.capabilities.operation_supply import OperationSupplyError, tool_request
from squadops.capabilities.skillsets import SCENARIO_VOCABULARY_FILE, load_skillsets
from squadops.cycles.skillset_content import scenario_vocabulary_for
from squadops.cycles.skillset_coverage import Assignment

QA = "roblox-studio-qa"
SCENARIO = "game.scenario_verification"


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


def test_the_strategy_skills_worked_example_is_one_the_rails_accept(catalog):
    """Bug caught: the vocabulary or the rails changing under the skill, so the one example the
    strategy model copies from teaches a scenario every proposal is refused for (an action the
    reader no longer takes, a surface that isn't the named assertion's path)."""
    import re

    import yaml

    from squadops.remote_execution.scenario import read_declaration

    text = catalog["roblox-increment-design"].skill_files["play-scenario-authoring"]["SKILL.md"]
    criterion = yaml.safe_load(re.search(r"```yaml\n(.*?)```", text, re.S).group(1))["criteria"][0]

    declaration = read_declaration(criterion["scenario"], studio_vocabulary.VOCABULARY)

    named = next(a for a in declaration.assertions if a.assertion_id == declaration.named_assertion)
    assert criterion["surface_kind"] == "scenario"
    assert declaration.scenario_id == criterion["id"]
    assert named.observe.arguments["path"] == criterion["surface"]
