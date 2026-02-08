"""
Factory for creating audit adapter instances (SIP-0062 Phase 3b).
"""

from squadops.ports.audit import AuditPort


def create_audit_provider(provider: str = "logging") -> AuditPort:
    """Create an AuditPort instance for the given provider.

    Args:
        provider: Provider type ('logging'). Default is 'logging'.

    Returns:
        AuditPort instance.

    Raises:
        ValueError: If provider is unknown.
    """
    if provider == "logging":
        from adapters.audit.logging_adapter import LoggingAuditAdapter

        return LoggingAuditAdapter()
    raise ValueError(f"Unknown audit provider: {provider}")
