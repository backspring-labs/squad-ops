"""``play_scenario``: a frozen scenario played on the candidate as one transaction (SIP-0117 R3.6,
R3.7, R5.8; #3040).

Entered at ``RobloxStudioRunner.run`` with a request as a worker is handed it, over the stand-in
``StudioMCP``. The stand-in models the play session (``play``), a click's effect (``clicks``), the
character's navigation and the console. The live runs on the real game are in the PR
(``scripts/dev/studio_play_scenario.py``).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio import harness
from adapters.remote_execution.game_dev_roblox_studio.runner import (
    OPERATION,
    PROVIDER,
    ProvedOn,
    RobloxStudioRunner,
)
from adapters.remote_execution.game_dev_roblox_studio.session import (
    StudioMcpSession,
    ToolDenied,
    tool_check,
)
from adapters.remote_execution.game_dev_roblox_studio.studio_app import PlaceFiles
from adapters.remote_execution.game_dev_roblox_studio.vocabulary import VOCABULARY
from squadops.remote_execution.models import (
    AssertionOutcome,
    OperationStatus,
    RemoteOperationRequest,
    Scenario,
)
from squadops.remote_execution.scenario import frozen_scenario
from tests.unit.remote_execution.test_roblox_studio_place_state import BASELINE
from tests.unit.remote_execution.test_roblox_studio_read_side import (
    MAIN,
    SERVER,
    STANDIN,
    _tools,
    _world,
)

PLAY_BUTTON = "@player.PlayerGui.Title.Play"
TITLE = "@player.PlayerGui.Title"
#: The title screen, then a click on Play opens the door on the server and drops the title.
DECLARATION = {
    "schema": "squadops.scenario/1",
    "scenario_id": "C-3",
    "reader": "roblox-studio/1",
    "setup": [
        {"action": "wait_until",
         "observe": {"kind": "gui_state", "path": PLAY_BUTTON, "state": "visible", "context": "client"},
         "expect": {"op": "equals", "value": True}, "deadline_s": 1},
        {"action": "click_gui", "path": PLAY_BUTTON},
    ],
    "steps": [
        {"action": "hold_key", "key": "W", "seconds": 0.2},
        {"action": "move_to", "point": [4, 3, -8], "deadline_s": 1},
    ],
    "assertions": [
        {"id": "title-gone",
         "observe": {"kind": "property", "path": TITLE, "name": "Name", "context": "client"},
         "expect": {"op": "absent"}},
        {"id": "door-open",
         "observe": {"kind": "property", "path": "Workspace.Door", "name": "CanCollide", "context": "server"},
         "expect": {"op": "equals", "value": False}},
        {"id": "gold",
         "observe": {"kind": "attribute", "path": "@player", "name": "Gold", "context": "server"},
         "expect": {"op": "greater_than", "value": 10}},
    ],
    "named_assertion": "door-open",
}  # fmt: skip
PLAYING = {
    "client": {
        "@player": {"properties": {"Character": "Workspace.PlayerOne", "Name": "PlayerOne"}},
        PLAY_BUTTON: {"gui": {"visible": True}},
        TITLE: {"properties": {"Name": "Title"}},
    },
    "server": {
        "Workspace.Door": {"properties": {"CanCollide": True}},
        "@player": {"attributes": {"Gold": 5}},
    },
}
CLICKS = {
    PLAY_BUTTON: {
        "client": {TITLE: None},
        "server": {"Workspace.Door": {"properties": {"CanCollide": False}}},
    }
}


def _scenario(**changes) -> Scenario:
    return frozen_scenario({**DECLARATION, **changes}, VOCABULARY)


def _request(scenario: Scenario | None = None, **changes) -> RemoteOperationRequest:
    fields = dict(
        contract="game.scenario_verification",
        mode="play",
        provider=PROVIDER,
        operation=OPERATION,
        location="worker",
        source_revision="rev_candidate",
        # The candidate changes Main, so the transaction has something to sync.
        source_files={
            "src/Server/Main.server.luau": MAIN + "-- the candidate\n",
            "src/Server/Util/Log.luau": "return {}",
        },
        scenario=scenario or _scenario(),
        task_id="task-1",
        dispatch_id="dispatch-1",
    )
    return RemoteOperationRequest(**{**fields, **changes})


def _played(tmp_path: Path, **changes) -> Path:
    world = {
        "baseline": BASELINE,
        "mode": "Edit",
        "play": json.loads(json.dumps(PLAYING)),
        "clicks": CLICKS,
        "console": "PlayerOne joined the game\nDoor opened for PlayerOne\n",
        "input_log": str(tmp_path / "input.log"),
        **changes,
    }
    return _world(tmp_path, **world)


class _Mac:
    """The Mac, as ``play_scenario`` asks of it: which app is in front, and Studio's process.
    A reset's reopening puts the pinned baseline back in the world, unless ``reopens_drifted``."""

    def __init__(self, front: int | None | OSError = 4242, *, world: Path | None = None,
                 reopens_drifted: bool = False) -> None:  # fmt: skip
        self.front, self.world, self.reopens_drifted = front, world, reopens_drifted
        self.pid: int | None = 4242
        self.done: list[str] = []

    def frontmost(self) -> int | None:
        if isinstance(self.front, OSError):
            raise self.front
        return self.front

    def pids(self) -> list[int]:
        return [self.pid] if self.pid else []

    def alive(self, pid: int) -> bool:
        return pid == self.pid

    def quit(self, pid: int, *, force: bool) -> None:
        self.done.append("quit")
        self.pid = None

    def open(self, place_file: Path) -> None:
        self.done.append(f"open {place_file.name}")
        self.pid = 4242
        doc = json.loads(self.world.read_text())
        doc["studios"] = [{**doc["studios"][0], "id": "s-2"}]
        if not self.reopens_drifted:
            doc["baseline"] = BASELINE
        self.world.write_text(json.dumps(doc))


PRISTINE = b"<roblox place, as downloaded>"
#: What the operation was proved on: the stand-in's Studio and its tool list.
PROVED = ProvedOn(
    "0.747.0", "{0.count}:{0.schema_digest}".format(tool_check(_tools(), frozenset()))
)


def _files(tmp_path: Path) -> PlaceFiles:
    baseline = tmp_path / "ta-copy.pristine.rbxl"
    baseline.write_bytes(PRISTINE)
    place_file = tmp_path / "ta-copy.rbxl"
    place_file.write_bytes(b"<the place as an earlier transaction left it>")
    return PlaceFiles(
        place=place_file,
        baseline=baseline,
        baseline_sha256=hashlib.sha256(PRISTINE).hexdigest(),
        baseline_digest=hashlib.sha256("\n".join(BASELINE).encode()).hexdigest(),
    )


def _runner(world: Path, mac: _Mac | None = None, *, proved_on: ProvedOn | None = PROVED,
            pinned: bool = True, **session) -> RobloxStudioRunner:  # fmt: skip
    return RobloxStudioRunner(
        Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"),
        session_factory=lambda **kw: StudioMcpSession(
            [sys.executable, str(STANDIN), str(world)], **{**session, **kw}
        ),
        studio_version_of=lambda _: "0.747.0",
        discover_seconds=0.2,
        reopen_seconds=1.0,
        place_files=_files(world.parent) if pinned else None,
        proved_on=proved_on,
        app=mac or _Mac(world=world),
    )


def _inputs(tmp_path: Path) -> list[dict]:
    log = tmp_path / "input.log"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def _outcomes(result) -> dict[str, str]:
    return {r.assertion_id: r.outcome.value for r in result.records}


async def test_play_scenario_runs_the_transaction_and_records_each_assertion(tmp_path):
    """The wiring: the candidate synced, play started, setup and steps done through Studio's
    input, each assertion read in its context, play stopped. Bugs caught:
    - an assertion read before its step ran, so the click's effect is missed;
    - one read in the wrong datamodel (the door is the server's), reading absent;
    - a click sent before its button is visible;
    - a navigation not waited on;
    - a result missing the reader or the source revision it ran on."""
    world = _played(tmp_path)

    result = await _runner(world).run(_request())

    calls = (tmp_path / "calls.log").read_text().split()
    tools = [i["tool"] for i in _inputs(tmp_path)]
    assert result.status is OperationStatus.COMPLETED, result.reason
    assert _outcomes(result) == {"title-gone": "passed", "door-open": "passed", "gold": "failed"}
    assert {r.assertion_id: r.context for r in result.records}["door-open"] == "server"
    assert tools == ["user_mouse_input", "user_keyboard_input", "character_navigation"]
    assert calls.index("execute_luau:sync") < calls.index("start_stop_play")
    assert calls[-1] != "start_stop_play" and calls.count("start_stop_play") == 2
    assert (result.ran_with["reader"], result.ran_with["source_revision"]) == (
        "roblox-studio/1",
        "rev_candidate",
    )
    assert result.ran_with["harness.observe"] == harness.digests()["observe"][:16]
    log = json.loads(next(e.content for e in result.evidence if e.name == "play_log.json"))
    assert log["play_session"] == result.ran_with["play_session"] and len(log["play_session"]) == 32


async def test_the_players_account_name_is_never_returned(tmp_path):
    """The session's player is whoever is signed in to Studio. Bug caught: a person's account
    name written into evidence a Release later publishes."""
    world = _played(tmp_path)
    scenario = _scenario(assertions=[{
        "id": "who", "observe": {"kind": "property", "path": "@player", "name": "Name",
                                 "context": "client"},
        "expect": {"op": "equals", "value": "someone"},
    }], named_assertion="who")  # fmt: skip

    result = await _runner(world).run(_request(scenario))

    returned = json.dumps([r.observed for r in result.records]) + "".join(
        e.content for e in result.evidence
    )
    assert "PlayerOne" not in returned
    assert "@player joined the game" in returned


@pytest.mark.parametrize(
    "player",
    [{"properties": {"Character": "Workspace.P"}}, None],
    ids=["a-player-with-no-name", "no-player-on-the-client"],
)
async def test_with_no_name_to_redact_nothing_is_returned(tmp_path, monkeypatch, player):
    """Bug caught: the player's name unread, so the console went out as Studio wrote it, with a
    person's account name in evidence a Release later publishes."""
    from adapters.remote_execution.game_dev_roblox_studio import play

    monkeypatch.setattr(play, "READY_SECONDS", 0.5)
    client = {k: v for k, v in PLAYING["client"].items() if k != "@player"}
    world = _played(
        tmp_path, play={**PLAYING, "client": client | ({"@player": player} if player else {})}
    )

    result = await _runner(world).run(_request())

    assert result.status is OperationStatus.INTERRUPTED
    assert (result.records, result.evidence) == ((), ())
    assert "can't be redacted" in result.reason and "PlayerOne" not in result.reason


@pytest.mark.parametrize(
    ("front", "says"),
    [
        (31620, "process 31620 is in front, and Studio's are [4242]"),
        (None, "no app is in front"),
        (OSError("lsappinfo front failed: no session"), "couldn't be read: lsappinfo front failed"),
    ],
    ids=["another-app-in-front", "nothing-in-front", "front-unreadable"],
)
async def test_a_scenario_using_studios_input_needs_studio_in_front(tmp_path, front, says):
    """Found live: with Terminal in front, a click never answered, so the run waited a minute and
    read every assertion ``setup_failed`` on a game that was fine. Bugs caught: a run started
    that can't act; or an unreadable front read as Studio's."""
    world = _played(tmp_path)

    result = await _runner(world, _Mac(front, world=world)).run(_request())

    assert result.status is OperationStatus.NOT_EXECUTED
    assert says in result.reason
    assert result.tool_unready is True  # #3192: this Mac's Studio, never the candidate
    assert not (tmp_path / "calls.log").exists()


@pytest.mark.parametrize(
    ("changes", "why"),
    [
        ({"play": {**PLAYING, "client": {**PLAYING["client"], PLAY_BUTTON: {"gui": {"visible": False}}}}},
         "setup 1 (wait_until) wasn't met"),
        ({"input_errors": ["user_mouse_input"]}, "setup 2 (click_gui) couldn't be done"),
    ],
    ids=["setup-never-established", "a-click-studio-refused"],
)  # fmt: skip
async def test_a_scenario_whose_setup_fails_reads_setup_failed_for_every_assertion(
    tmp_path, monkeypatch, changes, why
):
    """R3.7: outcomes kept apart. Bug caught: a scenario that never reached its world read as a
    behavioural failure (``failed``), so a criterion is "not met" on a session that never ran it,
    or as ``passed`` on whatever the title screen happens to show."""
    from adapters.remote_execution.game_dev_roblox_studio import play

    monkeypatch.setattr(play, "READY_SECONDS", 0.5)
    world = _played(tmp_path, **changes)

    result = await _runner(world).run(_request())

    assert result.status is OperationStatus.COMPLETED
    assert set(_outcomes(result).values()) == {AssertionOutcome.SETUP_FAILED.value}
    assert all(why in r.observed for r in result.records)


async def test_a_hidden_button_is_never_clicked(tmp_path):
    """Bug caught: a click sent at a hidden button, which does nothing and reads as done, so the
    assertions after it read the world as if the player had acted."""
    hidden = {**PLAYING, "client": {**PLAYING["client"], PLAY_BUTTON: {"gui": {"visible": False}}}}
    scenario = _scenario(setup=[{"action": "click_gui", "path": PLAY_BUTTON}])
    world = _played(tmp_path, play=hidden)

    result = await _runner(world).run(_request(scenario))

    assert set(_outcomes(result).values()) == {"setup_failed"}
    assert "isn't a visible GUI object" in result.records[0].observed
    assert "user_mouse_input" not in [i["tool"] for i in _inputs(tmp_path)]


@pytest.mark.parametrize(
    ("instance", "outcome"),
    [
        ({"unsupported": "Part has no property Lift"}, "unsupported_input"),
        ({"unreadable": "2 players are in the session"}, "missing"),
        ({"wrong_context": "declared for the server, and it ran on the client"}, "wrong_context"),
    ],
)
async def test_an_observation_that_cant_be_read_is_never_a_verdict(tmp_path, instance, outcome):
    """Bug caught: an unreadable observation compared as a value and read ``failed``, an executed
    behavioural failure the candidate didn't commit."""
    play_world = {**PLAYING, "server": {**PLAYING["server"], "Workspace.Door": instance}}
    world = _played(tmp_path, play=play_world, clicks={})

    result = await _runner(world).run(_request())

    assert _outcomes(result)["door-open"] == outcome
    assert result.records[1].observed == next(iter(instance.values()))


@pytest.mark.parametrize(
    ("scenario", "says"),
    [
        (Scenario("C-3", "sha256:" + "0" * 64, ("title-gone", "door-open", "gold"), "door-open",
                  json.dumps(DECLARATION)), "changed after it was frozen"),
        (None, "isn't a script roblox-studio places"),
    ],
    ids=["a-scenario-not-the-frozen-one", "a-file-it-cant-place"],
)  # fmt: skip
async def test_what_cant_be_run_as_frozen_is_never_started(tmp_path, scenario, says):
    """Bugs caught: a scenario edited after it was frozen played anyway, so a pass means a test
    nobody approved; or a candidate synced half way."""
    world = _played(tmp_path)
    files = {"src/Server/notes.txt": "x"} if scenario is None else None
    request = _request(scenario) if files is None else _request(source_files=files)

    result = await _runner(world).run(request)

    assert (result.status, says in result.reason) == (OperationStatus.NOT_EXECUTED, True)
    # #3192: the request's own defect stays the work's, so the Campaign doesn't retry it.
    assert result.tool_unready is False
    assert (
        not (tmp_path / "calls.log").exists()
        or "execute_luau:sync" not in (tmp_path / "calls.log").read_text()
    )


async def test_a_place_changed_through_play_proves_nothing(tmp_path):
    """R3.6. Bug caught: records returned from a session whose place moved, so a pass rests on a
    world the next session won't have."""
    moved = [BASELINE[0], BASELINE[1], BASELINE[2].replace("CFrame(0,-8", "CFrame(1,-8")]
    world = _played(tmp_path, baseline_after_play=moved)

    result = await _runner(world).run(_request())

    assert result.status is OperationStatus.NOT_EXECUTED
    assert "Workspace/Baseplate: CFrame" in result.reason and result.records == ()


async def test_a_session_that_fails_after_play_began_is_interrupted_and_play_is_stopped(tmp_path):
    """Bug caught: a hung Studio call leaving play running (found live), so the next transaction
    syncs into a play session; or the failure read as ``not_executed``, as if play never began."""
    world = _played(tmp_path, silent=["get_console_output"])

    result = await _runner(world, call_seconds=1.0).run(_request())

    assert result.status is OperationStatus.INTERRUPTED
    assert json.loads(world.read_text())["mode"] == "Edit"


async def test_the_observe_program_runs_only_in_a_play_session(tmp_path):
    """Bug caught: the observe program sent to the edit place, where it reads the place as saved
    and answers as if play had happened."""
    session = StudioMcpSession([sys.executable, str(STANDIN), str(_played(tmp_path))], harness=True)
    await session.open()
    try:
        with pytest.raises(ToolDenied, match="doesn't run in Edit"):
            await session.run_program("observe", "s-1", {"kind": "value", "path": "Workspace.X"})
    finally:
        await session.close()


@pytest.mark.parametrize(
    ("proved_on", "says"),
    [
        (ProvedOn("0.746.0", PROVED.studio_tools), "Studio is 0.747.0, and the operation was proved on 0.746.0"),
        (ProvedOn("0.747.0", "37:" + "0" * 64), "Studio's tools read"),
    ],
    ids=["another-studio-version", "another-tool-list"],
)  # fmt: skip
async def test_a_studio_other_than_the_one_proved_on_runs_nothing(tmp_path, proved_on, says):
    """R2.4: a mode not proved reads not executed. Bug caught: Studio updated itself (it does,
    unasked) or its tools changed, and the worker kept passing scenarios on a Studio nothing was
    proved on."""
    world = _played(tmp_path)

    result = await _runner(world, proved_on=proved_on).run(_request())

    assert result.status is OperationStatus.NOT_EXECUTED
    assert says in result.reason and "R2.4" in result.reason
    assert not (tmp_path / "calls.log").exists()  # not a tool was called


async def test_a_runner_with_nothing_pinned_runs_nothing(tmp_path):
    """Bug caught: a worker configured without its place files or proved-on pins playing on
    whatever place Studio has open, unconfirmed."""
    result = await _runner(_played(tmp_path), pinned=False).run(_request())

    assert result.status is OperationStatus.NOT_EXECUTED
    assert "no place files and proved-on pins" in result.reason
    assert not (tmp_path / "calls.log").exists()


DRIFTED = [BASELINE[0], BASELINE[1], BASELINE[2].replace("CFrame(0,-8", "CFrame(1,-8")]


async def test_a_place_that_drifted_from_its_pin_is_reset_and_then_played(tmp_path):
    """R3.6: the Studio is confirmed by its baseline digest at every claim. Bugs caught: a
    scenario played on a place someone moved a part in, so a pass rests on a world the baseline
    doesn't have; or a worker that refuses every claim from then on, since it resets only after
    an interrupted run."""
    world = _played(tmp_path, baseline=DRIFTED)
    mac = _Mac(world=world)

    result = await _runner(world, mac).run(_request())

    assert result.status is OperationStatus.COMPLETED, result.reason
    assert mac.done == ["quit", "open ta-copy.rbxl"]
    calls = (tmp_path / "calls.log").read_text().split()
    assert calls.count("execute_luau:sync") == 1  # nothing was written before the reset


@pytest.mark.parametrize(
    ("mac", "says"),
    [
        ({"reopens_drifted": True}, "the reset failed: PlaceStateError: the reopened place holds"),
        ({"front": None}, "no app is in front"),
    ],
    ids=["still-drifted-after-the-reset", "studio-not-in-front-after-the-reset"],
)
async def test_a_drifted_place_the_reset_doesnt_restore_runs_nothing(tmp_path, mac, says):
    """Bugs caught: a reset tried forever; or the second attempt skipping the checks the first
    one made, so a reopened Studio behind Terminal hangs on its first click."""
    world = _played(tmp_path, baseline=DRIFTED)
    front = mac.pop("front", 4242)
    machine = _Mac(4242, world=world, **mac)
    if front is None:
        original = machine.open

        def open_behind(place_file):
            original(place_file)
            machine.front = None

        machine.open = open_behind

    result = await _runner(world, machine).run(_request())

    assert result.status is OperationStatus.NOT_EXECUTED
    assert says in result.reason
    assert result.tool_unready is True  # #3192: a place this Mac couldn't restore
    assert "execute_luau:sync" not in (tmp_path / "calls.log").read_text()


async def test_a_script_changed_in_studio_while_the_scenario_ran_proves_nothing(tmp_path):
    """R3.6: a script that changes during a QA transaction fails it. Bug caught: records returned
    for a candidate that isn't what was played, since someone edited it in Studio mid-run."""
    world = _played(tmp_path, scripts_after_play={f"{SERVER}.Main": "-- edited in Studio\n"})

    result = await _runner(world).run(_request())

    assert result.status is OperationStatus.NOT_EXECUTED
    assert "scripts changed in Studio while the scenario ran" in result.reason
    assert "ServerScriptService.Server.Main's text differs" in result.reason
    assert result.records == ()
