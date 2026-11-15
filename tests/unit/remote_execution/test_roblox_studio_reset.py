"""The ``roblox-studio`` provider's reset (SIP-0117 R3.6; phase 2d, #3039): the place restored from
its read-only baseline file, and Studio reopened on it with no person involved.

Entered at ``RobloxStudioRunner.reset``. MCP is the stand-in ``StudioMCP``. The Mac is a fake
``StudioApp`` that records each quit, kill and open, and on ``open`` gives the stand-in a new
Studio id, as a restarted Studio has. The live reset of the real place is in the PR
(``scripts/dev/studio_reset.py``).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio import place
from adapters.remote_execution.game_dev_roblox_studio.runner import RobloxStudioRunner
from adapters.remote_execution.game_dev_roblox_studio.session import StudioMcpSession
from adapters.remote_execution.game_dev_roblox_studio.studio_app import PlaceFiles
from tests.unit.remote_execution.test_roblox_studio_place_state import BASELINE
from tests.unit.remote_execution.test_roblox_studio_read_side import STANDIN, STUDIO, _world

PRISTINE = b"<roblox place, as downloaded>"
DIGEST = hashlib.sha256("\n".join(BASELINE).encode()).hexdigest()


class _App:
    """The Mac, as the reset asks of it: one Studio at ``pid`` until it is quit."""

    def __init__(self, world: Path, *, pid: int | None = 4242, ignores_quit: bool = False,
                 never_dies: bool = False, lock_holder: int | None = None) -> None:  # fmt: skip
        self.world, self.pid = world, pid
        self.ignores_quit, self.never_dies, self.lock_holder = ignores_quit, never_dies, lock_holder
        self.done: list[str] = []

    def pids(self) -> list[int]:
        return [self.pid] if self.pid is not None else []

    def alive(self, pid: int) -> bool:
        return pid == self.pid or pid == self.lock_holder

    def quit(self, pid: int, *, force: bool) -> None:
        self.done.append("kill" if force else "quit")
        if self.never_dies or (self.ignores_quit and not force):
            return
        self.pid = None

    def open(self, place_file: Path) -> None:
        self.done.append(f"open {place_file.name}")
        doc = json.loads(self.world.read_text())
        doc["studios"] = [{**STUDIO, "id": "s-2"}]  # a restarted Studio has a new id
        self.world.write_text(json.dumps(doc))


def _files(tmp_path: Path, **pins) -> PlaceFiles:
    baseline = tmp_path / "ta-copy.pristine.rbxl"
    baseline.write_bytes(PRISTINE)
    baseline.chmod(0o444)
    place_file = tmp_path / "ta-copy.rbxl"
    place_file.write_bytes(b"<the place as an earlier transaction left it>")
    return PlaceFiles(
        place=place_file,
        baseline=baseline,
        baseline_sha256=pins.get("sha256", hashlib.sha256(PRISTINE).hexdigest()),
        baseline_digest=pins.get("digest", DIGEST),
    )


def _runner(world: Path, files: PlaceFiles | None, app: _App) -> RobloxStudioRunner:
    return RobloxStudioRunner(
        Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"),
        session_factory=lambda **kw: StudioMcpSession(
            [sys.executable, str(STANDIN), str(world)], **kw
        ),
        studio_version_of=lambda _: "0.747.0",
        discover_seconds=0.2,
        place_files=files,
        app=app,
        quit_seconds=0.5,
        reopen_seconds=1.0,
    )


async def test_a_reset_quits_studio_restores_the_baseline_and_confirms_the_reopened_place(
    tmp_path,
):
    """The wiring, with a Studio that ignores a quit (it does while it asks to save). Bugs
    caught:
    - the place left as the last transaction left it;
    - a quit that waits forever on a Studio showing a save prompt;
    - a stale lock left behind, so Studio opens the place read-only or refuses it;
    - a read-only place copied in, which Studio can't save;
    - a reset reported done before the reopened place is confirmed."""
    world = _world(tmp_path, baseline=BASELINE)
    files = _files(tmp_path)
    files.lock.write_text("4242\nRobloxStudio\nhost\n")
    app = _App(world, ignores_quit=True)

    await _runner(world, files, app).reset()

    assert app.done == ["quit", "kill", "open ta-copy.rbxl"]
    assert files.place.read_bytes() == PRISTINE
    assert files.place.stat().st_mode & 0o200  # Studio can save it
    assert not files.lock.exists()
    programs = [
        c for c in (tmp_path / "calls.log").read_text().split() if c.startswith("execute_luau:")
    ]
    # The reopened place is confirmed: identity, then its baseline read and released.
    assert programs[-3:] == [
        "execute_luau:identity",
        "execute_luau:baseline",
        "execute_luau:baseline",
    ]


@pytest.mark.parametrize(
    ("setup", "says"),
    [
        (lambda w, f: ({"sha256": "0" * 64}, {}), "not the pinned 0000000000000000"),
        (
            lambda w, f: ({}, {"studios": [{**STUDIO, "file": "someone-elses.rbxl"}]}),
            re.escape("holds ['someone-elses.rbxl'], not ta-copy.rbxl"),
        ),
        (lambda w, f: ({}, {"silent": ["list_roblox_studios"]}), "doesn't answer"),
    ],
    ids=["a-baseline-file-not-the-pinned-one", "a-studio-holding-another-place", "studio-hung"],
)
async def test_a_reset_that_cant_be_done_safely_touches_nothing(tmp_path, setup, says):
    """Bugs caught: a reset copying an edited baseline file over the place, so every later
    transaction starts from a place nobody pinned; or one force-quitting a Studio holding someone
    else's place, or one that can't say what it holds, discarding unsaved work."""
    pins, world_changes = setup(None, None)
    world = _world(tmp_path, baseline=BASELINE, **world_changes)
    files = _files(tmp_path, **pins)
    before = files.place.read_bytes()
    app = _App(world)
    runner = _runner(world, files, app)
    runner._session = lambda **kw: StudioMcpSession(  # a short deadline for the silent case
        [sys.executable, str(STANDIN), str(world)], call_seconds=0.5, **kw
    )

    with pytest.raises(place.PlaceStateError, match=says):
        await runner.reset()

    assert app.done == []
    assert files.place.read_bytes() == before


async def test_a_lock_a_running_studio_holds_is_never_removed(tmp_path):
    """Bug caught: a lock removed under a second, running Studio, so the place opens twice and
    one copy's save overwrites the other's."""
    world = _world(tmp_path, baseline=BASELINE)
    files = _files(tmp_path)
    files.lock.write_text("777\n")
    app = _App(world, lock_holder=777)

    with pytest.raises(place.PlaceStateError, match="held by running process 777"):
        await _runner(world, files, app).reset()

    assert files.lock.exists() and "open ta-copy.rbxl" not in app.done


async def test_a_studio_that_wont_quit_is_refused(tmp_path):
    world = _world(tmp_path, baseline=BASELINE)
    files = _files(tmp_path)
    app = _App(world, never_dies=True)

    with pytest.raises(place.PlaceStateError, match="didn't quit within 0.5s"):
        await _runner(world, files, app).reset()

    assert app.done == ["quit", "kill"]


async def test_a_reopened_place_not_holding_the_pinned_baseline_is_refused(tmp_path):
    """Bug caught: a reset that trusts the file copy, so a baseline file whose place state drifted
    (a Studio version that reads it differently) reads as reset."""
    world = _world(tmp_path, baseline=BASELINE)
    files = _files(tmp_path, digest="f" * 64)

    with pytest.raises(place.PlaceStateError, match="not the pinned ffffffffffffffff"):
        await _runner(world, files, _App(world)).reset()


async def test_a_runner_with_no_place_files_refuses_to_reset(tmp_path):
    """Bug caught: a reset that does nothing and returns, read by the worker as a place ready for
    the next transaction."""
    world = _world(tmp_path)

    with pytest.raises(place.PlaceStateError, match="nothing to reset from"):
        await _runner(world, None, _App(world)).reset()


async def test_a_studio_the_mcp_server_reports_late_is_still_the_one_quit(tmp_path):
    """Found live: ``StudioMCP`` lists no Studio for its first seconds, and a reset that read the
    first answer refused to quit the Studio it was asked to reset. Bug caught: an empty first
    answer believed, so every reset of a running Studio is refused."""
    world = _world(tmp_path, baseline=BASELINE, studios_late=2)
    files = _files(tmp_path)
    app = _App(world)
    runner = _runner(world, files, app)
    runner._discover_seconds = 5.0

    await runner.reset()

    assert app.done == ["quit", "open ta-copy.rbxl"]
