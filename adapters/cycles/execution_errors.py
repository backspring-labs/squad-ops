"""Shared internal control-flow errors for the cycle flow executors.

Hoisted from ``dispatched_flow_executor.py`` / ``in_process_flow_executor.py``
(SIP-0097 §6.5 slice 1) — the two executors previously carried duplicate
definitions. These are adapter-internal control flow, not domain errors;
the leading underscore is deliberate.
"""

from __future__ import annotations


class _ExecutionError(Exception):
    """Internal: task failure or gate rejection."""


class _CancellationError(Exception):
    """Internal: run was cancelled."""


class _PausedError(Exception):
    """Internal: run paused due to BLOCKED outcome."""


class _RecruitmentRejectedError(Exception):
    """Internal: cycle recruitment deferred (SIP-0089 §2.5/§11.4).

    A participating agent is committed to — or about to start — a hard duty
    window, so the run is paused (a *deferral*, not a failure). Re-attempt via
    ``squadops runs resume`` once the window closes.
    """

    def __init__(self, agent_id: str | None, reason: str | None) -> None:
        super().__init__(f"recruitment rejected for agent {agent_id}: {reason}")
        self.agent_id = agent_id
        self.reason = reason
