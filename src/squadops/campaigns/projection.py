"""Every control-log row, projected (SIP-0109 §13; step 6).

The control log is the authority; the security audit and the event bus are projections of it.
One builder for each, read by both writers:
- **the campaign routes**, which project the rows their callers write with the caller's identity
  type and request id;
- **every other writer** — the workload gate's submission, the completion boundary's promotion
  and decision, the launcher's mark — through :class:`ProjectingCampaignRegistry`, which wraps
  the registry those writers are given.

Both projections are fail-open: a failed projection is logged and loses no control record, and
the API's reads of the control log are authoritative after a missed event.
"""

from __future__ import annotations

import logging
from typing import Any

from squadops.auth.models import AuditEvent
from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperationRefused,
    ControlOutcome,
    LaunchIntent,
    TransitionResult,
)
from squadops.events.types import EventType
from squadops.ports.cycles.campaign_registry import CampaignRegistryPort

logger = logging.getLogger(__name__)


def audit_event(
    entry: ControlLogEntry, *, actor_type: str, request_id: str | None = None
) -> AuditEvent:
    """The security audit's view of one row (§13): ``AuditEvent``'s missing fields (role,
    reason, idempotency key) travel in its metadata."""
    return AuditEvent(
        action=f"campaign.{entry.operation}",
        actor_id=entry.actor,
        actor_type=actor_type,
        resource_type="campaign",
        resource_id=entry.campaign_id,
        result="success" if entry.outcome is ControlOutcome.APPLIED else "denied",
        denial_reason=str(entry.refusal) if entry.refusal else None,
        metadata=(
            ("actor_role", entry.actor_role),
            ("reason", entry.reason),
            ("idempotency_key", entry.idempotency_key),
            ("entry_id", entry.entry_id),
            ("prior_state", str(entry.prior_state)),
            ("next_state", str(entry.next_state)),
        ),
        request_id=request_id,
    )


def emit_transitioned(events: Any, result: TransitionResult) -> None:
    """The event bus's view of one applied row (SIP-0077): ``campaign.transitioned``."""
    entry = result.entry
    events.emit(
        EventType.CAMPAIGN_TRANSITIONED,
        entity_type="campaign",
        entity_id=entry.campaign_id,
        context={"campaign_id": entry.campaign_id, "project_id": result.campaign.project_id},
        payload={
            "entry_id": entry.entry_id,
            "operation": str(entry.operation),
            "prior_state": str(entry.prior_state) if entry.prior_state else None,
            "next_state": str(entry.next_state),
            "actor_role": entry.actor_role,
        },
    )


def project(
    audit: Any,
    events: Any,
    *,
    entry: ControlLogEntry,
    result: TransitionResult | None,
    actor_type: str,
    request_id: str | None = None,
) -> None:
    """Project one row: to the audit always, to the bus when it applied. Fail-open."""
    if audit is not None:
        try:
            audit.record(audit_event(entry, actor_type=actor_type, request_id=request_id))
        except Exception:  # noqa: BLE001 — fail-open, as the port's contract says
            logger.warning("campaign audit projection failed: %s", entry.entry_id, exc_info=True)
    if result is not None and events is not None:
        try:
            emit_transitioned(events, result)
        except Exception:  # noqa: BLE001 — a projection never fails the operation it projects
            logger.warning("campaign event projection failed: %s", entry.entry_id, exc_info=True)


#: The actor type of rows the framework writes for itself.
SYSTEM_ACTOR_TYPE = "service"


class ProjectingCampaignRegistry(CampaignRegistryPort):
    """The registry, projecting every row it writes for a non-route writer (§13)."""

    def __init__(self, inner: CampaignRegistryPort, *, audit: Any, events: Any) -> None:
        self._inner = inner
        self._audit = audit
        self._events = events

    async def _projected(self, write) -> TransitionResult:
        try:
            result = await write
        except ControlOperationRefused as refused:
            project(
                self._audit, None, entry=refused.entry, result=None, actor_type=SYSTEM_ACTOR_TYPE
            )
            raise
        if not result.replayed:
            project(
                self._audit,
                self._events,
                entry=result.entry,
                result=result,
                actor_type=SYSTEM_ACTOR_TYPE,
            )
        return result

    async def transition(
        self, campaign_id: str, transition: CampaignTransition
    ) -> TransitionResult:
        return await self._projected(self._inner.transition(campaign_id, transition))

    async def mark_launch_intent_launched(
        self, launch_id: str, cycle_id: str, *, actor: str
    ) -> TransitionResult:
        return await self._projected(
            self._inner.mark_launch_intent_launched(launch_id, cycle_id, actor=actor)
        )

    async def change_box_lease(
        self, campaign_id: str, transition: CampaignTransition, *, runs_in_flight: tuple[str, ...]
    ) -> TransitionResult:
        return await self._projected(
            self._inner.change_box_lease(campaign_id, transition, runs_in_flight=runs_in_flight)
        )

    async def box_lease(self):
        return await self._inner.box_lease()

    async def create_campaign(self, campaign: Campaign, **kwargs) -> TransitionResult:
        return await self._projected(self._inner.create_campaign(campaign, **kwargs))

    async def get_campaign(self, campaign_id: str) -> Campaign:
        return await self._inner.get_campaign(campaign_id)

    async def list_campaigns(self, project_id: str) -> list[Campaign]:
        return await self._inner.list_campaigns(project_id)

    async def campaigns_in_state(self, state: CampaignState) -> list[Campaign]:
        return await self._inner.campaigns_in_state(state)

    async def control_log(self, campaign_id: str) -> list[ControlLogEntry]:
        return await self._inner.control_log(campaign_id)

    async def pending_launch_intents(self) -> list[LaunchIntent]:
        return await self._inner.pending_launch_intents()

    async def launch_intents(self, campaign_id: str) -> list[LaunchIntent]:
        return await self._inner.launch_intents(campaign_id)

    async def get_launch_intent(self, launch_id: str) -> LaunchIntent:
        return await self._inner.get_launch_intent(launch_id)
