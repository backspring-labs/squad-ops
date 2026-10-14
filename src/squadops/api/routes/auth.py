"""
Auth routes — /auth/userinfo endpoint (SIP-0062 Phase 3a).
"""

from fastapi import APIRouter, Request

from squadops.api.errors import http_error

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/userinfo")
async def userinfo(request: Request):
    """Return the current identity from request.state (set by AuthMiddleware)."""
    identity = getattr(request.state, "identity", None)
    if not identity:
        raise http_error(401, "NOT_AUTHENTICATED", "Not authenticated")
    return {
        "user_id": identity.user_id,
        "display_name": identity.display_name,
        "roles": list(identity.roles),
        "scopes": list(identity.scopes),
        "identity_type": identity.identity_type,
    }
