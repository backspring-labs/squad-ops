"""Governance correction_decision handler (SIP-0079 §7.7).

Presents the 4 correction paths (continue, patch, rewind, abort) to
the LLM and captures the selected path, rationale, and affected task types.
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
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)

_VALID_CORRECTION_PATHS = ("continue", "patch", "rewind", "abort")

# SIP-0092 M2 → M3 gate diagnostic. The correction protocol can today
# only choose continue/patch/rewind/abort — it cannot mutate the
# implementation plan. M3 will add `decision: plan_change` with two
# operations (add_task, tighten_acceptance). To know whether M3 is
# worth shipping, we capture which structural plan change the lead
# would have chosen if it were available — the field is non-operative
# and exists only to drive the M3 justification gate.
_VALID_PLAN_CHANGE_CANDIDATES = ("none", "add_task", "tighten_acceptance", "other")


class GovernanceCorrectionDecisionHandler(_CycleTaskHandler):
    """Decide the correction path after a failure analysis."""

    _handler_name = "governance_correction_decision_handler"
    _capability_id = "governance.correction_decision"
    _role = "lead"
    _artifact_name = "correction_decision.md"

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        failure_analysis = inputs.get("failure_analysis", {})

        # SIP-0084: dual-path — use request renderer when available
        rendered = None
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables: dict[str, str] = {"prd": prd}
            if failure_analysis:
                variables["failure_analysis"] = (
                    f"\n\n## Failure Analysis\n\n{json.dumps(failure_analysis, indent=2)}"
                )
            rendered = await renderer.render(
                "request.governance_correction_decision",
                variables,
            )
            user_prompt = rendered.content
        else:
            user_parts = [f"## PRD\n\n{prd}"]
            if failure_analysis:
                user_parts.append(
                    f"\n\n## Failure Analysis\n\n{json.dumps(failure_analysis, indent=2)}"
                )
            user_prompt = "\n".join(user_parts)

        # System prompt is the task_type fragment ALONE — no role
        # identity prepend. Cycle cyc_a867cbf02205 (2026-05-05)
        # captured raw output where Max (under the lead-identity
        # prepend introduced by PR #126) wrote a "### Initialization
        # Verification / Role Configuration: LeadAgent_SquadOps
        # loaded ✅" markdown narrative instead of the JSON contract
        # the prompt asked for. The role-identity fragment primes
        # small models to enter role-play mode. Suppress it here
        # while keeping the task_type fragment as the externalized
        # source of truth.
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
            return HandlerResult(success=False, outputs={}, _evidence=evidence, error=str(exc))

        content = response.content

        # Parse JSON decision. Tolerates <think> blocks, code fences,
        # and prose preamble. Falls back to a structured `abort`
        # decision if no balanced JSON object is found anywhere in
        # the response, and logs a truncated raw response so triage
        # has the actual model output.
        try:
            decision = extract_first_json_object(content)
        except JSONExtractionError as exc:
            logger.warning(
                "%s: failed to parse correction decision JSON: %s | raw[:500]=%r",
                self._handler_name,
                exc,
                exc.raw_excerpt,
            )
            decision = {
                "correction_path": "abort",
                "decision_rationale": (f"Unable to parse LLM response: {exc.raw_excerpt[:200]}"),
                "affected_task_types": [],
            }

        # Validate correction_path
        path = decision.get("correction_path", "abort")
        if path not in _VALID_CORRECTION_PATHS:
            path = "abort"
            decision["correction_path"] = path

        # SIP-0092 M2 → M3 gate diagnostic. Validate and surface the
        # plan-change candidate; default to `none` when missing or
        # invalid so the field is always present in the artifact for
        # gate-evidence aggregation.
        plan_change_candidate = decision.get("structural_plan_change_candidate", "none")
        if plan_change_candidate not in _VALID_PLAN_CHANGE_CANDIDATES:
            logger.warning(
                "%s: invalid structural_plan_change_candidate %r — defaulting to 'none'",
                self._handler_name,
                plan_change_candidate,
            )
            plan_change_candidate = "none"
        decision["structural_plan_change_candidate"] = plan_change_candidate
        plan_change_rationale = str(decision.get("structural_plan_change_rationale", ""))
        decision["structural_plan_change_rationale"] = plan_change_rationale

        duration_ms = (time.perf_counter() - start_time) * 1000

        # SIP-0084 §10: prompt provenance (Stage 2 only — no assembled prompt)
        provenance: dict[str, Any] = {}
        if renderer is not None and rendered is not None:
            provenance["request_template_id"] = rendered.template_id
            provenance["request_template_version"] = rendered.template_version
            provenance["request_render_hash"] = rendered.render_hash
            provenance["prompt_environment"] = "production"

        outputs = {
            "summary": f"[lead] Correction decision: {path}",
            "role": self._role,
            "correction_path": path,
            "decision_rationale": decision.get("decision_rationale", ""),
            "affected_task_types": decision.get("affected_task_types", []),
            "structural_plan_change_candidate": plan_change_candidate,
            "structural_plan_change_rationale": plan_change_rationale,
            "artifacts": [
                {
                    "name": self._artifact_name,
                    "content": json.dumps(decision, indent=2),
                    "media_type": "text/markdown",
                    "type": "document",
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
