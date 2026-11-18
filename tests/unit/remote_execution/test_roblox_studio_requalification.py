"""Re-qualifying the worker after a Studio update (SIP-0117 R5.21; #3048).

Entered at ``requalify`` and at ``RobloxStudioRunner.run`` with the worker's pins read from its
qualification records, as ``worker.create_runner`` builds it, over the stand-in ``StudioMCP``.
Every record here is written by a re-qualification run, as on the worker. The live runs on the
real Studio are in the PR (``scripts/dev/studio_requalify.py``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio.qualification import (
    Qualifications,
    requalify,
)
from adapters.remote_execution.game_dev_roblox_studio.runner import (
    ProvedOn,
    RobloxStudioRunner,
    StudioBusy,
)
from adapters.remote_execution.game_dev_roblox_studio.session import StudioMcpSession
from squadops.remote_execution.models import OperationStatus
from tests.unit.remote_execution.test_roblox_studio_play_scenario import (
    DECLARATION,
    STANDIN,
    _files,
    _Mac,
    _played,
    _request,
    _scenario,
)
from tests.unit.remote_execution.test_roblox_studio_read_side import _tools

#: The qualification scenario: the click's two effects, each of which passes on the stand-in.
PASSING = _scenario(assertions=DECLARATION["assertions"][:2])


class _Studio:
    """The Mac's Studio as a test moves it: its version, and the world its StudioMCP reads."""

    def __init__(self, tmp_path: Path, version: str = "0.747.0") -> None:
        self.version = version
        self.world = _played(tmp_path)
        self.mac = _Mac(world=self.world)
        self.files = _files(tmp_path)

    def update(self, version: str, **tools) -> None:
        """Studio updated itself: a new version, and its tool list changed."""
        self.version = version
        doc = json.loads(self.world.read_text())
        doc["tools"] = _tools(**tools)
        self.world.write_text(json.dumps(doc))

    def runner(self, pins: ProvedOn | Qualifications) -> RobloxStudioRunner:
        return RobloxStudioRunner(
            Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"),
            session_factory=lambda **kw: StudioMcpSession(
                [sys.executable, str(STANDIN), str(self.world)], **kw
            ),
            studio_version_of=lambda _: self.version,
            discover_seconds=0.2,
            reopen_seconds=1.0,
            place_files=self.files,
            proved_on=pins,
            app=self.mac,
        )

    async def requalify(self, records: Qualifications, scenario=PASSING):
        return await requalify(
            records,
            self.runner,
            lambda name: _request(scenario, task_id=f"qualify-{name}", dispatch_id=name),
        )


def _records(tmp_path: Path) -> Qualifications:
    directory = tmp_path / "qualifications"
    directory.mkdir(exist_ok=True)
    return Qualifications(directory)


async def test_a_passing_requalification_moves_the_pin_and_the_next_claim_runs(tmp_path):
    """The done-when, end to end. Bugs caught:
    - an updated Studio still passing scenarios on the old pin;
    - a pin moved by a run that wasn't recorded, or a record that doesn't say what changed;
    - a worker that reads its pin only at start, so it refuses every claim after a passing
      re-qualification until a person restarts it."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    first, _ = await studio.requalify(records)
    worker = studio.runner(records)
    studio.update("0.748.0", insert_model={"readOnlyHint": True})

    refused = await worker.run(_request(PASSING))
    second, path = await studio.requalify(records)
    ran = await worker.run(_request(PASSING))

    assert refused.status is OperationStatus.NOT_EXECUTED
    assert "Studio is 0.748.0, and the operation was proved on 0.747.0" in refused.reason
    assert (first.passed, second.passed, second.failing) == (True, True, "")
    assert [s.name for s in second.steps] == ["play 1", "reset", "play 2"]
    assert (second.studio_version, second.replaces) == ("0.748.0", first.digest)
    assert (second.tools_added, second.tools_removed) == (("insert_model",), ())
    assert path.name.endswith("-passed.json") and records.pinned() == second
    assert ran.status is OperationStatus.COMPLETED, ran.reason
    assert ran.ran_with["qualified_by"] == second.digest[:16]


@pytest.mark.parametrize(
    ("break_it", "failing"),
    [
        (lambda s: None, "play 1: gold: failed"),
        (
            lambda s: s.files.baseline.write_bytes(b"another place"),
            "reset: failed: PlaceStateError: the baseline file",
        ),
    ],
    ids=["an-assertion-fails", "the-reset-fails"],
)
async def test_a_failing_requalification_leaves_the_pin_and_names_the_step(
    tmp_path, break_it, failing
):
    """Bugs caught: a failed run that moves the pin anyway, so the worker serves an updated
    Studio nothing passed on; a reset that fails after the update, read as qualified; a failure
    recorded with no step named, so the person can't tell what the update broke."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    first, _ = await studio.requalify(records)
    studio.update("0.748.0")
    break_it(studio)

    scenario = _scenario() if "gold" in failing else PASSING
    second, path = await studio.requalify(records, scenario)
    after = await studio.runner(records).run(_request(PASSING))

    assert (second.passed, second.studio_version) == (False, "0.748.0")
    assert second.failing.startswith(failing), second.failing
    assert path.name.endswith("-failed.json")
    assert records.pinned() == first
    assert after.status is OperationStatus.NOT_EXECUTED
    assert "proved on 0.747.0" in after.reason


def _hand_edited(path: Path) -> None:
    document = json.loads(path.read_text())
    document["studio_version"] = "0.748.0"
    path.write_text(json.dumps(document))


@pytest.mark.parametrize(
    ("spoil", "says"),
    [
        (None, "no passing qualification of roblox-studio 2 is recorded"),
        (_hand_edited, "doesn't match its own digest"),
        (lambda path: path.write_text("{"), "can't be read"),
    ],
    ids=["none-recorded", "a-record-edited-by-hand", "a-record-unreadable"],
)
async def test_a_worker_with_no_record_it_can_trust_runs_nothing(tmp_path, spoil, says):
    """R2.4 and the owner's ruling against silent fallbacks. Bugs caught: a pin moved by
    editing a file; an unreadable newer record skipped, so an older pin is used in its place;
    a worker with no record running on whatever Studio it finds."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    if spoil is not None:
        _, path = await studio.requalify(records)
        spoil(path)
    (tmp_path / "calls.log").unlink(missing_ok=True)

    result = await studio.runner(records).run(_request(PASSING))

    assert result.status is OperationStatus.NOT_EXECUTED
    assert says in result.reason
    assert not (tmp_path / "calls.log").exists()  # not a tool was called


async def test_studio_is_used_by_one_process_at_a_time(tmp_path):
    """Bugs caught: a claim played while a re-qualification quits and reopens Studio under it;
    a worker's reset quitting Studio mid-qualification; a re-qualification started during a
    claim, recording a run the claim interfered with."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    await studio.requalify(records)
    held = list(records.directory.glob("*.json"))
    worker = studio.runner(records)

    with records.exclusive():
        claimed = await worker.run(_request(PASSING))
        with pytest.raises(StudioBusy):
            await worker.reset()
    with worker._proved.exclusive(), pytest.raises(StudioBusy):
        await studio.requalify(records)

    assert claimed.status is OperationStatus.NOT_EXECUTED
    assert "is locked" in claimed.reason
    assert list(records.directory.glob("*.json")) == held  # nothing recorded
