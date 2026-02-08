"""
LoggingAuditAdapter — emits audit events as structured JSON log entries (SIP-0062).

Events go to the 'squadops.audit' logger at INFO level.
Serializes timestamp via .isoformat() to preserve timezone info.
"""

from __future__ import annotations

import json
import logging

from squadops.auth.models import AuditEvent
from squadops.ports.audit import AuditPort

logger = logging.getLogger("squadops.audit")


class LoggingAuditAdapter(AuditPort):
    """Emit audit events as structured JSON to the squadops.audit logger."""

    def record(self, event: AuditEvent) -> None:
        """Record audit event as JSON log entry. Never raises."""
        try:
            entry = {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "action": event.action,
                "actor_id": event.actor_id,
                "actor_type": event.actor_type,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "result": event.result,
                "denial_reason": event.denial_reason,
                "metadata": dict(event.metadata) if event.metadata else {},
                "request_id": event.request_id,
                "ip_address": event.ip_address,
            }
            logger.info(json.dumps(entry))
        except Exception:
            # MUST NOT raise — swallow errors internally
            pass

    def close(self) -> None:
        """No-op for logging adapter."""
