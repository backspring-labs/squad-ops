"""The ``roblox-studio`` provider's sync (SIP-0117 D10; phase 2d, #3039): the write side
``sync_source`` will stand on.

Entered at ``RobloxStudioRunner.sync`` and the session, over the stand-in ``StudioMCP``, which runs
only the harness's exact programs: it models the sync program by its payload. The Luau itself is
proved on the real place by ``scripts/dev/studio_sync.py --round-trip`` (recorded in the PR); CI
has no Studio.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio import harness, place
from adapters.remote_execution.game_dev_roblox_studio.runner import RobloxStudioRunner
from adapters.remote_execution.game_dev_roblox_studio.session import (
    HARNESS_TOOL,
    READ_ONLY_TOOLS,
    StudioMcpSession,
    StudioSessionError,
    ToolDenied,
)
from tests.unit.remote_execution.test_roblox_studio_read_side import (
    MAIN,
    SERVER,
    STANDIN,
    _world,
)

SHARED = "ReplicatedStorage.Shared"
#: The world's two scripts, as a repository holds them.
SOURCE = {"src/Server/Main.server.luau": MAIN, "src/Server/Util/Log.luau": "return {}"}


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
    log = tmp_path / "calls.log"
    return log.read_text().split() if log.exists() else []


def _held(world: Path) -> dict[str, str]:
    return json.loads(world.read_text())["scripts"]


async def test_sync_writes_what_differs_removes_the_rest_and_reads_it_back(tmp_path):
    """The wiring: a changed script, an unchanged one, a new one in a folder the place doesn't
    have, a class change and a script the manifest drops. Bugs caught: rewriting every script
    (or none); a dropped script left in the place, so a candidate runs beside a file it deleted;
    a class change written as a text change, so a Script runs as a ModuleScript; a new script's
    folder never made; or a sync that confirms nothing, reading as done when the place differs."""
    world = _world(tmp_path)
    source = {
        "src/Server/Main.luau": MAIN + "-- now a module\n",  # was a Script: class and text change
        "src/Server/Util/Log.luau": "return {}",  # unchanged
        "src/Shared/Modules/Rules.luau": "return { lives = 5 }\n",  # new, in a new folder
    }
    world_doc = json.loads(world.read_text())
    world_doc["scripts"][f"{SERVER}.Old"] = "-- dropped\n"
    world_doc["trees"][SERVER].append(
        {"fullPath": f"{SERVER}.Old", "name": "Old", "className": "Script"}
    )
    world.write_text(json.dumps(world_doc))

    result = await _runner(world).sync(source)

    held = json.loads(world.read_text())
    classes = {n["fullPath"]: n["className"] for t in held["trees"].values() for n in t}
    assert result.written == (f"{SERVER}.Main", f"{SHARED}.Modules.Rules")
    assert result.removed == (f"{SERVER}.Old",)
    assert held["scripts"] == {
        f"{SERVER}.Main": MAIN + "-- now a module\n",
        f"{SERVER}.Util.Log": "return {}",
        f"{SHARED}.Modules.Rules": "return { lives = 5 }\n",
    }
    assert (classes[f"{SERVER}.Main"], classes[f"{SHARED}.Modules"]) == ("ModuleScript", "Folder")
    # Identity is confirmed before anything is written, and the place is read before and after.
    calls = _calls(tmp_path)
    last_sync = len(calls) - 1 - calls[::-1].index("execute_luau:sync")
    assert calls.index("execute_luau:identity") < calls.index("execute_luau:sync")
    assert "script_read" in calls[last_sync:]  # read back after the last write


@pytest.mark.parametrize(
    ("identity", "says"),
    [
        ({"placeId": 1818, "gameId": 0, "edit": True, "running": False}, "placeId is 1818"),
        ({"placeId": 0, "gameId": 77, "edit": True, "running": False}, "gameId is 77"),
        ({"placeId": 0, "gameId": 0, "edit": True, "running": True}, "running is True"),
    ],
    ids=["a-published-place", "a-published-game", "play-running"],
)
async def test_a_place_that_isnt_a_local_one_in_edit_is_never_written(tmp_path, identity, says):
    """Bugs caught: the worker writing scripts into a published place, which reaches players
    the moment it is saved; or into a play session, whose edits are thrown away at stop."""
    world = _world(tmp_path, identity=identity)

    with pytest.raises(place.PlaceSyncError, match=says):
        await _runner(world).sync({**SOURCE, "src/Server/New.luau": "return 1"})

    assert "execute_luau:sync" not in _calls(tmp_path)
    assert _held(world) == {f"{SERVER}.Main": MAIN, f"{SERVER}.Util.Log": "return {}"}


async def test_a_read_back_that_differs_after_sync_is_refused_naming_it(tmp_path):
    """Studio accepting a write and holding something else. Bug caught: a sync reported done
    from the program's own count, so a candidate is played on text it isn't."""
    world = _world(tmp_path, ignore_writes=[f"{SERVER}.Main"])

    with pytest.raises(place.PlaceSyncError, match=f"{SERVER}.Main's text differs"):
        await _runner(world).sync({**SOURCE, "src/Server/Main.server.luau": "-- edited\n"})


@pytest.mark.parametrize(
    ("source", "says"),
    [
        (
            {"src/Server/Main.server.luau": MAIN, "src/Server/Util/Log/Inner.luau": "return 2"},
            f"{SERVER}.Util.Log holds {SERVER}.Util.Log.Inner",
        ),
        ({**SOURCE, "src/Server/Notes.txt": "x"}, "src/Server/Notes.txt isn't a script"),
    ],
    ids=["drops-a-script-it-keeps-one-inside", "a-file-it-cant-place"],
)
async def test_a_manifest_that_cant_be_synced_whole_writes_nothing(tmp_path, source, says):
    """Bugs caught: a sync that writes half a manifest and then fails, leaving a place that is
    neither tree; or a file under a synced folder silently left out of the place."""
    world = _world(tmp_path)

    with pytest.raises(place.PlaceSyncError, match=says):
        await _runner(world).sync(source)

    assert "execute_luau:sync" not in _calls(tmp_path)


async def test_a_large_sync_is_cut_into_bounded_calls(tmp_path, monkeypatch):
    """Bug caught: the whole tree sent in one call, past what Studio answers inside the call's
    deadline (R3.6: a blocking call has no timeout of its own)."""
    monkeypatch.setattr(place, "SYNC_BATCH_BYTES", 100)
    world = _world(tmp_path)
    source = {**SOURCE, **{f"src/Shared/M{i}.luau": "-- " + "x" * 60 + "\n" for i in range(5)}}

    result = await _runner(world).sync(source)

    assert len(result.written) == 5
    assert _calls(tmp_path).count("execute_luau:sync") == 5


async def test_only_the_harness_programs_reach_execute_luau_and_only_hex_is_put_in(tmp_path):
    """D5: ``execute_luau`` runs only the harness's fixed programs. Bugs caught: a direct
    ``execute_luau`` call allowed, so anything could run under the owner's Studio login; a
    session not opened for the harness running a program; or script text spliced into the code,
    where a ``]]`` or a quote in a source file would run as Luau."""
    world = _world(tmp_path, code_log=str(tmp_path / "code.log"))
    hostile = 'return "]] ; game:Destroy() --[["\n'
    with pytest.raises(ValueError, match="never a direct call"):
        StudioMcpSession(["x"], allowed=READ_ONLY_TOOLS | {HARNESS_TOOL})
    reading = StudioMcpSession([sys.executable, str(STANDIN), str(world)])
    await reading.open()
    try:
        with pytest.raises(ToolDenied):
            await reading.call(HARNESS_TOOL, {"code": "return 1"})
        with pytest.raises(ToolDenied):
            await reading.run_program("identity", "s-1")
    finally:
        await reading.close()

    await _runner(world).sync({**SOURCE, "src/Server/Hostile.luau": hostile})

    sent = [json.loads(line) for line in (tmp_path / "code.log").read_text().splitlines()]
    head, tail = harness.program("sync").text.split(harness.PAYLOAD_TOKEN)
    syncs = [c for c in sent if c.startswith(head)]
    assert syncs and all(c.endswith(tail) for c in syncs)
    assert all(set(c[len(head) : len(c) - len(tail)]) <= set("0123456789abcdef") for c in syncs)
    assert _held(world)[f"{SERVER}.Hostile"] == hostile


async def test_a_session_for_the_harness_requires_its_tool_offered(tmp_path):
    """Bug caught: a worker registering as able to sync on a Studio whose tool list lacks
    ``execute_luau``, so every sync fails at its first write."""
    tools = [{"name": n, "annotations": {"readOnlyHint": True}} for n in sorted(READ_ONLY_TOOLS)]
    world = _world(tmp_path, tools=tools)
    session = StudioMcpSession([sys.executable, str(STANDIN), str(world)], harness=True)

    with pytest.raises(StudioSessionError, match="execute_luau, which the harness needs"):
        await session.open()
    await session.close()


@pytest.mark.parametrize(
    ("files", "placed", "unplaced"),
    [
        ({"src/Shared/Foo/init.luau": "a"}, {f"{SHARED}.Foo": "ModuleScript"}, []),
        ({"src/Shared/Foo/init.server.luau": "a"}, {f"{SHARED}.Foo": "Script"}, []),
        ({"src/Shared/init.luau": "a"}, {}, ["src/Shared/init.luau"]),
        (
            {"src/Shared/Foo.luau": "a", "src/Shared/Foo/init.luau": "b"},
            {f"{SHARED}.Foo": "ModuleScript"},
            ["src/Shared/Foo/init.luau"],
        ),
    ],
    ids=["init-is-its-folder", "an-init-script", "init-at-a-root", "two-scripts-one-name"],
)
def test_an_init_file_is_the_script_its_folder_names(files, placed, unplaced):
    """Script Sync's ``X/init.luau``. Bugs caught: it placed as a script named ``init`` inside
    ``X``, so the game's ``require(script.Parent.X)`` finds a Folder; or ``X.luau`` beside
    ``X/init.luau`` silently resolved to whichever came last."""
    got, left = place.manifest_scripts(files)

    assert {p: s.script_class for p, s in got.items()} == placed
    assert left == unplaced
