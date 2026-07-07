"""Agent configuration resolution from squad profiles.

Single source for role → agent resolution (SIP-0097 §6.5 slice 1). Hoisted
from ``DispatchedFlowExecutor._resolve_agent_config`` / ``_build_agent_resolver``
and consolidated with the ``task_plan._resolve_agent_config`` mirror the
executor's docstring flagged (issues #110/#151): correction, repair, and
plan-generation envelopes all propagate the cycle's profile-specified model
and config overrides through this one path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from squadops.cycles.models import SquadProfile


@dataclass(frozen=True)
class ResolvedAgentConfig:
    """A role resolved against a squad profile (SIP-0097: named fields, not a tuple)."""

    agent_id: str
    model: str | None = None
    config_overrides: dict[str, Any] = field(default_factory=dict)


def resolve_agent_config(role: str, profile: SquadProfile | None) -> ResolvedAgentConfig:
    """Resolve a role to its agent id, model, and config overrides from the squad profile.

    Without the propagated model, ``inputs["agent_model"]`` is absent and the
    handler falls back to the agent container's instance default — silently
    diverging from the cycle's squad profile (issue #110).
    Falls back to ``ResolvedAgentConfig(role)`` when no enabled match exists,
    so a misconfigured profile can't crash the correction loop.
    """
    if profile:
        for agent in profile.agents:
            if agent.role == role and agent.enabled:
                model = agent.model if agent.model else None
                overrides = dict(agent.config_overrides or {})
                return ResolvedAgentConfig(agent.agent_id, model, overrides)
    return ResolvedAgentConfig(role, None, {})


def build_agent_resolver(profile: SquadProfile | None) -> dict[str, str]:
    """Build a role → agent_id mapping from the squad profile."""
    if not profile:
        return {}
    return {agent.role: agent.agent_id for agent in profile.agents if agent.enabled}
