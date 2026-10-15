"""Response bodies for the probe lane (``/health``), the agent-status writes and the identity
lane's userinfo (#1976).

Pydantic alone, beside the other schema modules (#582). A model written over a dict the health
checker builds mirrors that dict and allows extra keys, so a field the checker gains before its
model does still reaches the console, which reads these bodies field by field. A model a route
builds itself is closed.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class _Reading(BaseModel):
    model_config = ConfigDict(extra="allow")


class InfraProbeResponse(_Reading):
    """One infrastructure component, as its probe found it."""

    component: str
    type: str
    status: str
    version: str
    purpose: str
    notes: str


class EngineLoadedResponse(BaseModel):
    engine: str
    #: The models the engine holds, or ``None`` when it couldn't be read.
    loaded: list[str] | None


class BoxLeaseResponse(BaseModel):
    holder: str
    expires_at: str | None


class BoxResponse(BaseModel):
    quiet: bool
    lease: BoxLeaseResponse | None


class HostResponse(BaseModel):
    """The machine the deploy runs on (#2204): its readings, the floors and limits they are read
    against, the verdicts, each engine's loaded models, and the box. ``engines`` and ``box`` are
    ``None`` when the box could not be read."""

    host: dict[str, float | None]
    floors: dict[str, int]
    limits: dict[str, float]
    verdicts: dict[str, dict[str, Any]]
    engines: list[EngineLoadedResponse] | None
    box: BoxResponse | None


class AgentHealthResponse(_Reading):
    """An agent's status: posture (``mode``) and health (``runtime_status``) from its runtime row,
    and its heartbeat telemetry (``docs/agent-runtime-status-model.md``)."""

    agent_id: str
    agent_name: str
    role: str
    role_label: str
    mode: str | None
    runtime_status: str | None
    lifecycle_state: str
    version: str | None
    revision: str | None
    deployed_revision: str | None
    revision_matches_deploy: bool | None
    #: An int or a float as the heartbeat sent it: a float field would turn the fallback's 0 into 0.0.
    tps: int | float | None
    memory_count: int
    last_seen: str | None
    current_task_id: str | None


class RuntimeStateResponse(_Reading):
    """An agent's SIP-0089 runtime state."""

    agent_id: str
    mode: str
    runtime_status: str
    focus: str
    current_runtime_activity_id: str | None
    interruptibility: str
    last_heartbeat_at: str | None
    current_assignment_ref: str | None


class ActivityResponse(_Reading):
    """An agent's current runtime activity (SIP-0089 §4.7)."""

    runtime_activity_id: str
    agent_id: str
    mode: str
    activity_type: str
    goal: str
    priority: int
    state: str
    source_kind: str
    source_ref: str
    cycle_id: str | None
    workload_id: str | None
    task_id: str | None
    can_pause: bool
    can_resume: bool
    can_abort: bool
    started_at: str | None
    paused_at: str | None
    ended_at: str | None


class AgentStatusUpdatedResponse(BaseModel):
    status: Literal["updated"]
    agent_id: str


class UserInfoResponse(BaseModel):
    """The caller's identity, as the auth middleware resolved it."""

    user_id: str
    display_name: str
    roles: list[str]
    scopes: list[str]
    identity_type: str
