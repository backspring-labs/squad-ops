"""Data analyze_failure handler (SIP-0079 §7.7).

Receives failure evidence from the executor and asks the LLM to
classify the failure using the FailureClassification taxonomy,
producing a structured analysis summary.
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
from squadops.cycles.task_outcome import FailureClassification
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)

_ANALYSIS_SYSTEM_PROMPT = f"""\
You are a data analyst performing root cause analysis on a task failure.

Classify the failure into one of these categories:
- {FailureClassification.EXECUTION}: runtime error, timeout, infrastructure issue
- {FailureClassification.WORK_PRODUCT}: output doesn't meet quality/correctness bar
- {FailureClassification.ALIGNMENT}: output doesn't match requirements/contract
- {FailureClassification.DECISION}: wrong approach or architectural choice
- {FailureClassification.MODEL_LIMITATION}: LLM capability gap

Return JSON with:
- classification (string): one of the categories above
- analysis_summary (string): 2-3 sentence explanation of root cause
- contributing_factors (list[string]): factors that contributed

Return ONLY valid JSON, no markdown fences."""


class DataAnalyzeFailureHandler(_CycleTaskHandler):
    """Analyze a task failure and classify its root cause."""

    _handler_name = "data_analyze_failure_handler"
    _capability_id = "data.analyze_failure"
    _role = "data"
    _artifact_name = "failure_analysis.md"

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        failure_evidence = inputs.get("failure_evidence", {})

        # SIP-0084: dual-path — use request renderer when available
        rendered = None
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables: dict[str, str] = {"prd": prd}
            if failure_evidence:
                evidence_json = json.dumps(failure_evidence, indent=2)
                variables["failure_evidence"] = f"\n\n## Failure Evidence\n\n{evidence_json}"
            rendered = await renderer.render("request.data_analyze_failure", variables)
            user_prompt = rendered.content
        else:
            user_parts = [f"## PRD\n\n{prd}"]
            if failure_evidence:
                evidence_json = json.dumps(failure_evidence, indent=2)
                user_parts.append(f"\n\n## Failure Evidence\n\n{evidence_json}")
            user_prompt = "\n".join(user_parts)

        messages = [
            ChatMessage(role="system", content=_ANALYSIS_SYSTEM_PROMPT),
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

        # Parse JSON analysis
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [ln for ln in lines if not ln.strip().startswith("```")]
                cleaned = "\n".join(lines)
            analysis = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            # Fallback: use raw content as analysis summary
            analysis = {
                "classification": FailureClassification.EXECUTION,
                "analysis_summary": content[:500],
                "contributing_factors": [],
            }

        duration_ms = (time.perf_counter() - start_time) * 1000

        # SIP-0084 §10: prompt provenance (Stage 2 only — no assembled prompt)
        provenance: dict[str, Any] = {}
        if renderer is not None and rendered is not None:
            provenance["request_template_id"] = rendered.template_id
            provenance["request_template_version"] = rendered.template_version
            provenance["request_render_hash"] = rendered.render_hash
            provenance["prompt_environment"] = "production"

        outputs = {
            "summary": f"[data] Failure classified as {analysis.get('classification', 'unknown')}",
            "role": self._role,
            "classification": analysis.get("classification", FailureClassification.EXECUTION),
            "analysis_summary": analysis.get("analysis_summary", ""),
            "contributing_factors": analysis.get("contributing_factors", []),
            "artifacts": [
                {
                    "name": self._artifact_name,
                    "content": json.dumps(analysis, indent=2),
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
