"""
Model registry API routes (SIP-0074 §5.9).

Read-only endpoint exposing the model context registry (SIP-0073) over HTTP.
Values are code-defined and only change on redeploy.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from squadops.api.routes.cycles.dtos import ModelSpecResponse

router = APIRouter(prefix="/api/v1/models", tags=["models"])

_CACHE_HEADERS = {"Cache-Control": "public, max-age=300"}


@router.get("")
async def list_models():
    """Return all model registry entries."""
    from squadops.llm.model_registry import MODEL_SPECS

    specs = [
        ModelSpecResponse(
            name=spec.name,
            context_window=spec.context_window,
            default_max_completion=spec.default_max_completion,
        ).model_dump()
        for spec in MODEL_SPECS.values()
    ]
    return JSONResponse(content=specs, headers=_CACHE_HEADERS)
