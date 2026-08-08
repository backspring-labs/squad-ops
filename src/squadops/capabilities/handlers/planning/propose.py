"""Role-proposer handlers (#331 split from planning_tasks.py).

``_ProposeBaseHandler`` + the dev/qa/strategy proposers (SIP-0093 §5.4-5.6)
and their brief-id/planning-content helpers — every use site of both
helpers is propose-side.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)
from squadops.cycles.acceptance_check_spec import render_typed_acceptance_vocabulary

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext
from squadops.capabilities.handlers.planning.base import _PlanningTaskHandler

_PROPOSAL_MAX_ATTEMPTS_DEFAULT = 2


def _extract_brief_id_from_prior_outputs(prior_outputs: dict[str, Any] | None) -> str | None:
    """Pull the upstream brief_id out of a pre-resolved artifact-contents map.

    The pipeline pre-resolver (wired by PR 93.3 cutover) puts the brief's
    YAML content into ``prior_outputs["artifact_contents"]["plan_authoring_brief.yaml"]``.
    Returns ``None`` if the brief isn't in prior_outputs (caller decides
    whether that's a hard failure or an empty-context proposer call).
    """
    if not prior_outputs:
        return None
    contents = prior_outputs.get("artifact_contents")
    if not isinstance(contents, dict):
        return None
    brief_yaml = contents.get("plan_authoring_brief.yaml")
    if not brief_yaml:
        return None
    try:
        from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief

        return PlanAuthoringBrief.from_yaml(brief_yaml).brief_id
    except ValueError:
        return None


def _format_planning_content(prior_outputs: dict[str, Any] | None) -> str:
    """Concatenate non-brief planning artifacts for the user-prompt context.

    Filters out the brief itself (surfaced separately as ``brief_content``)
    and the artifact_contents key. Renders remaining role outputs as
    Markdown sections so the proposer sees the framing artifacts as a
    single narrative.
    """
    if not prior_outputs:
        return "(no upstream framing artifacts)"
    parts: list[str] = []

    contents = prior_outputs.get("artifact_contents")
    if isinstance(contents, dict):
        for name, content in contents.items():
            if name == "plan_authoring_brief.yaml":
                continue
            parts.append(f"### {name}\n{content}")

    for key, value in prior_outputs.items():
        if key in ("artifact_contents",):
            continue
        if isinstance(value, dict) and "summary" in value:
            parts.append(f"### {key}\n{value['summary']}")

    return "\n\n".join(parts) if parts else "(no upstream framing artifacts)"


class _ProposeBaseHandler(_PlanningTaskHandler):
    """Shared shape for the three SIP-0093 proposer handlers.

    Subclasses pin ``_capability_id``, ``_role``, ``_request_template_id``,
    ``_proposer_role`` (the value that appears in ``proposing_role`` of the
    parsed artifact), and implement ``_parse_and_validate``. The base
    drives the retry loop, surfaces the parsed artifact on success, and
    emits a ``ProposalFailure`` artifact on exhaustion (RC-23).
    """

    _success_artifact_name: str = ""  # subclasses override
    _success_artifact_type: str = ""  # subclasses override
    _proposer_role: str = ""  # subclasses override — appears as proposing_role in YAML

    def _failure_artifact_name(self) -> str:
        # capability_id with dots → underscores, plus _failure.yaml — a
        # filename the merger can pattern-match without parsing.
        return self._capability_id.replace(".", "_") + "_failure.yaml"

    def _parse_and_validate(
        self,
        yaml_content: str | None,
        expected_brief_id: str | None,
    ) -> tuple[Any | None, str | None]:
        """Subclass-specific parse + validate.

        Returns ``(parsed_obj, error_msg)``. ``error_msg is None`` means
        accept; otherwise the message becomes corrective feedback for the
        next retry attempt.
        """
        raise NotImplementedError

    def _build_render_variables(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any],
    ) -> dict[str, str]:
        import uuid

        brief_content = "(brief not yet provided — direct-invocation context)"
        if prior_outputs:
            contents = prior_outputs.get("artifact_contents")
            if isinstance(contents, dict):
                brief_content = contents.get("plan_authoring_brief.yaml", brief_content)

        brief_id = _extract_brief_id_from_prior_outputs(prior_outputs) or "(unknown)"
        proposal_id = inputs.get("proposal_id") or f"prop-{uuid.uuid4().hex[:8]}"

        profile_roles = inputs.get("profile_roles") or []
        roles_section = ""
        if profile_roles:
            roles_section = f"## Available roles in this squad\n\n{', '.join(profile_roles)}\n\n"

        builder_section = ""
        if "builder" in profile_roles and self._role != "builder":
            builder_section = (
                "## Builder role present\n\n"
                "This squad includes a dedicated builder role. Do NOT propose "
                "packaging, requirements files, Dockerfile, startup scripts, "
                "or qa_handoff.md tasks — those are the builder's domain. "
                "Reference builder tasks via ``depends_on_focus`` if your "
                "tasks need their outputs.\n\n"
            )

        return {
            "brief_content": brief_content,
            "planning_content": _format_planning_content(prior_outputs),
            "proposal_id": proposal_id,
            "source_brief_id": brief_id,
            "prd": prd,
            "roles_section": roles_section,
            "builder_section": builder_section,
            # Generated from CHECK_SPECS so the proposer sees exact param names
            # + a parser-valid example per check (issue #182 — was "", which let
            # models guess param names and fail count_at_least validation).
            "typed_acceptance_vocabulary": render_typed_acceptance_vocabulary(),
        }

    async def _bind_criteria_section(self, renderer: Any, inputs: dict[str, Any]) -> str:
        """The *bind, don't author* instruction + contract criteria index, or ""
        (SIP-0098 98.3).

        Non-empty ONLY in bind mode — a contract is seeded, so the executor injected
        ``contract_criteria_index`` into this proposer's inputs — and only for the dev/qa
        proposers that author build tasks (strategy proposes guidance, not tasks). The
        instruction prose lives in a managed asset (``request.plan_bind_criteria_appendix``);
        only the index *data* is a variable (CLAUDE.md #448). Absent contract → "" →
        today's author-mode proposer prompt exactly."""
        if self._proposer_role not in ("development", "qa"):
            return ""
        index = inputs.get("contract_criteria_index")
        if not index:
            return ""
        rendered = await renderer.render(
            "request.plan_bind_criteria_appendix", {"criteria_index": index}
        )
        return rendered.content

    async def _frozen_surface_section(self, renderer: Any, inputs: dict[str, Any]) -> str:
        """What the scaffold-frozen files declare, or "" (pf-42).

        The criteria index above names the fill slots only — four files of seventeen on
        the group_run skeleton. The other thirteen are frozen, and nothing told the
        proposer they exist, so a check it wanted on one was written against an invented
        interior (``RunEvent.meeting_location`` for the declared ``location``;
        ``backend.routes`` for a module that imports ``.routes``). Neither could pass and
        neither could be repaired — a frozen emission is restored before the check
        re-runs — so the plan was unwinnable before dispatch.

        Same conditions as the bind section: bind mode only, dev/qa proposers only. The
        index *data* is injected by the executor; the instruction prose is a managed
        asset (CLAUDE.md #448). No index → "" → today's proposer prompt exactly.
        """
        if self._proposer_role not in ("development", "qa"):
            return ""
        index = inputs.get("frozen_surface_index")
        if not index:
            return ""
        rendered = await renderer.render(
            "request.plan_frozen_surface_appendix", {"frozen_surface_index": index}
        )
        return rendered.content

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        from squadops.capabilities.handlers._plan_authoring import retry_yaml_call

        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")
        resolved_config = inputs.get("resolved_config", {})
        expected_brief_id = _extract_brief_id_from_prior_outputs(prior_outputs)

        # Render user prompt via the registered template (SIP-0084).
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            # No renderer in test contexts: emit a structured failure rather
            # than constructing an inline duplicate. This handler family is
            # new (PR 93.2) — tests inject a renderer mock, no migration
            # baggage to accommodate.
            return self._build_failure_result(
                start_time,
                inputs,
                "llm_error",
                f"{self._handler_name} requires request_renderer port",
            )

        variables = self._build_render_variables(prd, prior_outputs, inputs)
        # SIP-0098 98.3: in bind mode the dev/qa proposer is told to bind the contract's
        # covered-file criteria by id (not author them). Data-driven — only set when the
        # executor injected the criteria index (contract seeded) — and the instruction is
        # a managed asset, not an inline literal (#448). Only set when non-empty so a
        # non-bind render doesn't warn on an unknown variable.
        bind_criteria_section = await self._bind_criteria_section(renderer, inputs)
        if bind_criteria_section:
            variables["bind_criteria_section"] = bind_criteria_section
        # pf-42: the same bind-mode prompt names the fill slots but not the frozen files,
        # so checks aimed at those were written against an invented interior. Data-driven
        # and managed-asset prose, exactly like the section above.
        frozen_surface_section = await self._frozen_surface_section(renderer, inputs)
        if frozen_surface_section:
            variables["frozen_surface_section"] = frozen_surface_section
        # #686: the plan-shape rules the deterministic validators enforce. No input
        # to key on — they hold for every plan, so this one renders unconditionally.
        variables["authoring_rules_section"] = await self._authoring_rules_section(renderer)
        # #669: on a framing re-roll, the prior attempt's rejection — revise,
        # don't re-dice. Data-driven and managed-asset prose, exactly like the
        # sections above; a first-roll framing has no input and renders nothing.
        rejection_section = await self._rejection_context_section(renderer, inputs)
        if rejection_section:
            variables["rejection_context_section"] = rejection_section
        rendered = await renderer.render(self._request_template_id, variables)
        user_prompt = rendered.content

        assembled = context.ports.prompt_service.assemble(
            role=self._role,
            hook="agent_start",
            task_type=self._capability_id,
        )
        system_prompt = assembled.content

        max_attempts = int(
            resolved_config.get("proposal_max_attempts", _PROPOSAL_MAX_ATTEMPTS_DEFAULT)
        )
        chat_kwargs = self._build_chat_kwargs(inputs)

        def parse_and_validate(yaml_or_none: str | None) -> tuple[Any | None, str | None]:
            return self._parse_and_validate(yaml_or_none, expected_brief_id)

        parsed, last_yaml, last_error = await retry_yaml_call(
            llm=context.ports.llm,
            chat_kwargs=chat_kwargs,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            parse_and_validate=parse_and_validate,
            max_attempts=max_attempts,
            handler_name=self._handler_name,
        )

        if parsed is None:
            failure_reason = self._classify_failure(last_error, last_yaml)
            return self._build_failure_result(
                start_time,
                inputs,
                failure_reason,
                last_error or "exhausted retry budget without parseable output",
            )

        return self._build_success_result(start_time, inputs, last_yaml or "")

    def _classify_failure(self, last_error: str | None, last_yaml: str | None) -> str:
        """Map the retry loop's last error to a ProposalFailure failure_reason."""
        if not last_error:
            return "malformed_yaml" if not last_yaml else "schema_validation_error"
        lowered = last_error.lower()
        if "brief" in lowered and "mismatch" in lowered:
            return "mismatched_brief_id"
        if "malformed" in lowered or "yaml" in lowered:
            return "malformed_yaml"
        if last_yaml is None:
            return "malformed_yaml"
        return "schema_validation_error"

    def _build_success_result(
        self,
        start_time: float,
        inputs: dict[str, Any],
        yaml_content: str,
    ) -> HandlerResult:
        # The merger consumes this via prior_outputs (PR 93.3). The cycle
        # executor strips "artifacts" from prior_outputs by design, so we
        # surface the YAML content under a non-artifacts key the merger
        # reads by role.
        proposal_outcome: dict[str, Any] = {
            "status": "success",
            "proposing_role": self._proposer_role,
            "yaml_content": yaml_content,
            "artifact_name": self._success_artifact_name,
        }
        outputs = {
            "summary": f"[{self._role}] proposal produced for {self._capability_id}",
            "role": self._role,
            "artifacts": [
                {
                    "name": self._success_artifact_name,
                    "content": yaml_content,
                    "media_type": "text/yaml",
                    "type": self._success_artifact_type,
                },
            ],
            "proposal_outcome": proposal_outcome,
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )
        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)

    def _build_failure_result(
        self,
        start_time: float,
        inputs: dict[str, Any],
        failure_reason: str,
        details: str,
    ) -> HandlerResult:
        """Emit a ProposalFailure artifact (RC-23) — the cycle continues.

        Returns ``HandlerResult(success=True, ...)`` so the cycle pipeline
        keeps moving and the merger gets a chance to read this artifact.
        The "failure" is captured inside the artifact, not at the
        HandlerResult layer.
        """
        from squadops.cycles.proposal_failure import ProposalFailure

        failure = ProposalFailure(
            proposer_role=self._proposer_role,
            failure_reason=failure_reason,
            details=details,
        )
        failure_yaml = failure.to_yaml()
        outputs = {
            "summary": (
                f"[{self._role}] proposal failed ({failure_reason}) — "
                f"failure record emitted for merger"
            ),
            "role": self._role,
            "artifacts": [
                {
                    "name": self._failure_artifact_name(),
                    "content": failure_yaml,
                    "media_type": "text/yaml",
                    "type": "proposal_failure",
                },
            ],
            # PR 93.3 wire: the merger reads this from prior_outputs by role.
            "proposal_outcome": {
                "status": "failure",
                "proposing_role": self._proposer_role,
                "yaml_content": failure_yaml,
                "artifact_name": self._failure_artifact_name(),
                "failure_reason": failure_reason,
            },
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )
        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)


class DevelopmentProposePlanTasksHandler(_ProposeBaseHandler):
    """SIP-0093 PR 93.2: development-domain plan-task proposer."""

    _handler_name = "development_propose_plan_tasks_handler"
    _capability_id = "development.propose_plan_tasks"
    _role = "dev"
    _request_template_id = "request.development_propose_plan_tasks"
    _success_artifact_name = "proposed_plan_tasks.yaml"
    _success_artifact_type = "proposed_plan_tasks"
    _proposer_role = "development"

    def _parse_and_validate(
        self,
        yaml_content: str | None,
        expected_brief_id: str | None,
    ) -> tuple[Any | None, str | None]:
        from squadops.cycles.proposed_role_tasks import ProposedRoleTasks

        if yaml_content is None:
            return (
                None,
                "No fenced YAML block found. Emit your proposal in a ```yaml:proposed_plan_tasks.yaml``` block.",
            )
        try:
            proposal = ProposedRoleTasks.from_yaml(yaml_content)
        except ValueError as exc:
            return None, f"proposed_plan_tasks.yaml failed to parse: {exc}"
        if expected_brief_id and proposal.source_brief_id != expected_brief_id:
            return None, (
                f"brief_id mismatch: proposal cites {proposal.source_brief_id!r}, "
                f"upstream brief is {expected_brief_id!r}. Use the upstream brief_id verbatim."
            )
        if proposal.proposing_role not in ("development", "dev"):
            return None, (
                f"proposing_role must be 'development' for this handler, "
                f"got {proposal.proposing_role!r}"
            )
        return proposal, None


class QaProposePlanTasksHandler(_ProposeBaseHandler):
    """SIP-0093 PR 93.2: qa-domain plan-task proposer."""

    _handler_name = "qa_propose_plan_tasks_handler"
    _capability_id = "qa.propose_plan_tasks"
    _role = "qa"
    _request_template_id = "request.qa_propose_plan_tasks"
    _success_artifact_name = "proposed_plan_tasks.yaml"
    _success_artifact_type = "proposed_plan_tasks"
    _proposer_role = "qa"

    def _parse_and_validate(
        self,
        yaml_content: str | None,
        expected_brief_id: str | None,
    ) -> tuple[Any | None, str | None]:
        from squadops.cycles.proposed_role_tasks import ProposedRoleTasks

        if yaml_content is None:
            return (
                None,
                "No fenced YAML block found. Emit your proposal in a ```yaml:proposed_plan_tasks.yaml``` block.",
            )
        try:
            proposal = ProposedRoleTasks.from_yaml(yaml_content)
        except ValueError as exc:
            return None, f"proposed_plan_tasks.yaml failed to parse: {exc}"
        if expected_brief_id and proposal.source_brief_id != expected_brief_id:
            return None, (
                f"brief_id mismatch: proposal cites {proposal.source_brief_id!r}, "
                f"upstream brief is {expected_brief_id!r}. Use the upstream brief_id verbatim."
            )
        if proposal.proposing_role != "qa":
            return None, (
                f"proposing_role must be 'qa' for this handler, got {proposal.proposing_role!r}"
            )
        return proposal, None


class StrategyProposePlanGuidanceHandler(_ProposeBaseHandler):
    """SIP-0093 PR 93.2: strategy plan-authoring guidance proposer."""

    _handler_name = "strategy_propose_plan_guidance_handler"
    _capability_id = "strategy.propose_plan_guidance"
    _role = "strat"
    _request_template_id = "request.strategy_propose_plan_guidance"
    _success_artifact_name = "plan_guidance.yaml"
    _success_artifact_type = "plan_guidance"
    _proposer_role = "strategy"

    def _build_render_variables(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any],
    ) -> dict[str, str]:
        # #484: strategy emits PlanGuidance (guidance_id), not a ProposedRoleTasks
        # (proposal_id), so its request template requires a `guidance_id` the shared
        # proposer base never provides — the strategy proposer crashed with
        # TemplateMissingVariableError on every multi-role cycle. Supply one, mirroring
        # the base's proposal_id generation.
        import uuid

        variables = super()._build_render_variables(prd, prior_outputs, inputs)
        variables["guidance_id"] = str(inputs.get("guidance_id") or f"guid-{uuid.uuid4().hex[:8]}")
        return variables

    def _parse_and_validate(
        self,
        yaml_content: str | None,
        expected_brief_id: str | None,
    ) -> tuple[Any | None, str | None]:
        from squadops.cycles.plan_guidance import PlanGuidance

        if yaml_content is None:
            return (
                None,
                "No fenced YAML block found. Emit your guidance in a ```yaml:plan_guidance.yaml``` block.",
            )
        try:
            guidance = PlanGuidance.from_yaml(yaml_content)
        except ValueError as exc:
            return None, f"plan_guidance.yaml failed to parse: {exc}"
        if expected_brief_id and guidance.source_brief_id != expected_brief_id:
            return None, (
                f"brief_id mismatch: guidance cites {guidance.source_brief_id!r}, "
                f"upstream brief is {expected_brief_id!r}. Use the upstream brief_id verbatim."
            )
        return guidance, None
