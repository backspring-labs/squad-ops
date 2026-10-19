"""
Cycle request profile API routes (SIP-0074 §5.9).

Read-only endpoints exposing cycle request profiles over HTTP.
These are code/config-file-backed value objects that only change on redeploy.
A profile's name is resolved into the cycle-create body here too (#2520), by the one builder the
CLI and a campaign's launches use, so the console holds no copy of it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import ValidationError

from squadops.api.cycle_schemas import (
    CycleCreateRequest,
    CycleRequestProfileResponse,
    CycleRequestResolveRequest,
    PromptMetaResponse,
)
from squadops.api.errors import http_error
from squadops.api.middleware.auth import require_scopes
from squadops.auth.models import Scope
from squadops.stacks.request_defaults import STACK_REQUEST_DEFAULTS

router = APIRouter(
    prefix="/api/v1/cycle-request-profiles",
    tags=["cycle-request-profiles"],
)

_CACHE_HEADERS = {"Cache-Control": "public, max-age=300"}


def _profile_to_response(profile) -> CycleRequestProfileResponse:
    """Convert a CycleRequestProfile to its response, with the stacks it can run on."""
    # deferred (pair): api and contracts would import each other at load
    from squadops.contracts.cycle_request_profiles import OPERATOR_PROFILES

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
        stacks=sorted(STACK_REQUEST_DEFAULTS) if profile.name in OPERATOR_PROFILES else [],
    )


@router.get("", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def list_cycle_request_profiles(response: Response) -> list[CycleRequestProfileResponse]:
    """The operator's request profiles, with prompts metadata (#316, R2.4). The campaign's and
    every frozen old name still resolve by name, through the route below, but aren't listed."""
    # deferred (pair): api and contracts would import each other at load
    from squadops.contracts.cycle_request_profiles import OPERATOR_PROFILES, load_profile

    names = list(OPERATOR_PROFILES)
    response.headers.update(_CACHE_HEADERS)
    return [_profile_to_response(load_profile(name)) for name in names]


@router.get("/{profile_name}", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def get_cycle_request_profile(
    profile_name: str, response: Response
) -> CycleRequestProfileResponse:
    """Return a single cycle request profile by name."""
    # deferred (pair): api and contracts would import each other at load
    from squadops.contracts.cycle_request_profiles import load_profile

    try:
        profile = load_profile(profile_name)
    except FileNotFoundError as e:
        raise http_error(404, "PROFILE_NOT_FOUND", str(e)) from e
    response.headers.update(_CACHE_HEADERS)
    return _profile_to_response(profile)


@router.post("/{profile_name}/resolve", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def resolve_cycle_request(
    profile_name: str, body: CycleRequestResolveRequest
) -> CycleCreateRequest:
    """The cycle-create body this profile makes with the caller's values: exactly what ``squadops
    cycles create`` sends and a campaign's launch builds, an operator profile's stack defaults
    included (#316, R2.3). The console previews it and creates the cycle from it (#2520). Nothing
    is created here."""
    # deferred (pair): api and contracts would import each other at load
    from squadops.contracts.cycle_request_profiles import cycle_request_body

    try:
        request = cycle_request_body(
            profile_name,
            squad_profile_id=body.squad_profile_id,
            user_values=body.values,
            notes=body.notes,
            prd_ref=body.prd_ref,
        )
    except FileNotFoundError as e:
        raise http_error(404, "PROFILE_NOT_FOUND", str(e)) from e
    try:
        return CycleCreateRequest.model_validate(request)
    except ValidationError as e:
        # The create route would refuse the same body, so the caller learns it before creating.
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
