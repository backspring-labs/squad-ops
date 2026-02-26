"""
Project API routes (SIP-0064 §9.1).
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

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


@router.get("/{project_id}/prd-content")
async def get_project_prd_content(project_id: str):
    """Read PRD file content for a project (SIP-0074 §3.5).

    Best-effort: returns 404 if prd_path is not configured or the file is not
    readable (e.g. containerized deployment where the PRD lives on the host).
    """
    from squadops.api.runtime.deps import get_project_registry

    try:
        registry = get_project_registry()
        project = await registry.get_project(project_id)
    except CycleError as e:
        raise handle_cycle_error(e) from e

    if not project.prd_path:
        raise HTTPException(404, detail="No PRD file configured for this project")

    prd_path = Path(project.prd_path)
    if not prd_path.is_file():
        raise HTTPException(404, detail=f"PRD file not found: {project.prd_path}")

    try:
        content = prd_path.read_text()
    except OSError as exc:
        raise HTTPException(404, detail=f"PRD file not readable: {project.prd_path}") from exc

    return PlainTextResponse(content)
