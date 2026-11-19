"""The ``roblox-studio`` provider's reset (SIP-0117 R3.6; phase 2d, #3039): the place restored from
its read-only baseline file, and Studio reopened on it with no person involved.

Entered at ``RobloxStudioRunner.reset``. MCP is the stand-in ``StudioMCP``. The Mac is a fake
``StudioApp`` that records each quit, kill and open, and on ``open`` gives the stand-in a new
Studio id, as a restarted Studio has. The live reset of the real place is in the PR
(``scripts/dev/studio_reset.py``).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio import place
from adapters.remote_execution.game_dev_roblox_studio.runner import (
    OPERATION,
    PROVIDER,
    ProvedOn,
    RobloxStudioRunner,
)
from adapters.remote_execution.game_dev_roblox_studio.session import StudioMcpSession
from adapters.remote_execution.game_dev_roblox_studio.studio_app import PlaceFiles
from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.remote_execution.models import OperationStatus
from squadops.remote_execution.registry import WorkerRegistry
from squadops.remote_execution.serving import Worker
from squadops.remote_execution.workers import OperationState, ServedOperation
from tests.unit.remote_execution.registry_contract import Clock, queue, request
from tests.unit.remote_execution.test_roblox_studio_place_state import BASELINE
from tests.unit.remote_execution.test_roblox_studio_read_side import STANDIN, STUDIO, _world
from tests.unit.remote_execution.worker_harness import RegistryWorkerApi, Serving, sleeping_on

PRISTINE = b"<roblox place, as downloaded>"
DIGEST = hashlib.sha256("\n".join(BASELINE).encode()).hexdigest()


class _App:
    """The Mac, as the reset asks of it: one Studio at ``pid`` until it is quit. ``installed``
    is Studio's version, read from its bundle. ``updates_to`` is what a launch replaces it with
    (a version, or ``None`` for a bundle that can't be read mid-replacement), and
    ``comes_back_with`` is the place the updated Studio then holds: none, as Studio's installer
    launches it. ``channel_now`` is the release channel the running Studio started on (an
    ``OSError`` for one that can't be read), and ``reopens_on`` the one a launch brings it
    back on (#3206)."""

    def __init__(self, world: Path, *, pid: int | None = 4242, ignores_quit: bool = False,
                 never_dies: bool = False, lock_holder: int | None = None) -> None:  # fmt: skip
        self.world, self.pid = world, pid
        self.ignores_quit, self.never_dies, self.lock_holder = ignores_quit, never_dies, lock_holder
        self.done: list[str] = []
        self.installed: str | None = "0.747.0"
        self.updates = False
        self.updates_to: str | None = None
        self.comes_back_with: str | None = None
        self.channel_now: str | OSError = "production"
        self.reopens_on: str | OSError | None = None

    def channel(self) -> str:
        if isinstance(self.channel_now, OSError):
            raise self.channel_now
        return self.channel_now

    def version(self, _mcp: Path) -> str:
        if self.installed is None:
            raise ValueError("Studio's version can't be read from Info.plist: no such file")
        return self.installed

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
        if self.reopens_on is not None:
            self.channel_now = self.reopens_on
        doc = json.loads(self.world.read_text())
        doc["studios"] = [{**STUDIO, "id": "s-2"}]  # a restarted Studio has a new id
        if self.updates:
            self.installed, self.updates = self.updates_to, False
            if self.comes_back_with is None:
                doc["studios"] = [{"id": "s-2", "file": None}]
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


PROVED = ProvedOn("0.747.0", "38:tools", "production")


def _runner(world: Path, files: PlaceFiles | None, app: _App,
            proved_on: ProvedOn | None = PROVED) -> RobloxStudioRunner:  # fmt: skip
    return RobloxStudioRunner(
        Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"),
        session_factory=lambda **kw: StudioMcpSession(
            [sys.executable, str(STANDIN), str(world)], **kw
        ),
        studio_version_of=app.version,
        discover_seconds=0.2,
        place_files=files,
        proved_on=proved_on,
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


@pytest.mark.parametrize(
    ("updates_to", "comes_back_with", "says", "then"),
    [
        ("0.748.0", None, "it was 0.747.0 and is now 0.748.0, which no operation is proved on",
         "The reopened Studio then read: PlaceReadError: the place in Studio (None)"),
        ("0.748.0", "ta-copy.rbxl", "it was 0.747.0 and is now 0.748.0, which no operation",
         "The place was restored and reopened in it at its baseline."),
        (None, None, "Studio was 0.747.0 before the reset reopened it, and its version can't be "
         "read now", "The reopened Studio then read: PlaceReadError"),
    ],
    ids=["updated-and-holding-no-place", "updated-and-the-place-reopened", "mid-replacement"],
)  # fmt: skip
async def test_a_studio_that_updates_itself_as_the_reset_reopens_it_is_named(
    tmp_path, updates_to, comes_back_with, says, then
):
    """#3184, found in the 2.8 rehearsal: the reset's reopening is a launch, Studio replaced
    itself with 0.748 at it, and its installer started the new Studio with no place. Bugs
    caught:
    - a reset that reports only what the reopened Studio read ("the place in Studio (None) is
      saved to the cloud, or doesn't say"), so nothing says Studio updated or what to do;
    - a reset that reads as done on an updated Studio whose place did reopen, leaving the next
      play to find a version nothing was proved on;
    - a bundle that can't be read mid-replacement read as "no change"."""
    world = _world(tmp_path, baseline=BASELINE)
    files = _files(tmp_path)
    app = _App(world)
    app.updates, app.updates_to, app.comes_back_with = True, updates_to, comes_back_with

    with pytest.raises(place.PlaceStateError) as raised:
        await _runner(world, files, app).reset()

    said = str(raised.value)
    assert says in said and then in said
    assert "scripts/dev/studio_requalify.py, #3048" in said
    assert app.done == ["quit", "open ta-copy.rbxl"]
    assert files.place.read_bytes() == PRISTINE  # the restore was made before the launch


async def test_a_studio_that_isnt_the_proved_version_is_refused_before_anything_is_touched(
    tmp_path,
):
    """#3184's second attempt. An updated Studio holding no place was refused as "the running
    Studio holds [None]", which is what the runtime recorded. Bug caught: the version the
    worker has no proof for going unsaid, or a reset that quits and restores under a Studio
    nothing can play on."""
    world = _world(tmp_path, baseline=BASELINE, studios=[{"id": "s-2", "file": None}])
    files = _files(tmp_path)
    before = files.place.read_bytes()
    app = _App(world)
    app.installed = "0.748.0"

    with pytest.raises(place.PlaceStateError) as raised:
        await _runner(world, files, app).reset()

    assert str(raised.value) == (
        "Studio is 0.748.0, and the operation was proved on 0.747.0: Studio has updated "
        "itself. Re-qualify the worker on 0.748.0 with the place open in it "
        "(scripts/dev/studio_requalify.py, #3048); nothing was touched"
    )
    assert app.done == []
    assert files.place.read_bytes() == before


async def test_a_studio_whose_version_cant_be_read_is_refused_before_anything_is_touched(
    tmp_path,
):
    """Bug caught: an unreadable bundle read as "the proved version", so the reset quits a
    Studio it can't compare with anything."""
    world = _world(tmp_path, baseline=BASELINE)
    files = _files(tmp_path)
    app = _App(world)
    app.installed = None

    with pytest.raises(place.PlaceStateError, match="can't be read .*; nothing was touched"):
        await _runner(world, files, app).reset()

    assert app.done == []


_NO_LOG = "Studio (pid 4343) holds 0 startup logs open (none)"
_ON_ZBETA = "Re-qualify the worker on 0.747.0 on channel zbeta with the place open in it"


@pytest.mark.parametrize(
    ("proved_on", "reopens_on", "comes_back", "says", "then"),
    [
        (PROVED, "zbeta", True,
         "Studio moved channel as the reset reopened it: it was on production and is now on "
         f"zbeta at 0.747.0, which no operation is proved on. {_ON_ZBETA}",
         "The place was restored and reopened in it at its baseline."),
        (PROVED, "zbeta", False,
         "Studio moved channel as the reset reopened it: it was on production and is now on "
         f"zbeta at 0.747.0, which no operation is proved on. {_ON_ZBETA}",
         "The reopened Studio then read: PlaceReadError: the place in Studio (None)"),
        (None, "zbeta", True,
         "Studio moved channel as the reset reopened it: it was on production and is now on "
         "zbeta at 0.747.0",
         "The place was restored and reopened in it at its baseline."),
        (PROVED, OSError(_NO_LOG), True,
         f"Studio's channel can't be read after the reset reopened it ({_NO_LOG}), and a "
         "Studio whose channel isn't known is one nothing was proved on.",
         "The place was restored and reopened in it at its baseline."),
    ],
    ids=["moved-and-the-place-reopened", "moved-and-holding-no-place",
         "moved-under-a-reset-with-no-proof", "unreadable-after-the-reopening"],
)  # fmt: skip
async def test_a_studio_that_changes_channel_as_the_reset_reopens_it_is_named(
    tmp_path, proved_on, reopens_on, comes_back, says, then
):
    """#3206: Roblox's updater moves an install to another channel at a launch, with the
    version unchanged, and the reset's reopening is a launch. On 2026-11-18 the Mac's Studio
    went from ``production`` to another channel at 0.748.0.7481526 that way, and came back
    holding no place. Bugs caught:
    - a reset that reads as done on a Studio no operation is proved on, since its version is
      the proved one;
    - a reset that reports only what the reopened Studio read ("the place in Studio (None)"),
      so nothing says the channel moved or what to do;
    - a reset run by hand, with no proof to hold Studio to, saying nothing of a move;
    - a reopened Studio that doesn't say its channel read as ready."""
    world = _world(tmp_path, baseline=BASELINE)
    files = _files(tmp_path)
    app = _App(world)
    app.reopens_on = reopens_on
    # The installer starts the moved Studio with no place, as it does an updated one.
    app.updates, app.updates_to = not comes_back, "0.747.0"

    with pytest.raises(place.PlaceStateError) as raised:
        await _runner(world, files, app, proved_on).reset()

    said = str(raised.value)
    assert says in said and then in said
    assert app.done == ["quit", "open ta-copy.rbxl"]
    assert files.place.read_bytes() == PRISTINE  # the restore was made before the launch


async def test_a_studio_on_another_channel_is_refused_before_anything_is_touched(tmp_path):
    """#3206, and #3184's rule for a version applied to a channel. A reset that relaunches a
    Studio nothing is proved on gains nothing, and each launch is another chance for Studio to
    replace itself. Bug caught: a reset that quits, restores and reopens under such a Studio,
    then reports only that the reopened one is on the wrong channel."""
    world = _world(tmp_path, baseline=BASELINE)
    files = _files(tmp_path)
    before = files.place.read_bytes()
    app = _App(world)
    app.channel_now = "zbeta"

    with pytest.raises(place.PlaceStateError) as raised:
        await _runner(world, files, app).reset()

    assert str(raised.value) == (
        "Studio is on channel zbeta, and the operation was proved on channel production: "
        "Studio moved channel at 0.747.0. Re-qualify the worker on 0.747.0 on channel zbeta "
        "with the place open in it (scripts/dev/studio_requalify.py, #3048); nothing was touched"
    )
    assert app.done == []
    assert files.place.read_bytes() == before


async def test_a_studio_that_doesnt_say_its_channel_can_still_be_reset(tmp_path):
    """The Studio a reset quits may be hung or half-started, which is why it is being reset.
    Bug caught: a reset refused because the Studio it is about to quit doesn't say its
    channel, so a worker whose Studio hung can never recover without a person. The reopened
    Studio's channel is the one read against the proof."""
    world = _world(tmp_path, baseline=BASELINE)
    files = _files(tmp_path)
    app = _App(world)
    app.channel_now, app.reopens_on = OSError(_NO_LOG), "production"

    await _runner(world, files, app).reset()

    assert app.done == ["quit", "open ta-copy.rbxl"]
    assert files.place.read_bytes() == PRISTINE


async def test_the_runtime_is_told_studio_updated_when_a_workers_reset_meets_it(tmp_path):
    """#3184's wiring, entered at ``Worker.serve()`` with the real runner over the real
    registry. The worker's first reset meets the update, as attempt 1's did in the rehearsal.
    The operation it then claims is answered ``not_executed``, as attempt 2 was. The updated
    Studio here reopened the place, so the worker reads online and is handed the claim (an
    offline worker is handed nothing). Bugs caught:
    - the reason the runtime records naming neither version (it read "the running Studio holds
      [None], not ta-copy.rbxl; the reset doesn't quit it");
    - the worker's own status reading ready after a reset that failed."""
    world = _world(tmp_path, baseline=BASELINE)
    app = _App(world)
    app.updates, app.updates_to, app.comes_back_with = True, "0.748.0", "ta-copy.rbxl"
    clock = Clock()
    store = MemoryWorkerRegistryStore()
    registry = WorkerRegistry(store, clock=clock)
    reports = []
    worker = Worker(
        RegistryWorkerApi(registry, clock), _runner(world, _files(tmp_path), app),
        worker_id="macbook", platform="darwin-arm64", clock=clock, sleep=sleeping_on(clock),
        report=reports.append,
    )  # fmt: skip
    play = ServedOperation(PROVIDER, OPERATION)
    queued = await queue(registry, request(play, dispatch_id="dispatch-1"), max_attempts=1)

    async def settled() -> bool:
        await asyncio.sleep(0.01)  # the stand-in's sessions are real processes, in real time
        async with store.exclusive() as tx:
            return (await tx.operation(queued.operation_id)).state is OperationState.SETTLED

    async with Serving(worker) as serving:
        await serving.until(settled, turns=6000)  # a minute at most

    async with store.exclusive() as tx:
        result = (await tx.operation(queued.operation_id)).result
    assert result.status is OperationStatus.NOT_EXECUTED
    assert result.reason == (
        "the worker's tool could not be reset (the worker has just started, and its tool's "
        "state is unknown): PlaceStateError: Studio is 0.748.0, and the operation was proved "
        "on 0.747.0: Studio has updated itself. Re-qualify the worker on 0.748.0 with the "
        "place open in it (scripts/dev/studio_requalify.py, #3048); nothing was touched"
    )
    assert reports[0].tool_ready is False
    assert "it was 0.747.0 and is now 0.748.0" in reports[0].tool_note
    assert (reports[-1].tool_ready, reports[-1].tool_note) == (
        False,
        result.reason.split("): ", 1)[1],
    )
