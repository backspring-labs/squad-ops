"""The play's stage times (#3250): what the certification window's matched sets are read from.

What bugs would these catch?
- A stage that raised left untimed, so the slow stage that failed reads as fast.
- A misspelt stage name recorded under a name the window's amendment doesn't name.
- Stages reported out of their running order, or a stage that didn't run reported as zero.
"""

from __future__ import annotations

import json

import pytest

from adapters.remote_execution.game_dev_roblox_studio.stages import STAGES, STAGES_NAME, PlayStages
from squadops.remote_execution.models import OperationStatus
from tests.unit.remote_execution.test_roblox_studio_play_scenario import (
    DRIFTED,
    _Mac,
    _played,
    _request,
    _runner,
)


class _Clock:
    def __init__(self, *readings: float) -> None:
        self.readings = list(readings)

    def __call__(self) -> float:
        return self.readings.pop(0)


def test_each_stage_that_ran_is_timed_in_running_order_with_its_waits():
    stages = PlayStages(clock=_Clock(0.0, 1.5, 10.0, 12.25, 20.0, 120.0))
    with stages.stage("sync_s"):
        pass
    with stages.stage("session_open_s"):
        pass
    with stages.stage("scenario_s"):
        stages.wait(41.5)
        stages.wait(12.0)

    document = json.loads(stages.document())

    assert list(document["stages"]) == ["session_open_s", "sync_s", "scenario_s"]
    assert document["stages"] == {"session_open_s": 2.25, "sync_s": 1.5, "scenario_s": 100.0}
    assert (document["waits"], document["stopped_at"]) == ([41.5, 12.0], None)


def test_a_stage_that_raised_is_timed_to_where_it_raised_and_named():
    stages = PlayStages(clock=_Clock(0.0, 7.0))

    with pytest.raises(OSError), stages.stage("console_s"):
        raise OSError("the console couldn't be read")

    document = json.loads(stages.document())
    assert (document["stages"], document["stopped_at"]) == ({"console_s": 7.0}, "console_s")


def test_a_name_that_isnt_a_stage_is_refused():
    with pytest.raises(ValueError, match="isn't one of the play's stages"):
        with PlayStages().stage("sync"):
            pass


# --- the runner's own stages, over the stand-in StudioMCP --------------------------------------


def _stages(result) -> dict:
    [item] = [e for e in result.evidence if e.name == STAGES_NAME]
    assert item.media_type == "application/json"
    return json.loads(item.content)


async def test_a_played_scenario_carries_each_stage_it_ran_and_each_wait(tmp_path):
    """Entered at ``RobloxStudioRunner.run``, the call a worker makes. Bugs caught: a stage the
    transaction ran left untimed, or stages reported in another order than they run, so the
    matched sets compare the wrong stage; a wait missing from ``waits``."""
    world = _played(tmp_path)

    result = await _runner(world, _Mac(world=world)).run(_request())

    assert result.status is OperationStatus.COMPLETED, result.reason
    document = _stages(result)
    # R5.36: the state is read twice, at the pin check and after play; no reset ran.
    ran = [name for name in STAGES if name not in ("reset_s", "baseline_before_s")]
    assert list(document["stages"]) == ran
    assert all(seconds >= 0 for seconds in document["stages"].values())
    assert len(document["waits"]) == 1  # the declaration's one wait_until
    assert (document["stopped_at"], document["transactions"]) == (None, 1)


async def test_a_play_begun_again_after_a_drift_times_the_reset(tmp_path):
    world = _played(tmp_path, baseline=DRIFTED)

    result = await _runner(world, _Mac(world=world)).run(_request())

    assert result.status is OperationStatus.COMPLETED, result.reason
    document = _stages(result)
    # Two attempts at the transaction, each stage summed over them, and the reset between.
    assert (document["transactions"], "reset_s" in document["stages"]) == (2, True)
