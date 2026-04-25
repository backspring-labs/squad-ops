"""Correlation-context contextvar + helpers.

The authoritative source of per-request ``CorrelationContext`` during an
asyncio run. ``PrefectLogHandler`` (SIP-0087) reads from this contextvar to
scope log records to the active Prefect flow / task run.

Contextvars copy at ``asyncio.create_task`` boundaries, so children inherit a
snapshot of the parent's context without explicit plumbing.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace

from squadops.telemetry.models import CorrelationContext

_correlation_context: ContextVar[CorrelationContext | None] = ContextVar(
    "squadops_correlation_context", default=None
)


def get_correlation_context() -> CorrelationContext | None:
    """Return the currently-active ``CorrelationContext`` (``None`` if unset)."""
    return _correlation_context.get()


@contextmanager
def use_correlation_context(ctx: CorrelationContext) -> Iterator[CorrelationContext]:
    """Scope a full ``CorrelationContext`` to a block.

    Use at the outermost boundary where the cycle/pulse/task IDs are first
    known (flow dispatch, agent message handler). Inner scopes should prefer
    ``use_run_ids`` for targeted overrides rather than replacing the whole
    context.
    """
    token = _correlation_context.set(ctx)
    try:
        yield ctx
    finally:
        _correlation_context.reset(token)


@contextmanager
def use_run_ids(
    *,
    flow_run_id: str | None = None,
    task_run_id: str | None = None,
) -> Iterator[CorrelationContext]:
    """Overlay ``flow_run_id`` / ``task_run_id`` on the active context.

    Requires an active ``CorrelationContext`` — raises ``RuntimeError`` if
    none is set. Synthesizing an empty context here would leak a
    ``cycle_id=""`` sentinel to every other consumer of
    ``get_correlation_context()`` (LangFuse, audit, etc.) and silently
    produce broken traces. Callers that dispatch Prefect tasks always have
    a cycle_id in hand, so they should enter ``use_correlation_context``
    first and then overlay run IDs.

    Passing ``None`` for a field leaves the current value unchanged.
    """
    current = _correlation_context.get()
    if current is None:
        raise RuntimeError(
            "use_run_ids requires an active CorrelationContext; "
            "enter use_correlation_context(...) first."
        )
    merged = replace(
        current,
        flow_run_id=(flow_run_id if flow_run_id is not None else current.flow_run_id),
        task_run_id=(task_run_id if task_run_id is not None else current.task_run_id),
    )
    token = _correlation_context.set(merged)
    try:
        yield merged
    finally:
        _correlation_context.reset(token)


__all__ = [
    "get_correlation_context",
    "use_correlation_context",
    "use_run_ids",
]
