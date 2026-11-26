"""SIP-0117 R5.33 (#3193): a dedicated worker brings Studio to the front, inside its declared window.

The tests the amendment requires (the Spark lane's text, on #3193). Each is entered at the
runner's transaction (``RobloxStudioRunner.run``, where R5.18's check sits) over the stand-in
``StudioMCP``, with the app, the clock, the idle counter, the lock and the activation as fakes, and
asserts the result's status, its ``tool_unready`` flag, its ``front.*`` keys, and whether the
activation was called. The last group enters at the serving loop.

What bugs would these catch? A worker that takes the front from a person: one at the keyboard, one
who arrived between two reads or during the activation, one outside the declared window, on a
locked screen, or with a lease nobody vouches for. And a worker that does so on a reading it
couldn't make.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio.front import (
    REFUSALS,
    FrontPolicy,
    FrontRecord,
    bring_studio_forward,
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
STUDIO, OTHER = 4242, 31620
#: An app a person might have in front, which no record may carry.
SECRET = "Messages — a private conversation"


class _FrontMac(_Mac):
    """The Mac as R5.33 reads it. ``idle`` is the idle counter's readings in order, each a
    number or an ``OSError``; ``lock`` and ``session`` read as given, or raise. The activation
    brings Studio forward unless ``activation`` says otherwise."""

    def __init__(self, world: Path, *, idle=(300.0, 301.0, 302.0), lock=False, session=True,
                 activation: str | OSError = "brings-studio", front_after=STUDIO) -> None:  # fmt: skip
        super().__init__(OTHER, world=world)
        self.idle, self.lock, self.session = list(idle), lock, session
        self.activation, self.front_after = activation, front_after
        self.activations = 0
        self.frontmost_name = SECRET  # what a person was doing: never read into a record

    def _read(self, value):
        if isinstance(value, Exception):
            raise value
        return value

    def idle_seconds(self) -> float:
        if not self.idle:
            raise AssertionError("the idle counter was read more times than the rule reads it")
        return self._read(self.idle.pop(0))

    def locked(self) -> bool:
        return self._read(self.lock)

    def session_available(self) -> bool:
        return self._read(self.session)

    def activate(self) -> None:
        self.activations += 1
        if isinstance(self.activation, Exception):
            raise self.activation
        if self.activation == "brings-studio":
            self.front = self.front_after


class _NoReadsMac(_FrontMac):
    """A Mac whose conditions may not be read at all."""

    def idle_seconds(self):
        raise AssertionError("the idle counter was read")

    def locked(self):
        raise AssertionError("the lock was read")

    def session_available(self):
        raise AssertionError("the session was read")

    def activate(self):
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
            proved_on: ProvedOn = PROVED, monotonic=None) -> RobloxStudioRunner:  # fmt: skip
    ticks = iter(range(10_000))
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
        monotonic=monotonic or (lambda: float(next(ticks)) * 0.001),
    )  # fmt: skip


def _held(*, accepted=True, refused=None, expires=NOON + timedelta(minutes=5)) -> HeldLease:
    return HeldLease(expires, lambda: NOON, accepted=accepted, refused=refused)


async def _run(world, mac, *, lease: HeldLease | None = None, request=None, **runner):
    token = held_lease.holding(lease if lease is not None else _held())
    try:
        return await _runner(world, mac, **runner).run(request or _request())
    finally:
        held_lease.released(token)


def _front(result) -> dict[str, str]:
    return {k: v for k, v in result.ran_with.items() if k.startswith("front.")}


def _refused(result, reason: str) -> None:
    """R5.18's refusal, as R5.28 reads it, with R5.33's reason recorded."""
    assert result.status is OperationStatus.NOT_EXECUTED, result.reason
    assert result.tool_unready is True
    assert result.records == ()  # never a failed criterion
    assert _front(result)["front.activated"] == "false"
    assert _front(result)["front.refused"] == reason
    assert reason in REFUSALS


# --- 1 ---------------------------------------------------------------------------------------


async def test_the_front_lost_and_recovered(tmp_path):
    world = _played(tmp_path)
    mac = _FrontMac(world)

    result = await _run(world, mac)

    assert result.status is OperationStatus.COMPLETED, result.reason
    assert mac.activations == 1
    assert _front(result) == {
        "front.activated": "true",
        "front.was": "other",
        "front.idle_s": "301",
    }
    assert [i["tool"] for i in _inputs(tmp_path)]  # the scenario's own input, and nothing else


# --- 2 ---------------------------------------------------------------------------------------

_LATE = datetime.fromisoformat(f"2026-11-26T21:00:00{EST}")


@pytest.mark.parametrize(
    ("policy", "lease", "mac", "clock", "refused"),
    [
        (FrontPolicy(None, START, END, "120"), None, {}, None, "not_dedicated"),
        (FrontPolicy("true", None, END, "120"), None, {}, None, "not_dedicated"),
        (FrontPolicy("true", START, None, "120"), None, {}, None, "not_dedicated"),
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
        (DEDICATED, None, {"lock": True}, None, "locked"),
        (DEDICATED, None, {"session": False}, None, "session_unavailable"),
    ],
    ids=[
        "no-dedicated-flag", "no-start", "no-end",
        "a-start-with-no-offset", "a-start-that-doesnt-parse", "an-end-before-its-start",
        "before-the-start", "exactly-at-the-end", "after-the-end",
        "the-renewal-refused", "the-expiry-passed",
        "idle-under-the-threshold", "a-threshold-of-59",
        "a-locked-screen", "no-console-session",
    ],
)  # fmt: skip
async def test_each_condition_failing_alone_refuses_and_never_activates(
    tmp_path, policy, lease, mac, clock, refused
):
    world = _played(tmp_path)
    front_mac = _FrontMac(world, **mac)

    result = await _run(world, front_mac, lease=lease, policy=policy, clock=_clock(clock or NOON))

    _refused(result, refused)
    assert front_mac.activations == 0
    assert not (tmp_path / "calls.log").exists()  # nothing synced, nothing played


# --- 3 ---------------------------------------------------------------------------------------

_DOWN = OSError("the read failed")


@pytest.mark.parametrize(
    ("mac", "clock", "activated"),
    [
        ({}, _DOWN, 0),
        ({"idle": (_DOWN,)}, None, 0),
        ({"idle": (300.0, _DOWN)}, None, 0),
        ({"idle": (300.0, 301.0, _DOWN)}, None, 1),
        ({"lock": _DOWN}, None, 0),
        ({"front_after": _DOWN}, None, 1),
    ],
    ids=["the-clock", "the-first-idle-read", "the-second-idle-read", "the-third-idle-read",
         "the-lock", "the-front-after-the-activation"],
)  # fmt: skip
async def test_each_read_failing_is_read_failed_and_nothing_plays(tmp_path, mac, clock, activated):
    world = _played(tmp_path)
    front_mac = _FrontMac(world, **{k: v for k, v in mac.items() if k != "front_after"})
    if "front_after" in mac:
        front_mac.front_after = mac["front_after"]

    result = await _run(world, front_mac, clock=_clock(clock) if clock else None)

    _refused(result, "read_failed")
    assert front_mac.activations == activated
    assert _inputs(tmp_path) == []


# --- 4, 5 ------------------------------------------------------------------------------------


async def test_input_between_the_two_reads_refuses_before_any_activation(tmp_path):
    world = _played(tmp_path)
    mac = _FrontMac(world, idle=(300.0, 150.0))

    result = await _run(world, mac)

    _refused(result, "input_before_activation")
    assert (mac.activations, _front(result)["front.idle_s"]) == (0, "150")


async def test_the_window_closing_between_the_two_reads_refuses(tmp_path):
    world = _played(tmp_path)
    mac = _FrontMac(world)
    past_the_end = datetime.fromisoformat(END) + timedelta(seconds=1)

    result = await _run(world, mac, clock=_clock(NOON, past_the_end))

    _refused(result, "outside_window_at_activation")
    assert mac.activations == 0


# --- 6, 7 ------------------------------------------------------------------------------------


async def test_input_during_the_activation_plays_nothing_and_moves_the_front_no_more(tmp_path):
    """The third reading is lower than the time since the second: a person arrived."""
    world = _played(tmp_path)
    mac = _FrontMac(world, idle=(300.0, 301.0, 0.2))
    seconds = iter([100.0, 101.5])  # condition 5's read, then the read after the activation

    result = await _run(world, mac, monotonic=lambda: next(seconds))

    _refused(result, "input_during_activation")
    assert mac.activations == 1
    assert _inputs(tmp_path) == []  # no input sent
    assert not (tmp_path / "calls.log").exists()  # nothing synced or played


@pytest.mark.parametrize(
    "activation", [OSError("open -a failed"), "leaves-studio-behind"], ids=["raises", "doesnt-take"]
)
async def test_an_activation_that_fails_is_tried_once(tmp_path, activation):
    world = _played(tmp_path)
    mac = _FrontMac(world, activation=activation)

    result = await _run(world, mac)

    _refused(result, "activation_failed")
    assert mac.activations == 1


async def test_a_studio_that_quit_before_the_activation_is_never_started(tmp_path):
    """``open -a`` starts an app that isn't running, so Studio's process is read first."""
    world = _played(tmp_path)
    mac = _FrontMac(world)
    original = mac.session_available

    def quits_while_read():
        mac.pid = None  # Studio quit between the proof and the activation
        return original()

    mac.session_available = quits_while_read

    result = await _run(world, mac)

    _refused(result, "activation_failed")
    assert mac.activations == 0
    assert "never starts one" in result.reason


# --- 8 ---------------------------------------------------------------------------------------


async def test_a_studio_that_isnt_running_is_refused_as_today_with_no_activation(tmp_path):
    world = _played(tmp_path)
    mac = _NoReadsMac(world)
    runner = RobloxStudioRunner(
        Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"),
        session_factory=lambda **kw: StudioMcpSession([sys.executable, "-c", "raise SystemExit(3)"], **kw),
        studio_version_of=lambda _: "0.747.0",
        discover_seconds=0.2,
        place_files=_files(world.parent),
        proved_on=PROVED,
        app=mac,
        front_policy=DEDICATED,
        clock=_clock(NOON),
    )  # fmt: skip
    token = held_lease.holding(_held())
    try:
        result = await runner.run(_request())
    finally:
        held_lease.released(token)

    assert (result.status, result.tool_unready) == (OperationStatus.NOT_EXECUTED, True)
    assert "front.activated" not in result.ran_with  # refused before R5.18's check is reached


async def test_a_studio_that_isnt_the_proved_one_is_refused_first_after_each_restart(tmp_path):
    """R2.4 and R5.29 come before the activation: after Studio restarts (its process quit and
    the place opened again), and on a fresh runner (a worker restart)."""
    world = _played(tmp_path)
    another = ProvedOn("0.746.0", PROVED.studio_tools, PROVED.studio_channel)
    mac = _NoReadsMac(world)

    first = await _run(world, mac, proved_on=another)
    mac.quit(STUDIO, force=True)
    mac.open(_files(world.parent).place)
    after_reset = await _run(world, mac, proved_on=another)
    after_restart = await _run(world, _NoReadsMac(world), proved_on=another)

    for result in (first, after_reset, after_restart):
        assert (result.status, result.tool_unready) == (OperationStatus.NOT_EXECUTED, True)
        assert "proved on" in result.reason
        assert "front.activated" not in result.ran_with


# --- 9, 10, 12 -------------------------------------------------------------------------------


async def test_a_scenario_with_no_input_action_reads_no_condition(tmp_path):
    """R5.18's scope is unchanged: nothing to click, nothing to bring forward."""
    world = _played(tmp_path)
    no_input = _scenario(setup=[], steps=[])

    result = await _run(world, _NoReadsMac(world), request=_request(no_input))

    assert result.status is OperationStatus.COMPLETED, result.reason
    assert _front(result) == {}


@pytest.mark.parametrize("activated", [True, False], ids=["a-play", "a-refusal"])
async def test_no_record_names_what_was_in_front(tmp_path, activated):
    world = _played(tmp_path)
    mac = _FrontMac(world, lock=not activated)

    result = await _run(world, mac)

    whole = json.dumps(
        {
            "ran_with": result.ran_with,
            "reason": result.reason,
            "evidence": [(e.name, e.content) for e in result.evidence],
        }
    )
    assert SECRET not in whole and "Messages" not in whole
    assert _front(result)["front.was"] == "other"


async def test_a_worker_with_no_dedicated_setting_refuses_exactly_as_today(tmp_path):
    world = _played(tmp_path)
    mac = _NoReadsMac(world)

    result = await _run(world, mac, policy=None)

    assert (result.status, result.tool_unready) == (OperationStatus.NOT_EXECUTED, True)
    assert result.reason.startswith(
        "nothing was run: the scenario acts through Studio's input, which acts only on a Studio "
        f"in front, and process {OTHER} is in front, and Studio's are [{STUDIO}]"
    )
    assert _front(result) == {
        "front.activated": "false",
        "front.was": "other",
        "front.refused": "not_dedicated",
    }


# --- 11: from the serving loop ---------------------------------------------------------------


class _FrontReadingRunner(ScriptedRunner):
    """A tool whose run, once let go, makes R5.33's check against the serving loop's own record of
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
        self.front = bring_studio_forward(
            self.mac, policy, lease=held_lease.current(), was="other", clock=self._clock
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
        assert (runner.front.activated, runner.front.refused) == (False, "lease_not_held")
        assert "didn't reach the runtime" in runner.front.reason
        assert mac.activations == 0
    else:
        assert runner.front.activated is True
        assert mac.activations == 1


@pytest.mark.parametrize(
    ("was_accepted", "reading", "held"),
    [
        (False, LeaseReading(None, expires_at=NOON + timedelta(minutes=5)), True),
        (True, LeaseReading(FenceRefusal.LEASE_EXPIRED), False),
    ],
    ids=["a-renewal-held-after-one-that-failed", "a-renewal-refused-after-one-held"],
)
def test_a_renewals_answer_is_kept_on_the_record(was_accepted, reading, held):
    """Each case starts from the other reading, so the answer is what moves it. Bugs caught: a
    refused renewal that leaves the record reading held, so the run it is about to stop takes the
    front first; and an accepted renewal that leaves an earlier failure on the record."""
    record = HeldLease(NOON + timedelta(seconds=1), lambda: NOON, accepted=was_accepted)
    assert record.held() is was_accepted

    _kept(record, reading)

    assert record.held() is held


def test_a_front_record_is_an_activation_or_a_refusal_from_the_closed_lists():
    with pytest.raises(ValueError, match="front.was is one of"):
        FrontRecord(False, "Terminal", refused="locked")
    with pytest.raises(ValueError, match="closed list"):
        FrontRecord(False, "other", refused="somebody_was_typing")
    with pytest.raises(ValueError, match="never both"):
        FrontRecord(True, "other", refused="locked")


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
