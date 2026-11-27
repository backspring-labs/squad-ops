"""SIP-0117 R5.36 (#3250): a play reads the place's non-script state twice, at its pin check and
after play, and holds the second to the first.

The read after the sync is gone. The sync writes only inside the three synced folders, which the
state read leaves out, so that read saw nothing the read after play doesn't. Entered at
``RobloxStudioRunner.run`` over the stand-in ``StudioMCP``.

What bugs would these catch?
- A change to the place made while the sync ran, and left in place, credited: it is now caught,
  where the two reads after the pin check used to agree on it.
- A place without a synced root its scripts go into: the sync creates the folder, the read after
  play then differs from the pin on every play, and every play is refused as the work's.
- ``place_baseline`` recorded as the pin's constant rather than the pin check's own reading.
"""

from __future__ import annotations

import hashlib
import json

from squadops.remote_execution.models import OperationStatus
from tests.unit.remote_execution.test_roblox_studio_place_state import BASELINE
from tests.unit.remote_execution.test_roblox_studio_play_scenario import (
    _Mac,
    _played,
    _request,
    _runner,
)

MOVED = [line.replace("Brightness=1", "Brightness=2") for line in BASELINE]


async def test_a_change_made_while_the_sync_ran_is_refused_as_the_works(tmp_path):
    """Before R5.36 the read after the sync and the read after play both held the change and
    agreed, so the play was credited on a place that wasn't its pin."""
    world = _played(tmp_path, baseline_after_sync=MOVED, baseline_after_play=MOVED)

    result = await _runner(world, _Mac(world=world)).run(_request())

    assert (result.status, result.tool_unready) == (OperationStatus.NOT_EXECUTED, False)
    assert result.reason.startswith(
        "the place's non-script state changed between its pin check and the end of play, so "
        "the run proves nothing: "
    )
    assert "Workspace/Lamp" in result.reason  # baseline_changes names what changed
    assert result.records == ()


async def test_a_play_reads_the_state_twice_and_records_the_pin_checks_own_reading(tmp_path):
    world = _played(tmp_path)

    result = await _runner(world, _Mac(world=world)).run(_request())

    assert result.status is OperationStatus.COMPLETED, result.reason
    pinned = hashlib.sha256("\n".join(BASELINE).encode()).hexdigest()
    assert result.ran_with["place_baseline"] == pinned[:16]
    baselines = [
        c for c in (tmp_path / "calls.log").read_text().split() if c == "execute_luau:baseline"
    ]
    # Two reads of the state, each one page and its release here, not three.
    assert len(baselines) == 2 * 2


async def test_a_place_without_the_synced_root_its_scripts_go_into_is_refused_by_name(tmp_path):
    """Nothing is written: the root's absence is read from the pin check's own lines."""
    rootless = [line for line in BASELINE if not line.startswith("ServerScriptService/Server\t")]
    world = _played(tmp_path, baseline=rootless)
    files_digest = hashlib.sha256("\n".join(rootless).encode()).hexdigest()
    runner = _runner(world, _Mac(world=world))
    runner._files = runner._files.__class__(
        **{**runner._files.__dict__, "baseline_digest": files_digest}
    )  # the pin is the rootless place, so the pin check holds and the root check is reached

    result = await runner.run(_request())

    assert (result.status, result.tool_unready) == (OperationStatus.NOT_EXECUTED, True)
    assert result.reason.startswith(
        "nothing was run: the place has no ServerScriptService/Server, which the sync would create"
    )
    calls = (tmp_path / "calls.log").read_text().split()
    assert "execute_luau:sync" not in calls
    assert json.loads(world.read_text())["mode"] == "Edit"
