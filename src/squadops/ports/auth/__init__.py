"""
Auth port interfaces (SIP-0062).

AuthPort for token validation/identity resolution.
AuthorizationPort for role/scope enforcement.
"""

from squadops.ports.auth.authentication import AuthPort
from squadops.ports.auth.authorization import AuthorizationPort

__all__ = [
    "AuthPort",
    "AuthorizationPort",
]
