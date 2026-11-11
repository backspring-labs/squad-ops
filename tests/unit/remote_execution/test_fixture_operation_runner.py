"""The fixture provider's one operation (SIP-0117 R5.5)."""

from __future__ import annotations

import hashlib
import json

import pytest

from adapters.remote_execution.factory import create_operation_runner
from adapters.remote_execution.fixture_operation_runner import (
    HOLD_PATH,
    MANIFEST_NAME,
    OPERATION,
    PROVIDER,
    FixtureOperationRunner,
)
from squadops.remote_execution.models import (
    AssertionOutcome,
    OperationStatus,
    RemoteOperationRequest,
    Scenario,
    outcomes_by_assertion,
    result_defects,
)


def _request(files: dict[str, str], *assertions: str, operation: str = OPERATION):
    return RemoteOperationRequest(
        contract="fixture.contract",
        mode="simulation",
        provider=PROVIDER,
        operation=operation,
        location="worker",
        source_revision="rev_1",
        source_files=files,
        scenario=Scenario("scn_1", "sha256:abc", assertions),
        dispatch_id="dispatch-3",
    )


async def test_each_assertion_reads_whether_its_path_is_staged_with_content():
    """Bug caught: the fixture passing every assertion whatever was staged, so a rehearsal
    proves nothing; or a result its own request can't be read against."""
    asked = _request({"a.luau": "return 1\n", "b.luau": ""}, "a.luau", "b.luau", "c.luau")

    result = await FixtureOperationRunner().run(asked)

    assert result_defects(asked, result) == []
    outcomes = {k: (r.outcome, r.observed) for k, r in outcomes_by_assertion(asked, result).items()}
    assert outcomes == {
        "a.luau": (AssertionOutcome.PASSED, "staged, 9 bytes"),
        "b.luau": (AssertionOutcome.FAILED, "staged, empty"),
        "c.luau": (AssertionOutcome.FAILED, "not staged"),
    }
    (manifest,) = result.evidence
    assert (manifest.name, manifest.media_type) == (MANIFEST_NAME, "application/json")
    assert json.loads(manifest.content) == {
        "a.luau": "sha256:" + hashlib.sha256(b"return 1\n").hexdigest(),
        "b.luau": "sha256:" + hashlib.sha256(b"").hexdigest(),
    }


async def test_a_staged_hold_waits_that_long_before_it_checks():
    """Bug caught: the hold ignored, so a rehearsal never sees a lease renewed."""
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    result = await FixtureOperationRunner(sleep=sleep).run(_request({HOLD_PATH: " 42.5\n"}))

    assert slept == [42.5]
    assert result.status is OperationStatus.COMPLETED


@pytest.mark.parametrize("held", ["soon", "-1", "nan", "inf", ""])
async def test_a_hold_that_isnt_a_number_of_seconds_is_not_executed_with_the_value(held):
    """Bug caught: an unreadable hold read as no hold, or as a wait that never ends."""
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    asked = _request({HOLD_PATH: held, "a.luau": "x"}, "a.luau")
    result = await FixtureOperationRunner(sleep=sleep).run(asked)

    assert result.status is OperationStatus.NOT_EXECUTED
    assert result.reason == f"{HOLD_PATH} is {held!r}, which isn't a number of seconds"
    assert (result.records, slept) == ((), [])
    assert result_defects(asked, result) == []


async def test_an_operation_the_fixture_doesnt_run_is_not_executed():
    """Bug caught: any operation name answered with the staged-files check."""
    asked = _request({"a.luau": "x"}, "a.luau", operation="play_scenario")

    result = await FixtureOperationRunner().run(asked)

    assert result.status is OperationStatus.NOT_EXECUTED
    assert result.reason == (
        "the fixture provider runs fixture/staged_files, and was asked for fixture/play_scenario"
    )


def test_a_provider_the_factory_doesnt_know_is_refused_by_name():
    """Bug caught: an unknown provider answered with the fixture, so a worker meant for a real
    tool serves the fixture's operation under its name."""
    with pytest.raises(ValueError, match="Unknown operation runner provider: roblox-studio"):
        create_operation_runner("roblox-studio")
    assert [(o.provider, o.operation) for o in create_operation_runner("fixture").serves()] == [
        (PROVIDER, OPERATION)
    ]
