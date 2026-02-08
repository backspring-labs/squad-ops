"""
Squad Profile API routes (SIP-0064 §9.2).
"""

from fastapi import APIRouter

from squadops.api.routes.cycles.dtos import SetActiveProfileRequest
from squadops.api.routes.cycles.errors import handle_cycle_error
from squadops.api.routes.cycles.mapping import profile_to_response
from squadops.cycles.models import CycleError

router = APIRouter(prefix="/api/v1/squad-profiles", tags=["squad-profiles"])


@router.get("")
async def list_profiles():
    from squadops.api.runtime.deps import get_squad_profile_port

    try:
        port = get_squad_profile_port()
        profiles = await port.list_profiles()
        return [profile_to_response(p) for p in profiles]
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/active")
async def get_active_profile():
    from squadops.api.runtime.deps import get_squad_profile_port

    try:
        port = get_squad_profile_port()
        profile = await port.get_active_profile()
        return profile_to_response(profile)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.post("/active")
async def set_active_profile(body: SetActiveProfileRequest):
    from squadops.api.runtime.deps import get_squad_profile_port

    try:
        port = get_squad_profile_port()
        await port.set_active_profile(body.profile_id)
        return {"status": "ok", "active_profile_id": body.profile_id}
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/{profile_id}")
async def get_profile(profile_id: str):
    from squadops.api.runtime.deps import get_squad_profile_port

    try:
        port = get_squad_profile_port()
        profile = await port.get_profile(profile_id)
        return profile_to_response(profile)
    except CycleError as e:
        raise handle_cycle_error(e) from e
