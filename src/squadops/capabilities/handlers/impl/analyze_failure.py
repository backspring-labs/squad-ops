"""Data analyze_failure handler (SIP-0079 §7.7).

Receives failure evidence from the executor and asks the LLM to
classify the failure using the FailureClassification taxonomy,
producing a structured analysis summary.

Issue #84: Pydantic-validated output schema — empty/missing required
fields now fail loudly and route to NEEDS_REPLAN instead of being
silently coerced into useless defaults.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.cycle_tasks import _CycleTaskHandler
from squadops.cycles.task_outcome import FailureClassification, TaskOutcome
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)


_VALID_CLASSIFICATIONS = {
    FailureClassification.EXECUTION,
    FailureClassification.WORK_PRODUCT,
    FailureClassification.ALIGNMENT,
    FailureClassification.DECISION,
    FailureClassification.MODEL_LIMITATION,
}


class FailureAnalysis(BaseModel):
    """Structured failure analysis output (issue #84).

    Required fields are required for a reason — downstream
    governance.correction_decision needs concrete inputs to author a
    plan delta. Empty strings and unknown classifications are rejected.
    """

    classification: str = Field(min_length=1)
    analysis_summary: str = Field(min_length=20)
    contributing_factors: list[str] = Field(min_length=1)

    @field_validator("classification")
    @classmethod
    def classification_must_be_known(cls, v: str) -> str:
        if v not in _VALID_CLASSIFICATIONS:
            raise ValueError(
                f"classification {v!r} not in {sorted(_VALID_CLASSIFICATIONS)}"
            )
        return v

    @field_validator("contributing_factors")
    @classmethod
    def contributing_factors_must_be_substantive(cls, v: list[str]) -> list[str]:
        if not all(isinstance(s, str) and len(s.strip()) >= 5 for s in v):
            raise ValueError(
                "each contributing factor must be a string >=5 chars"
            )
        return v


_ANALYSIS_SYSTEM_PROMPT = f"""\
You are a data analyst performing root cause analysis on a task failure.

The Failure Evidence block below carries structured signals from the failed
handler. When present, USE THEM rather than restating the error string:

- `validation_result.checks` — per-criterion typed-acceptance outcomes from
  the failed handler. A `failed`-status check tells you the EXACT criterion
  that rejected the work (regex pattern, missing field, missing endpoint).
  Quote the failing check's name and `actual` field in your analysis.
- `validation_result.missing_components` — specific files/sections the
  validator expected but did not find. Name them in your analysis.
- `rejected_artifacts[*].content_snippet` — the first ~1500 chars of what
  the handler actually emitted. Compare against the failing checks to
  identify whether it's a format issue, a missing-content issue, or a
  scope-too-large issue.
- `preliminary_failure_classification` — the failed handler's own classification.
  Do not just echo it; corroborate or override it with evidence.

Distinguish content-quality failures from structural failures explicitly,
because downstream correction-decision uses your analysis to choose between
patch (single-task content fix) and rewind (multi-task scope change). State
which you observed.

Classify the failure into one of these categories:
- {FailureClassification.EXECUTION}: runtime error, timeout, infrastructure issue
- {FailureClassification.WORK_PRODUCT}: output doesn't meet quality/correctness bar
  (typed check failed on emitted artifact — usually patchable)
- {FailureClassification.ALIGNMENT}: output doesn't match requirements/contract
  (artifact correct in isolation but wrong against PRD/contract — may need rewind)
- {FailureClassification.DECISION}: wrong approach or architectural choice
- {FailureClassification.MODEL_LIMITATION}: LLM capability gap (e.g. completion
  truncated at token cap, scope exceeds single-call budget)

Return JSON with these REQUIRED fields:
- classification (string): EXACTLY one of: {", ".join(sorted(_VALID_CLASSIFICATIONS))}
- analysis_summary (string, >=20 chars): concrete 2-3 sentence root cause. State the
  specific component, the specific symptom (cite the failing check name when
  available), and (if knowable) the specific cause. Do NOT write "N/A", "unknown",
  or empty strings — if you cannot determine the cause from the evidence, say SO
  and name the missing evidence.
- contributing_factors (list[string], >=1 item, each >=5 chars): factors that
  contributed. Each factor must be a concrete observable, not a generic phrase.

Empty fields, the literal "N/A", and the literal "unknown" will be rejected.

Return ONLY valid JSON, no markdown fences, no explanation."""


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

        # Parse JSON, then validate against schema (issue #84). Validation
        # failure routes to NEEDS_REPLAN with a clear log line — silent
        # coercion to a useless default produced wrong corrections in the
        # past (live evidence: cyc_4cac11018af7).
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            raw = json.loads(cleaned)
            analysis_model = FailureAnalysis.model_validate(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "analyze_failure_handler rejected output: %s | raw=%s",
                exc,
                content[:300],
            )
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
                error=f"Failure analysis rejected by schema: {exc}",
            )

        analysis = analysis_model.model_dump()
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
