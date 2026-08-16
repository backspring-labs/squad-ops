"""Plan sign-off handler (#331 split from planning_tasks.py).

``governance.review_plan`` — sign-off only post-93.3 cutover (the merger
authors the plan), with the frontmatter-retry recovery path.
"""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any

import yaml

from squadops.capabilities.handlers.base import (
    HandlerResult,
)
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext
from squadops.capabilities.handlers.emission_log import log_emission_shape
from squadops.capabilities.handlers.planning.base import _PlanningTaskHandler

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_VALID_READINESS = {"go", "revise", "no-go"}


class GovernanceReviewPlanHandler(_PlanningTaskHandler):
    """Planning sign-off (SIP-0093 PR 93.3 cutover).

    Produces ``planning_artifact.md`` — a reconstituted narrative synthesizing
    all upstream planning outputs with YAML frontmatter carrying the
    readiness recommendation and sufficiency score. After SIP-0093 PR 93.3,
    this handler is **sign-off only**: it does NOT author
    ``implementation_plan.yaml``. The merger (``governance.merge_plan``)
    runs upstream and emits the canonical plan plus ``merge_decisions.yaml``
    via the same handler chain regardless of authoring mode (multi-role or
    sole-author).

    Performs lightweight post-generation validation on the artifact content:
    - YAML frontmatter exists (``---`` delimiters)
    - ``readiness`` field is one of ``go``, ``revise``, ``no-go``
    - ``sufficiency_score`` is an integer 0–5
    """

    _handler_name = "governance_assess_readiness_handler"
    _capability_id = "governance.review_plan"
    _role = "lead"
    _artifact_name = "planning_artifact.md"

    async def _retry_without_frontmatter(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        prior_content: str,
    ) -> str | None:
        """Re-prompt Max once with a corrective instruction.

        Returns the new artifact content if the retry produced any
        response, else ``None`` so the caller can fail the task. The
        caller still validates frontmatter on the result, so a retry
        that comes back empty or still missing frontmatter terminates
        the task.
        """
        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")
        raw_budget = inputs.get("resolved_config", {}).get("time_budget_seconds")
        time_budget_seconds = int(raw_budget) if raw_budget is not None else None

        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables = self._build_render_variables(prd, prior_outputs, inputs)
            rendered = await renderer.render(self._request_template_id, variables)
            user_prompt = rendered.content
        else:
            user_prompt = self._build_user_prompt(prd, prior_outputs, time_budget_seconds)

        assembled = context.ports.prompt_service.assemble(
            role=self._role,
            hook="agent_start",
            task_type=self._capability_id,
        )

        messages = [
            ChatMessage(role="system", content=assembled.content),
            ChatMessage(role="user", content=user_prompt),
            ChatMessage(role="assistant", content=prior_content),
            ChatMessage(role="user", content=self._FRONTMATTER_RETRY_INSTRUCTION),
        ]
        chat_kwargs = self._build_chat_kwargs(inputs)

        try:
            response = await context.ports.llm.chat_stream_with_usage(messages, **chat_kwargs)
        except LLMError as exc:
            logger.warning("assess_readiness: frontmatter-retry LLM call failed: %s", exc)
            return None

        log_emission_shape(
            f"{self._handler_name}:frontmatter_retry",
            response.content if response else None,
            getattr(response, "completion_tokens", None),
        )
        return response.content if response and response.content else None

    _FRONTMATTER_RETRY_INSTRUCTION = (
        "Your previous response did not include the required YAML frontmatter. "
        "The planning artifact MUST start with a `---` delimited block "
        "containing `readiness` (one of `go`, `revise`, `no-go`) and "
        "`sufficiency_score` (integer 0–5), followed by `---` and the body. "
        "Re-emit the full planning artifact, starting with the frontmatter."
    )

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        result = await super().handle(context, inputs)
        if not result.success:
            return result

        content = result.outputs["artifacts"][0]["content"]

        # Structural validation: YAML frontmatter must be authored by the
        # LLM. Issue #109: we used to silently synthesize a default
        # `readiness=revise / sufficiency_score=3` block when frontmatter
        # was missing, which made it look like Max had reviewed the plan
        # when in fact every downstream consumer was reading defaults.
        # Now: retry once with a corrective prompt; if the retry still
        # omits frontmatter, fail the task so the cycle's correction
        # loop can fire instead of papering over it.
        m = _FRONTMATTER_RE.match(content)
        if not m:
            retry_content = await self._retry_without_frontmatter(context, inputs, content)
            if retry_content is not None:
                content = retry_content
                # #155: `result` is a frozen HandlerResult. Rebuild it with the
                # retry content instead of mutating its nested `outputs` dict in
                # place — `frozen=True` does not freeze nested containers, and the
                # original result may be shared/cached/retried elsewhere.
                artifacts = result.outputs["artifacts"]
                new_artifacts = [{**artifacts[0], "content": content}, *artifacts[1:]]
                new_outputs = {**result.outputs, "artifacts": new_artifacts}
                result = replace(result, outputs=new_outputs)
                m = _FRONTMATTER_RE.match(content)

            if not m:
                logger.warning(
                    "assess_readiness: LLM omitted YAML frontmatter on initial "
                    "response and retry; failing task to surface the gap"
                )
                return HandlerResult(
                    success=False,
                    outputs={},
                    _evidence=result._evidence,
                    error=(
                        "Planning artifact missing required YAML frontmatter "
                        "(readiness, sufficiency_score) after one corrective retry"
                    ),
                )

        try:
            fm = yaml.safe_load(m.group(1))
        except yaml.YAMLError as exc:
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=result._evidence,
                error=f"Planning artifact has invalid YAML frontmatter: {exc}",
            )

        if not isinstance(fm, dict):
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=result._evidence,
                error="Planning artifact YAML frontmatter is not a mapping",
            )

        # Validate readiness field — default to "revise" if missing/invalid
        readiness = fm.get("readiness")
        if readiness not in _VALID_READINESS:
            logger.warning(
                "assess_readiness: frontmatter readiness=%r invalid, defaulting to 'revise'",
                readiness,
            )
            fm["readiness"] = "revise"

        # Validate sufficiency_score — default to 3 if missing/invalid
        try:
            score = int(fm.get("sufficiency_score", 3))
            if not (0 <= score <= 5):
                raise ValueError
        except (TypeError, ValueError):
            logger.warning(
                "assess_readiness: frontmatter sufficiency_score=%r invalid, defaulting to 3",
                fm.get("sufficiency_score"),
            )
            score = 3

        # SIP-0093 PR 93.3 cutover: implementation_plan.yaml is no longer
        # produced here. The merger (governance.merge_plan) runs upstream
        # and emits the canonical plan + merge_decisions.yaml. This handler
        # is sign-off only — it consumes the consolidated planning artifact
        # and adds the readiness recommendation.
        #
        # The merger's artifacts already live in the cycle's artifact
        # stream; PR 93.4 surfaces them in the gate package primary view.
        return result
