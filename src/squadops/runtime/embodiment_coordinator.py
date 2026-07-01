"""
EmbodimentCoordinator — validates and applies Embodiment lifecycle transitions,
emitting reason-coded events (SIP-0090 Phase 1 §5.2 / §5.5).

Mirrors the SIP-0089 ``RuntimeCoordinator``: a pure orchestrator over an injected
:class:`EmbodimentStatePort` (+ optional :class:`RuntimeEventPublisher`). It validates
each transition against the §4.1 allow-list, enforces the single-active-embodiment
rule (§5.5), persists the result, and emits the matching ``embodiment.*`` event. It
decides nothing about intent or action — that authority stays outside the substrate
(§6 authority boundary).

Adapter-free (D26): imports only runtime models, ports, events/reasons, and typing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from squadops.ports.runtime.embodiment import EmbodimentStatePort
from squadops.ports.runtime.event_publisher import RuntimeEventPublisher
from squadops.runtime import events, reasons
from squadops.runtime.embodiment import (
    AttachmentState,
    Embodiment,
    is_active_attachment,
    is_allowed_attachment_transition,
)

# Which `embodiment.*` event each attachment *target* state emits (§5.2). `unattached`
# is only an initial state, never a transition target, so it carries no event.
_STATE_EVENT: dict[AttachmentState, str] = {
    "attaching": events.EMBODIMENT_ATTACHING,
    "attached": events.EMBODIMENT_ATTACHED,
    "desynced": events.EMBODIMENT_DESYNCED,
    "reconnecting": events.EMBODIMENT_RECONNECTING,
    "detached": events.EMBODIMENT_DETACHED,
}


@dataclass(frozen=True)
class EmbodimentTransitionOutcome:
    """Result of a :meth:`EmbodimentCoordinator.request_transition` call.

    Exactly one of two shapes: applied (``applied=True``, ``event_name`` set) or
    rejected (``applied=False``, ``rejected_reason`` set). ``reason_code`` echoes the
    requested reason in both cases.
    """

    applied: bool
    embodiment_id: str
    agent_id: str
    from_state: AttachmentState
    to_state: AttachmentState
    reason_code: str
    event_name: str | None = None
    rejected_reason: str | None = None


class EmbodimentCoordinator:
    """Validates and applies Embodiment attachment transitions; emits reason-coded events."""

    def __init__(
        self,
        state: EmbodimentStatePort,
        *,
        events_publisher: RuntimeEventPublisher | None = None,
    ) -> None:
        self._state = state
        self._events = events_publisher

    async def request_transition(
        self,
        embodiment: Embodiment,
        target_state: AttachmentState,
        reason_code: str,
        *,
        conn: Any = None,
    ) -> EmbodimentTransitionOutcome:
        """Validate and apply ``embodiment.attachment_state → target_state``.

        Rejections write nothing and emit nothing: a missing reason code
        (``missing_reason_code``), an illegal transition
        (``invalid_attachment_transition``), or a single-active violation
        (``embodiment_already_active`` — a second live embodiment for the agent,
        §5.5). On success the transition is persisted and the matching
        ``embodiment.*`` event is emitted best-effort.
        """
        from_state = embodiment.attachment_state

        def _reject(rejected_reason: str) -> EmbodimentTransitionOutcome:
            return EmbodimentTransitionOutcome(
                applied=False,
                embodiment_id=embodiment.embodiment_id,
                agent_id=embodiment.agent_id,
                from_state=from_state,
                to_state=target_state,
                reason_code=reason_code,
                rejected_reason=rejected_reason,
            )

        # (1) a reason code is mandatory (mirrors SIP-0089 §11.2).
        if not reason_code:
            return _reject(reasons.MISSING_REASON_CODE)

        # (2 §5.2) the transition must be on the allow-list.
        if not is_allowed_attachment_transition(from_state, target_state):
            return _reject(reasons.INVALID_ATTACHMENT_TRANSITION)

        # (3 §5.5) single-active: entering a live state must not create a second
        # active embodiment for the agent. Only attaching→attached crosses
        # non-active → active, so that is the one moment this guard fires.
        if is_active_attachment(target_state) and not is_active_attachment(from_state):
            active = await self._state.get_active_embodiment(embodiment.agent_id)
            if active is not None and active.embodiment_id != embodiment.embodiment_id:
                return _reject(reasons.EMBODIMENT_ALREADY_ACTIVE)

        # (4) persist, then emit the target-state event (best-effort — never fatal).
        await self._state.transition_state(embodiment.embodiment_id, target_state, conn=conn)
        event_name = _STATE_EVENT[target_state]
        if self._events is not None:
            self._events.emit(
                event_name,
                agent_id=embodiment.agent_id,
                reason_code=reason_code,
                payload={"embodiment_id": embodiment.embodiment_id},
            )
        return EmbodimentTransitionOutcome(
            applied=True,
            embodiment_id=embodiment.embodiment_id,
            agent_id=embodiment.agent_id,
            from_state=from_state,
            to_state=target_state,
            reason_code=reason_code,
            event_name=event_name,
        )
