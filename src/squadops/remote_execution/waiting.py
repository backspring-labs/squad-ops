"""Waiting for a queued operation's result: one loop for every requester (SIP-0117 R5.6).

Two requesters queue an operation and then wait for it: an agent's handler, which reaches the
registry through the runtime API (``adapters.remote_execution.runtime_api_remote_execution``),
and the runtime's own Campaign acceptance, which holds the registry (#3053,
``adapters.remote_execution.registry_remote_execution``). How each reads and cancels the
operation is its own. What the wait means is this module's, so the two can't drift:

- the operation is read every ``POLL_SECONDS`` until it has a result or the wait ends;
- when the wait ends it is asked to stop, and read for up to one lease's length, since a claimed
  operation's worker sees the cancel at its next heartbeat and a silent one loses its lease;
- a result that arrives settled ``completed`` as the cancel was sent stands; any other is the
  result, with the stop named in its reason;
- still unsettled after that: ``interrupted``, naming its state. Whether it ran is unknown.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace

from squadops.remote_execution.models import (
    OperationStatus,
    RemoteOperationRequest,
    RemoteOperationResult,
)
from squadops.remote_execution.workers import OperationState, RuntimeUnreachable

#: How often a waiting requester reads its operation. The requester's own number: the lease's
#: length is the registry's.
POLL_SECONDS = 2.0


@dataclass(frozen=True)
class OperationReading:
    """One reading of the operation a requester waits on."""

    state: OperationState
    result: RemoteOperationResult | None
    lease_seconds: float


def ended(
    request: RemoteOperationRequest, status: OperationStatus, reason: str
) -> RemoteOperationResult:
    """A result the requester writes itself, for an operation that didn't run or whose end is
    unknown: never a pass."""
    return RemoteOperationResult(status=status, reason=reason, dispatch_id=request.dispatch_id)


async def await_result(
    request: RemoteOperationRequest,
    operation_id: str,
    reading: OperationReading,
    *,
    deadline: float,
    waited_for: float,
    read: Callable[[OperationReading], Awaitable[OperationReading]],
    cancel: Callable[[], Awaitable[OperationReading]],
    clock: Callable[[], float],
    sleep: Callable[[float], Awaitable[None]],
) -> RemoteOperationResult:
    """The operation's result, waiting until ``deadline`` (on ``clock``) and then stopping it.

    ``read`` is given the last reading, so a requester whose read went unanswered can keep it;
    ``cancel`` asks for the stop and returns the reading after it. ``waited_for`` is the wait in
    seconds, for the words. Anything else either raises is the caller's to handle."""
    while reading.result is None and clock() < deadline:
        await sleep(POLL_SECONDS)
        reading = await read(reading)
    if reading.result is not None:
        return reading.result
    waited = f"no result within {waited_for:g} s of asking"
    try:
        reading = await cancel()
    except RuntimeUnreachable as e:
        return ended(
            request,
            OperationStatus.INTERRUPTED,
            # The exception's own words name what couldn't be reached.
            f"{waited}, and operation {operation_id} couldn't be asked to stop: whether it ran "
            f"is unknown ({e})",
        )
    grace = reading.lease_seconds
    grace_ends = clock() + grace
    while reading.result is None and clock() < grace_ends:
        await sleep(POLL_SECONDS)
        reading = await read(reading)
    if reading.result is None:
        return ended(
            request,
            OperationStatus.INTERRUPTED,
            f"{waited}; operation {operation_id} was asked to stop and is still "
            f"{reading.state.value} {grace:g} s later",
        )
    if reading.result.status is OperationStatus.COMPLETED:
        # It finished as the cancel was sent. Its result stands.
        return reading.result
    return replace(
        reading.result,
        reason=f"{reading.result.reason} (its requester asked it to stop: {waited})",
    )
