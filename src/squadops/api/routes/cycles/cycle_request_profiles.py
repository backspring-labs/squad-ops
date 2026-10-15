"""
Cycle request profile API routes (SIP-0074 §5.9).

Read-only endpoints exposing cycle request profiles over HTTP.
These are code/config-file-backed value objects that only change on redeploy.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from squadops.api.cycle_schemas import (
    CycleRequestProfileResponse,
    PromptMetaResponse,
)
from squadops.api.errors import http_error
from squadops.api.middleware.auth import require_scopes
from squadops.auth.models import Scope

router = APIRouter(
    prefix="/api/v1/cycle-request-profiles",
    tags=["cycle-request-profiles"],
)

_CACHE_HEADERS = {"Cache-Control": "public, max-age=300"}


def _profile_to_response(profile) -> CycleRequestProfileResponse:
    """Convert a CycleRequestProfile to its response."""
    prompts = {}
    for key, meta in profile.prompts.items():
        prompts[key] = PromptMetaResponse(
            label=meta.label,
            help_text=meta.help_text,
            choices=meta.choices,
            type=meta.type,
            required=meta.required,
        )
    return CycleRequestProfileResponse(
        name=profile.name,
        description=profile.description,
        defaults=profile.defaults,
        prompts=prompts,
    )


@router.get("", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def list_cycle_request_profiles(response: Response) -> list[CycleRequestProfileResponse]:
    """Return all registered cycle request profiles with prompts metadata."""
    from squadops.contracts.cycle_request_profiles import list_profiles, load_profile

    names = list_profiles()
    response.headers.update(_CACHE_HEADERS)
    return [_profile_to_response(load_profile(name)) for name in names]


@router.get("/{profile_name}", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def get_cycle_request_profile(
    profile_name: str, response: Response
) -> CycleRequestProfileResponse:
    """Return a single cycle request profile by name."""
    from squadops.contracts.cycle_request_profiles import load_profile

    try:
        profile = load_profile(profile_name)
    except FileNotFoundError as e:
        raise http_error(404, "PROFILE_NOT_FOUND", str(e)) from e
    response.headers.update(_CACHE_HEADERS)
    return _profile_to_response(profile)
