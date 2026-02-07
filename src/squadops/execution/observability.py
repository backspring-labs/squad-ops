"""Observability helpers for the execution layer (SIP-0061).

Bridges LLM port output into the observability domain.
"""
from __future__ import annotations

import uuid

from squadops.llm.models import LLMResponse
from squadops.telemetry.models import GenerationRecord


def build_generation_record(
    llm_response: LLMResponse,
    model: str,
    prompt_text: str,
    latency_ms: float | None = None,
) -> GenerationRecord:
    """Bridge LLMResponse -> GenerationRecord with UUID4 generation_id.

    The generation_id is created here — adapters MUST NOT generate or backfill it.

    Args:
        llm_response: Response from an LLMPort call.
        model: Model name used for the generation.
        prompt_text: The prompt text sent to the model.
        latency_ms: Optional latency in milliseconds.

    Returns:
        A frozen GenerationRecord with a unique generation_id.
    """
    return GenerationRecord(
        generation_id=str(uuid.uuid4()),
        model=model,
        prompt_text=prompt_text,
        response_text=llm_response.text,
        prompt_tokens=llm_response.prompt_tokens,
        completion_tokens=llm_response.completion_tokens,
        total_tokens=llm_response.total_tokens,
        latency_ms=latency_ms,
    )
