"""The ``roblox-studio`` provider's read side (SIP-0117 phase 2d, #3039, the first slice).

Entered at the adapter's own calls (``RobloxStudioRunner``, the session and the place reads), over
a stand-in ``StudioMCP`` process that answers as the real one did on Studio 0.747. The live read
of the real place is recorded in the PR; CI has no Studio.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio import place
from adapters.remote_execution.game_dev_roblox_studio.runner import RobloxStudioRunner
from adapters.remote_execution.game_dev_roblox_studio.session import (
    READ_ONLY_TOOLS,
    StudioMcpSession,
    StudioSessionError,
    StudioToolError,
    ToolDenied,
)
from squadops.remote_execution.models import OperationStatus
from squadops.remote_execution.workers import ServedOperation
from tests.unit.remote_execution.registry_contract import request

STANDIN = Path(__file__).with_name("studio_mcp_standin.py")
SERVER = "ServerScriptService.Server"
STUDIO = {"id": "s-1", "file": "ta-copy.rbxl", "persistedToCloud": False}
MAIN = "-- Starts the server.\nlocal x = 1\n\tprint(x)\n"


def _tools(**changes) -> list[dict]:
    """The live tool list: the allowed tools, read-only, and a write tool beside them."""
    tools = [{"name": n, "annotations": {"readOnlyHint": True}} for n in sorted(READ_ONLY_TOOLS)]
    tools.append({"name": "execute_luau", "annotations": {"readOnlyHint": False}})
    for control in (
        "start_stop_play",
        "user_mouse_input",
        "user_keyboard_input",
        "character_navigation",
    ):
        tools.append({"name": control, "annotations": {}})
    for name, marks in changes.items():
        tools = [t for t in tools if t["name"] != name]
        if marks is not None:
            tools.append({"name": name, "annotations": marks})
    return tools


def _world(tmp_path: Path, **changes) -> Path:
    world = {
        "tools": _tools(),
        "studios": [STUDIO],
        "state": "- Current Studio Mode: Edit\n- Available DataModels: Edit",
        "trees": {
            SERVER: [
                {"fullPath": SERVER, "name": "Server", "className": "Folder"},
                {"fullPath": f"{SERVER}.Main", "name": "Main", "className": "Script"},
                {"fullPath": f"{SERVER}.Util", "name": "Util", "className": "Folder"},
                {"fullPath": f"{SERVER}.Util.Log", "name": "Log", "className": "ModuleScript"},
            ],
            **{f: [{"fullPath": f, "name": f.rsplit(".")[-1], "className": "Folder"}]
               for f in place.SYNCED_FOLDERS if f != SERVER},
        },
        "scripts": {f"{SERVER}.Main": MAIN, f"{SERVER}.Util.Log": "return {}"},
        "log": str(tmp_path / "calls.log"),
        **changes,
    }  # fmt: skip
    path = tmp_path / "world.json"
    path.write_text(json.dumps(world))
    return path


def _session(world: Path, **kw) -> StudioMcpSession:
    return StudioMcpSession([sys.executable, str(STANDIN), str(world)], **kw)


def _runner(world: Path) -> RobloxStudioRunner:
    return RobloxStudioRunner(
        Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"),
        session_factory=lambda: _session(world),
        studio_version_of=lambda _: "0.747.0",
        discover_seconds=0.2,
    )


async def _opened(world: Path, **kw) -> StudioMcpSession:
    session = _session(world, **kw)
    await session.open()
    return session


async def test_a_tool_off_the_allow_list_is_refused_before_anything_is_sent(tmp_path):
    """Deny by default (R3.6). Bug caught: a write tool, here ``execute_luau``, reaching Studio
    because the server offered it, so a read-only slice changes the place."""
    world = _world(tmp_path)
    session = await _opened(world)
    try:
        with pytest.raises(ToolDenied, match="execute_luau is not on the allow-list"):
            await session.call("execute_luau", {"code": "workspace:ClearAllChildren()"})
        await session.call("get_console_output", {"studio_id": "s-1"})
    finally:
        await session.close()

    assert (tmp_path / "calls.log").read_text().split() == ["get_console_output"]


@pytest.mark.parametrize(
    ("change", "says"),
    [
        ({"script_read": None}, "script_read is not offered"),
        ({"search_game_tree": {"readOnlyHint": False}}, "search_game_tree is not marked read-only"),
    ],
)
async def test_a_live_tool_list_that_fails_the_allow_list_refuses_the_session(
    tmp_path, change, says
):
    """R3.6: counted against a live ``tools/list``. Bug caught: a Studio update that drops a tool
    or turns one into a writer read through as before."""
    with pytest.raises(StudioSessionError, match=says):
        await _opened(_world(tmp_path, tools=_tools(**change)))


async def test_every_call_has_a_deadline(tmp_path):
    """Bug caught: a Studio that stops answering holding the worker's lease forever."""
    session = await _opened(_world(tmp_path, silent=["get_console_output"]), call_seconds=0.5)
    try:
        with pytest.raises(StudioSessionError, match="no answer within 0.5s"):
            await session.call("get_console_output", {"studio_id": "s-1"})
    finally:
        await session.close()


async def test_an_error_answered_as_a_success_is_an_error(tmp_path):
    """Studio 0.747 answers ``inspect_instance`` misses as ``isError: false``, ``Error: …``. Bug
    caught: an error read as the place's answer."""
    session = await _opened(_world(tmp_path, errors_as_success=["get_console_output"]))
    try:
        with pytest.raises(StudioToolError, match="Could not find any instances"):
            await session.call("get_console_output", {"studio_id": "s-1"})
    finally:
        await session.close()


@pytest.mark.parametrize(
    ("change", "says"),
    [
        ({"studios": []}, "exactly one connected Studio is required; 0 are"),
        ({"studios": [STUDIO, {**STUDIO, "id": "s-2"}]}, "exactly one connected Studio"),
        ({"studios": [{**STUDIO, "persistedToCloud": True}]}, "saved to the cloud"),
        ({"studios": [{"id": "s-1", "file": "x.rbxl"}]}, "saved to the cloud, or doesn't say"),
        ({"state": "- Current Studio Mode: Play"}, "Studio is in Play mode"),
    ],
    ids=["none", "two", "cloud", "unsaid", "playing"],
)
async def test_identity_requires_one_local_studio_in_edit_mode(tmp_path, change, says):
    """Bugs caught: the read side reading whichever Studio answers first, a published place, or a
    place mid-play; or a Studio that doesn't say where its place lives read as local."""
    session = await _opened(_world(tmp_path, **change))
    try:
        with pytest.raises(place.PlaceReadError, match=says):
            await place.identity(session, discover_seconds=0.2, poll_seconds=0.05)
    finally:
        await session.close()


@pytest.mark.parametrize(
    ("node", "says"),
    [
        ({"unexploredChildCount": 4}, "deeper than 10 levels"),
        ({"name": "Main.old"}, "holds a dot"),
    ],
)
async def test_a_tree_read_that_isnt_whole_is_refused(tmp_path, node, says):
    """Bug caught: ``search_game_tree``'s depth limit (three levels by default) or an ambiguous
    path read as the whole folder, so a script beneath it is never compared."""
    world = json.loads(_world(tmp_path).read_text())
    world["trees"][SERVER][1].update(node)
    (tmp_path / "world.json").write_text(json.dumps(world))
    session = await _opened(tmp_path / "world.json")
    try:
        with pytest.raises(place.PlaceReadError, match=says):
            await place.read_scripts(session, "s-1")
    finally:
        await session.close()


@pytest.mark.parametrize(
    ("text", "page_lines"),
    [
        (MAIN, 2_000),  # ends with a newline, read in one page
        ("a\nb\nc\nd", 2),  # fills its pages exactly: the next one starts past the end
        ("x" * 30 + "\n" + "y" * 30 + "\n" + "z" * 30, 3),  # a page the server cut is halved
    ],
    ids=["one page", "exact pages", "halved"],
)
async def test_a_script_reads_back_exactly_whatever_its_paging(
    tmp_path, monkeypatch, text, page_lines
):
    """R3.6: pages under 90,000 characters, since the server cuts at 100,000 and still answers
    success. Here it cuts at 100 against a limit of 90. Bugs caught: a script's last line, or its
    trailing newline, lost at a page's end; a cut page joined as if whole."""
    monkeypatch.setattr(place, "PAGE_LIMIT", 90)
    world = _world(tmp_path, scripts={f"{SERVER}.Main": text}, page_cap=100)
    session = await _opened(world)
    try:
        read = await place.read_script(session, "s-1", f"{SERVER}.Main", page_lines=page_lines)
    finally:
        await session.close()

    assert read == text


async def test_a_line_alone_over_the_page_limit_is_refused(tmp_path, monkeypatch):
    """Bug caught: a page the server cut accepted because no smaller one exists."""
    monkeypatch.setattr(place, "PAGE_LIMIT", 20)
    world = _world(tmp_path, scripts={f"{SERVER}.Main": "short\n" + "w" * 40})
    session = await _opened(world)
    try:
        with pytest.raises(place.PlaceReadError, match="line 2 alone reaches 20 characters"):
            await place.read_script(session, "s-1", f"{SERVER}.Main", page_lines=4)
    finally:
        await session.close()


async def test_read_back_names_each_way_the_place_differs_from_the_manifest(tmp_path):
    """Entered at ``RobloxStudioRunner.read_back``. Bugs caught: a moved, dropped, re-classed or
    edited script read as synced; or a file the provider can't place left out unnamed."""
    manifest = {
        "src/Server/Main.luau": MAIN,  # a ModuleScript in the manifest, a Script in the place
        "src/Server/Util/Extra.luau": "return 1",
        "src/Server/notes.md": "x",
        "README.md": "outside every synced folder",
    }

    found = await _runner(_world(tmp_path)).read_back(manifest)

    assert found == [
        "src/Server/notes.md isn't a script roblox-studio places",
        f"{SERVER}.Util.Extra is in the manifest and not in the place",
        f"{SERVER}.Util.Log is in the place and not in the manifest",
        f"{SERVER}.Main is a Script; the manifest's is a ModuleScript",
    ]
    exact = {"src/Server/Main.server.luau": MAIN, "src/Server/Util/Log.luau": "return {}"}
    assert await _runner(_world(tmp_path)).read_back(exact) == []


async def test_the_runner_registers_what_it_runs_with_and_serves_play_scenario_alone(tmp_path):
    """R4.6 and R2.4. Bugs caught: a worker registered without Studio's version, the tool digest,
    the harness's programs or the vocabulary's reader, so a changed Studio or harness runs
    unnoticed; or an operation it doesn't run answered as run."""
    runner = _runner(_world(tmp_path))

    versions = await runner.tool_versions()
    result = await runner.run(request(ServedOperation("roblox-studio", "capture")))

    # 2 since #3176: gui_state visible reads a screen as enabled.
    assert versions["roblox-studio"] == "2" and versions["studio"] == "0.747.0"
    assert versions["studio_tools"].startswith(f"{len(_tools())}:")
    assert (versions["reader"], len(versions["harness.observe"])) == ("roblox-studio/1", 16)
    assert runner.serves() == (ServedOperation("roblox-studio", "play_scenario"),)
    assert result.status is OperationStatus.NOT_EXECUTED
    assert (
        "runs roblox-studio/play_scenario, and was asked for roblox-studio/capture" in result.reason
    )
    assert await runner.health() == "online"
    assert await _runner(_world(tmp_path, studios=[])).health() == "offline"
