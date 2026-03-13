"""Repair task handlers — LLM-powered handlers for pulse verification repair loop.

4 handlers forming the repair chain invoked when a pulse boundary check fails.
Each extends ``_CycleTaskHandler`` with role-specific prompts that inject
verification failure context from ``inputs["verification_context"]``.

Part of SIP-0070 Phase 3.
"""

from __future__ import annotations

from typing import Any

from squadops.capabilities.handlers.cycle_tasks import _CycleTaskHandler


class _RepairTaskHandler(_CycleTaskHandler):
    """Base for repair handlers — injects verification failure context."""

    _request_template_id = "request.repair_task_base"

    def _build_render_variables(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any],
    ) -> dict[str, str]:
        """Build template variables with verification context extraction."""
        verification_ctx = (prior_outputs or {}).get("verification_context", "")
        verification_section = ""
        if verification_ctx:
            verification_section = (
                f"\n\n## Verification Failure Context\n\n{verification_ctx}"
            )

        upstream = {
            k: v for k, v in (prior_outputs or {}).items() if k != "verification_context"
        }
        return {
            "prd": prd,
            "role": self._role,
            "verification_context": verification_section,
            "prior_outputs": self._format_prior_outputs(upstream or None),
        }

    def _build_user_prompt(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
    ) -> str:
        """Assemble prompt with PRD, verification context, and upstream outputs."""
        parts = [f"## Product Requirements Document\n\n{prd}"]

        # Inject verification failure context (passed by executor)
        verification_ctx = (prior_outputs or {}).get("verification_context", "")
        if verification_ctx:
            parts.append(f"\n\n## Verification Failure Context\n\n{verification_ctx}")

        # Include upstream repair-chain outputs (not the verification_context key)
        if prior_outputs:
            upstream = {k: v for k, v in prior_outputs.items() if k != "verification_context"}
            if upstream:
                parts.append("\n\n## Prior Analysis from Upstream Roles\n")
                for role, summary in upstream.items():
                    parts.append(f"### {role}\n{summary}\n")

        parts.append(f"\nPlease provide your {self._role} analysis and deliverables.")
        return "\n".join(parts)


class DataAnalyzeVerificationHandler(_RepairTaskHandler):
    """Analyze verification failures and extract actionable data patterns."""

    _handler_name = "data_analyze_verification_handler"
    _capability_id = "data.analyze_verification"
    _role = "data"
    _artifact_name = "verification_analysis.md"


class GovernanceRootCauseHandler(_RepairTaskHandler):
    """Perform root cause analysis on verification failures."""

    _handler_name = "governance_root_cause_handler"
    _capability_id = "governance.root_cause_analysis"
    _role = "lead"
    _artifact_name = "root_cause_analysis.md"


class StrategyCorrectivePlanHandler(_RepairTaskHandler):
    """Produce a corrective action plan from root cause analysis."""

    _handler_name = "strategy_corrective_plan_handler"
    _capability_id = "strategy.corrective_plan"
    _role = "strat"
    _artifact_name = "corrective_plan.md"


class DevelopmentRepairHandler(_RepairTaskHandler):
    """Execute corrective repairs based on the corrective plan."""

    _handler_name = "development_repair_handler"
    _capability_id = "development.repair"
    _role = "dev"
    _artifact_name = "repair_output.md"
