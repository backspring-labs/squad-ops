"""
Auth port globals for the health app (SIP-0062 Phase 3a).

Same pattern as runtime/deps.py but for the health-check service.
"""

from squadops.ports.auth.authentication import AuthPort
from squadops.ports.auth.authorization import AuthorizationPort

_auth_port: AuthPort | None = None
_authz_port: AuthorizationPort | None = None


def set_health_auth_ports(
    auth: AuthPort | None = None,
    authz: AuthorizationPort | None = None,
) -> None:
    """Set auth adapter instances for the health app."""
    global _auth_port, _authz_port
    _auth_port = auth
    _authz_port = authz


def get_health_auth_port() -> AuthPort | None:
    """Return the current AuthPort instance, or None if not configured."""
    return _auth_port


def get_health_authz_port() -> AuthorizationPort | None:
    """Return the current AuthorizationPort instance, or None if not configured."""
    return _authz_port
