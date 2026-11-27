"""SIP-0117 R5.33 and R5.37 (#3193, #3300): the checks that guard a person hold for every play that
acts through Studio's input, and a dedicated worker brings Studio to the front, inside its window.

R5.37's tests are numbered as the rule numbers them. Each is entered at the runner's transaction
(``RobloxStudioRunner.run``) over the stand-in ``StudioMCP``, with the app, the clock, the idle
counter, the lock, the session and the activation as fakes, and asserts the result's status, its
``tool_unready`` flag, its ``front.*`` keys, whether the activation was called and whether any input
was sent. The wiring tests enter at ``Worker.serve()``.

What bugs would these catch? A worker that sends input on a person's Mac: one at the keyboard, one
who arrived between two reads, during the activation or during the play, outside the declared
window, on a locked screen, or with a lease nobody vouches for; one that plays because Studio was
already in front, where no check was read; one that starts Studio, or brings another Studio forward
than the proved one; and one that does any of it on a reading it couldn't make.
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio import studio_app
from adapters.remote_execution.game_dev_roblox_studio.front import (
    ACTIVATION_SECONDS,
    REFUSALS,
    FrontPolicy,
    FrontRecord,
    permit_input,
)
from adapters.remote_execution.game_dev_roblox_studio.runner import ProvedOn, RobloxStudioRunner
from adapters.remote_execution.game_dev_roblox_studio.session import StudioMcpSession
from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.remote_execution import held_lease
from squadops.remote_execution.held_lease import HeldLease
from squadops.remote_execution.models import OperationStatus
from squadops.remote_execution.registry import WorkerRegistry
from squadops.remote_execution.serving import Worker, _kept
from squadops.remote_execution.workers import (
    FenceRefusal,
    LeaseReading,
    OperationState,
)
from tests.unit.remote_execution.registry_contract import Clock, passing, queue, request
from tests.unit.remote_execution.test_roblox_studio_cancel import _Deploy
from tests.unit.remote_execution.test_roblox_studio_play_scenario import (
    PROVED,
    STANDIN,
    _files,
    _inputs,
    _Mac,
    _played,
    _request,
    _scenario,
)
from tests.unit.remote_execution.worker_harness import (
    RegistryWorkerApi,
    ScriptedRunner,
    Serving,
    sleeping_on,
)

EST = "-05:00"
START, END = f"2026-11-26T08:00:00{EST}", f"2026-11-26T20:00:00{EST}"
NOON = datetime.fromisoformat(f"2026-11-26T12:00:00{EST}")
DEDICATED = FrontPolicy("true", START, END, "120")
STUDIO, OTHER, ANOTHER_STUDIO = 4242, 31620, 5151
#: An app a person might have in front, which no record may carry.
SECRET = "Messages — a private conversation"
#: The default scenario's input actions: the setup's click, then a held key and a walk.
INPUTS = ["user_mouse_input", "user_keyboard_input", "character_navigation"]


class _FrontMac(_Mac):
    """The Mac as R5.37 reads it. ``idle`` and ``lock`` are readings in order, each a value or an
    ``OSError``; once they run out the counter goes on rising and the lock stays as it last read.
    ``session`` reads as given, or raises. The activation brings the proved Studio forward unless
    ``activation`` says otherwise."""

    def __init__(self, world: Path, *, front=OTHER, idle=(300.0, 301.0), lock=(False,),
                 session=True, activation: str | Exception = "brings-studio") -> None:  # fmt: skip
        super().__init__(front, world=world)
        self.idle, self.locks, self.session = list(idle), list(lock), session
        self.activation = activation
        self.activations: list[tuple[int, float]] = []
        self.idle_reads = self.lock_reads = self.front_reads = 0
        self._last_idle, self._last_lock = 300.0, False
        self.frontmost_name = SECRET  # what a person was doing: never read into a record

    @staticmethod
    def _read(value):
        if isinstance(value, Exception):
            raise value
        return value

    def frontmost(self) -> int | None:
        self.front_reads += 1
        return super().frontmost()

    def idle_seconds(self) -> float:
        self.idle_reads += 1
        if self.idle:
            self._last_idle = self._read(self.idle.pop(0))
        else:
            self._last_idle += 1.0  # nobody touches it: it only rises
        return self._last_idle

    def locked(self) -> bool:
        self.lock_reads += 1
        if self.locks:
            self._last_lock = self._read(self.locks.pop(0))
        return self._last_lock

    def session_available(self) -> bool:
        return self._read(self.session)

    def activate(self, pid: int, timeout_s: float) -> None:
        self.activations.append((pid, timeout_s))
        if isinstance(self.activation, Exception):
            raise self.activation
        if self.activation == "brings-studio":
            self.front = pid


class _NoReadsMac(_FrontMac):
    """A Mac whose conditions may not be read at all."""

    def idle_seconds(self):
        raise AssertionError("the idle counter was read")

    def locked(self):
        raise AssertionError("the lock was read")

    def session_available(self):
        raise AssertionError("the session was read")

    def activate(self, pid, timeout_s):
        raise AssertionError("the front was moved")


def _clock(*readings):
    """The system clock: each read gives the next reading, the last one thereafter."""
    left = list(readings) or [NOON]

    def read() -> datetime:
        value = left.pop(0) if len(left) > 1 else left[0]
        if isinstance(value, Exception):
            raise value
        return value

    return read


def _runner(world: Path, mac: _FrontMac, *, policy: FrontPolicy | None = DEDICATED, clock=None,
            proved_on: ProvedOn = PROVED) -> RobloxStudioRunner:  # fmt: skip
    return RobloxStudioRunner(
        Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"),
        session_factory=lambda **kw: StudioMcpSession([sys.executable, str(STANDIN), str(world)], **kw),
        studio_version_of=lambda _: "0.747.0",
        discover_seconds=0.2,
        reopen_seconds=1.0,
        place_files=_files(world.parent),
        proved_on=proved_on,
        app=mac,
        front_policy=policy,
        clock=clock or _clock(NOON),
    )  # fmt: skip


def _held(
    *, accepted=True, refused=None, expires=NOON + timedelta(minutes=5), now=NOON
) -> HeldLease:
    return HeldLease(expires, (lambda: now) if not callable(now) else now, accepted=accepted,
                     refused=refused)  # fmt: skip


async def _run(world, mac, *, lease: HeldLease | None = None, request=None, **runner):
    token = held_lease.holding(lease if lease is not None else _held())
    try:
        return await _runner(world, mac, **runner).run(request or _request())
    finally:
        held_lease.released(token)


def _front(result) -> dict[str, str]:
    return {k: v for k, v in result.ran_with.items() if k.startswith("front.")}


def _sub(tmp_path: Path, name: str) -> Path:
    (tmp_path / name).mkdir()
    return tmp_path / name


def _tools(tmp_path) -> list[str]:
    return [i["tool"] for i in _inputs(tmp_path)]


def _refused(result, reason: str, *, activated: bool = False) -> None:
    """R5.18's refusal, as R5.28 reads it, with R5.37's reason recorded."""
    assert result.status is OperationStatus.NOT_EXECUTED, result.reason
    assert result.tool_unready is True
    assert result.records == ()  # never a failed criterion
    front = _front(result)
    assert (front["front.input"], front["front.refused"]) == ("refused", reason)
    assert front["front.activated"] == ("true" if activated else "false")
    assert reason in REFUSALS


# --- R5.37 tests 1 to 3: Studio already in front, on a dedicated worker -----------------------


@pytest.mark.parametrize(
    ("mac", "refused"),
    [({"lock": (True,)}, "locked"), ({"idle": (119.9,)}, "idle_below_threshold")],
    ids=["1-locked", "2-somebody-typing"],
)
async def test_studio_already_in_front_still_reads_every_condition(tmp_path, mac, refused):
    """The review's finding: with Studio in front, R5.33 read nothing, and played."""
    world = _played(tmp_path)
    front_mac = _FrontMac(world, front=STUDIO, **mac)

    result = await _run(world, front_mac)

    _refused(result, refused)
    assert _front(result)["front.was"] == "studio"
    assert (front_mac.activations, _inputs(tmp_path)) == ([], [])
    assert not (tmp_path / "calls.log").exists()  # nothing synced, nothing played


async def test_3_studio_in_front_idle_unlocked_inside_the_window_plays(tmp_path):
    world = _played(tmp_path)
    mac = _FrontMac(world, front=STUDIO)

    result = await _run(world, mac)

    assert result.status is OperationStatus.COMPLETED, result.reason
    assert _front(result) == {
        "front.input": "permitted",
        "front.activated": "false",
        "front.was": "studio",
        "front.idle_s": "301",
    }
    assert mac.activations == []
    assert _tools(tmp_path) == INPUTS


# --- R5.33's conditions, each failing alone, with Studio behind and with it in front ----------

_LATE = datetime.fromisoformat(f"2026-11-26T21:00:00{EST}")


@pytest.mark.parametrize("front", [OTHER, STUDIO], ids=["studio-behind", "studio-in-front"])
@pytest.mark.parametrize(
    ("policy", "lease", "mac", "clock", "refused"),
    [
        (FrontPolicy("true", "2026-11-26T08:00:00", END, "120"), None, {}, None, "window_unreadable"),
        (FrontPolicy("true", "eight in the morning", END, "120"), None, {}, None, "window_unreadable"),
        (FrontPolicy("true", END, START, "120"), None, {}, None, "window_unreadable"),
        (DEDICATED, None, {}, datetime.fromisoformat(f"2026-11-26T07:59:59{EST}"), "outside_window"),
        (DEDICATED, None, {}, datetime.fromisoformat(END), "outside_window"),
        (DEDICATED, None, {}, _LATE, "outside_window"),
        (DEDICATED, _held(refused=FenceRefusal.NOT_CLAIMED.value), {}, None, "lease_not_held"),
        (DEDICATED, _held(expires=NOON - timedelta(seconds=1)), {}, None, "lease_not_held"),
        (DEDICATED, None, {"idle": (119.9,)}, None, "idle_below_threshold"),
        (FrontPolicy("true", START, END, "59"), None, {"idle": (3600.0,)}, None, "threshold_too_low"),
        (DEDICATED, None, {"lock": (True,)}, None, "locked"),
        (DEDICATED, None, {"session": False}, None, "session_unavailable"),
        (DEDICATED, None, {"idle": (300.0, 150.0)}, None, "input_before_activation"),
    ],
    ids=[
        "a-start-with-no-offset", "a-start-that-doesnt-parse", "an-end-before-its-start",
        "before-the-start", "exactly-at-the-end", "after-the-end",
        "the-renewal-refused", "the-expiry-passed",
        "idle-under-the-threshold", "a-threshold-of-59",
        "a-locked-screen", "no-console-session", "input-between-the-two-reads",
    ],
)  # fmt: skip
async def test_each_condition_failing_alone_refuses_and_sends_nothing(
    tmp_path, front, policy, lease, mac, clock, refused
):
    world = _played(tmp_path)
    front_mac = _FrontMac(world, front=front, **mac)

    result = await _run(world, front_mac, lease=lease, policy=policy, clock=_clock(clock or NOON))

    _refused(result, refused)
    assert (front_mac.activations, _inputs(tmp_path)) == ([], [])
    assert not (tmp_path / "calls.log").exists()  # nothing synced, nothing played


# --- R5.37 tests 4 and 5, and point 6: the reads before input ---------------------------------


async def test_4_input_between_the_activation_and_the_first_input_action(tmp_path):
    """The read before the first input re-reads the counter: lower than the activation's own
    reading is a person who arrived since. The play had started; nothing was sent."""
    world = _played(tmp_path)
    mac = _FrontMac(world, idle=(300.0, 301.0, 302.0, 5.0))

    result = await _run(world, mac)

    _refused(result, "input_before_activation", activated=True)
    assert len(mac.activations) == 1
    assert _inputs(tmp_path) == []


async def test_5_a_lock_before_the_second_input_action_stops_the_play(tmp_path):
    """The check's lock read, then the first action's: both unlocked. Locked before the second:
    the first input was sent, and nothing after it."""
    world = _played(tmp_path)
    mac = _FrontMac(world, front=STUDIO, lock=(False, False, True))

    result = await _run(world, mac)

    _refused(result, "locked_during_play")
    assert _tools(tmp_path) == INPUTS[:1]
    assert "nothing more is sent" in result.reason


async def test_input_during_a_play_is_read_as_a_held_key_ends(tmp_path):
    """Point 6: a counter lower than the guard's previous reading is a person's input (measured
    on the Mac: a scenario's own clicks and held keys leave the counter alone, as-built table).
    The held key is the scenario's last input, so only the read at its end can see a person who
    arrived during it."""
    world = _played(tmp_path)
    hold_last = _scenario(steps=[{"action": "hold_key", "key": "W", "seconds": 0.2}])
    # the check's two reads, then before the click and before the hold; then at the hold's end
    mac = _FrontMac(world, front=STUDIO, idle=(300.0, 301.0, 302.0, 303.0, 0.4))

    result = await _run(world, mac, request=_request(hold_last))

    _refused(result, "input_during_play")
    assert _tools(tmp_path) == INPUTS[:2]


@pytest.mark.parametrize(
    ("lease", "clock", "refused"),
    [
        # the lease's own clock: held at condition 2, past its expiry once the front is settled
        (_held(expires=NOON + timedelta(seconds=2), now=_clock(NOON, NOON + timedelta(seconds=3))),
         None, "lease_not_held_before_input"),
        (None, _clock(NOON, NOON, NOON, datetime.fromisoformat(END)), "outside_window_before_input"),
    ],
    ids=["the-lease-expiring-during-the-activation", "the-window-closing-during-it"],
)  # fmt: skip
async def test_11_authority_ended_during_the_activation_refuses_before_input(
    tmp_path, lease, clock, refused
):
    world = _played(tmp_path)
    mac = _FrontMac(world)

    result = await _run(world, mac, lease=lease, clock=clock)

    _refused(result, refused, activated=True)
    assert len(mac.activations) == 1
    assert _inputs(tmp_path) == []


async def test_11_a_cancel_during_the_activation_is_the_cancels(tmp_path):
    """R5.30: the run is cancelled, never refused by the activation, and no input follows."""
    world = _played(tmp_path)
    started, release = threading.Event(), threading.Event()
    mac = _FrontMac(world)
    original = mac.activate

    def slow(pid, timeout_s):
        started.set()
        release.wait(5)
        original(pid, timeout_s)

    mac.activate = slow
    token = held_lease.holding(_held())
    try:
        run = asyncio.ensure_future(_runner(world, mac).run(_request()))
        while not started.is_set():
            await asyncio.sleep(0.01)
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run
    finally:
        release.set()
        held_lease.released(token)
    await asyncio.sleep(0.05)
    assert _inputs(tmp_path) == []
    assert not (tmp_path / "calls.log").exists()


async def test_the_activation_is_bounded_by_the_leases_time_left(tmp_path):
    """Point 4: never longer than the lease has left, and nothing at all under a second of it."""
    short = _played(_sub(tmp_path, "short"))
    mac = _FrontMac(short)
    await _run(short, mac, lease=_held(expires=NOON + timedelta(seconds=12)))
    assert mac.activations == [(STUDIO, 12.0)]

    usual = _played(_sub(tmp_path, "usual"))
    mac = _FrontMac(usual, front=OTHER)
    await _run(usual, mac)
    assert mac.activations == [(STUDIO, ACTIVATION_SECONDS)]

    nearly = _played(_sub(tmp_path, "nearly"))
    mac = _FrontMac(nearly)
    result = await _run(nearly, mac, lease=_held(expires=NOON + timedelta(seconds=0.5)))
    _refused(result, "lease_not_held")
    assert mac.activations == []


# --- R5.37 tests 6 to 8: unreadable conditions, a worker that isn't dedicated, the front ------


@pytest.mark.parametrize("policy", [DEDICATED, None], ids=["dedicated", "not-dedicated"])
@pytest.mark.parametrize(
    "mac",
    [{"lock": (OSError("ioreg failed"),)}, {"session": OSError("ioreg failed")}],
    ids=["the-lock", "the-session"],
)
async def test_6_the_lock_or_session_unreadable_with_studio_in_front(tmp_path, policy, mac):
    world = _played(tmp_path)
    front_mac = _FrontMac(world, front=STUDIO, **mac)

    result = await _run(world, front_mac, policy=policy)

    _refused(result, "read_failed")
    assert _inputs(tmp_path) == []


async def test_7_a_worker_that_isnt_dedicated_reads_the_lock_on_every_input_play(tmp_path):
    locked = _played(_sub(tmp_path, "locked"))
    result = await _run(locked, _FrontMac(locked, front=STUDIO, lock=(True,)), policy=None)
    _refused(result, "locked")
    assert _inputs(tmp_path / "locked") == []

    unlocked = _played(_sub(tmp_path, "unlocked"))
    mac = _FrontMac(unlocked, front=STUDIO, idle=(0.1,))
    result = await _run(unlocked, mac, policy=None)
    assert result.status is OperationStatus.COMPLETED, result.reason
    assert _front(result) == {
        "front.input": "permitted",
        "front.activated": "false",
        "front.was": "studio",
    }
    assert mac.idle_reads == 0  # attended by definition: no threshold, and no reads in play
    assert _tools(tmp_path / "unlocked") == INPUTS


async def test_a_worker_that_isnt_dedicated_refuses_studio_behind_as_before(tmp_path):
    world = _played(tmp_path)
    mac = _FrontMac(world)

    result = await _run(world, mac, policy=None)

    _refused(result, "not_dedicated")
    assert "another app is in front" in result.reason
    assert (mac.activations, mac.idle_reads) == ([], 0)


@pytest.mark.parametrize("policy", [DEDICATED, None], ids=["dedicated", "not-dedicated"])
async def test_8_a_failed_first_read_of_the_front_reads_nothing_else(tmp_path, policy):
    world = _played(tmp_path)
    mac = _FrontMac(world, front=OSError("lsappinfo front failed"))

    result = await _run(world, mac, policy=policy)

    _refused(result, "read_failed")
    assert _front(result)["front.was"] == "unread"
    assert result.reason.endswith("which app is in front couldn't be read")
    # no second read authorizes the play, and no condition after it is read
    assert (mac.front_reads, mac.idle_reads, mac.lock_reads, mac.activations) == (1, 0, 0, [])
    assert _inputs(tmp_path) == []


# --- R5.37 tests 9 and 10: an activation that can't launch -----------------------------------


async def test_9_studio_running_is_activated_exactly_once_by_its_process(tmp_path):
    world = _played(tmp_path)
    mac = _FrontMac(world)

    result = await _run(world, mac)

    assert result.status is OperationStatus.COMPLETED, result.reason
    assert mac.activations == [(STUDIO, ACTIVATION_SECONDS)]
    assert _front(result) == {
        "front.input": "permitted",
        "front.activated": "true",
        "front.was": "other",
        "front.idle_s": "301",
    }
    assert _tools(tmp_path) == INPUTS


async def test_9_studio_gone_before_the_activation_is_never_launched(tmp_path):
    world = _played(tmp_path)
    mac = _FrontMac(world)
    original = mac.session_available

    def quits_while_read():
        mac.pid = None  # Studio quit between the proof and the activation
        return original()

    mac.session_available = quits_while_read

    result = await _run(world, mac)

    _refused(result, "activation_failed")
    assert mac.activations == []
    assert "never starts one" in result.reason


async def test_9_the_process_set_changing_during_the_activation_refuses(tmp_path):
    world = _played(tmp_path)
    mac = _FrontMac(world)
    original = mac.activate

    def restarts_studio(pid, timeout_s):
        original(pid, timeout_s)
        mac.pid = ANOTHER_STUDIO

    mac.activate = restarts_studio

    result = await _run(world, mac)

    _refused(result, "activation_failed", activated=True)
    assert len(mac.activations) == 1
    assert _inputs(tmp_path) == []


@pytest.mark.parametrize(
    "activation",
    [OSError("the activation answered 'refused'"), "leaves-studio-behind"],
    ids=["raises", "doesnt-take"],
)
async def test_9_an_activation_that_fails_is_never_retried(tmp_path, activation):
    world = _played(tmp_path)
    mac = _FrontMac(world, activation=activation)

    result = await _run(world, mac)

    _refused(result, "activation_failed", activated=True)
    assert len(mac.activations) == 1
    assert _inputs(tmp_path) == []


async def test_10_two_studios_running_bring_neither_forward(tmp_path):
    """No proved process among two: nothing is brought forward, and another Studio in front is
    another app, never the proved one."""
    world = _played(tmp_path)
    mac = _FrontMac(world, front=ANOTHER_STUDIO)
    mac.pids = lambda: [STUDIO, ANOTHER_STUDIO]

    result = await _run(world, mac)

    _refused(result, "activation_failed")
    assert _front(result)["front.was"] == "other"
    assert (mac.activations, _inputs(tmp_path)) == ([], [])


async def test_10_only_the_proved_studio_is_brought_forward(tmp_path):
    """A second Studio appearing after the proof: the activation names the proved process."""
    world = _played(tmp_path)
    mac = _FrontMac(world)
    reads = iter([[STUDIO]])
    mac.pids = lambda: next(reads, [STUDIO, ANOTHER_STUDIO])

    result = await _run(world, mac)

    assert result.status is OperationStatus.COMPLETED, result.reason
    assert [pid for pid, _ in mac.activations] == [STUDIO]


async def test_the_read_after_the_activation_is_held_to_the_second_read(tmp_path):
    """The third reading lower than the second: a person arrived during the activation."""
    world = _played(tmp_path)
    mac = _FrontMac(world, idle=(300.0, 301.0, 300.9))

    result = await _run(world, mac)

    _refused(result, "input_during_activation", activated=True)
    assert _inputs(tmp_path) == []


async def test_the_window_closing_before_the_activation_refuses(tmp_path):
    world = _played(tmp_path)
    mac = _FrontMac(world)
    past_the_end = datetime.fromisoformat(END) + timedelta(seconds=1)

    result = await _run(world, mac, clock=_clock(NOON, past_the_end))

    _refused(result, "outside_window_at_activation")
    assert mac.activations == []


# --- R5.37 test 12: the console session, entry by entry --------------------------------------


def _ioreg(*entries: str) -> str:
    return f'+-o Root\n    "IOConsoleLocked" = No\n    "IOConsoleUsers" = ({",".join(entries)})\n'


def _entry(on: str, done: str, name: str = "u") -> str:
    return (f'{{"kCGSSessionOnConsoleKey"={on},"kCGSessionUserNameKey"="{name}",'
            f'"kCGSessionLoginDoneKey"={done}}}')  # fmt: skip


@pytest.mark.parametrize(
    ("ioreg", "available"),
    [
        (_ioreg(_entry("Yes", "No", "a"), _entry("No", "Yes", "b")), False),
        (_ioreg(_entry("Yes", "Yes")), True),
        (_ioreg(_entry("Yes", "No")), False),
        (_ioreg(_entry("Yes", "Yes", "a"), _entry("Yes", "Yes", "b")), False),
        (_ioreg(_entry("No", "Yes", "a"), _entry("Yes", "Yes", "b")), True),
        (_ioreg(), False),
        (_ioreg('{"kCGSSessionOnConsoleKey"=Yes,"kCGSSessionOnConsoleKey"=No,'
                '"kCGSessionLoginDoneKey"=Yes}', _entry("Yes", "Yes", "b")), False),
        (_ioreg(_entry("Yes", "Yes", "{braces}, and a ) too")), True),
    ],
    ids=["12-two-users-one-on-the-console-the-other-logged-in", "one-ready-session",
         "on-the-console-still-logging-in", "two-on-the-console",
         "one-switched-out-one-ready", "no-entry", "a-contradiction-within-one-entry",
         "a-name-with-braces"],
)  # fmt: skip
def test_12_the_console_session_is_read_entry_by_entry(ioreg, available):
    assert studio_app.session_available_in(ioreg) is available


def test_a_listing_with_no_console_users_cant_be_read():
    with pytest.raises(OSError, match="names no IOConsoleUsers"):
        studio_app.session_available_in('+-o Root\n  "IOConsoleLocked" = No\n')
    with pytest.raises(OSError, match="doesn't close"):
        studio_app.session_available_in('"IOConsoleUsers" = ({"kCGSSessionOnConsoleKey"=Yes')


# --- Records ---------------------------------------------------------------------------------


async def test_a_scenario_with_no_input_action_reads_no_condition(tmp_path):
    """R5.18's scope is unchanged: nothing to click, nothing to read."""
    world = _played(tmp_path)

    result = await _run(world, _NoReadsMac(world), request=_request(_scenario(setup=[], steps=[])))

    assert result.status is OperationStatus.COMPLETED, result.reason
    assert _front(result) == {}


@pytest.mark.parametrize("permitted", [True, False], ids=["a-play", "a-refusal"])
async def test_no_record_names_what_was_in_front(tmp_path, permitted):
    world = _played(tmp_path)
    mac = _FrontMac(world, lock=(not permitted,))

    result = await _run(world, mac)

    whole = json.dumps({"ran_with": result.ran_with, "reason": result.reason,
                        "evidence": [(e.name, e.content) for e in result.evidence]})  # fmt: skip
    assert SECRET not in whole and "Messages" not in whole
    assert _front(result)["front.was"] == "other"


def test_a_front_record_is_from_the_closed_lists():
    with pytest.raises(ValueError, match="front.was is one of"):
        FrontRecord(False, "Terminal", refused="locked")
    with pytest.raises(ValueError, match="closed list"):
        FrontRecord(False, "other", refused="somebody_was_typing")
    with pytest.raises(ValueError, match="never activated"):
        FrontRecord(True, "studio")


def test_a_policy_reads_its_settings_and_nothing_else():
    settings = {
        "roblox_studio_dedicated": "true",
        "roblox_studio_window_start": START,
        "roblox_studio_window_end": END,
        "roblox_studio_idle_threshold_s": "120",
    }

    assert FrontPolicy.from_settings(settings) == DEDICATED
    assert FrontPolicy.from_settings({}) == FrontPolicy()
    assert datetime.fromisoformat(START).astimezone(UTC).hour == 13


# --- R5.37 test 13, and the lease: from the serving loop -------------------------------------


async def test_13_a_play_on_a_locked_mac_with_studio_in_front_sends_no_input(tmp_path):
    """Wiring, entered at ``Worker.serve()`` with the registry in process: the review's path."""
    deploy = _Deploy(tmp_path)
    deploy.mac.locked = lambda: True
    deploy.mac.session_available = lambda: True

    async with Serving(deploy.worker) as serving:
        await serving.until(deploy.registered, turns=6000)
        result = await deploy.play(serving, "cyc_locked")

    assert (result.status, result.tool_unready) == (OperationStatus.NOT_EXECUTED, True)
    assert _front(result) == {
        "front.input": "refused",
        "front.activated": "false",
        "front.was": "studio",
        "front.refused": "locked",
    }
    assert _inputs(tmp_path) == []


class _FrontReadingRunner(ScriptedRunner):
    """A tool whose run, once let go, makes R5.37's check against the serving loop's own record of
    the lease, as the Studio runner does, with every other condition holding."""

    def __init__(self, clock: Clock, mac: _FrontMac) -> None:
        super().__init__(clock)
        self.mac, self.go, self.front = mac, False, None

    async def run(self, request):
        self.runs.append(request)
        while not self.go:
            await asyncio.sleep(0)
        now = self._clock()
        policy = FrontPolicy("true", (now - timedelta(hours=1)).isoformat(),
                             (now + timedelta(hours=1)).isoformat(), "120")  # fmt: skip
        self.front = permit_input(
            self.mac, policy, proved_pid=STUDIO, lease=held_lease.current(), clock=self._clock
        )
        return passing(request.dispatch_id)


class _CountingApi(RegistryWorkerApi):
    def __init__(self, registry, clock) -> None:
        super().__init__(registry, clock)
        self.renewals_asked = 0

    async def renew(self, session_id, runtime_status, fence):
        self.renewals_asked += 1
        return await super().renew(session_id, runtime_status, fence)


@pytest.mark.parametrize("renewal", ["reaches-the-runtime", "doesnt"])
async def test_the_lease_is_read_from_the_serving_loops_record(tmp_path, renewal):
    """Wiring, entered at ``Worker.serve()``: an operation claimed, then run after its renewal
    failed to reach the runtime, reaches the runner with a lease that reads not held, and no
    activation is made. The control: the same run after a renewal the runtime accepted."""
    clock = Clock()
    store = MemoryWorkerRegistryStore()
    registry = WorkerRegistry(store, clock=clock)
    api = _CountingApi(registry, clock)
    mac = _FrontMac(_played(tmp_path))
    runner = _FrontReadingRunner(clock, mac)
    worker = Worker(api, runner, worker_id="macbook", platform="darwin-arm64",
                    clock=clock, sleep=sleeping_on(clock))  # fmt: skip
    queued = await queue(registry, request(dispatch_id="dispatch-1"), max_attempts=1)

    async def claimed() -> bool:
        async with store.exclusive() as tx:
            return (await tx.operation(queued.operation_id)).state is OperationState.CLAIMED

    async def renewed() -> bool:
        return api.renewals_asked >= 1

    async def settled() -> bool:
        async with store.exclusive() as tx:
            return (await tx.operation(queued.operation_id)).state is OperationState.SETTLED

    async with Serving(worker) as serving:
        await serving.until(claimed)
        if renewal == "doesnt":
            api.down = {"renew"}
        await serving.until(renewed)
        runner.go = True
        await serving.until(settled)

    if renewal == "doesnt":
        assert (runner.front.permitted, runner.front.refused) == (False, "lease_not_held")
        assert "didn't reach the runtime" in runner.front.reason
        assert mac.activations == []
    else:
        assert (runner.front.permitted, runner.front.activated) == (True, True)
        assert len(mac.activations) == 1


@pytest.mark.parametrize(
    ("was_accepted", "reading", "held"),
    [
        (False, LeaseReading(None, expires_at=NOON + timedelta(minutes=5)), True),
        (True, LeaseReading(FenceRefusal.LEASE_EXPIRED), False),
    ],
    ids=["a-renewal-held-after-one-that-failed", "a-renewal-refused-after-one-held"],
)
def test_a_renewals_answer_is_kept_on_the_record(was_accepted, reading, held):
    """Each case starts from the other reading, so the answer is what moves it."""
    record = HeldLease(NOON + timedelta(seconds=1), lambda: NOON, accepted=was_accepted)
    assert record.held() is was_accepted

    _kept(record, reading)

    assert record.held() is held
