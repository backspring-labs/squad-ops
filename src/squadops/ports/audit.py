"""
AuditPort — abstract interface for structured security audit events (SIP-0062).

Flat port (not nested under auth — audit could expand beyond auth later).
"""

from abc import ABC, abstractmethod

from squadops.auth.models import AuditEvent


class AuditPort(ABC):
    """Port for recording structured audit events."""

    @abstractmethod
    def record(self, event: AuditEvent) -> None:
        """Record audit event. MUST NOT raise — swallow errors internally."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""
