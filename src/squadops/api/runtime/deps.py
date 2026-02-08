"""
FastAPI dependencies for Runtime API (SIP-0048, SIP-0062).

Part of SIP-0.8.8 migration from _v0_legacy/infra/runtime-api/deps.py
"""

from __future__ import annotations

from squadops.ports.auth.authentication import AuthPort
from squadops.ports.auth.authorization import AuthorizationPort
from squadops.ports.tasks.registry import TaskRegistryPort

# Global adapter instances (initialized at startup)
_adapter: TaskRegistryPort | None = None
_auth_port: AuthPort | None = None
_authz_port: AuthorizationPort | None = None
_audit_port = None  # AuditPort | None


def set_tasks_adapter(adapter: TaskRegistryPort) -> None:
    """Set the tasks adapter instance for dependency injection."""
    global _adapter
    _adapter = adapter


def set_auth_ports(
    auth: AuthPort | None = None,
    authz: AuthorizationPort | None = None,
) -> None:
    """Set auth adapter instances for dependency injection (SIP-0062)."""
    global _auth_port, _authz_port
    _auth_port = auth
    _authz_port = authz


def set_audit_port(audit) -> None:
    """Set audit port instance (SIP-0062 Phase 3b)."""
    global _audit_port
    _audit_port = audit


def get_auth_port() -> AuthPort | None:
    """Return the current AuthPort instance, or None if not configured."""
    return _auth_port


def get_authz_port() -> AuthorizationPort | None:
    """Return the current AuthorizationPort instance, or None if not configured."""
    return _authz_port


def get_audit_port():
    """Return the current AuditPort instance, or None if not configured."""
    return _audit_port


async def get_tasks_adapter_dep() -> TaskRegistryPort:
    """
    FastAPI dependency function that returns the configured tasks adapter.

    Used via FastAPI Depends() in route handlers.

    Returns:
        TaskRegistryPort instance

    Raises:
        RuntimeError: If adapter not initialized
    """
    if _adapter is None:
        raise RuntimeError("Tasks adapter not initialized. Call set_tasks_adapter() at startup.")
    return _adapter
