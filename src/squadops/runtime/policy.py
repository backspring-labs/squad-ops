"""
Ambient irreversibility policy seam (SIP-0089 §4.6).

The v1.2 embodiment hook. Per §10.4/§10.5, an Ambient agent may observe, idle, or
respond lightly, but may **not** perform an irreversible external action (mutate
external systems, spend material compute) unless it holds **both** a granted
FocusLease and a started RuntimeActivity. `AmbientPolicy.assert_action_permitted`
enforces that, evaluated against the *ports* (not in-memory agent fields) so it
works unchanged once embodiment adapters arrive.

In v1.1 this gate has **no real callers** — no embodied actions exist yet. It
exists so v1.2 plugs into a working policy seam without a redesign.

Reconciliation note: §4.6's sketch reads "raises if ... no FocusLease AND no
RuntimeActivity", but the canonical invariant (§10.4) requires *both* a lease and
an activity to act. This implements the stricter, spec-faithful rule: an ambient
agent is refused an irreversible action unless it holds a lease **and** an
activity (i.e. either one missing → refused).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from squadops.runtime import reasons

if TYPE_CHECKING:
    from squadops.ports.runtime.activity import RuntimeActivityPort
    from squadops.ports.runtime.focus_lease import FocusLeasePort
    from squadops.ports.runtime.state import RuntimeStatePort


class AmbientActionForbidden(Exception):
    """An ambient agent attempted an irreversible action without the required
    FocusLease + RuntimeActivity (§4.6 / §10.4)."""

    def __init__(self, agent_id: str, action_kind: str) -> None:
        self.agent_id = agent_id
        self.action_kind = action_kind
        self.reason_code = reasons.AMBIENT_IRREVERSIBLE_ACTION_FORBIDDEN
        super().__init__(
            f"ambient agent {agent_id!r} may not perform irreversible action "
            f"{action_kind!r} without an active focus lease and runtime activity"
        )


class AmbientPolicy:
    """Gate irreversible actions for ambient agents against the runtime ports."""

    def __init__(
        self,
        state: RuntimeStatePort,
        focus_lease: FocusLeasePort,
        activity: RuntimeActivityPort,
    ) -> None:
        self._state = state
        self._focus_lease = focus_lease
        self._activity = activity

    async def assert_action_permitted(
        self,
        agent_id: str,
        action_kind: str,
        *,
        irreversible: bool,
    ) -> None:
        """Raise `AmbientActionForbidden` if the action is not permitted.

        Reversible actions are always permitted. Irreversible actions are gated
        only for ambient agents (duty/cycle agents are already doing claimed work);
        an agent with no runtime-state row is treated as ambient (most restrictive).
        `irreversible` is supplied by the caller — v1.1 does not classify every
        possible action.
        """
        if not irreversible:
            return

        state = await self._state.get_state(agent_id)
        # Only ambient is gated. A missing row (never heartbeated) → treat as
        # ambient so the seam fails closed rather than open.
        if state is not None and state.mode != "ambient":
            return

        lease = await self._focus_lease.get_current_lease(agent_id)
        activity = await self._activity.get_current_activity(agent_id)
        if lease is not None and activity is not None:
            return

        raise AmbientActionForbidden(agent_id, action_kind)
