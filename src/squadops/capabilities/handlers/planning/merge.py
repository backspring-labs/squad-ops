"""Plan-merger handler (#331 split from planning_tasks.py).

``governance.merge_plan`` (SIP-0093 PR 93.3) — deterministic merger of the
role proposals into ``implementation_plan.yaml`` + ``merge_decisions.yaml``,
with the sole-author fallback.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.cycle import _CycleTaskHandler

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

# ---------------------------------------------------------------------------
# Merger handler (SIP-0093 PR 93.3) — the cutover. Runtime route changes here:
# governance.review_plan no longer authors implementation_plan.yaml; the
# merger does, consuming proposer artifacts via prior_outputs[role][...].
#
# Pure-deterministic per §5.8 (no LLM call). Falls back to
# PlanAuthoringService.produce_plan(...) when no proposals are available
# (configured or degraded sole-author).
# ---------------------------------------------------------------------------


class GovernanceMergePlanHandler(_CycleTaskHandler):
    """SIP-0093 PR 93.3: deterministic merger of role proposals.

    Consumes:
      - ``plan_authoring_brief.yaml`` (read-only — RC-22). Surfaced via
        ``prior_outputs["lead"]["brief_outcome"]["yaml_content"]``.
      - Proposer outcomes via ``prior_outputs[role]["proposal_outcome"]``
        for each contributor role (dev, qa, strat). Outcomes carry
        ``status: success | failure`` and the YAML content; the merger
        parses success records into ``ProposedRoleTasks`` /
        ``PlanGuidance`` and translates failures into ``MissingProposal``
        entries for ``merge_decisions.yaml``.
      - The configured contributors list via
        ``inputs["resolved_config"]["plan_authoring_contributors"]``.
        Drives the §5.9 missing-role operator warnings and the
        configured-vs-degraded distinction in sole-author mode.

    Produces (always two artifacts):
      - ``implementation_plan.yaml`` — canonical SIP-0092 M1 plan.
      - ``merge_decisions.yaml`` — auditable record with
        ``authoring_mode`` / ``sole_author_reason`` / ``proposal_completeness``
        per RC-26.

    Sole-author fallback: when no proposals are available (empty
    contributors list, or all configured proposals failed), the merger
    calls ``PlanAuthoringService.produce_plan(...)`` directly with the
    brief and the framing-tail planning_content concatenated. The same
    handler chain runs regardless of authoring mode — only the content
    inside ``merge_decisions.yaml`` differs.
    """

    _handler_name = "governance_merge_plan_handler"
    _capability_id = "governance.merge_plan"
    _role = "lead"

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        start_time = time.perf_counter()

        from squadops.capabilities.handlers._plan_merger import (
            build_sole_author_decisions,
            emit_merge_decisions_yaml,
            emit_plan_yaml,
            merge_proposals,
        )
        from squadops.cycles.merge_decisions import MissingProposal
        from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief
        from squadops.cycles.plan_guidance import PlanGuidance
        from squadops.cycles.proposed_role_tasks import ProposedRoleTasks

        prior_outputs = inputs.get("prior_outputs") or {}
        resolved_config = inputs.get("resolved_config") or {}
        configured_contributors = list(resolved_config.get("plan_authoring_contributors") or [])

        # Brief is mandatory upstream — without it the merger has no
        # contract to anchor proposals against. Fail loudly if absent
        # (this is a wiring bug, not a recoverable runtime condition).
        brief_outcome = prior_outputs.get("lead", {}).get("brief_outcome")
        if not brief_outcome or not brief_outcome.get("yaml_content"):
            return self._failure_result(
                start_time,
                inputs,
                "governance.merge_plan requires plan_authoring_brief.yaml in "
                "prior_outputs['lead']['brief_outcome']",
            )
        try:
            brief = PlanAuthoringBrief.from_yaml(brief_outcome["yaml_content"])
        except ValueError as exc:
            return self._failure_result(
                start_time,
                inputs,
                f"plan_authoring_brief.yaml failed to parse at merger: {exc}",
            )

        # Read each role's proposal outcome. Absent role-key (e.g. dev
        # not in contributors) is distinct from present-but-failed
        # (degraded mode tracking). Both yield a None proposal but only
        # the latter contributes to missing_proposals.
        dev_outcome = prior_outputs.get("dev", {}).get("proposal_outcome")
        qa_outcome = prior_outputs.get("qa", {}).get("proposal_outcome")
        strat_outcome = prior_outputs.get("strat", {}).get("proposal_outcome")

        dev_proposal, dev_missing = self._parse_proposal_outcome(
            dev_outcome, "development", ProposedRoleTasks
        )
        qa_proposal, qa_missing = self._parse_proposal_outcome(qa_outcome, "qa", ProposedRoleTasks)
        strategy_guidance, strat_missing = self._parse_proposal_outcome(
            strat_outcome, "strategy", PlanGuidance
        )

        missing_proposals: list[MissingProposal] = []
        for entry in (dev_missing, qa_missing, strat_missing):
            if entry is not None:
                missing_proposals.append(entry)

        successful_count = sum(
            1 for p in (dev_proposal, qa_proposal, strategy_guidance) if p is not None
        )

        prd = inputs.get("prd", "")
        prd_hash = inputs.get("config_hash") or ""
        project_id = getattr(context, "project_id", None) or "(unknown)"
        cycle_id = getattr(context, "cycle_id", None) or "(unknown)"

        if successful_count == 0:
            return await self._handle_sole_author(
                start_time=start_time,
                inputs=inputs,
                context=context,
                brief=brief,
                missing_proposals=missing_proposals,
                configured_contributors=configured_contributors,
                project_id=project_id,
                cycle_id=cycle_id,
                prd=prd,
                prd_hash=prd_hash,
                prior_outputs=prior_outputs,
                build_sole_author_decisions=build_sole_author_decisions,
                emit_plan_yaml=emit_plan_yaml,
                emit_merge_decisions_yaml=emit_merge_decisions_yaml,
            )

        plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=qa_proposal,
            strategy_guidance=strategy_guidance,
            project_id=project_id,
            cycle_id=cycle_id,
            prd_hash=prd_hash,
            configured_contributors=configured_contributors,
            missing_proposals=missing_proposals,
        )

        return self._success_result(
            start_time,
            inputs,
            plan_yaml=emit_plan_yaml(plan),
            decisions_yaml=emit_merge_decisions_yaml(decisions),
            authoring_mode=decisions.authoring_mode,
            interface_manifest_yaml=self._read_interface_manifest(prior_outputs),
        )

    @staticmethod
    def _read_interface_manifest(prior_outputs: dict[str, Any]) -> str | None:
        """Raw ``interface_manifest.yaml`` a framing proposer emitted (dev preferred, qa
        fallback), or ``None`` (SIP-0099 99.2). Data-driven: absence = today's behavior,
        no flag."""
        for role_key in ("dev", "qa"):
            outcome = (prior_outputs.get(role_key) or {}).get("proposal_outcome") or {}
            raw = outcome.get("interface_manifest_yaml")
            if raw:
                return raw
        return None

    def _parse_proposal_outcome(
        self,
        outcome: dict[str, Any] | None,
        proposer_role: str,
        schema_cls: Any,
    ) -> tuple[Any | None, Any]:
        """Parse a proposer outcome into (parsed_object, MissingProposal | None).

        Returns the parsed proposal/guidance on success (no MissingProposal
        entry). On failure outcome OR malformed outcome: returns (None,
        MissingProposal) so the merger can record the gap. Absent outcome
        (proposer not in pipeline) returns (None, None) — neither parsed
        content nor a missing-role entry.
        """
        from squadops.cycles.merge_decisions import MissingProposal
        from squadops.cycles.proposal_failure import ProposalFailure

        if not outcome:
            return None, None

        status = outcome.get("status")
        if status == "failure":
            reason = outcome.get("failure_reason") or "unknown"
            details = ""
            yaml_content = outcome.get("yaml_content")
            if yaml_content:
                try:
                    parsed_failure = ProposalFailure.from_yaml(yaml_content)
                    reason = parsed_failure.failure_reason
                    details = parsed_failure.details
                except ValueError:
                    details = "proposal_failure artifact malformed"
            return None, MissingProposal(
                role=proposer_role,
                failure_reason=f"{reason}{(': ' + details) if details else ''}"[:256],
            )

        yaml_content = outcome.get("yaml_content")
        if not yaml_content:
            return None, MissingProposal(
                role=proposer_role,
                failure_reason="malformed_yaml: outcome carried no yaml_content",
            )

        try:
            parsed = schema_cls.from_yaml(yaml_content)
        except ValueError as exc:
            return None, MissingProposal(
                role=proposer_role,
                failure_reason=f"schema_validation_error: {exc}"[:256],
            )

        return parsed, None

    async def _handle_sole_author(
        self,
        *,
        start_time: float,
        inputs: dict[str, Any],
        context: ExecutionContext,
        brief: Any,
        missing_proposals: list[Any],
        configured_contributors: list[str],
        project_id: str,
        cycle_id: str,
        prd: str,
        prd_hash: str,
        prior_outputs: dict[str, Any],
        build_sole_author_decisions: Any,
        emit_plan_yaml: Any,
        emit_merge_decisions_yaml: Any,
    ) -> HandlerResult:
        """Sole-author fallback: delegate to PlanAuthoringService.

        Two sub-cases per §5.10:
          - ``no_contributors_configured`` — empty contributors list.
          - ``all_proposals_failed`` — non-empty contributors, all failed.
        The split is determined by whether missing_proposals is empty (no
        failures were recorded) or populated (every configured role
        failed).
        """
        from squadops.capabilities.handlers._plan_authoring_service import (
            produce_plan,
        )
        from squadops.cycles.implementation_plan import ImplementationPlan

        sole_author_reason = (
            "no_contributors_configured" if not configured_contributors else "all_proposals_failed"
        )

        planning_content = self._build_planning_content_from_framing(prior_outputs)

        manifest = await produce_plan(
            context,
            inputs,
            planning_content=planning_content,
            resolved_config=inputs.get("resolved_config", {}),
            role=self._role,
            handler_name=self._handler_name,
            chat_kwargs=self._build_chat_kwargs(inputs),
        )

        if manifest is None:
            return self._failure_result(
                start_time,
                inputs,
                "sole-author fallback exhausted PlanAuthoringService retry budget",
            )

        plan = ImplementationPlan.from_yaml(manifest["content"])
        decisions = build_sole_author_decisions(
            brief=brief,
            cycle_id=cycle_id,
            sole_author_reason=sole_author_reason,
            canonical_tasks=list(plan.tasks),
            missing_proposals=missing_proposals,
        )
        return self._success_result(
            start_time,
            inputs,
            plan_yaml=emit_plan_yaml(plan),
            decisions_yaml=emit_merge_decisions_yaml(decisions),
            authoring_mode="sole_author",
            # sole-author path: the interface manifest, if any, rides produce_plan's
            # return (SIP-0099 99.2).
            interface_manifest_yaml=manifest.get("interface_manifest_yaml"),
        )

    def _build_planning_content_from_framing(
        self,
        prior_outputs: dict[str, Any],
    ) -> str:
        """Concatenate the four framing-tail role outputs for sole-author fallback.

        ``PlanAuthoringService.produce_plan`` expects a ``planning_content``
        string that historically came from ``governance.review_plan``'s
        consolidated planning artifact. Post-cutover, the planning artifact
        is produced AFTER the merger (in review_plan's sign-off step), so
        the merger has to assemble its own context from the framing tail.
        """
        parts: list[str] = []
        for role_key in ("data", "strat", "dev", "qa"):
            slot = prior_outputs.get(role_key) or {}
            summary = slot.get("summary")
            if summary:
                parts.append(f"## {role_key} output\n\n{summary}")
        return "\n\n".join(parts) if parts else "(no framing context available)"

    def _success_result(
        self,
        start_time: float,
        inputs: dict[str, Any],
        *,
        plan_yaml: str,
        decisions_yaml: str,
        authoring_mode: str,
        interface_manifest_yaml: str | None = None,
    ) -> HandlerResult:
        artifacts: list[dict[str, Any]] = [
            {
                "name": "implementation_plan.yaml",
                "content": plan_yaml,
                "media_type": "text/yaml",
                "type": "control_implementation_plan",
            },
            {
                "name": "merge_decisions.yaml",
                "content": decisions_yaml,
                "media_type": "text/yaml",
                "type": "merge_decisions",
            },
        ]
        # SIP-0099 99.2: the framing-authored interface manifest rides alongside the plan
        # as a sibling artifact — surfaced in the gate package for operator review and
        # loaded by the executor (99.3). Emitted only when a proposer/sole-author authored
        # one; absent → the artifact set is byte-identical to today. The merger does NOT
        # validate it — that is net-b's job (dispatched_flow_executor), keeping emission
        # and validation cleanly separated.
        if interface_manifest_yaml:
            artifacts.append(
                {
                    "name": "interface_manifest.yaml",
                    "content": interface_manifest_yaml,
                    "media_type": "text/yaml",
                    "type": "interface_manifest",
                }
            )
        outputs = {
            "summary": f"[{self._role}] merged plan produced ({authoring_mode})",
            "role": self._role,
            "artifacts": artifacts,
            # Surfaced for review_plan's sign-off and the gate package.
            "merge_outcome": {
                "authoring_mode": authoring_mode,
                "plan_yaml": plan_yaml,
                "decisions_yaml": decisions_yaml,
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

    def _failure_result(
        self,
        start_time: float,
        inputs: dict[str, Any],
        error: str,
    ) -> HandlerResult:
        duration_ms = (time.perf_counter() - start_time) * 1000
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
            error=error,
        )
