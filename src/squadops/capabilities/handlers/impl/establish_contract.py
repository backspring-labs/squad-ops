"""Governance establish_contract handler (SIP-0079 §7.2).

Extracts the planning artifact from prior outputs and asks the LLM
to produce a structured RunContract (objective, acceptance criteria,
stop conditions, etc.). On parse failure returns NEEDS_REPLAN.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.cycle_tasks import _CycleTaskHandler
from squadops.capabilities.handlers.impl._json_extraction import (
    JSONExtractionError,
    extract_first_json_object,
)
from squadops.cycles.task_outcome import TaskOutcome
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)


class GovernanceEstablishContractHandler(_CycleTaskHandler):
    """Establish a run contract before implementation begins."""

    _handler_name = "governance_establish_contract_handler"
    _capability_id = "governance.establish_contract"
    _role = "lead"
    _artifact_name = "run_contract.json"

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")

        # SIP-0084: dual-path — use request renderer when available
        rendered = None
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables = self._build_render_variables(prd, prior_outputs, inputs)
            rendered = await renderer.render(self._request_template_id, variables)
            user_prompt = rendered.content
        else:
            user_prompt = self._build_user_prompt(prd, prior_outputs)

        # System prompt is the task_type fragment ALONE — no role
        # identity prepend. Same regression family as the other two
        # SIP-0079 impl handlers; cycle cyc_a4e6dc3afe7a's "char 0"
        # parse failure was the first symptom in this handler.
        # Role-identity layer primes role-play responses; suppress
        # it for this JSON-emitting handler.
        assembled = context.ports.prompt_service.assemble_task_only(
            role=self._role,
            task_type=self._capability_id,
        )
        messages = [
            ChatMessage(role="system", content=assembled.content),
            ChatMessage(role="user", content=user_prompt),
        ]

        chat_kwargs = self._build_chat_kwargs(inputs)

        try:
            response = await context.ports.llm.chat_stream_with_usage(messages, **chat_kwargs)
        except LLMError as exc:
            logger.warning("LLM call failed for %s: %s", self._handler_name, exc)
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False,
                outputs={"outcome_class": TaskOutcome.NEEDS_REPLAN},
                _evidence=evidence,
                error=str(exc),
            )

        content = response.content

        # Parse JSON contract from LLM response. Tolerates <think>
        # blocks, code fences, and prose preamble around the JSON —
        # every impl handler is one model tantrum away from a "char 0"
        # parse error otherwise. Logs a truncated raw response on
        # failure so triage doesn't have to reconstruct what the LLM
        # wrote from token counts alone.
        try:
            contract_data = extract_first_json_object(content)
        except JSONExtractionError as exc:
            logger.warning(
                "%s: failed to parse run contract JSON: %s | raw[:500]=%r",
                self._handler_name,
                exc,
                exc.raw_excerpt,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False,
                outputs={"outcome_class": TaskOutcome.NEEDS_REPLAN},
                _evidence=evidence,
                error=f"Failed to parse run contract: {exc}",
            )

        duration_ms = (time.perf_counter() - start_time) * 1000

        # SIP-0084 §10: prompt provenance (Stage 2 only — no assembled prompt)
        provenance: dict[str, Any] = {}
        if renderer is not None and rendered is not None:
            provenance["request_template_id"] = rendered.template_id
            provenance["request_template_version"] = rendered.template_version
            provenance["request_render_hash"] = rendered.render_hash
            provenance["prompt_environment"] = "production"

        outputs = {
            "summary": (
                f"[lead] Run contract established: {contract_data.get('objective', '')[:60]}"
            ),
            "role": self._role,
            "contract": contract_data,
            "artifacts": [
                {
                    "name": self._artifact_name,
                    "content": json.dumps(contract_data, indent=2),
                    "media_type": "application/json",
                    "type": "run_contract",
                },
            ],
            "prompt_provenance": provenance,
        }

        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )

        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)
