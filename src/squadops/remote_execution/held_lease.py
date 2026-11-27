"""The serving loop's own record of the lease on the operation it is running (#3193).

A runner that acts on a person's Mac (SIP-0117 R5.33: bringing Studio to the front) does so only
while the worker holds the operation's lease. That is read from the loop's record, never assumed
from "a runner only runs under a claim": a worker cut off from the runtime goes on running its
operation until the lease runs out, and no renewal of it has been accepted in that time.

``serving.Worker`` sets the record for the one run it starts, and updates it at every renewal.
A runner reads it with :func:`current`. Outside a serving loop there is none, and nothing that
needs a lease is done.
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime


@dataclass
class HeldLease:
    """The lease as the serving loop last knew it. Mutable: the loop updates the one record the
    run's task was started with, so the runner reads it as it stands."""

    expires_at: datetime
    clock: Callable[[], datetime]
    #: Whether the last thing the runtime said of the lease held it: the claim, then each
    #: renewal. A renewal that failed to reach the runtime is no acceptance.
    accepted: bool = True
    #: Why the lease isn't held, once the runtime said so.
    refused: str | None = None

    def held(self) -> bool:
        """Whether the worker holds the lease now: its last word from the runtime accepted it,
        nothing has refused it since, and its expiry is ahead of the worker's clock."""
        return self.accepted and self.refused is None and self.clock() < self.expires_at

    def why_not(self) -> str:
        """Why the lease isn't held, in a sentence. Only asked when :meth:`held` is false."""
        if self.refused is not None:
            return f"the runtime refused the lease ({self.refused})"
        if not self.accepted:
            return "its last renewal didn't reach the runtime"
        return f"it ran out at {self.expires_at.isoformat(timespec='seconds')}"


_CURRENT: ContextVar[HeldLease | None] = ContextVar("squadops_held_lease", default=None)


def current() -> HeldLease | None:
    """The record of the lease on the operation this task runs, or ``None`` outside a serving
    loop's run."""
    return _CURRENT.get()


def holding(record: HeldLease | None):
    """Set the record for the task about to be started; returns the token to reset with."""
    return _CURRENT.set(record)


def released(token) -> None:
    _CURRENT.reset(token)
