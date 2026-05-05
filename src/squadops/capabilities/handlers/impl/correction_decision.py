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
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)

_VALID_CORRECTION_PATHS = ("continue", "patch", "rewind", "abort")


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

        # System prompt assembled from role + task_type fragments
        # (fragments/roles/lead + fragments/shared/task_type/
        # task_type.governance.correction_decision.md). Aligns this
        # handler with the planning_tasks.py pattern so prompt
        # versions are tracked by PromptService and surfaced to
        # LangFuse rather than living as a Python string.
        assembled = context.ports.prompt_service.assemble(
            role=self._role,
            hook="agent_start",
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

        # Parse JSON decision
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [ln for ln in lines if not ln.strip().startswith("```")]
                cleaned = "\n".join(lines)
            decision = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            # Fallback: abort if unparseable
            decision = {
                "correction_path": "abort",
                "decision_rationale": f"Unable to parse LLM response: {content[:200]}",
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
