"""
Squad Profile API routes (SIP-0064 §9.2, SIP-0075 CRUD).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime

from fastapi import APIRouter

from squadops.api.routes.cycles.dtos import (
    ProfileCloneRequest,
    ProfileCreateRequest,
    ProfileUpdateRequest,
    SetActiveProfileRequest,
)
from squadops.api.routes.cycles.errors import handle_cycle_error
from squadops.api.routes.cycles.mapping import profile_to_response
from squadops.cycles.models import (
    AgentProfileEntry,
    CycleError,
    ProfileValidationError,
    SquadProfile,
)
from squadops.cycles.profile_utils import (
    slugify_profile_name,
    validate_agent_entries,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/squad-profiles", tags=["squad-profiles"])


def _validate_agent_request(agents_data: list) -> tuple[AgentProfileEntry, ...]:
    """Validate agent entries and convert to domain objects.

    Raises ProfileValidationError on validation failure.
    validate_agent_entries already checks config_overrides keys internally.
    """
    raw = [
        {
            "agent_id": a.agent_id,
            "role": a.role,
            "model": a.model,
            "enabled": a.enabled,
            "config_overrides": a.config_overrides,
        }
        for a in agents_data
    ]
    errors = validate_agent_entries(raw)
    if errors:
        raise ProfileValidationError("; ".join(errors))

    return tuple(
        AgentProfileEntry(
            agent_id=a.agent_id,
            role=a.role,
            model=a.model,
            enabled=a.enabled,
            config_overrides=a.config_overrides,
        )
        for a in agents_data
    )


async def _check_model_availability(agents: tuple[AgentProfileEntry, ...]) -> list[str]:
    """Generate warnings for models not currently pulled in Ollama.

    If Ollama is unreachable, skip model validation entirely and log it.
    Never silently produce zero warnings as if validation passed.
    """
    try:
        from squadops.api.runtime.deps import get_llm_port

        llm = get_llm_port()
    except RuntimeError:
        logger.debug("LLM port not configured — skipping model availability check")
        return []

    try:
        pulled = await llm.refresh_models()
    except Exception:
        logger.warning("Ollama unreachable — skipping model availability check")
        return []

    warnings = []
    for a in agents:
        if a.model and a.model not in pulled:
            warnings.append(f"Model {a.model!r} (agent {a.agent_id}) is not currently pulled")
    return warnings


@router.get("")
async def list_profiles():
    from squadops.api.runtime.deps import get_squad_profile_port

    try:
        port = get_squad_profile_port()
        profiles = await port.list_profiles()
        active_id = await port.get_active_profile_id()
        return [profile_to_response(p, is_active=(p.profile_id == active_id)) for p in profiles]
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/active")
async def get_active_profile():
    from squadops.api.runtime.deps import get_squad_profile_port

    try:
        port = get_squad_profile_port()
        profile = await port.get_active_profile()
        return profile_to_response(profile, is_active=True)
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


@router.post("")
async def create_profile(body: ProfileCreateRequest):
    from squadops.api.runtime.deps import get_squad_profile_port

    try:
        agents = _validate_agent_request(body.agents)
        profile_id = slugify_profile_name(body.name)

        profile = SquadProfile(
            profile_id=profile_id,
            name=body.name,
            description=body.description,
            version=1,
            agents=agents,
            created_at=datetime.now(UTC),
        )

        port = get_squad_profile_port()
        created = await port.create_profile(profile)
        warnings = await _check_model_availability(agents)
        return profile_to_response(created, warnings=warnings)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.put("/{profile_id}")
async def update_profile(profile_id: str, body: ProfileUpdateRequest):
    from squadops.api.runtime.deps import get_squad_profile_port

    try:
        agents = None
        if body.agents is not None:
            agents = _validate_agent_request(body.agents)

        port = get_squad_profile_port()
        updated = await port.update_profile(
            profile_id,
            name=body.name,
            description=body.description,
            agents=agents,
        )
        active_id = await port.get_active_profile_id()
        warnings = []
        if body.agents is not None:
            warnings = await _check_model_availability(agents)
        return profile_to_response(
            updated, is_active=(updated.profile_id == active_id), warnings=warnings
        )
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.post("/{profile_id}/clone")
async def clone_profile(profile_id: str, body: ProfileCloneRequest):
    from squadops.api.runtime.deps import get_squad_profile_port

    try:
        port = get_squad_profile_port()
        source = await port.get_profile(profile_id)
        new_id = slugify_profile_name(body.name)

        cloned = replace(
            source,
            profile_id=new_id,
            name=body.name,
            version=1,
            created_at=datetime.now(UTC),
        )
        created = await port.create_profile(cloned)
        warnings = await _check_model_availability(cloned.agents)
        return profile_to_response(created, warnings=warnings)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.delete("/{profile_id}")
async def delete_profile(profile_id: str):
    from squadops.api.runtime.deps import get_squad_profile_port

    try:
        port = get_squad_profile_port()
        await port.delete_profile(profile_id)
        return {"status": "deleted", "profile_id": profile_id}
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.post("/{profile_id}/activate")
async def activate_profile(profile_id: str):
    from squadops.api.runtime.deps import get_squad_profile_port

    try:
        port = get_squad_profile_port()
        profile = await port.activate_profile(profile_id)
        return profile_to_response(profile, is_active=True)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/{profile_id}")
async def get_profile(profile_id: str):
    from squadops.api.runtime.deps import get_squad_profile_port

    try:
        port = get_squad_profile_port()
        profile = await port.get_profile(profile_id)
        active_id = await port.get_active_profile_id()
        return profile_to_response(profile, is_active=(profile.profile_id == active_id))
    except CycleError as e:
        raise handle_cycle_error(e) from e
