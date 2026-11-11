"""The fixture provider's one operation: a declared scenario read against a staged world
(SIP-0117 R5.5, R5.8; #3044)."""

from __future__ import annotations

import dataclasses
import json

import pytest

from adapters.remote_execution.factory import create_operation_runner
from adapters.remote_execution.fixture_operation_runner import (
    HOLD_PATH,
    OPERATION,
    PROVIDER,
    RUN_LOG_NAME,
    VOCABULARY,
    WORLD_PATH,
    FixtureOperationRunner,
)
from squadops.remote_execution.models import (
    AssertionOutcome,
    OperationStatus,
    RemoteOperationRequest,
    outcomes_by_assertion,
    result_defects,
)
from squadops.remote_execution.scenario import canonical_text, frozen_scenario
from tests.unit.remote_execution.scenario_fixture import (
    DOOR_OPENS,
    OPEN,
    SHUT,
    door_opens,
    tree,
)


def _request(files: dict[str, str], *, scenario=None, operation: str = OPERATION):
    return RemoteOperationRequest(
        contract="game.scenario_verification",
        mode="play",
        provider=PROVIDER,
        operation=operation,
        location="worker",
        source_revision="rev_1",
        source_files=files,
        scenario=scenario if scenario is not None else door_opens(),
        task_id="task_1",
        dispatch_id="dispatch-3",
    )


def _outcomes(asked, result) -> dict[str, tuple[AssertionOutcome, str]]:
    return {k: (r.outcome, r.observed) for k, r in outcomes_by_assertion(asked, result).items()}


@pytest.mark.parametrize(
    ("world", "door"),
    [
        (SHUT, (AssertionOutcome.FAILED, "true")),
        (OPEN, (AssertionOutcome.PASSED, "false")),
        # The door isn't built yet: the observation executes, and observes an absent instance.
        ({**SHUT, "server": {}}, (AssertionOutcome.FAILED, "<absent>")),
    ],
)
async def test_each_assertion_is_read_from_the_world_the_request_stages(world, door):
    """Bug caught: the fixture passing every assertion whatever was staged, so a rehearsal
    proves nothing; or an instance that isn't there read as not executed, which would block
    every feature not yet built instead of failing it on the baseline."""
    asked = _request(tree(world))

    result = await FixtureOperationRunner().run(asked)

    assert result_defects(asked, result) == []
    assert _outcomes(asked, result) == {
        "spawned": (AssertionOutcome.PASSED, "100"),
        "door-open": door,
    }
    (log,) = result.evidence
    assert log.name == RUN_LOG_NAME
    assert [step["action"] for step in json.loads(log.content)["steps"]] == [
        "move_to",
        "click_gui",
    ]


async def test_a_setup_that_isnt_established_reads_every_assertion_setup_failed():
    """Bug caught: assertions read in a world the scenario's setup never established, so a
    player who never spawned reads as a door that didn't open: an executed failure."""
    unspawned = {**OPEN, "client": {}}
    asked = _request(tree(unspawned))

    result = await FixtureOperationRunner().run(asked)

    assert result.status is OperationStatus.COMPLETED
    assert {k: o for k, (o, _) in _outcomes(asked, result).items()} == {
        "spawned": AssertionOutcome.SETUP_FAILED,
        "door-open": AssertionOutcome.SETUP_FAILED,
    }


def _edited(scenario):
    """The frozen text with one expected value changed, as an edit after freezing would."""
    return scenario.document.replace('"value":false', '"value":true')


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (
            lambda s: dataclasses.replace(s, document=_edited(s)),
            "it was changed after it was frozen",
        ),
        (
            lambda s: dataclasses.replace(s, named_assertion="spawned"),
            "the request names 'spawned' as the criterion's assertion",
        ),
        (
            lambda s: frozen_scenario(
                {**DOOR_OPENS, "reader": "studio/1"},
                dataclasses.replace(VOCABULARY, reader="studio/1"),
            ),
            "'reader' is 'studio/1', and the vocabulary is 'fixture/1'",
        ),
    ],
)
async def test_a_scenario_that_isnt_the_frozen_one_for_this_reader_is_not_executed(change, reason):
    """Bug caught: a scenario edited after it was frozen, or one for another reader, run
    anyway, so a pass no longer means the scenario that was approved."""
    asked = _request(tree(OPEN), scenario=change(door_opens()))

    result = await FixtureOperationRunner().run(asked)

    assert result.status is OperationStatus.NOT_EXECUTED
    assert reason in result.reason
    assert result.records == ()


@pytest.mark.parametrize(
    ("world", "reason"),
    [
        (None, f"no world is staged at {WORLD_PATH}"),
        ("{not json", f"{WORLD_PATH} isn't JSON"),
        (json.dumps({"lobby": {}}), f"{WORLD_PATH} is an object keyed by context"),
        (json.dumps({"server": {"Workspace.Door": 1}}), "server maps each instance path"),
    ],
)
async def test_a_world_that_cant_be_read_is_not_executed_with_why(world, reason):
    """Bug caught: a missing or malformed world read as an empty one, so every assertion
    executes against nothing and fails: an executed failure of a scenario that never ran."""
    files = tree(OPEN)
    if world is None:
        del files[WORLD_PATH]
    else:
        files[WORLD_PATH] = world

    result = await FixtureOperationRunner().run(_request(files))

    assert result.status is OperationStatus.NOT_EXECUTED
    assert reason in result.reason


async def test_a_staged_hold_waits_that_long_before_it_reads():
    """Bug caught: the hold ignored, so a rehearsal never sees a lease renewed."""
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    result = await FixtureOperationRunner(sleep=sleep).run(
        _request(tree(OPEN, **{HOLD_PATH: " 42.5\n"}))
    )

    assert slept == [42.5]
    assert result.status is OperationStatus.COMPLETED


@pytest.mark.parametrize("held", ["soon", "-1", "nan", "inf", ""])
async def test_a_hold_that_isnt_a_number_of_seconds_is_not_executed_with_the_value(held):
    """Bug caught: an unreadable hold read as no hold, or as a wait that never ends."""
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    asked = _request(tree(OPEN, **{HOLD_PATH: held}))
    result = await FixtureOperationRunner(sleep=sleep).run(asked)

    assert result.status is OperationStatus.NOT_EXECUTED
    assert result.reason == f"{HOLD_PATH} is {held!r}, which isn't a number of seconds"
    assert (result.records, slept) == ((), [])
    assert result_defects(asked, result) == []


async def test_an_operation_the_fixture_doesnt_run_is_not_executed():
    """Bug caught: any operation name answered with the fixture's reading."""
    result = await FixtureOperationRunner().run(_request(tree(OPEN), operation="play_scenario"))

    assert result.status is OperationStatus.NOT_EXECUTED
    assert result.reason == (
        "the fixture provider runs fixture/declared_scenario, and was asked for "
        "fixture/play_scenario"
    )


def test_the_frozen_fixture_is_the_canonical_text_of_its_declaration():
    """Bug caught: the fixture's text drifting from its declaration, so a test stages one
    scenario and freezes another."""
    assert door_opens().document == canonical_text(DOOR_OPENS)


def test_a_provider_the_factory_doesnt_know_is_refused_by_name():
    """Bug caught: an unknown provider answered with the fixture, so a worker meant for a real
    tool serves the fixture's operation under its name."""
    with pytest.raises(ValueError, match="Unknown operation runner provider: roblox-studio"):
        create_operation_runner("roblox-studio")
    assert [(o.provider, o.operation) for o in create_operation_runner("fixture").serves()] == [
        (PROVIDER, OPERATION)
    ]
