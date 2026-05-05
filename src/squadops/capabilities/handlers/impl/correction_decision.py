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
_VALID_PLAN_CHANGE_CANDIDATES = ("none", "add_task", "tighten_acceptance", "other")

# SIP-0092 M2 → M3 gate diagnostic. The correction protocol can today
# only choose continue/patch/rewind/abort — it cannot mutate the
# implementation plan. M3 will add `decision: plan_change` with two
# operations (add_task, tighten_acceptance). To know whether M3 is
# worth shipping, we need to know how often the lead would have chosen
# a structural plan change if it were available. This field captures
# that intent without changing behavior.
_DECISION_SYSTEM_PROMPT = """\
You are the governance lead deciding how to respond to a failure during
implementation. Given the failure analysis, select ONE correction path:

- continue: the failure is non-critical; proceed with the remaining tasks
- patch: inject repair tasks to fix the specific issue, then continue
- rewind: restore the last checkpoint and retry from that point
- abort: the failure is unrecoverable; stop the run

Then, separately, answer a diagnostic question: if you could ALSO modify
the implementation plan itself (not yet available in this framework),
which structural plan change would you choose?

- none: the failure does not call for a plan change; continue/patch/rewind/abort suffices
- add_task: a new task should be inserted into the plan to cover a gap the
  original plan missed (e.g., a coverage gap for an endpoint, an integration
  step the framing phase did not anticipate)
- tighten_acceptance: an existing task's acceptance criteria should be
  strengthened so this failure mode is caught next time (e.g., adding a
  required regex_match or field_present check to an existing task)
- other: a different structural change would be needed (remove/replace/reorder)

This is a DIAGNOSTIC field. Your operative decision is the correction path
above; the plan-change candidate does not run anything. Pick the answer
that best describes what you would do if plan changes were available,
even if you have to extrapolate.

Return JSON with:
- correction_path (string): one of continue/patch/rewind/abort
- decision_rationale (string): 2-3 sentence justification of correction_path
- affected_task_types (list[string]): task types affected by the decision
- structural_plan_change_candidate (string): one of
  none/add_task/tighten_acceptance/other
- structural_plan_change_rationale (string): 1-2 sentence justification of
  the plan-change candidate; explain what task would be added or what
  acceptance would be tightened. Empty string if candidate is `none`.

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

        messages = [
            ChatMessage(role="system", content=_DECISION_SYSTEM_PROMPT),
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
