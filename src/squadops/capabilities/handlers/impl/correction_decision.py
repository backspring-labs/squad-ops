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

_DECISION_SYSTEM_PROMPT = """\
You are the governance lead deciding how to respond to a failure during
implementation. Given the failure analysis, select ONE correction path:

- continue: the failure is non-critical; proceed with the remaining tasks
- patch: inject repair tasks to fix the specific issue, then continue
- rewind: restore the last checkpoint and retry from that point
- abort: the failure is unrecoverable; stop the run

Return JSON with:
- correction_path (string): one of continue/patch/rewind/abort
- decision_rationale (string): 2-3 sentence justification
- affected_task_types (list[string]): task types affected by the decision

Return ONLY valid JSON, no markdown fences."""


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

        user_parts = [f"## PRD\n\n{prd}"]
        if failure_analysis:
            user_parts.append(
                f"\n\n## Failure Analysis\n\n{json.dumps(failure_analysis, indent=2)}"
            )
        user_prompt = "\n".join(user_parts)

        messages = [
            ChatMessage(role="system", content=_DECISION_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        chat_kwargs = self._build_chat_kwargs(inputs)

        try:
            response = await context.ports.llm.chat(messages, **chat_kwargs)
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
                success=False, outputs={}, _evidence=evidence, error=str(exc)
            )

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

        duration_ms = (time.perf_counter() - start_time) * 1000

        outputs = {
            "summary": f"[lead] Correction decision: {path}",
            "role": self._role,
            "correction_path": path,
            "decision_rationale": decision.get("decision_rationale", ""),
            "affected_task_types": decision.get("affected_task_types", []),
            "artifacts": [
                {
                    "name": self._artifact_name,
                    "content": json.dumps(decision, indent=2),
                    "media_type": "text/markdown",
                    "type": "document",
                },
            ],
        }

        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )

        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)
