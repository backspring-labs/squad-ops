"""
Runtime state dataclasses for SIP-0089 Phase 1.

`AgentRuntimeState` mirrors SIP-0089 §10.1. Frozen dataclass; mutate via
`dataclasses.replace()`. `Literal` types in code; matching `CHECK` constraints
at the DB level (D3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

RuntimeMode = Literal["duty", "cycle", "ambient"]
RuntimeStatus = Literal["online", "degraded", "recovering", "offline"]
Interruptibility = Literal["none", "low", "medium", "high"]


@dataclass(frozen=True)
class AgentRuntimeState:
    """Observable runtime state for a single agent.

    `mode`, `focus`, `current_runtime_activity_id`, and `current_assignment_ref`
    are coordinator-owned (D16). Heartbeat may initialize a missing row and
    update `last_heartbeat_at` + `runtime_status`, but must not overwrite
    coordinator-owned fields (D17).
    """

    agent_id: str
    mode: RuntimeMode
    runtime_status: RuntimeStatus
    focus: str
    current_runtime_activity_id: str | None
    interruptibility: Interruptibility
    last_heartbeat_at: datetime
    current_assignment_ref: str | None
