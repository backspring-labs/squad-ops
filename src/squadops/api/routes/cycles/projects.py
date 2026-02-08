"""
Project API routes (SIP-0064 §9.1).
"""

from fastapi import APIRouter

from squadops.api.routes.cycles.errors import handle_cycle_error
from squadops.api.routes.cycles.mapping import project_to_response
from squadops.cycles.models import CycleError

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("")
async def list_projects():
    from squadops.api.runtime.deps import get_project_registry

    try:
        registry = get_project_registry()
        projects = await registry.list_projects()
        return [project_to_response(p) for p in projects]
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/{project_id}")
async def get_project(project_id: str):
    from squadops.api.runtime.deps import get_project_registry

    try:
        registry = get_project_registry()
        project = await registry.get_project(project_id)
        return project_to_response(project)
    except CycleError as e:
        raise handle_cycle_error(e) from e
