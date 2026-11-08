"""The task an LLM call serves, scoped around the task for any provider that keys by it (#2495).

A provider sees only the call: its messages and its model. The scripted provider answers by the
task the call serves (its type, its id, its cycle) and by the script the cycle named, and none of
that is in the call. The correlation context the agent already scopes around each task is
telemetry's: it carries the ids a trace needs and no task type or cycle configuration, and widening
it would put the cycle's config on every trace and log record. So the agent's task loop scopes this
beside it, from the same envelope, and only a provider that needs it reads it.

Contextvars copy at ``asyncio.create_task`` boundaries, so a call made from a child task of the
handler still sees the scope it was started under.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from squadops.llm.script import LLM_SCRIPT_KEY


@dataclass(frozen=True)
class LLMCallScope:
    """The task a call serves, and the script its cycle named, if any."""

    cycle_id: str
    task_id: str
    task_type: str
    #: The cycle's ``llm_script`` (``<name>@<version>``) as the envelope's resolved config carries
    #: it. ``None`` when the envelope carries none: every model cycle, and a step whose envelope
    #: is built without the cycle's config (a pulse-check repair).
    llm_script: str | None = None

    @classmethod
    def from_envelope(cls, envelope: Any) -> LLMCallScope:
        """The scope of a ``TaskEnvelope``."""
        inputs = getattr(envelope, "inputs", None) or {}
        resolved = inputs.get("resolved_config") if isinstance(inputs, dict) else None
        script = resolved.get(LLM_SCRIPT_KEY) if isinstance(resolved, dict) else None
        return cls(
            cycle_id=str(getattr(envelope, "cycle_id", "") or ""),
            task_id=str(getattr(envelope, "task_id", "") or ""),
            task_type=str(getattr(envelope, "task_type", "") or ""),
            llm_script=str(script) if script is not None else None,
        )


_scope: ContextVar[LLMCallScope | None] = ContextVar("squadops_llm_call_scope", default=None)


def current_llm_call_scope() -> LLMCallScope | None:
    """The scope of the task being served, or ``None`` outside any task."""
    return _scope.get()


@contextmanager
def use_llm_call_scope(scope: LLMCallScope) -> Iterator[LLMCallScope]:
    """Scope ``scope`` to a block: the agent wraps each task's handling in it."""
    token = _scope.set(scope)
    try:
        yield scope
    finally:
        _scope.reset(token)


__all__ = ["LLMCallScope", "current_llm_call_scope", "use_llm_call_scope"]
