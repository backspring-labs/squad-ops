"""
Model registry + management API routes (SIP-0074 §5.9, SIP-0075 §2.3).

Registry endpoint: read-only model specs (code-defined, change on redeploy).
Management endpoints: pulled models, pull/delete via Ollama proxy.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from squadops.api.routes.cycles.dtos import (
    ModelSpecResponse,
    PulledModelResponse,
    PullModelRequest,
    PullStatusResponse,
)

logger = logging.getLogger(__name__)

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


def _get_ollama_adapter():
    """Get the OllamaAdapter from DI, raising 503 if not configured."""
    from adapters.llm.ollama import OllamaAdapter
    from squadops.api.runtime.deps import get_llm_port

    try:
        port = get_llm_port()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="LLM port not configured") from None

    if not isinstance(port, OllamaAdapter):
        raise HTTPException(status_code=503, detail="Model management requires Ollama adapter")
    return port


@router.get("/pulled")
async def list_pulled_models():
    """List locally pulled models with active profile cross-reference."""
    from squadops.llm.model_registry import MODEL_SPECS

    adapter = _get_ollama_adapter()

    try:
        raw_models = await adapter.list_pulled_models()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama unreachable: {e}") from e

    # Cross-reference against active squad profile
    active_agents: dict[str, list[str]] = {}  # model -> [agent_id, ...]
    try:
        from squadops.api.runtime.deps import get_squad_profile_port

        port = get_squad_profile_port()
        active_id = await port.get_active_profile_id()
        if active_id:
            profile = await port.get_profile(active_id)
            for agent in profile.agents:
                if agent.model:
                    active_agents.setdefault(agent.model, []).append(agent.agent_id)
    except Exception:
        logger.debug("Could not resolve active profile for model cross-ref")

    results = []
    for m in raw_models:
        name = m.get("name", "")
        spec = MODEL_SPECS.get(name)
        results.append(
            PulledModelResponse(
                name=name,
                size_bytes=m.get("size"),
                modified_at=m.get("modified_at"),
                in_active_profile=name in active_agents,
                used_by_agents=active_agents.get(name, []),
                registry_spec=(
                    ModelSpecResponse(
                        name=spec.name,
                        context_window=spec.context_window,
                        default_max_completion=spec.default_max_completion,
                    )
                    if spec
                    else None
                ),
            ).model_dump()
        )
    return results


@router.post("/pull", status_code=202)
async def pull_model(body: PullModelRequest):
    """Start pulling a model in the background. Returns 202 with pull_id."""
    from squadops.api.runtime.pull_tracker import (
        complete_pull_job,
        create_pull_job,
        fail_pull_job,
    )

    adapter = _get_ollama_adapter()
    job = create_pull_job(body.name)

    async def _do_pull():
        try:
            await adapter.pull_model(body.name)
            complete_pull_job(job.pull_id)
        except Exception as e:
            fail_pull_job(job.pull_id, str(e))

    asyncio.create_task(_do_pull())

    return PullStatusResponse(
        pull_id=job.pull_id,
        model_name=job.model_name,
        status=job.status,
    ).model_dump()


@router.get("/pull/{pull_id}/status")
async def pull_status(pull_id: str):
    """Poll the status of a model pull job."""
    from squadops.api.runtime.pull_tracker import get_pull_job

    job = get_pull_job(pull_id)
    if not job:
        raise HTTPException(status_code=404, detail="Pull job not found or expired")

    return PullStatusResponse(
        pull_id=job.pull_id,
        model_name=job.model_name,
        status=job.status,
        error=job.error,
    ).model_dump()


@router.delete("/{model_name:path}")
async def delete_model(model_name: str):
    """Delete a locally pulled model."""
    from squadops.llm.exceptions import LLMConnectionError, LLMModelNotFoundError

    adapter = _get_ollama_adapter()

    try:
        await adapter.delete_model(model_name)
        return {"status": "deleted", "model_name": model_name}
    except LLMModelNotFoundError as e:
        raise HTTPException(
            status_code=404, detail=f"Model '{model_name}' not found locally"
        ) from e
    except LLMConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
