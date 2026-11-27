"""Whether a play may act through Studio's input, and a dedicated worker bringing Studio to the
front (SIP-0117 R5.18, R5.33, R5.37; #3193, #3300).

# Platform: dev-mac (Roblox Studio runs only on the worker's Mac)

R5.18 refuses a scenario that acts through Studio's input unless Studio is the app in front, and
R5.28 reads that refusal as the worker's own. R5.37 makes the checks gate the input itself, not
only the activation, so they are read on every play that has an input action:

- **One reading of the front** (:func:`front_reading`), with four outcomes: the proved Studio,
  another app, none, or a read that failed. A failed read refuses as ``read_failed`` and nothing
  else is read. Another Studio than the proved one is another app.
- **On a worker not declared dedicated,** R5.18 as it was, except that the lock and the console
  session are read on every input play: a locked screen is never played on.
- **On a dedicated worker,** conditions 1 to 5 are read whether or not Studio is in front, in
  their order:

  1. the worker is declared dedicated, and the clock is inside its window (start <= now < end);
  2. the worker holds the operation's lease, by the serving loop's own record (``held_lease``);
  3. nobody has used the Mac for at least the threshold, which is never under 60 seconds;
  4. the Mac is unlocked and exactly one console session is on the console and logged in;
  5. nobody has touched it since: the idle counter, read again, is still at or over the
     threshold and no lower than the first reading.

  Studio already in front only skips the activation. Otherwise the clock is read again, and the
  proved Studio (R2.4, R5.29: its process is the one the proof read) is brought forward by its
  process id, once, never by its name, so nothing can be started. Its process must be the same
  before and after, Studio must read in front, and the idle counter must show nobody arrived.
- **Then, and immediately before the first input action** (:class:`InputGuard`), the lease and
  the window are read again; before every input action, the lock.

Anything else, and anything that can't be read, is R5.18's refusal: ``not_executed`` with
``tool_unready``. A locked screen is never unlocked, dismissed or worked around, and the front is
never moved a second time.

Every input play's record (``FrontRecord.ran_with``) says whether its input was permitted, and
names what happened by a closed vocabulary. It never names the app that was in front or anything
about what a person was doing: results go on a public Release.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from adapters.remote_execution.game_dev_roblox_studio.studio_app import StudioApp
from squadops.remote_execution.held_lease import HeldLease

#: The worker's optional settings that declare it dedicated (R5.33). Written by the person who
#: owns the Mac; no code ships with a value.
SETTINGS = (
    "roblox_studio_dedicated",
    "roblox_studio_window_start",
    "roblox_studio_window_end",
    "roblox_studio_idle_threshold_s",
)
#: The least the idle threshold may be. A lower setting is refused as a setting.
THRESHOLD_FLOOR_S = 60
#: The longest the activation is given, and never longer than the lease has left.
ACTIVATION_SECONDS = 30.0
#: The least lease the activation needs left. Under it, nothing is moved.
ACTIVATION_FLOOR_S = 1.0
#: What the one reading of the front found. ``unread`` is a read that failed.
WAS = ("studio", "other", "none", "unread")
#: Whether the play's input was permitted.
INPUT = ("permitted", "refused")
#: Why the input wasn't permitted: a closed list (R5.33, R5.37).
REFUSALS = (
    "not_dedicated",
    "window_unreadable",
    "outside_window",
    "lease_not_held",
    "threshold_too_low",
    "idle_below_threshold",
    "locked",
    "session_unavailable",
    "input_before_activation",
    "outside_window_at_activation",
    "activation_failed",
    "input_during_activation",
    "read_failed",
    "outside_window_before_input",
    "lease_not_held_before_input",
    "locked_during_play",
    "input_during_play",
)
_TRUE = frozenset({"true", "yes", "1"})


@dataclass(frozen=True)
class FrontPolicy:
    """The worker's declaration, as written, unparsed. It is read at each check, so a value that
    can't be read refuses that check by name and never stops the worker from serving."""

    dedicated: str | None = None
    window_start: str | None = None
    window_end: str | None = None
    idle_threshold_s: str | None = None

    @classmethod
    def from_settings(cls, settings: Mapping[str, str | None]) -> FrontPolicy:
        return cls(*(settings.get(name) for name in SETTINGS))


@dataclass(frozen=True)
class FrontRecord:
    """What R5.37's check found for one play that acts through Studio's input."""

    #: Whether the front was moved: never when Studio was already in front.
    activated: bool
    #: One of :data:`WAS`.
    was: str
    #: The idle counter at condition 5's read, in whole seconds, or ``None`` when not reached.
    idle_s: int | None = None
    #: One of :data:`REFUSALS`, or ``None`` when the input was permitted.
    refused: str | None = None
    reason: str = ""
    #: The idle counter's last reading, unrounded, which the reads during the play are held to.
    #: Not part of the record.
    idle_last: float | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        if self.was not in WAS:
            raise ValueError(f"front.was is one of {WAS}, not {self.was!r}")
        if self.refused is not None and self.refused not in REFUSALS:
            raise ValueError(f"front.refused is one of the closed list, not {self.refused!r}")
        if self.activated and self.was == "studio":
            raise ValueError("a Studio already in front is never activated")

    @property
    def permitted(self) -> bool:
        return self.refused is None

    def ran_with(self) -> dict[str, str]:
        record = {
            "front.input": INPUT[0] if self.permitted else INPUT[1],
            "front.activated": "true" if self.activated else "false",
            "front.was": self.was,
        }
        if self.idle_s is not None:
            record["front.idle_s"] = str(self.idle_s)
        if self.refused is not None:
            record["front.refused"] = self.refused
        return record

    def refusing(self, refused: str, reason: str) -> FrontRecord:
        """This record, with the input refused after all (a read before an input action)."""
        return replace(self, refused=refused, reason=reason)


class InputRefused(Exception):
    """Raised before an input action that may not be sent. Never a failed criterion: the runner
    reads it as R5.18's refusal, and nothing more is sent."""

    def __init__(self, refused: str, reason: str) -> None:
        super().__init__(reason)
        self.refused, self.reason = refused, reason


class _Refused(Exception):
    def __init__(self, refused: str, reason: str) -> None:
        super().__init__(reason)
        self.refused, self.reason = refused, reason


def front_reading(app: StudioApp, proved_pid: int | None) -> str:
    """The one reading of the front, as one of :data:`WAS`. ``studio`` only for the proved
    Studio's process: any other Studio is another app. Never the app's name."""
    try:
        front = app.frontmost()
    except Exception:  # noqa: BLE001 - a read that failed is its own outcome, never a guess
        return "unread"
    if front is None:
        return "none"
    return "studio" if proved_pid is not None and front == proved_pid else "other"


def permit_input(
    app: StudioApp,
    policy: FrontPolicy,
    *,
    proved_pid: int | None,
    lease: HeldLease | None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FrontRecord:
    """R5.37's check for a play with an input action, and R5.33's one activation. Returns the
    record, permitted or refused; never raises."""
    was = front_reading(app, proved_pid)
    reading = _Reading()
    if was == "unread":
        return FrontRecord(
            False, was, None, "read_failed", "which app is in front couldn't be read"
        )
    try:
        declared = _declared(policy)
    except _Refused as r:
        if r.refused != "not_dedicated":
            return FrontRecord(False, was, None, r.refused, r.reason)
        declared = None
    try:
        if declared is None:
            _lock_and_session(app, reading)
            if was != "studio":
                raise _Refused(
                    "not_dedicated",
                    f"{_WHAT[was]}, and the worker isn't declared dedicated, so it doesn't bring "
                    "Studio forward",
                )
            return FrontRecord(False, was, None, None, "Studio was in front")
        start, end, threshold = declared
        _conditions(app, reading, start, end, threshold, lease=lease, clock=clock)
        if was != "studio":
            reading.step = "the clock, again"
            if not start <= clock() < end:
                raise _Refused(
                    "outside_window_at_activation",
                    "the worker's window closed before the activation",
                )
            _activate(app, reading, proved_pid, lease=lease, clock=clock)
            reading.activated = True
        # Point 4's read of the lease and the window again is the guard's, immediately before
        # the first input action (InputGuard), after the activation or the in-front check.
    except _Refused as r:
        return FrontRecord(
            reading.activated, was, reading.idle_s, r.refused, r.reason, reading.last
        )
    except Exception as e:  # noqa: BLE001 - an unread condition never counts as held
        return FrontRecord(
            reading.activated,
            was,
            reading.idle_s,
            "read_failed",
            f"{reading.step} couldn't be read ({type(e).__name__})",
        )
    done = "Studio was brought to the front" if reading.activated else "Studio was in front"
    return FrontRecord(reading.activated, was, reading.idle_s, None, done, reading.last)


#: Whether the idle counter is read during a play (R5.37 point 6). It holds only if a scenario's
#: own input leaves macOS's counter alone, which the MacBook lane measures (the as-built table).
READS_IDLE_IN_PLAY = True


class InputGuard:
    """The reads around each input action of a permitted play (R5.37 points 4 and 6). Raises
    :class:`InputRefused`, and a read that fails refuses as ``read_failed``.

    - **Before the first:** the lock; on a dedicated worker the lease, the window, and the idle
      counter, held to the check's last reading (``input_before_activation`` when lower).
    - **Before each after it, and as soon as a held key ends:** the lock; on a dedicated worker
      the idle counter, held to the guard's previous reading (``input_during_play``).

    A worker that isn't dedicated runs attended, so its counter isn't read (point 1)."""

    def __init__(
        self,
        app: StudioApp,
        policy: FrontPolicy,
        *,
        lease: HeldLease | None,
        idle_s: float | None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        reads_idle: bool = READS_IDLE_IN_PLAY,
    ) -> None:
        self._app, self._lease, self._clock = app, lease, clock
        try:
            self._window: tuple[datetime, datetime] | None = _declared(policy)[:2]
        except _Refused:
            self._window = None  # not dedicated: permit_input refused any broken declaration
        self._last = idle_s
        self._reads_idle = reads_idle
        self._first = True

    def before(self, action: str) -> None:
        first, self._first = self._first, False
        self._read(action, f"before a {action}", first=first)

    def after(self, action: str) -> None:
        """As soon as a held key ends: a person who arrived during it is seen here."""
        self._read(action, f"as a {action} ended", first=False)

    def _read(self, action: str, when: str, *, first: bool) -> None:
        step = "the lock"
        try:
            if self._app.locked():
                raise InputRefused(
                    "locked_during_play",
                    f"the screen is locked {when}; nothing more is sent",
                )
            if self._window is None:
                return
            if first:
                self._authority(action)
            if first or self._reads_idle:
                step = "the idle counter"
                now = self._app.idle_seconds()
                if self._last is not None and now < self._last:
                    refused = "input_before_activation" if first else "input_during_play"
                    raise InputRefused(
                        refused,
                        f"the Mac was used {when} ({int(self._last)}s, then {int(now)}s); "
                        "nothing more is sent",
                    )
                self._last = now
        except InputRefused:
            raise
        except Exception as e:  # noqa: BLE001 - a read that failed never permits input
            raise InputRefused(
                "read_failed", f"{step} couldn't be read {when} ({type(e).__name__})"
            ) from e

    def _authority(self, action: str) -> None:
        """Point 4: the lease and the window, immediately before the first input action."""
        start, end = self._window  # type: ignore[misc]
        if self._lease is None or not self._lease.held():
            why = "no serving loop vouches for it" if self._lease is None else self._lease.why_not()
            raise InputRefused(
                "lease_not_held_before_input",
                f"the worker doesn't hold the lease before the first {action}: {why}",
            )
        if not start <= self._clock() < end:
            raise InputRefused(
                "outside_window_before_input",
                f"the worker's window closed before the first {action}",
            )


_WHAT = {"other": "another app is in front", "none": "no app is in front"}


@dataclass
class _Reading:
    """How far the check got: the step being read, the idle counter at condition 5, and whether
    the front was moved."""

    step: str = "the worker's declaration"
    idle_s: int | None = None
    #: The idle counter at condition 5's read, which the read after the activation is held to.
    second: float = 0.0
    #: The idle counter's latest reading.
    last: float | None = None
    activated: bool = False


def _lock_and_session(app: StudioApp, reading: _Reading) -> None:
    """The lock and the console session, read on every input play (R5.37)."""
    reading.step = "the lock"
    if app.locked():
        raise _Refused("locked", "the screen is locked, and is never unlocked")
    reading.step = "the console session"
    if not app.session_available():
        raise _Refused("session_unavailable", "the console session isn't available")


def _conditions(
    app: StudioApp,
    reading: _Reading,
    start: datetime,
    end: datetime,
    threshold: int,
    *,
    lease: HeldLease | None,
    clock: Callable[[], datetime],
) -> None:
    """Conditions 1 to 5, in their order. Raises the refusal of the first that doesn't hold."""
    reading.step = "the clock"
    if not start <= clock() < end:
        raise _Refused("outside_window", "the time is outside the worker's declared window")
    reading.step = "the lease"
    if lease is None or not lease.held():
        why = "no serving loop vouches for it" if lease is None else lease.why_not()
        raise _Refused("lease_not_held", f"the worker doesn't hold the lease: {why}")
    reading.step = "the idle counter"
    first = app.idle_seconds()
    if first < threshold:
        raise _Refused(
            "idle_below_threshold",
            f"the Mac was used {int(first)}s ago, under the {threshold}s threshold",
        )
    _lock_and_session(app, reading)
    reading.step = "the idle counter, again"
    second = app.idle_seconds()
    reading.idle_s, reading.second, reading.last = int(second), second, second
    if second < threshold or second < first:
        raise _Refused(
            "input_before_activation",
            f"the Mac was used between two reads ({int(first)}s, then {int(second)}s)",
        )


def _activate(
    app: StudioApp,
    reading: _Reading,
    proved_pid: int | None,
    *,
    lease: HeldLease | None,
    clock: Callable[[], datetime],
) -> None:
    """The one activation of the proved Studio, and the reads after it. Raises the refusal
    when it didn't take. Never retried."""
    reading.step = "Studio's process"
    studios = set(app.pids())
    if proved_pid is None or proved_pid not in studios:
        raise _Refused(
            "activation_failed",
            "the proved Studio isn't running, and the activation never starts one",
        )
    reading.step = "the lease's time left"
    left = (lease.expires_at - clock()).total_seconds() if lease is not None else 0.0
    if left < ACTIVATION_FLOOR_S:
        raise _Refused(
            "lease_not_held", f"the lease has {left:.1f}s left, too little for the activation"
        )
    reading.step = "the activation"
    reading.activated = True  # asked for: whatever it did, the front isn't moved again
    try:
        app.activate(proved_pid, min(ACTIVATION_SECONDS, left))
    except Exception as e:  # noqa: BLE001 - every way it failed is the refusal, named
        raise _Refused("activation_failed", f"the activation failed: {type(e).__name__}") from e
    reading.step = "Studio's process, after"
    if set(app.pids()) != studios:
        raise _Refused(
            "activation_failed",
            "Studio's processes changed across the activation, so it isn't the proved one's play",
        )
    reading.step = "the front"
    now_was = front_reading(app, proved_pid)
    if now_was == "unread":
        raise OSError("which app is in front couldn't be read after the activation")
    if now_was != "studio":
        raise _Refused("activation_failed", "the proved Studio isn't in front after the activation")
    reading.step = "the idle counter, after"
    third = app.idle_seconds()
    reading.last = third
    # An untouched counter only rises, so a reading lower than condition 5's is input since it,
    # with no gap and no clock between the two reads.
    if third < reading.second:
        raise _Refused(
            "input_during_activation",
            "the Mac was used during the activation, so nothing is played and the front isn't "
            "moved again",
        )


def _declared(policy: FrontPolicy) -> tuple[datetime, datetime, int]:
    """The window and the threshold, or the refusal naming what in the declaration is wrong.
    Nothing is defaulted: a missing flag, start, end or threshold is not dedicated."""
    if (policy.dedicated or "").strip().lower() not in _TRUE:
        raise _Refused("not_dedicated", "the worker isn't declared dedicated")
    if not (policy.window_start and policy.window_end and policy.idle_threshold_s):
        raise _Refused(
            "not_dedicated",
            "the worker's declaration names no window start, window end or idle threshold",
        )
    start, end = _instant(policy.window_start), _instant(policy.window_end)
    if start is None or end is None:
        raise _Refused(
            "window_unreadable",
            "the window's start or end isn't an ISO 8601 time with a UTC offset",
        )
    if end <= start:
        raise _Refused("window_unreadable", "the window's end isn't after its start")
    try:
        threshold = int(policy.idle_threshold_s)
    except ValueError:
        threshold = -1
    if threshold < THRESHOLD_FLOOR_S:
        raise _Refused(
            "threshold_too_low",
            f"the idle threshold isn't a whole number of seconds of at least {THRESHOLD_FLOOR_S}",
        )
    return start, end, threshold


def _instant(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None
