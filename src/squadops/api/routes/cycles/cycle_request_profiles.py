"""
Cycle request profile API routes (SIP-0074 §5.9).

Read-only endpoints exposing cycle request profiles over HTTP.
These are code/config-file-backed value objects that only change on redeploy.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from squadops.api.routes.cycles.dtos import (
    CycleRequestProfileResponse,
    PromptMetaResponse,
)

router = APIRouter(
    prefix="/api/v1/cycle-request-profiles",
    tags=["cycle-request-profiles"],
)

_CACHE_HEADERS = {"Cache-Control": "public, max-age=300"}


def _profile_to_response(profile) -> dict:
    """Convert a CycleRequestProfile to a response dict."""
    prompts = {}
    for key, meta in profile.prompts.items():
        prompts[key] = PromptMetaResponse(
            label=meta.label,
            help_text=meta.help_text,
            choices=meta.choices,
            type=meta.type,
            required=meta.required,
        ).model_dump()
    return CycleRequestProfileResponse(
        name=profile.name,
        description=profile.description,
        defaults=profile.defaults,
        prompts=prompts,
    ).model_dump()


@router.get("")
async def list_cycle_request_profiles():
    """Return all registered cycle request profiles with prompts metadata."""
    from squadops.contracts.cycle_request_profiles import list_profiles, load_profile

    names = list_profiles()
    profiles = [_profile_to_response(load_profile(name)) for name in names]
    return JSONResponse(content=profiles, headers=_CACHE_HEADERS)


@router.get("/{profile_name}")
async def get_cycle_request_profile(profile_name: str):
    """Return a single cycle request profile by name."""
    from squadops.contracts.cycle_request_profiles import load_profile

    try:
        profile = load_profile(profile_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return JSONResponse(
        content=_profile_to_response(profile), headers=_CACHE_HEADERS
    )
