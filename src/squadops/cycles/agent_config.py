"""Agent configuration resolution from squad profiles.

Single source for role → agent resolution (SIP-0097 §6.5 slice 1). Hoisted
from ``DispatchedFlowExecutor._resolve_agent_config`` / ``_build_agent_resolver``
and consolidated with the ``task_plan._resolve_agent_config`` mirror the
executor's docstring flagged (issues #110/#151): correction, repair, and
plan-generation envelopes all propagate the cycle's profile-specified model
and config overrides through this one path.

**The map is declared, never inferred (SIP-0108 §10i item 1).** Until 1.8.1 an
unmatched role resolved to ``ResolvedAgentConfig(role, None, {})`` — an agent id
equal to the role name, which is a queue no agent consumes. Nothing failed at
resolution; the envelope was published to a queue with no consumer and the run
waited out its budget. That is a default at a seam, and the owner's ruling of
2026-09-14 is require, don't default: a role no enabled agent serves is a
configuration error, raised here where the profile is read, not a silent queue at
dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from squadops.cycles.models import AgentProfileEntry, SquadProfile


class UnservedRoleError(ValueError):
    """A role the plan names that no enabled agent in the squad profile serves.

    Raised at resolution rather than returning a role-named agent id: the former is a
    configuration error a person can read and fix, the latter is a message published to
    a queue nobody consumes.
    """


@dataclass(frozen=True)
class ResolvedAgentConfig:
    """A role resolved against a squad profile (SIP-0097: named fields, not a tuple)."""

    agent_id: str
    model: str | None = None
    config_overrides: dict[str, Any] = field(default_factory=dict)


def roles_served(agent: AgentProfileEntry) -> tuple[str, ...]:
    """The step roles *agent* serves: its declaration, or its own role.

    One place decides what "this agent serves that role" means, so the resolver, the
    dispatch map and the builder-presence reader cannot drift apart.
    """
    # Convert first, then test: a declaration that is present but empty means the same as
    # no declaration, and a test double whose attribute iterates empty must not read as
    # "serves nothing".
    declared = tuple(agent.serves_roles)
    return declared or (agent.role,)


def serves_role(profile: SquadProfile | None, role: str) -> bool:
    """Whether *profile* has an enabled agent serving *role*."""
    if not profile:
        return False
    return any(role in roles_served(a) for a in profile.agents if a.enabled)


def served_roles(profile: SquadProfile | None) -> frozenset[str]:
    """Every step role *profile*'s enabled agents serve.

    The one reader of "which roles does this profile carry": create-time preflight, plan
    building and implementation-plan validation all ask it, and a profile that assigns
    several roles to one agent has to read the same in all three.
    """
    if not profile:
        return frozenset()
    return frozenset(r for a in profile.agents if a.enabled for r in roles_served(a))


def resolve_agent_config(role: str, profile: SquadProfile | None) -> ResolvedAgentConfig:
    """Resolve a role to its agent id, model, and config overrides from the squad profile.

    Without the propagated model, ``inputs["agent_model"]`` is absent and the
    handler falls back to the agent container's instance default — silently
    diverging from the cycle's squad profile (issue #110).

    Raises:
        UnservedRoleError: when no profile is bound, or no enabled agent in it serves
            *role*. Both were the same silent fallback before 1.8.1 (SIP-0108 §10i).
    """
    if not profile:
        raise UnservedRoleError(
            f"no squad profile is bound, so role {role!r} cannot be resolved to an agent; "
            "a cycle names its squad profile at creation"
        )
    for agent in profile.agents:
        if agent.enabled and role in roles_served(agent):
            model = agent.model if agent.model else None
            overrides = dict(agent.config_overrides or {})
            return ResolvedAgentConfig(agent.agent_id, model, overrides)
    served = sorted(served_roles(profile))
    raise UnservedRoleError(
        f"squad profile {profile.profile_id!r} has no enabled agent serving role {role!r}; "
        f"it serves {served or ['(nothing — every agent is disabled)']}. Declare the role on "
        "an agent's `serves_roles`, or run this cycle on a profile that carries it."
    )


def build_agent_resolver(profile: SquadProfile | None) -> dict[str, str]:
    """Build a role → agent_id mapping from the squad profile.

    Every role each enabled agent serves, so a one-agent profile resolves the whole plan.
    """
    if not profile:
        return {}
    return {
        role: agent.agent_id
        for agent in profile.agents
        if agent.enabled
        for role in roles_served(agent)
    }
