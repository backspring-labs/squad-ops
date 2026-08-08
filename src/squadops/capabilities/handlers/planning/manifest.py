"""The interface-manifest authoring stage (#791, M1 — SIP-0103 §3.1).

The squad writes its own interface manifest instead of binding one an operator seeded.

Placement is the whole design decision. SIP-0099 99.2 already emitted a manifest, bolted
onto the dev *proposer* as a second fenced block beside its plan tasks — §5a's
"least-informed moment", with no gate and no revision. This stage relocates that work to
the point where dev has the PRD, data's research, strategy's frame and its own technical
design, gives it the deterministic gates as an in-stage verdict, and lets it revise. The
old path is removed rather than left beside this one: two emitters of the same artifact is
a dual path, and the merger's fallback made *which* one won depend on proposer ordering.

Two budgets, at their existing seams (§5b Q4): ``manifest_max_attempts`` buys revisions
inside this task — cheap, the model still holds its own draft — and a manifest that
exhausts them is emitted anyway so the framing gate can reject it into a
``framing_max_rerolls`` re-roll. Failing the task instead would spend a whole framing
workload to produce nothing a human or the taxonomy could read.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import HandlerEvidence, HandlerResult
from squadops.capabilities.handlers.planning.base import _PlanningTaskHandler
from squadops.cycles.authoring_failure import AuthoringOutcome, assess_authoring_outcome
from squadops.cycles.contract_derivation import SEEDED_MANIFEST_FILENAME
from squadops.cycles.manifest_authoring import (
    AUTHOR_MANIFEST_CAPABILITY,
    AUTHOR_MANIFEST_ROLE,
    MANIFEST_ARTIFACT_TYPE,
)

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)

#: Matches ``PlanAuthoringService``'s default so the two authoring stages spend the same
#: budget when a profile configures neither (the validated profiles set 4).
_MANIFEST_MAX_ATTEMPTS_DEFAULT = 2


class DevelopmentAuthorManifestHandler(_PlanningTaskHandler):
    """Framing handler: author ``interface_manifest.yaml``, revising against the gates."""

    _handler_name = "development_author_manifest_handler"
    _capability_id = AUTHOR_MANIFEST_CAPABILITY
    _role = AUTHOR_MANIFEST_ROLE
    _artifact_name = SEEDED_MANIFEST_FILENAME
    _request_template_id = "request.development_author_manifest"

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        from squadops.capabilities.handlers._plan_authoring import retry_yaml_call

        start_time = time.perf_counter()

        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return self._failure(
                start_time, inputs, f"{self._handler_name} requires request_renderer port"
            )

        resolved_config = inputs.get("resolved_config") or {}
        stack = str(resolved_config.get("build_profile") or "")

        variables = self._build_render_variables(
            inputs.get("prd", ""), inputs.get("prior_outputs"), inputs
        )
        variables["stack"] = stack
        # #686's binding, one level up: the gates' author-facing rules are a managed asset
        # keyed to the proof constants, so a proof cannot be added without a decision about
        # whether the author is told. Unconditional — every rule holds for every manifest.
        variables["authoring_rules_section"] = (
            await renderer.render("request.manifest_authoring_rules_appendix", {})
        ).content
        rejection_section = await self._rejection_context_section(renderer, inputs)
        if rejection_section:
            variables["rejection_context_section"] = rejection_section

        rendered = await renderer.render(self._request_template_id, variables)
        assembled = context.ports.prompt_service.assemble(
            role=self._role, hook="agent_start", task_type=self._capability_id
        )

        outcomes: list[AuthoringOutcome] = []

        async def parse_and_validate(yaml_or_none: str | None) -> tuple[str | None, str | None]:
            if not yaml_or_none or not yaml_or_none.strip():
                return None, (
                    f"No `{SEEDED_MANIFEST_FILENAME}` block was found in your response. "
                    f"Emit exactly one fenced block whose header carries that filename."
                )
            outcome = assess_authoring_outcome(yaml_or_none)
            outcomes.append(outcome)
            if not outcome.rejected:
                return yaml_or_none, None
            feedback = await renderer.render(
                "request.manifest_revision_feedback",
                {"findings": _findings_lines(outcome)},
            )
            return None, feedback.content

        accepted, last_yaml, last_error = await retry_yaml_call(
            llm=context.ports.llm,
            chat_kwargs=self._build_chat_kwargs(inputs),
            system_prompt=assembled.content,
            user_prompt=rendered.content,
            parse_and_validate=parse_and_validate,
            max_attempts=int(
                resolved_config.get("manifest_max_attempts", _MANIFEST_MAX_ATTEMPTS_DEFAULT)
            ),
            handler_name=self._handler_name,
        )

        content = accepted or last_yaml
        if not content:
            # Nothing to hand forward. Distinct from an unwinnable manifest: there is no
            # document for the gate to reject or for M6 to classify.
            return self._failure(
                start_time,
                inputs,
                last_error or "exhausted the revision budget without emitting a manifest",
            )

        outcome = outcomes[-1] if outcomes else AuthoringOutcome()
        if accepted is None:
            # Emitted deliberately (see the module docstring): the framing gate owns
            # acceptance, and a rejected manifest in hand is what makes the rejection
            # readable — to the operator, and to the taxonomy that has to attribute it.
            logger.warning(
                "%s: revision budget exhausted with the manifest still failing its gates "
                "(%s) — emitting it for the framing gate to reject",
                self._handler_name,
                outcome.class_counts(),
            )

        return self._success(start_time, inputs, content, outcome, assembled, rendered)

    # -- results ------------------------------------------------------------------

    def _success(
        self,
        start_time: float,
        inputs: dict[str, Any],
        content: str,
        outcome: AuthoringOutcome,
        assembled: Any,
        rendered: Any,
    ) -> HandlerResult:
        outputs: dict[str, Any] = {
            "summary": f"[{self._role}] {_summary(outcome)}",
            "role": self._role,
            "artifacts": [
                {
                    "name": SEEDED_MANIFEST_FILENAME,
                    "content": content,
                    "media_type": "text/yaml",
                    "type": MANIFEST_ARTIFACT_TYPE,
                }
            ],
            # M6's second consumer: the class counts a window accumulates. Data on the
            # outcome, not a second artifact — provenance stamping is M5's.
            "authoring_outcome": {
                "gates_passed": not outcome.rejected,
                "class_counts": outcome.class_counts(),
                "open_questions": list(outcome.open_questions),
            },
            "prompt_provenance": {
                "system_prompt_bundle_hash": assembled.assembly_hash,
                "request_template_id": rendered.template_id,
                "request_template_version": rendered.template_version,
                "request_render_hash": rendered.render_hash,
                "prompt_environment": "production",
            },
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        return HandlerResult(
            success=True,
            outputs=outputs,
            _evidence=HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
                outputs_hash=self._hash_dict(outputs),
            ),
        )

    def _failure(self, start_time: float, inputs: dict[str, Any], error: str) -> HandlerResult:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.warning("%s: %s", self._handler_name, error)
        return HandlerResult(
            success=False,
            outputs={},
            _evidence=HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            ),
            error=error,
        )


def _findings_lines(outcome: AuthoringOutcome) -> str:
    """The gates' findings as revision instructions — every finding, not the first.

    All of them, because one-defect-per-attempt would spend the whole revision budget on a
    manifest that had three (the same reason ``assess_winnability`` accumulates rather than
    short-circuits).
    """
    return "\n".join(f"- **{f.proof}** — {f.detail}" for f in outcome.findings)


def _summary(outcome: AuthoringOutcome) -> str:
    """The chained summary — the only cross-task context that survives artifact stripping."""
    if outcome.rejected:
        return f"interface manifest emitted but rejected by its gates: {outcome.class_counts()}"
    if outcome.open_questions:
        return (
            f"interface manifest authored; {len(outcome.open_questions)} question(s) "
            f"left unresolved for review"
        )
    return "interface manifest authored and passing both gates"
