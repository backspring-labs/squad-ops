"""A memory change to a running campaign, as a row in its control log (SIP-0110 Appendix A §3.5,
§3.7; #2178, #2179).

A task instruction changed on a campaign's cycle after admission, and a re-binding of a campaign's
snapshot, are interventions. Each is a record-only control-log row, which the intervention ledger
reads (SIP-0113 §4.3), so a measurement window reports it. The memory change is already stored
when the row is written: a row that can't be written is said, never implied.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request

from squadops.api.routes.campaigns.campaigns import actor_from
from squadops.api.runtime.deps import get_campaign_registry
from squadops.auth.models import Identity
from squadops.campaigns.models import CampaignTransition, ControlOperation

logger = logging.getLogger(__name__)


async def record_on_control_log(
    request: Request,
    identity: Identity | None,
    campaign_id: str,
    *,
    operation: ControlOperation,
    reason: str,
    idempotency_key: str,
    target: str,
    binding: dict[str, Any],
) -> str | None:
    """The row's id, or ``None`` when it couldn't be written (logged at WARNING)."""
    actor, role = actor_from(identity)
    transition = CampaignTransition(
        operation=operation,
        actor=actor,
        actor_role=role,
        reason=reason,
        idempotency_key=idempotency_key,
        next_state=None,
        target=target,
        binding=binding,
    )
    try:
        result = await get_campaign_registry(request).transition(campaign_id, transition)
    except Exception:  # noqa: BLE001 — a missing row is said, never implied
        logger.warning(
            "memory_intervention_not_logged campaign=%s op=%s", campaign_id, operation,
            exc_info=True,
        )  # fmt: skip
        return None
    return result.entry.entry_id
