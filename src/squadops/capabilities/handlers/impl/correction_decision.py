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
    extract_object_with_reask,
)
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage
from squadops.tasks.task_types import TaskType

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


def _refuted_block(inputs: dict[str, Any]) -> str:
    """The analysis's refuted file claims, as a block the decision cannot miss (#968).

    SIP-0104 P6 roll 6 carried round 1's diagnosis into the decision word for word, and
    the decision instructed the squad to "correct the store imports" that line 3 of the
    named file already had right. Three false factual claims in one roll, and the subject
    oscillated app → tests → app on identical evidence with no convergence.

    The analysis is printed unedited — a silently rewritten analysis is a second
    unverifiable claim — and this contradicts it in place, naming the sentence and the
    file the workspace does not have. Empty string when nothing was refuted, so a sound
    analysis renders exactly as it did.
    """
    refuted = inputs.get("refuted_source_claims") or []
    entries = [e for e in refuted if isinstance(e, dict) and e.get("path")]
    if not entries:
        return ""
    lines = "\n".join(
        f"- `{e['path']}` — no such file in this workspace. The analysis says: "
        f'"{str(e.get("claim") or "").strip()}"'
        for e in entries
    )
    return (
        "\n\n## Refuted by the workspace (authoritative — the analysis above is NOT)\n\n"
        f"{lines}\n\n"
        "These files do not exist in the tree this failure came from, so any reasoning "
        "that rests on them is unsound. Do not carry those statements into your decision "
        "or your rationale, and do not aim a repair at these paths."
    )


class GovernanceCorrectionDecisionHandler(_CycleTaskHandler):
    """Decide the correction path after a failure analysis."""

    _handler_name = "governance_correction_decision_handler"
    _task_type = TaskType.GOVERNANCE_CORRECTION_DECISION
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
            variables["refuted_source_claims"] = _refuted_block(inputs)
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
            refuted = _refuted_block(inputs)
            if refuted:
                user_parts.append(refuted)
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
            task_type=self._task_type,
        )
        messages = [
            ChatMessage(role="system", content=assembled.content),
            ChatMessage(role="user", content=user_prompt),
        ]

        chat_kwargs = self._build_chat_kwargs(inputs)

        try:
            _, content = await self._llm_call(
                context,
                messages,
                chat_kwargs,
                inputs=inputs,
                started=start_time,
            )
        except LLMError as exc:
            logger.warning("LLM call failed for %s: %s", self._handler_name, exc)
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                task_type=self._task_type,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(success=False, outputs={}, _evidence=evidence, error=str(exc))

        # #1008: one bounded re-ask when extraction fails (V38 shakedown truncation).
        async def _reask(feedback: str) -> str:
            retry_messages = [
                *messages,
                ChatMessage(role="assistant", content=content),
                ChatMessage(role="user", content=feedback),
            ]
            _, retry_content = await self._llm_call(
                context,
                retry_messages,
                chat_kwargs,
                inputs=inputs,
                started=start_time,
                shape_label=f"{self._handler_name}:json_reask",
                attempt=2,
            )
            return retry_content

        # Parse JSON decision. Tolerates <think> blocks, code fences,
        # and prose preamble. Falls back to a structured `abort`
        # decision if no balanced JSON object is found anywhere in
        # the response (after the #1008 re-ask), and logs a truncated raw
        # response so triage has the actual model output.
        try:
            decision, content = await extract_object_with_reask(
                content, reask=_reask, logger=logger, handler_name=self._handler_name
            )
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
            task_type=self._task_type,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )

        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)
