"""Plan-authoring-brief handler (#331 split from planning_tasks.py).

``governance.prepare_plan_authoring_brief`` (SIP-0093 PR 93.0) — produces
the read-only ``plan_authoring_brief.yaml`` the proposers bind to.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext
from squadops.capabilities.handlers.planning.base import _PlanningTaskHandler

_BRIEF_MAX_ATTEMPTS_DEFAULT = 2


class GovernancePreparePlanAuthoringBriefHandler(_PlanningTaskHandler):
    """SIP-0093 PR 93.0: produce ``plan_authoring_brief.yaml``.

    The brief pins stack, scope, requirements, scope cuts, and risk areas
    before plan-authoring fan-out so role proposers operate from one shared
    frame. The merger consumes it (RC-22 immutability) regardless of whether
    proposers ran or sole-author mode kicks in.

    Runs an LLM call with up to ``brief_max_attempts`` retries; each attempt's
    raw response is fence-stripped via ``retry_yaml_call`` before
    ``PlanAuthoringBrief.from_yaml`` validates it. Mirrors the proposer
    handlers in this module.
    """

    _handler_name = "governance_prepare_plan_authoring_brief_handler"
    _capability_id = "governance.prepare_plan_authoring_brief"
    _role = "lead"
    _artifact_name = "plan_authoring_brief.yaml"

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        from squadops.capabilities.handlers._plan_authoring import retry_yaml_call
        from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief

        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")
        resolved_config = inputs.get("resolved_config", {})
        raw_budget = resolved_config.get("time_budget_seconds")
        time_budget_seconds = int(raw_budget) if raw_budget is not None else None

        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables = self._build_render_variables(prd, prior_outputs, inputs)
            # #686: the brief pins the frame the proposers author against, so the
            # plan-shape rules belong here as much as on the proposers themselves.
            variables["authoring_rules_section"] = await self._authoring_rules_section(renderer)
            # #669: the brief pins the frame the proposers work from — on a
            # re-roll it must know what died, or it re-pins the rejected shape.
            rejection_section = await self._rejection_context_section(renderer, inputs)
            if rejection_section:
                variables["rejection_context_section"] = rejection_section
            rendered = await renderer.render(self._request_template_id, variables)
            user_prompt = rendered.content
        else:
            user_prompt = self._build_user_prompt(prd, prior_outputs, time_budget_seconds)

        assembled = context.ports.prompt_service.assemble(
            role=self._role,
            hook="agent_start",
            task_type=self._capability_id,
        )
        system_prompt = assembled.content

        max_attempts = int(resolved_config.get("brief_max_attempts", _BRIEF_MAX_ATTEMPTS_DEFAULT))
        chat_kwargs = self._build_chat_kwargs(inputs)

        def parse_and_validate(
            yaml_or_none: str | None,
        ) -> tuple[Any | None, str | None]:
            if yaml_or_none is None:
                return None, (
                    "No YAML brief found. Emit your output as a fenced block: "
                    "```yaml:plan_authoring_brief.yaml ... ``` (or ```yaml ... ```)."
                )
            try:
                brief = PlanAuthoringBrief.from_yaml(yaml_or_none)
            except ValueError as exc:
                return None, f"plan_authoring_brief.yaml failed to parse: {exc}"
            return brief, None

        parsed, last_yaml, last_error = await retry_yaml_call(
            llm=context.ports.llm,
            chat_kwargs=chat_kwargs,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            parse_and_validate=parse_and_validate,
            max_attempts=max_attempts,
            handler_name=self._handler_name,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000

        if parsed is None:
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=evidence,
                error=(
                    f"plan_authoring_brief.yaml failed to parse: "
                    f"{last_error or 'exhausted retry budget without parseable output'}"
                ),
            )

        # ``last_yaml`` is the fence-extracted body; persist that as the
        # artifact content so downstream callers (merger, gate package) get
        # raw YAML without code-fence wrappers.
        assert last_yaml is not None  # invariant: parsed is not None → yaml was extracted
        outputs = {
            "summary": f"[{self._role}] plan_authoring_brief produced",
            "role": self._role,
            "artifacts": [
                {
                    "name": self._artifact_name,
                    "content": last_yaml,
                    "media_type": "text/yaml",
                    "type": "plan_authoring_brief",
                },
            ],
            # PR 93.3 wire: surface the brief YAML in a non-artifacts key so
            # the merger can consume it from prior_outputs["lead"]["brief_outcome"].
            # The executor's prior_outputs builder strips "artifacts" by design.
            "brief_outcome": {
                "status": "success",
                "yaml_content": last_yaml,
                "artifact_name": self._artifact_name,
            },
        }
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )
        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)


# ---------------------------------------------------------------------------
# 3 Proposer handlers (SIP-0093 PR 93.2)
#
# Three handlers that contribute domain-scoped plan-authoring artifacts:
# development.propose_plan_tasks, qa.propose_plan_tasks, and
# strategy.propose_plan_guidance. Registered but NOT wired into
# PLANNING_TASK_STEPS — cutover happens in PR 93.3. The handlers are
# reachable via direct dispatch and in tests until then.
#
# Each handler:
#   1. Reads plan_authoring_brief.yaml from prior_outputs["artifact_contents"]
#      (RC-22: brief is immutable upstream context).
#   2. Renders its user prompt from a registered template that surfaces the
#      brief content, planning_content, proposal_id, source_brief_id.
#   3. Assembles its system prompt via prompt_service.assemble(..., task_type=
#      self._capability_id) — task-type fragments live in
#      src/squadops/prompts/fragments/shared/task_type/.
#   4. Runs retry_yaml_call (SIP-0093 _plan_authoring helper) for up to
#      manifest_max_attempts attempts with corrective feedback on each
#      parse failure.
#   5. Enforces source_brief_id matching the upstream brief's brief_id.
#   6. On success: emits the parseable artifact (proposed_plan_tasks.yaml or
#      plan_guidance.yaml).
#   7. On exhausted failure: emits a ProposalFailure artifact (RC-23) rather
#      than an exception that kills the cycle. The merger (PR 93.3) reads
#      these as "this role's proposal is missing."
# ---------------------------------------------------------------------------
