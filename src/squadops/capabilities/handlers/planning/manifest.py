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

import yaml

from squadops.capabilities.handlers.base import HandlerEvidence, HandlerResult
from squadops.capabilities.handlers.planning.base import _PlanningTaskHandler
from squadops.cycles.authoring_failure import AuthoringOutcome, assess_authoring_outcome
from squadops.cycles.contract_derivation import SEEDED_MANIFEST_FILENAME
from squadops.cycles.manifest_authoring import (
    AUTHOR_MANIFEST_CAPABILITY,
    AUTHOR_MANIFEST_ROLE,
    AUTHORED_MODE,
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
        rejection_section = await self._revision_context_section(renderer, inputs)
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
            # #838: the gate compares the declared stack to the one this cycle is
            # configured for. `stack` is already resolved above for the prompt.
            outcome = assess_authoring_outcome(yaml_or_none, stack)
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
        content = _stamp_provenance(content, context, outcomes)
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

    async def _revision_context_section(self, renderer: Any, inputs: dict[str, Any]) -> str:
        """The revision appendix on a re-roll or an operator-requested revision, or "".

        Overrides the planning base's version, which renders the *plan* re-roll appendix —
        wrong for a manifest author, and it would show them a rejected plan they did not
        write. Same #669 rail, a document-appropriate asset.

        The prior manifest is what makes this a revision rather than a re-roll (§5c.6,
        #811): shown the design being revised, the author changes what was asked about;
        shown only a note, it re-derives everything and the reviewer reads a new design.
        """
        reasons = [
            str(r).strip() for r in (inputs.get("rejection_reasons") or []) if str(r).strip()
        ]
        if not reasons:
            return ""
        variables: dict[str, str] = {"reviewer_notes": "\n".join(f"- {r}" for r in reasons)}
        prior = str(inputs.get("prior_manifest_yaml") or "").strip()
        if prior:
            variables["prior_manifest"] = (
                "\n### The design you are revising\n\n"
                f"```yaml:interface_manifest.yaml\n{prior}\n```\n"
            )
        rendered = await renderer.render("request.manifest_revision_request_appendix", variables)
        return rendered.content

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


def _stamp_provenance(
    content: str, context: ExecutionContext, outcomes: list[AuthoringOutcome]
) -> str:
    """Append the system-owned provenance block to the authored document (#803, M5).

    **Appended, never re-emitted.** Round-tripping the manifest through the parser and
    re-serialising would discard the author's comments, key order and grouping — this is a
    design document a human reads, not a wire format. Everything above the block stays
    byte-identical to what the squad wrote.

    **Observed, not claimed.** Attempts and their rejection classes come from the loop that
    just ran, so the record cannot flatter itself. An author-supplied block is discarded
    rather than rejected: the field is system-owned, so overwriting it costs nothing, while a
    rejection would spend a revision on bookkeeping the system replaces anyway — and the same
    gate runs again at the framing net, where a stamped block is entirely legitimate.

    Excluded from ``_canonical`` at the model, so stamping cannot move the manifest hash the
    verification contract binds (pinned by test — the M2 ``decisions`` lesson).
    """
    revisions = [
        {
            "attempt": i,
            "classes": o.class_counts(),
            "proofs": sorted({f.proof for f in o.findings}),
        }
        for i, o in enumerate(outcomes, start=1)
        if o.rejected
    ]
    block = {
        "provenance": {
            "mode": AUTHORED_MODE,
            "cycle_id": context.cycle_id,
            "task_id": context.task_id,
            "attempts": len(outcomes),
            "revisions": revisions,
        }
    }
    body = _without_authored_provenance(content).rstrip("\n")
    return f"{body}\n\n{yaml.safe_dump(block, sort_keys=False)}"


def _without_authored_provenance(content: str) -> str:
    """Drop a top-level ``provenance:`` block the author wrote, if any.

    Line-scoped so the rest of the document is untouched: from the ``provenance:`` line to
    the next top-level key (or the end). Duplicate top-level keys would otherwise leave two
    blocks in one document — parseable (last wins) and unreadable.
    """
    lines = content.splitlines()
    out: list[str] = []
    skipping = False
    for line in lines:
        if skipping:
            # A new top-level key ends the block; blanks and indented lines belong to it.
            if line and not line[0].isspace():
                skipping = False
            else:
                continue
        if line.startswith("provenance:"):
            logger.info(
                "%s: discarding an author-supplied provenance block — the field is "
                "system-owned and is stamped from the observed authoring loop",
                DevelopmentAuthorManifestHandler._handler_name,
            )
            skipping = True
            continue
        out.append(line)
    return "\n".join(out)


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
