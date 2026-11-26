"""A dedicated worker brings Studio to the front, inside its declared window (SIP-0117 R5.33, #3193).

# Platform: dev-mac (Roblox Studio runs only on the worker's Mac)

R5.18 refuses a scenario that acts through Studio's input unless Studio is the app in front, and
R5.28 reads that refusal as the worker's own. Both stand. On a worker its owner has declared
dedicated, inside the window its owner has declared, the runner may bring the running Studio to
the front itself, once per operation, before R5.18's refusal. Only when every condition holds at
the moment it is read:

1. the worker is declared dedicated, and the clock is inside its window (start <= now < end);
2. the worker holds the operation's lease, by the serving loop's own record (``held_lease``);
3. nobody has used the Mac for at least the threshold, which is never under 60 seconds;
4. the Mac is unlocked and its console session is available;
5. nobody has touched it since: the idle counter, read again immediately before, is still at or
   over the threshold and no lower than the first reading, and the clock is still inside;
6. a proved Studio is running (R2.4, R5.29: the runner checks that before it gets here).

The activation brings the running Studio forward and does nothing else. Then Studio must read in
front, and the idle counter must show nobody arrived during it. Anything else, and anything that
can't be read, is R5.18's refusal: ``not_executed`` with ``tool_unready``. A locked screen is never
unlocked, dismissed or worked around, and the front is never moved a second time.

The record (``FrontRecord.ran_with``) names what happened by a closed vocabulary. It never names
the app that was in front or anything about what a person was doing: results go on a public
Release.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
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
#: What was in front when R5.18's check found Studio behind.
WAS = ("studio", "other", "none", "unread")
#: Why the front wasn't brought forward: a closed list (R5.33).
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
    """What happened when R5.18's check found Studio behind."""

    activated: bool
    #: One of :data:`WAS`.
    was: str
    #: The idle counter at condition 5's read, in whole seconds, or ``None`` when not reached.
    idle_s: int | None = None
    #: One of :data:`REFUSALS`, or ``None`` on an activation.
    refused: str | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.was not in WAS:
            raise ValueError(f"front.was is one of {WAS}, not {self.was!r}")
        if (self.refused is None) != self.activated:
            raise ValueError("a front record is an activation or a refusal, never both")
        if self.refused is not None and self.refused not in REFUSALS:
            raise ValueError(f"front.refused is one of the closed list, not {self.refused!r}")

    def ran_with(self) -> dict[str, str]:
        record = {"front.activated": "true" if self.activated else "false", "front.was": self.was}
        if self.idle_s is not None:
            record["front.idle_s"] = str(self.idle_s)
        if self.refused is not None:
            record["front.refused"] = self.refused
        return record


class _Refused(Exception):
    def __init__(self, refused: str, reason: str) -> None:
        super().__init__(reason)
        self.refused, self.reason = refused, reason


def front_was(app: StudioApp) -> str:
    """What is in front, by R5.18's own read, as one of :data:`WAS`. Never the app's name."""
    try:
        front, studios = app.frontmost(), app.pids()
    except OSError:
        return "unread"
    if front is None:
        return "none"
    return "studio" if front in studios else "other"


def bring_studio_forward(
    app: StudioApp,
    policy: FrontPolicy,
    *,
    lease: HeldLease | None,
    was: str,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    monotonic: Callable[[], float] = time.monotonic,
) -> FrontRecord:
    """R5.33's check and its one activation. Returns the record; never raises."""
    reading = _Reading()
    try:
        start, end, threshold = _declared(policy)
        _conditions(app, reading, start, end, threshold, lease=lease, clock=clock)
        reading.since = monotonic()
        reading.step = "the clock, again"
        if not start <= clock() < end:
            raise _Refused(
                "outside_window_at_activation", "the worker's window closed before the activation"
            )
        _activate(app, reading, monotonic)
    except _Refused as r:
        return FrontRecord(False, was, reading.idle_s, r.refused, r.reason)
    except Exception as e:  # noqa: BLE001 - an unread condition never counts as held
        return FrontRecord(
            False,
            was,
            reading.idle_s,
            "read_failed",
            f"{reading.step} couldn't be read ({type(e).__name__})",
        )
    return FrontRecord(True, was, reading.idle_s, None, "Studio was brought to the front")


@dataclass
class _Reading:
    """How far the check got: the step being read, and the idle counter at condition 5."""

    step: str = "the worker's declaration"
    idle_s: int | None = None
    since: float = 0.0


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
    reading.step = "the lock"
    if app.locked():
        raise _Refused("locked", "the screen is locked, and is never unlocked")
    reading.step = "the console session"
    if not app.session_available():
        raise _Refused("session_unavailable", "the console session isn't available")
    reading.step = "the idle counter, again"
    second = app.idle_seconds()
    reading.idle_s = int(second)
    if second < threshold or second < first:
        raise _Refused(
            "input_before_activation",
            f"the Mac was used between two reads ({int(first)}s, then {int(second)}s)",
        )


def _activate(app: StudioApp, reading: _Reading, monotonic: Callable[[], float]) -> None:
    """The one activation, and the two reads after it. Raises the refusal when it didn't take."""
    reading.step = "Studio's process"
    if not app.pids():
        raise _Refused(
            "activation_failed", "no Studio is running, and the activation never starts one"
        )
    reading.step = "the activation"
    try:
        app.activate()
    except Exception as e:  # noqa: BLE001 - every way it failed is the refusal, named
        raise _Refused("activation_failed", f"the activation failed: {type(e).__name__}") from e
    reading.step = "the front"
    now_was = front_was(app)
    if now_was == "unread":
        raise OSError("which app is in front couldn't be read after the activation")
    if now_was != "studio":
        raise _Refused("activation_failed", "Studio isn't in front after the activation")
    reading.step = "the idle counter, after"
    third = app.idle_seconds()
    # Measured after the read: an untouched counter is then at least the time since condition
    # 5's read, and any input in that span leaves it lower.
    if third < monotonic() - reading.since:
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
