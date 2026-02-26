"""
Artifact Vault API routes (SIP-0064 §9.5, T16).
"""

import hashlib
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from squadops.api.routes.cycles.dtos import BaselinePromoteRequest
from squadops.api.routes.cycles.errors import handle_cycle_error
from squadops.api.routes.cycles.mapping import artifact_to_response
from squadops.cycles.models import ArtifactRef, BaselineNotAllowedError, CycleError

router = APIRouter(prefix="/api/v1", tags=["artifacts"])

# T16: Max upload size 50 MB
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@router.post("/projects/{project_id}/artifacts/ingest")
async def ingest_artifact(
    project_id: str,
    file: UploadFile = File(...),
    artifact_type: str = Form(...),
    filename: str = Form(...),
    media_type: str = Form(...),
):
    """Ingest an artifact via multipart/form-data (T16)."""
    from squadops.api.runtime.deps import get_artifact_vault

    try:
        content = await file.read()
        if len(content) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail={
                    "error": {
                        "code": "PAYLOAD_TOO_LARGE",
                        "message": f"File exceeds {_MAX_UPLOAD_BYTES} byte limit",
                        "details": None,
                    }
                },
            )

        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        content_hash = hashlib.sha256(content).hexdigest()

        ref = ArtifactRef(
            artifact_id=artifact_id,
            project_id=project_id,
            artifact_type=artifact_type,
            filename=filename,
            content_hash=content_hash,
            size_bytes=len(content),
            media_type=media_type,
            created_at=datetime.now(UTC),
        )

        vault = get_artifact_vault()
        stored = await vault.store(ref, content)
        return artifact_to_response(stored)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/artifacts/{artifact_id}")
async def get_artifact_metadata(artifact_id: str):
    from squadops.api.runtime.deps import get_artifact_vault

    try:
        vault = get_artifact_vault()
        ref = await vault.get_metadata(artifact_id)
        return artifact_to_response(ref)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(artifact_id: str):
    from squadops.api.runtime.deps import get_artifact_vault

    try:
        vault = get_artifact_vault()
        ref, content = await vault.retrieve(artifact_id)
        from fastapi.responses import Response

        return Response(
            content=content,
            media_type=ref.media_type,
            headers={"Content-Disposition": f'attachment; filename="{ref.filename}"'},
        )
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/projects/{project_id}/artifacts")
async def list_project_artifacts(project_id: str, artifact_type: str | None = None):
    from squadops.api.runtime.deps import get_artifact_vault

    try:
        vault = get_artifact_vault()
        refs = await vault.list_artifacts(project_id=project_id, artifact_type=artifact_type)
        return [artifact_to_response(r) for r in refs]
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/projects/{project_id}/cycles/{cycle_id}/artifacts")
async def list_cycle_artifacts(project_id: str, cycle_id: str):
    from squadops.api.runtime.deps import get_artifact_vault

    try:
        vault = get_artifact_vault()
        refs = await vault.list_artifacts(project_id=project_id, cycle_id=cycle_id)
        return [artifact_to_response(r) for r in refs]
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/artifacts")
async def list_run_artifacts(project_id: str, cycle_id: str, run_id: str):
    from squadops.api.runtime.deps import get_artifact_vault

    try:
        vault = get_artifact_vault()
        refs = await vault.list_artifacts(project_id=project_id, cycle_id=cycle_id, run_id=run_id)
        return [artifact_to_response(r) for r in refs]
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.post("/projects/{project_id}/baseline/{artifact_type}")
async def promote_baseline(project_id: str, artifact_type: str, body: BaselinePromoteRequest):
    """Promote an artifact as baseline (T6: enforcement here, not in vault)."""
    from squadops.api.runtime.deps import get_artifact_vault, get_cycle_registry

    try:
        vault = get_artifact_vault()

        # T6: Business policy enforcement at route level
        # Check if any cycle for this project uses fresh build strategy
        # (simplified: just check the artifact's cycle if available)
        ref = await vault.get_metadata(body.artifact_id)
        if ref.cycle_id:
            registry = get_cycle_registry()
            cycle = await registry.get_cycle(ref.cycle_id)
            if cycle.build_strategy == "fresh":
                raise BaselineNotAllowedError(
                    "Cannot promote baseline for a fresh build strategy cycle"
                )

        await vault.set_baseline(project_id, artifact_type, body.artifact_id)
        return {"status": "ok", "project_id": project_id, "artifact_type": artifact_type}
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/projects/{project_id}/baseline/{artifact_type}")
async def get_baseline(project_id: str, artifact_type: str):
    from squadops.api.runtime.deps import get_artifact_vault

    try:
        vault = get_artifact_vault()
        ref = await vault.get_baseline(project_id, artifact_type)
        if ref is None:
            from squadops.cycles.models import ArtifactNotFoundError

            raise ArtifactNotFoundError(f"No baseline for {artifact_type} in project {project_id}")
        return artifact_to_response(ref)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/projects/{project_id}/baseline")
async def list_baselines(project_id: str):
    from squadops.api.runtime.deps import get_artifact_vault

    try:
        vault = get_artifact_vault()
        baselines = await vault.list_baselines(project_id)
        return {k: artifact_to_response(v) for k, v in baselines.items()}
    except CycleError as e:
        raise handle_cycle_error(e) from e
