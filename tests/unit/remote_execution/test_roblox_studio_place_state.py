"""The ``roblox-studio`` provider's frame around play (SIP-0117 R3.6; phase 2d, #3039).

Entered at ``RobloxStudioRunner.play_round`` and the place reads, over the stand-in ``StudioMCP``:
- synced scripts checked for attributes and tags (#3042's rule, placed at the worker);
- the non-script baseline read in pages and held equal through play;
- play started and stopped.

The live round on the real place is in the PR (``scripts/dev/studio_play_round.py``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio import place
from adapters.remote_execution.game_dev_roblox_studio.place import PlaceBaseline
from adapters.remote_execution.game_dev_roblox_studio.runner import RobloxStudioRunner
from adapters.remote_execution.game_dev_roblox_studio.session import StudioMcpSession, ToolDenied
from tests.unit.remote_execution.test_roblox_studio_read_side import STANDIN, _world

#: The place's non-script state as the baseline program writes it: path, class, then fields.
PLATE = "Workspace/Baseplate\tPart\tAnchored=boolean(true)\tCFrame=CFrame(0,-8,0,1,0,0,0,1,0,0,0,1)"
LAMP = "Workspace/Lamp\tPointLight\tBrightness=1\tEnabled=boolean(true)"
BASELINE = [
    "Lighting\tLighting\tClockTime=14",
    LAMP,
    PLATE,
    # The synced root the stand-in's requests write into, as a real place holds it (R5.36).
    "ServerScriptService/Server\tFolder",
]


def _runner(world: Path) -> RobloxStudioRunner:
    return RobloxStudioRunner(
        Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"),
        session_factory=lambda **kw: StudioMcpSession(
            [sys.executable, str(STANDIN), str(world)], **kw
        ),
        studio_version_of=lambda _: "0.747.0",
        discover_seconds=0.2,
    )


def _calls(tmp_path: Path) -> list[str]:
    return (tmp_path / "calls.log").read_text().split()


async def test_a_play_round_holds_the_place_and_stops_play(tmp_path):
    """The wiring. Bugs caught: the baseline taken after play starts, or not again after stop,
    so a play that changed the place reads as one that held; play left running, so the next
    transaction syncs into a play session whose edits stop throws away; or the marks read after
    play, when a marked script has already run."""
    world = _world(tmp_path, baseline=BASELINE, mode="Edit")

    held = await _runner(world).play_round()

    calls = _calls(tmp_path)
    starts = [i for i, c in enumerate(calls) if c == "start_stop_play"]
    baselines = [i for i, c in enumerate(calls) if c == "execute_luau:baseline"]
    assert (held.instances, len(held.baseline_digest)) == (len(BASELINE), 64)
    assert calls.index("execute_luau:identity") < calls.index("execute_luau:script_marks")
    assert calls.index("execute_luau:script_marks") < baselines[0] < starts[0]
    assert len(starts) == 2 and baselines[-1] > starts[1]
    assert json.loads(world.read_text())["mode"] == "Edit"


async def test_a_change_through_play_is_refused_naming_the_instance_and_what_changed(tmp_path):
    """R3.6: a part moved 0.01 studs. Bug caught: a round that compares counts or digests only, so
    the owner is told the place changed and not where."""
    moved = PLATE.replace("CFrame(0,-8", "CFrame(0.00999999978,-8")
    world = _world(tmp_path, baseline=BASELINE, baseline_after_play=[BASELINE[0], LAMP, moved])

    with pytest.raises(place.PlaceStateError) as raised:
        await _runner(world).play_round()

    assert str(raised.value).endswith(
        "Workspace/Baseplate: CFrame CFrame(0,-8,0,1,0,0,0,1,0,0,0,1) -> "
        "CFrame(0.00999999978,-8,0,1,0,0,0,1,0,0,0,1)"
    )


async def test_a_synced_script_carrying_attributes_or_tags_is_refused_before_play(tmp_path):
    """#3042's rule, placed at the worker. Bug caught: a script the repository can't describe
    played, so a pass rests on state the change request never named."""
    marked = [
        {"path": "ServerScriptService.Server.Main", "attributes": ["Debug"], "tags": ["Boss"]}
    ]
    world = _world(tmp_path, baseline=BASELINE, marked=marked)

    with pytest.raises(place.PlaceStateError, match="Main carries attributes Debug and tags Boss"):
        await _runner(world).play_round()

    assert "start_stop_play" not in _calls(tmp_path)


async def test_the_baseline_is_read_in_pages_and_released(tmp_path):
    """Bugs caught: one call for the whole place, past R3.6's 100,000-character result cap, which
    Studio truncates and reports as a success; or the snapshot kept in ``_G`` after the read, so
    the next read in the same Studio pages through stale lines."""
    world = _world(tmp_path, baseline=BASELINE, code_log=str(tmp_path / "code.log"))
    session = StudioMcpSession([sys.executable, str(STANDIN), str(world)], harness=True)
    await session.open()
    try:
        read = await place.baseline(session, "s-1", page_chars=len(PLATE) + 1)
    finally:
        await session.close()

    sent = [json.loads(line) for line in (tmp_path / "code.log").read_text().splitlines()]
    payloads = [json.loads(bytes.fromhex(c.split('"')[1]).decode()) for c in sent]
    assert read.lines == tuple(BASELINE)
    # A page a line, then the release.
    assert len(payloads) == len(BASELINE) + 1 and payloads[-1]["release"] is True
    assert len({p["snapshot"] for p in payloads}) == 1


async def test_a_baseline_page_that_doesnt_advance_is_refused_and_still_released(tmp_path):
    """Bug caught: a read that loops forever on a page that stops at its own offset, or returns
    the lines it had as the whole place."""
    world = _world(tmp_path, baseline=BASELINE, baseline_stall=True)
    session = StudioMcpSession([sys.executable, str(STANDIN), str(world)], harness=True)
    await session.open()
    try:
        with pytest.raises(place.PlaceReadError, match="didn't advance"):
            await place.baseline(session, "s-1")
    finally:
        await session.close()

    assert _calls(tmp_path)[-1] == "execute_luau:baseline"  # the release, after the refusal


async def test_play_that_never_reaches_its_mode_is_refused(tmp_path, monkeypatch):
    """Bug caught: a round that waits forever on a Studio that won't start play, or runs on as if
    it had (R3.6: a blocking call has no timeout of its own)."""
    world = _world(tmp_path, baseline=BASELINE, mode="Edit", stuck=True)
    monkeypatch.setattr(place, "PLAY_SECONDS", 0.3)

    with pytest.raises(place.PlaceReadError, match="didn't reach Play within 0.3s; it reads Edit"):
        await _runner(world).play_round()


async def test_only_a_harness_session_may_start_or_stop_play(tmp_path):
    """Bug caught: the read side's session able to start play, which changes Studio's state under
    a read that promised to write nothing."""
    world = _world(tmp_path)
    session = StudioMcpSession([sys.executable, str(STANDIN), str(world)])
    await session.open()
    try:
        with pytest.raises(ToolDenied):
            await session.call("start_stop_play", {"studio_id": "s-1", "is_start": True})
    finally:
        await session.close()
    log = tmp_path / "calls.log"
    assert not log.exists() or "start_stop_play" not in log.read_text()


@pytest.mark.parametrize(
    ("after", "named"),
    [
        ([BASELINE[0], PLATE], "Workspace/Lamp is gone"),
        ([*BASELINE, "Workspace/New\tPart"], "Workspace/New appeared (Part)"),
        (
            [BASELINE[0], LAMP + "\tattributes{Lit=boolean(true)}", PLATE],
            "Workspace/Lamp: attributes (none) -> attributes{Lit=boolean(true)}",
        ),
        (
            [BASELINE[0], LAMP.replace("PointLight", "SpotLight"), PLATE],
            "class PointLight -> SpotLight",
        ),
    ],
    ids=["gone", "appeared", "an-attribute-added", "a-class-changed"],
)
def test_each_kind_of_change_is_named(after, named):
    """Bug caught: a change the comparison reads as no change (an attribute, a class), or names
    without the instance."""
    before = PlaceBaseline("a", tuple(BASELINE))

    changes = place.baseline_changes(before, PlaceBaseline("b", tuple(after)))

    assert named in "; ".join(changes)
