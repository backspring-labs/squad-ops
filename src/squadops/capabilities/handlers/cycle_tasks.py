"""Cycle task handlers — LLM-powered handlers for cycle execution pipeline.

5 handlers whose capability_id matches the pinned task_type values
from the static task plan (SIP-0066 §5.4). Each handler calls
``context.ports.llm.chat()`` with role-specific system prompts
assembled via ``PromptService`` (SIP-0057), passing the PRD and
upstream outputs as context. Per-agent models are threaded from
squad profile metadata.

Part of SIP-0066.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    CapabilityHandler,
    HandlerEvidence,
    HandlerResult,
)
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)


class _CycleTaskHandler(CapabilityHandler):
    """Base class for cycle task handlers.

    Provides shared validate_inputs (requires 'prd') and a template
    handle() that calls ``context.ports.llm.chat()`` with system prompts
    assembled via ``context.ports.prompt_service`` (SIP-0057).
    Subclasses set ``_role`` and ``_artifact_name``.
    """

    _handler_name: str = ""
    _capability_id: str = ""
    _role: str = ""
    _artifact_name: str = ""

    @property
    def name(self) -> str:
        return self._handler_name

    @property
    def capability_id(self) -> str:
        return self._capability_id

    @property
    def description(self) -> str:
        return f"Cycle task handler for {self._role} role ({self._capability_id})"

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract=None,
    ) -> list[str]:
        errors = super().validate_inputs(inputs, contract)
        if "prd" not in inputs:
            errors.append("'prd' is required")
        return errors

    def _build_user_prompt(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
    ) -> str:
        """Assemble user prompt from PRD and upstream handler outputs."""
        parts = [f"## Product Requirements Document\n\n{prd}"]
        if prior_outputs:
            parts.append("\n\n## Prior Analysis from Upstream Roles\n")
            for role, summary in prior_outputs.items():
                parts.append(f"### {role}\n{summary}\n")
        parts.append(f"\nPlease provide your {self._role} analysis and deliverables.")
        return "\n".join(parts)

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")

        user_prompt = self._build_user_prompt(prd, prior_outputs)

        assembled = context.ports.prompt_service.get_system_prompt(self._role)
        system_prompt = assembled.content

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

        try:
            response = await context.ports.llm.chat(messages)
        except LLMError as exc:
            logger.warning(
                "LLM call failed for %s: %s", self._handler_name, exc,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False, outputs={}, _evidence=evidence, error=str(exc),
            )

        content = response.content
        llm_duration_ms = (time.perf_counter() - start_time) * 1000

        # Record LLM generation for LangFuse tracing (SIP-0061 Option B)
        llm_obs = getattr(context.ports, "llm_observability", None)
        if llm_obs and context.correlation_context:
            import uuid

            from squadops.telemetry.models import (
                GenerationRecord,
                PromptLayer,
                PromptLayerMetadata,
            )

            gen_record = GenerationRecord(
                generation_id=str(uuid.uuid4()),
                model=context.ports.llm.default_model,
                prompt_text=user_prompt[:2000],
                response_text=content[:2000],
                latency_ms=llm_duration_ms,
            )
            layers = PromptLayerMetadata(
                prompt_layer_set_id=f"{self._role}-cycle",
                layers=(
                    PromptLayer(layer_type="system", layer_id=f"{self._role}-system"),
                    PromptLayer(
                        layer_type="user", layer_id=f"cycle-{self._capability_id}"
                    ),
                ),
            )
            llm_obs.record_generation(context.correlation_context, gen_record, layers)

        prd_summary = str(prd)[:80] if prd else "(no PRD)"

        outputs = {
            "summary": f"[{self._role}] {prd_summary}",
            "role": self._role,
            "artifacts": [
                {
                    "name": self._artifact_name,
                    "content": content,
                    "media_type": "text/markdown",
                    "type": "document",
                },
            ],
        }

        duration_ms = (time.perf_counter() - start_time) * 1000

        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )

        return HandlerResult(
            success=True,
            outputs=outputs,
            _evidence=evidence,
        )


class StrategyAnalyzeHandler(_CycleTaskHandler):
    """Cycle task handler for strategy analysis (strat role)."""

    _handler_name = "strategy_analyze_handler"
    _capability_id = "strategy.analyze_prd"
    _role = "strat"
    _artifact_name = "strategy_analysis.md"


class DevelopmentImplementHandler(_CycleTaskHandler):
    """Cycle task handler for development implementation (dev role)."""

    _handler_name = "development_implement_handler"
    _capability_id = "development.implement"
    _role = "dev"
    _artifact_name = "implementation_plan.md"


class QAValidateHandler(_CycleTaskHandler):
    """Cycle task handler for QA validation (qa role)."""

    _handler_name = "qa_validate_handler"
    _capability_id = "qa.validate"
    _role = "qa"
    _artifact_name = "validation_plan.md"


class DataReportHandler(_CycleTaskHandler):
    """Cycle task handler for data reporting (data role)."""

    _handler_name = "data_report_handler"
    _capability_id = "data.report"
    _role = "data"
    _artifact_name = "data_report.md"


class GovernanceReviewHandler(_CycleTaskHandler):
    """Cycle task handler for governance review (lead role)."""

    _handler_name = "governance_review_handler"
    _capability_id = "governance.review"
    _role = "lead"
    _artifact_name = "governance_review.md"
