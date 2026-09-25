"""A run's cancel reaches the agents already holding its tasks (#1648, 1.8.2 plan §3.2 item 10).

Cancelling a run marks it ``cancelled``, stops its Prefect flow run (#77), releases its focus
leases (#529) and ends its activity rows (#561). None of that reaches a task already dispatched:
the agent that consumed it ran it to completion on the GPU, and the next cycle's first task
waited behind it while every gate read the box as quiet (#1648, deploy B′ 2026-09-23).

So the cancel route sends a notice to each agent holding the run's work, on the agent's
**control** queue. It can't use the comms queue: the agent consumes that one delivery at a time,
so a notice there would wait behind the very task it was sent to stop. The agent drops a queued
task of a cancelled run before it starts, and cancels one it is running.

One home for the queue's name and the notice's shape, because the runtime API writes it and
every agent reads it.
"""

from __future__ import annotations

from typing import Any

#: The notice's action, beside ``comms.task`` and ``comms.task.result``.
RUN_CANCELLED_ACTION = "comms.run_cancelled"
#: The agent's control queue, beside ``<agent>_comms`` (tasks) and ``<agent>_replies``.
CONTROL_QUEUE_SUFFIX = "_control"
#: The envelope metadata key the dispatcher stamps with the task's run, so an agent can tell
#: which run a task it holds belongs to.
RUN_ID_METADATA_KEY = "run_id"


def control_queue(agent_id: str) -> str:
    return f"{agent_id}{CONTROL_QUEUE_SUFFIX}"


def run_cancelled_notice(cycle_id: str, run_ids: list[str]) -> dict[str, Any]:
    return {
        "action": RUN_CANCELLED_ACTION,
        "payload": {"cycle_id": cycle_id, "run_ids": sorted(set(run_ids))},
    }


def cancelled_run_ids(message: dict[str, Any]) -> frozenset[str]:
    """The run ids a control message cancels; empty for anything that is not a notice."""
    if not isinstance(message, dict) or message.get("action") != RUN_CANCELLED_ACTION:
        return frozenset()
    run_ids = (message.get("payload") or {}).get("run_ids") or []
    return frozenset(str(r) for r in run_ids if r)
