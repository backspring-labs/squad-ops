"""Repair handlers for the SIP-0079 correction protocol.

Thin subclasses of _CycleTaskHandler used by the repair-task selector in
cycles/task_plan.py: development.correction_repair (dev) and
builder.assemble_repair (builder).

Issue #100: this file used to define a `DevelopmentRepairHandler` with
`_capability_id = "development.repair"`. That collided with the SIP-0070
pulse-check `DevelopmentRepairHandler` in handlers/repair_tasks.py. The
correction-loop variant is now `DevelopmentCorrectionRepairHandler` with
`_capability_id = "development.correction_repair"` so the pulse-check and
correction-loop flows have distinct, non-overlapping capability ids.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.cycle_tasks import _classify_file, _CycleTaskHandler
from squadops.capabilities.handlers.fenced_parser import extract_fenced_files
from squadops.cycles.failure_evidence import failing_cases_from_evidence
from squadops.cycles.verification_integrity import ResultStatus

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from squadops.capabilities.handlers.base import HandlerResult
    from squadops.capabilities.handlers.context import ExecutionContext


def _artifacts_from_fenced_blocks(content: str, fallback_name: str) -> list[dict[str, Any]]:
    """Extract per-file artifacts from fenced code blocks in *content*.

    Repair handlers ask the LLM to emit replacement source files in the
    same fenced format the develop handler uses. Without this extraction
    the base handler wraps the entire response as a single markdown doc
    and the repaired files never land in artifact storage — the failure
    mode that motivated this helper.

    Falls back to a single markdown wrap when no fenced blocks are found
    so the LLM output is not silently dropped.
    """
    extracted = extract_fenced_files(content)
    if not extracted:
        return [
            {
                "name": fallback_name,
                "content": content,
                "media_type": "text/markdown",
                "type": "document",
            },
        ]
    artifacts: list[dict[str, Any]] = []
    for file_rec in extracted:
        artifact_type, media_type = _classify_file(file_rec["filename"])
        artifacts.append(
            {
                "name": file_rec["filename"],
                "content": file_rec["content"],
                "media_type": media_type,
                "type": artifact_type,
            }
        )
    return artifacts


def _format_bullets(items: Any) -> str:
    """Format list-of-strings inputs as a markdown bullet list, "(none)" if empty."""
    if not items:
        return "(none specified)"
    if isinstance(items, str):
        return items
    try:
        rendered = "\n".join(
            f"- `{item}`" if "/" in str(item) or "." in str(item) else f"- {item}" for item in items
        )
        return rendered or "(none specified)"
    except TypeError:
        return str(items)


# Deterministic, data-derived evidence the correction runner injects, each rendered as an
# authoritative block. Order is deliberate — conformance first, then ownership, then the two
# scaffold-knowledge seams — and it is a table rather than four copy-pasted branches so a
# fifth seam is one row, not another clause (and does not push this function past C901).
#
#   interface_drift      — exact renamed identifiers vs the manifest (deterministic, not the
#                          analyzer's guess), so the repair renames to interface names.
#   scaffold_enforcement — SIP-0100 3.4b: a prior repair's edit to a frozen file was rejected
#                          and restored; tell this repair rather than let it silently fight.
#   error_contract       — pf-34: the ApiError(code, message) convention + code→status map.
#                          Without it repairs guess the signature and 500 every error path at
#                          the behavioral retest despite passing every typed check.
#   model_surface        — pf-41: the exact importable names from the frozen models.py.
#                          Repairs invented them on three consecutive attempts, degrading
#                          working imports into unimportable ones; the unresolved-import gate
#                          rejects such a patch but never says what the real names are.
_AUTHORITATIVE_EVIDENCE_BLOCKS: tuple[tuple[str, str], ...] = (
    ("interface_drift", "INTERFACE CONFORMANCE"),
    ("scaffold_enforcement", "FROZEN OWNERSHIP"),
    ("error_contract", "ERROR CONTRACT"),
    ("model_surface", "MODEL SURFACE"),
    # #870: the fate of this task's previous repair — the rejection's named
    # evidence (failed checks / retest verdict), so a re-repair addresses what
    # was actually rejected instead of re-rolling blind (roll 12: a repair that
    # fixed the diagnosed axis and stopped compiling; the next round never knew).
    ("prior_repair_rejections", "PRIOR REPAIR REJECTED"),
)


def _evidence_lines(value: Any) -> list[str]:
    """Normalize one evidence entry to its instruction lines.

    Interface drift arrives as dicts carrying an ``instruction``; the rest arrive as plain
    strings. Blank entries are dropped so an empty list never renders a bare header.
    """
    lines: list[str] = []
    for item in value or []:
        text = item.get("instruction", "") if isinstance(item, dict) else item
        if text := str(text).strip():
            lines.append(text)
    return lines


def _authoritative_blocks(failure_evidence: dict) -> list[str]:
    """Render every present authoritative evidence block, in table order."""
    blocks: list[str] = []
    for key, header in _AUTHORITATIVE_EVIDENCE_BLOCKS:
        lines = _evidence_lines(failure_evidence.get(key))
        if lines:
            blocks.append(
                f"{header} (authoritative — apply exactly):\n"
                + "\n".join(f"- {line}" for line in lines)
            )
    return blocks


def _format_failure_summary(failure_evidence: Any, failure_analysis: Any) -> str:
    """Compose a compact failure description from evidence + analysis."""
    parts: list[str] = []
    if isinstance(failure_evidence, dict):
        parts.extend(_authoritative_blocks(failure_evidence))
        vr = failure_evidence.get("validation_result") or {}
        summary = vr.get("summary") or failure_evidence.get("error") or ""
        if summary:
            parts.append(f"Validation summary: {summary}")
        missing = vr.get("missing_components") or []
        if missing:
            parts.append("Missing components: " + ", ".join(str(m) for m in missing))
        rejected = failure_evidence.get("rejected_artifacts") or []
        if rejected:
            names = ", ".join(str(r.get("name", "?")) for r in rejected)
            parts.append(f"Rejected artifacts: {names}")
    if isinstance(failure_analysis, dict):
        analysis = failure_analysis.get("analysis_summary")
        if analysis:
            parts.append(f"Analyzer summary: {analysis}")
        factors = failure_analysis.get("contributing_factors") or []
        if factors:
            parts.append("Contributing factors:\n" + "\n".join(f"- {f}" for f in factors))
    return "\n\n".join(parts) if parts else "(no structured failure evidence available)"


def _format_correction_decision(correction_decision: Any) -> str:
    """Render the lead's correction decision rationale for the prompt."""
    if isinstance(correction_decision, dict):
        rationale = correction_decision.get("decision_rationale") or ""
        path = correction_decision.get("correction_path") or ""
        if rationale:
            return f"Path: {path}\n\n{rationale}" if path else rationale
        return str(correction_decision)
    return str(correction_decision or "(no decision available)")


class _RepairPromptMixin:
    """Shared prompt-building for correction-loop repair handlers.

    The base `_CycleTaskHandler` user prompt is PRD + prior_outputs only —
    the repair handler never sees the failed task's expected_artifacts /
    acceptance_criteria, so the dev/builder roles emit generic content
    instead of re-producing the named artifact that failed acceptance.
    This mixin surfaces the failed task's contract and the failure
    context to the LLM. Used by both repair handlers below.
    """

    _request_template_id = "request.cycle_repair_task"

    def _build_render_variables(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any],
    ) -> dict[str, str]:
        from squadops.cycles.contract_expectations import expectation_lines, prose_criteria

        criteria = inputs.get("acceptance_criteria") or []
        # pf-31 Fix A2: typed criteria render ONLY through the authoritative
        # Contract Expectations block; the narrative section carries prose alone.
        # Rendering TypedCheck dicts through _format_bullets produced the repr
        # soup every pf-31 repair ignored in favor of contradicting prose.
        narrative = prose_criteria(criteria) if expectation_lines(criteria) else criteria
        return {
            "prd": prd,
            "role": self._role,
            "failed_task_type": str(inputs.get("failed_task_type", "")),
            "failure_summary": _format_failure_summary(
                inputs.get("failure_evidence"),
                inputs.get("failure_analysis"),
            ),
            "correction_decision": _format_correction_decision(inputs.get("correction_decision")),
            "subtask_focus": str(inputs.get("subtask_focus") or ""),
            "subtask_description": str(inputs.get("subtask_description") or ""),
            "expected_artifacts": _format_bullets(inputs.get("expected_artifacts")),
            "acceptance_criteria": _format_bullets(narrative),
            "prior_outputs": self._format_prior_outputs(prior_outputs),
            # Same scaffold fill-only constraint the develop handler injects (SIP-0099
            # 99.3). Rendered in handle() and threaded via inputs; "" when absent.
            "fill_only_section": str(inputs.get("fill_only_section") or ""),
            # pf-31 Fix A1: authoritative typed-expectations block, rendered in
            # handle() from the managed appendix asset; "" when no typed criteria.
            "contract_expectations": str(inputs.get("contract_expectations_section") or ""),
            # #667: the qa DOM anchor contract, rendered in handle(); "" for
            # non-qa repairs or when no anchor surface was threaded.
            "dom_anchor_section": str(inputs.get("dom_anchor_section") or ""),
            # Roll 9: the frozen index (import-as forms + package.json's dependency
            # surface), rendered in handle() for qa repairs; dev repairs receive the
            # same block inside fill_only_section. "" when no surface was threaded.
            "frozen_surface_section": str(inputs.get("frozen_surface_section") or ""),
            # #1015 part C: the repair could not see the loop. No attempt counter, no
            # statement that rounds are finite — each round rendered only the fresh
            # failure, so a dev with no reason to think anything was running out
            # re-emitted the same approach. V38 slot 4 rounds 1-2 and slot 6 round 1
            # are the samples. Rendered in handle(); "" when the executor threaded no
            # counter (author-mode and legacy paths render byte-identically).
            "loop_state": str(inputs.get("loop_state_section") or ""),
            # #970 / #969 (1.6.5 D): the SAME fill-mode brief qa.test authored under,
            # plus the slots whose fills failed. "" for non-qa repairs or no scaffold.
            "qa_fill_mode_section": str(inputs.get("qa_fill_mode_section") or ""),
        }

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        """Inject the scaffold fill-only constraint before the base render.

        The develop handler tells the dev to FILL the seeded skeleton's slots and NOT
        rewrite scaffold-owned interface (route paths/decorators/signatures, the wired
        ``ApiError`` seam) — but the correction/repair path previously got none of that
        and was told to "re-produce the artifact", so repairs freely rewrote the seeded
        interface (observed: ``ApiError(status_code=...)`` vs the seeded
        ``ApiError(code, message)``; ``APIRouter(prefix=...)`` vs seeded absolute
        decorators). Reuse the SAME managed appendix the dev gets so the repair honors
        the same boundary. Dev-role repairs on a scaffoldable stack only; no-op otherwise.
        """
        fill_only = await self._render_fill_only_section(context, inputs)
        if fill_only:
            inputs = {**inputs, "fill_only_section": fill_only}
        expectations = await self._render_contract_expectations_section(context, inputs)
        if expectations:
            inputs = {**inputs, "contract_expectations_section": expectations}
        dom_anchor = await self._render_dom_anchor_section(context, inputs)
        if dom_anchor:
            inputs = {**inputs, "dom_anchor_section": dom_anchor}
        client_surface = await self._render_client_surface_section(context, inputs)
        if client_surface:
            inputs = {**inputs, "client_surface_section": client_surface}
        failing_cases = await self._render_failing_cases_section(context, inputs)
        if failing_cases:
            inputs = {**inputs, "failing_cases_section": failing_cases}
        frozen = await self._render_qa_frozen_surface_section(context, inputs)
        if frozen:
            inputs = {**inputs, "frozen_surface_section": frozen}
        loop_state = await self._render_loop_state_section(context, inputs)
        if loop_state:
            inputs = {**inputs, "loop_state_section": loop_state}
        qa_fill_mode = await self._render_qa_fill_mode_section(context, inputs)
        if qa_fill_mode:
            inputs = {**inputs, "qa_fill_mode_section": qa_fill_mode}
        result = await super().handle(context, inputs)
        await self._after_emission(inputs, result)
        return result

    async def _after_emission(self, inputs: dict[str, Any], result: HandlerResult) -> None:
        """What happens to the emission before it leaves the agent: the typed checks.

        A handler with its own post-processing (the qa repair merges fills first)
        overrides this and calls up, so the checks always run on the artifacts the
        executor will verify — never on an intermediate shape.
        """
        await self._attach_typed_checks(inputs, result)

    async def _attach_typed_checks(self, inputs: dict[str, Any], result: HandlerResult) -> None:
        """#1229 (the owner's rule B): the repair evaluates the failed task's typed criteria
        on its own patched tree HERE — in the agent container, where the stack's toolchain
        lives — and hands the executed rows to the executor's verification with the patch.

        Until this, a repair was verified only in runtime-api, which has no node: on the
        Next.js stack every check owning a ``.ts`` file skipped there, no blocking check
        executed, and the verdict was ``unverifiable`` three rounds running
        (``cyc_05abfc7c1f00``; #1221 stopped the loop, it could not make the verdict
        obtainable). The rows are the same shape the primary handlers bank
        (``_evaluate_typed_acceptance``, framework-injected checks included — which the
        executor-side verification never ran on a repair at all), evaluated on the same
        workspace the verifier materialises (``acceptance_workspace_files``, forwarded by
        ``repair_forwarded_inputs``). They are evidence for the verifier, not a verdict
        on the task: a failing row here does not fail the repair task, it lets the
        verifier reject the patch with an executed reason instead of a shrug.
        """
        outputs = getattr(result, "outputs", None)
        if not getattr(result, "success", False) or not isinstance(outputs, dict):
            return
        if outputs.get("emission_failure"):
            return
        artifacts = list(outputs.get("artifacts") or [])
        if not artifacts:
            return
        checks: list[dict[str, Any]] = []
        missing: list[str] = []
        await self._evaluate_typed_acceptance(inputs, artifacts, checks, missing, {})
        rows = [c for c in checks if str(c.get("check", "")).startswith("acceptance:")]
        outputs["repair_typed_checks"] = {
            "environment": f"agent:{self._role}",
            "workspace_revision_id": inputs.get("workspace_revision_id"),
            "checks": rows,
        }
        executed = sum(
            1 for c in rows if c.get("status") in (ResultStatus.PASSED, ResultStatus.FAILED)
        )
        # Every row with its status, and the reason when it did not execute: the Next.js
        # shakeout of 2026-09-02 logged "rows=4 executed=2" and nothing in any store said
        # WHICH two skipped or why — the diagnosis had to be read out of the code paths.
        logger.info(
            "repair_typed_checks environment=agent:%s rows=%d executed=%d failed=%d checks=%s",
            self._role,
            len(rows),
            executed,
            sum(1 for c in rows if c.get("status") == ResultStatus.FAILED),
            " ".join(
                f"{str(c.get('check', '')).removeprefix('acceptance:')}:{c.get('status')}"
                + (
                    f"({c.get('reason')})"
                    if c.get("status") not in (ResultStatus.PASSED, ResultStatus.FAILED)
                    and c.get("reason")
                    else ""
                )
                for c in rows
            )
            or "-",
        )

    async def _render_qa_fill_mode_section(
        self, context: ExecutionContext, inputs: dict[str, Any]
    ) -> str:
        """The qa fill-mode brief for a scaffold-bound repair, or "" (#969, #970).

        Third instance of the missing-brief pattern, closed at the seam rather than
        with a fourth appendix: the repair renders the SAME fill-mode section
        ``qa.test`` authored under (slot protocol, store vocabulary, error envelope,
        in-process execution model) through ``fill_mode_brief``, followed by the
        repair addendum naming the slots whose fills failed.
        """
        if self._role != "qa" or not inputs.get("verification_scaffold"):
            return ""
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return ""
        from squadops.capabilities.handlers.cycle.fill_mode_brief import (
            render_fill_mode_section,
            render_repair_fill_section,
        )

        brief = await render_fill_mode_section(
            renderer, inputs.get("verification_scaffold"), inputs.get("expected_artifacts") or []
        )
        addendum = await render_repair_fill_section(renderer, inputs.get("repair_slots"))
        return "\n\n".join(part for part in (brief, addendum) if part)

    async def _render_loop_state_section(
        self, context: ExecutionContext, inputs: dict[str, Any]
    ) -> str:
        """The correction loop's position, or "" (#1015 part C).

        Data only — the prose lives in the managed asset (CLAUDE.md #448). Both numbers
        already exist at the dispatch site; they simply never reached the prompt.

        Rounds after the first also carry an explicit persistence note. The observed
        failure is a repair that re-emits the same approach against the same failure
        (#864: "diagnoses accurately, then re-emits it — twice"), and a round that
        renders only the fresh failure gives the author no signal that the previous
        attempt was already tried and did not work.
        """
        attempt = inputs.get("correction_attempt")
        max_attempts = inputs.get("max_correction_attempts")
        renderer = getattr(getattr(context, "ports", None), "request_renderer", None)
        if renderer is None or not isinstance(attempt, int) or not isinstance(max_attempts, int):
            return ""
        variables = {"attempt": str(attempt), "max_attempts": str(max_attempts)}
        if attempt > 1:
            variables["persistence_note"] = (
                "\nThe failure has already survived at least one repair. Re-emitting the "
                "same change will spend this round the same way — reconsider the approach "
                "before producing the files, and if the previous diagnosis looks right but "
                "the fix did not take, say so rather than repeating it."
            )
        rendered = await renderer.render("request.cycle_repair_loop_state", variables)
        return rendered.content

    async def _render_contract_expectations_section(
        self, context: ExecutionContext, inputs: dict[str, Any]
    ) -> str:
        """The authoritative typed-expectations appendix, or "" (pf-31 Fix A1).

        Rendered whenever the failed task's acceptance criteria carry typed
        checks — the resolved contract expectations were already delivered to
        repairs but as low-salience dict reprs below contradicting prose (the
        pf-31 ``{run_id}``-vs-``{id}`` poisoning: 7 of 7 repairs rejected).
        """
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return ""
        from squadops.cycles.contract_expectations import expectation_lines

        lines = expectation_lines(inputs.get("acceptance_criteria"))
        if not lines:
            return ""
        rendered = await renderer.render(
            "request.cycle_repair_contract_expectations_appendix",
            {"expectations": "\n".join(f"- {line}" for line in lines)},
        )
        return rendered.content

    async def _render_fill_only_section(
        self, context: ExecutionContext, inputs: dict[str, Any]
    ) -> str:
        """The dev fill-only appendix, or "" (non-dev role, non-scaffolded, no renderer)."""
        if self._role != "dev":
            return ""
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return ""
        from squadops.capabilities.dev_capabilities import (
            effective_capability_name,
            get_capability,
        )
        from squadops.capabilities.scaffold import is_scaffoldable_stack

        resolved_config = inputs.get("resolved_config") or {}
        stack = str(resolved_config.get("build_profile") or "")
        if not is_scaffoldable_stack(stack):
            return ""
        # #902 replaced the single shared appendix with a per-stack template, and fixed
        # the DEVELOP path only. This path kept rendering the hardcoded stack-#1 asset,
        # which tells the author its client helper prefixes `/api` for it. A nextjs_ts
        # repair believed that and rewrote `api('/api/runs')` back to `api('/runs')` —
        # roll 1's dead-UI defect, reintroduced by the correction loop on a cycle whose
        # initial dev output was correct (diagnostic cyc_831dfe6ac551, 2026-08-16).
        # Resolved exactly as develop resolves it; an unset template means NO appendix,
        # because wrong guidance is worse than none (#818).
        try:
            capability = get_capability(effective_capability_name(resolved_config))
        except ValueError:
            return ""
        if not capability.fill_only_template:
            return ""
        variables: dict[str, Any] = {"stack": stack}
        # Parity with develop's four surfaces. The repair had two; being blind to the
        # error contract and the model surface is the #861/#667 class exactly — and a
        # repair asked to fix "500s from incorrect model field names" was, until now,
        # the one agent in the chain that could not see the model's field names.
        error_contract = await self._render_error_contract_block(renderer, inputs)
        if error_contract:
            variables["error_contract"] = error_contract
        model_surface = await self._render_model_surface_block(renderer, inputs)
        if model_surface:
            variables["model_surface"] = model_surface
        # #667: the appendix's {{testid_surface}} slot rendered empty on every
        # repair — fay-14's repairs regenerated the view blind to the anchor
        # contract the first fill honored. Same section the develop handler
        # builds at initial dispatch, from the same threaded lines.
        testid_surface = await self._render_testid_surface_section(renderer, inputs)
        if testid_surface:
            variables["testid_surface"] = testid_surface
        # Roll 7 (cyc_0e301961f099): #861 gave the INITIAL dev the frozen index and
        # the repair stayed blind — it re-invented `runStore` against the same module
        # and the chain terminated as plan_defect on a defect no repair could see.
        # Same section the develop handler builds, from the same threaded lines.
        frozen_surface = await self._render_frozen_surface_block(renderer, inputs)
        if frozen_surface:
            variables["frozen_surface"] = frozen_surface
        # #1060 (cyc_87c12c7f199e): the fifth surface, and the one the repair most
        # needed. #1029's floor named a shape defect on all four rounds — the manifest
        # declares `participants: list[Participant]` and every repair re-emitted
        # `string[]`, because this brief never carried what the response must contain.
        # The agent retrying a shape defect was the only one not shown the shape.
        response_surface = await self._render_response_surface_block(renderer, inputs)
        if response_surface:
            variables["response_surface"] = response_surface
        rendered = await renderer.render(capability.fill_only_template, variables)
        return rendered.content

    @staticmethod
    async def _render_response_surface_block(renderer: Any, inputs: dict[str, Any]) -> str:
        """Render the SUCCESS RESPONSE block from threaded lines, or "" (#1060).

        Mirrors ``DevelopmentDevelopHandler._response_surface_section`` — manifest-derived
        data (``response_shape.response_surface_instructions``), all prose in the asset
        (#448), same appendix so the two agents read one description of the shape.
        """
        lines = [str(line).strip() for line in (inputs.get("response_surface") or [])]
        lines = [line for line in lines if line]
        if not lines:
            return ""
        rendered = await renderer.render(
            "request.development_develop_response_surface_appendix",
            {"response_lines": "\n".join(f"- {line}" for line in lines)},
        )
        return rendered.content

    @staticmethod
    async def _render_error_contract_block(renderer: Any, inputs: dict[str, Any]) -> str:
        """Render the ERROR CONTRACT block from threaded lines, or "".

        Mirrors ``DevelopHandler._error_contract_section`` — manifest-derived data
        (``scaffold.error_seam_instructions``), all prose in the asset (#448).
        """
        lines = [str(line).strip() for line in (inputs.get("error_contract") or [])]
        lines = [line for line in lines if line]
        if not lines:
            return ""
        rendered = await renderer.render(
            "request.development_develop_error_contract_appendix",
            {"error_lines": "\n".join(f"- {line}" for line in lines)},
        )
        return rendered.content

    @staticmethod
    async def _render_model_surface_block(renderer: Any, inputs: dict[str, Any]) -> str:
        """Render the MODEL SURFACE block from threaded lines, or "".

        Mirrors ``DevelopHandler._model_surface_section`` — field-level signatures plus
        the frozen store, as data; all prose in the asset (#448).
        """
        lines = [str(line).strip() for line in (inputs.get("model_surface") or [])]
        lines = [line for line in lines if line]
        if not lines:
            return ""
        rendered = await renderer.render(
            "request.development_develop_model_surface_appendix",
            {"surface_lines": "\n".join(f"- {line}" for line in lines)},
        )
        return rendered.content

    @staticmethod
    async def _render_frozen_surface_block(renderer: Any, inputs: dict[str, Any]) -> str:
        """Render the FROZEN FILES block from threaded lines, or "".

        Mirrors ``DevelopHandler._frozen_surface_section``: the lines are
        manifest-derived data (``scaffold.frozen_surface_index_lines``); all
        prose lives in the appendix asset (CLAUDE.md #448).
        """
        lines = [str(line).strip() for line in (inputs.get("frozen_surface") or [])]
        lines = [line for line in lines if line]
        if not lines:
            return ""
        rendered = await renderer.render(
            "request.development_develop_frozen_surface_appendix",
            {"frozen_lines": "\n".join(lines)},
        )
        return rendered.content

    async def _render_qa_frozen_surface_section(
        self, context: ExecutionContext, inputs: dict[str, Any]
    ) -> str:
        """The qa frozen-surface appendix, or "" (non-qa role, no surface, no renderer).

        Roll 9 (cyc_a92eaa4f4052): the suite imported a package ``package.json`` does
        not declare, and a re-authoring repair would have been blind identically. The
        dev flavor rides inside the fill-only appendix; builder repairs re-emit
        packaging artifacts and import nothing, so they carry no block.
        """
        if self._role != "qa":
            return ""
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return ""
        lines = [str(line).strip() for line in (inputs.get("frozen_surface") or [])]
        lines = [line for line in lines if line]
        if not lines:
            return ""
        rendered = await renderer.render(
            "request.qa_test_frozen_surface_appendix",
            {"frozen_lines": "\n".join(lines)},
        )
        return rendered.content

    @staticmethod
    async def _render_testid_surface_section(renderer: Any, inputs: dict[str, Any]) -> str:
        """Render the DOM ANCHOR CONTRACT block from threaded lines, or "".

        Mirrors ``DevelopHandler._testid_surface_section``: the lines are
        manifest-derived data (``scaffold.testid_surface_instructions``); all
        prose lives in the appendix asset (CLAUDE.md #448).
        """
        lines = [str(line).strip() for line in (inputs.get("testid_surface") or [])]
        lines = [line for line in lines if line]
        if not lines:
            return ""
        rendered = await renderer.render(
            "request.development_develop_testid_surface_appendix",
            {"testid_lines": "\n".join(f"- {line}" for line in lines)},
        )
        return rendered.content

    async def _render_failing_cases_section(
        self, context: ExecutionContext, inputs: dict[str, Any]
    ) -> str:
        """The qa REPAIR SCOPE block — the cases the runner reported failing — or "".

        #1123: the qa repair re-authored the whole file with no list of what failed
        (1.6.6 React roll 6: two failing cases of four, the passing two rewritten with
        them). The cases come from the runner's structured rows on the failed task's
        ``tests_pass`` row (``failing_cases``); the "repair only these" prose lives in
        the appendix asset (CLAUDE.md #448). Non-qa roles, no evidence, no renderer → "".
        """
        if self._role != "qa":
            return ""
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return ""
        cases = failing_cases_from_evidence(inputs.get("failure_evidence"))
        if not cases:
            return ""
        lines = []
        for case in cases:
            where = case["file"] + (f":{case['line']}" if case.get("line") else "")
            title = case["title"] or "(suite-level)"
            message = f" — {case['message']}" if case.get("message") else ""
            lines.append(f"`{where}` › {title}{message}")
        rendered = await renderer.render(
            "request.qa_test_repair_failing_cases_appendix",
            {"case_lines": "\n".join(f"- {line}" for line in lines), "case_count": len(lines)},
        )
        return rendered.content

    async def _render_client_surface_section(
        self, context: ExecutionContext, inputs: dict[str, Any]
    ) -> str:
        """The qa frozen-client appendix, or "" (non-qa role, no lines, no renderer).

        #668: the re-authored suite mocks beneath the same frozen client the original
        dispatch was shown (``_client_surface_section`` in the qa_test handler); a repair
        blind to the client's surface re-invents it. Same appendix asset, same lines.
        """
        if self._role != "qa":
            return ""
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return ""
        lines = [str(line).strip() for line in (inputs.get("frozen_client_surface") or [])]
        lines = [line for line in lines if line]
        if not lines:
            return ""
        rendered = await renderer.render(
            "request.qa_test_client_surface_appendix",
            {"client_lines": "\n".join(f"- {line}" for line in lines)},
        )
        return rendered.content

    async def _render_dom_anchor_section(
        self, context: ExecutionContext, inputs: dict[str, Any]
    ) -> str:
        """The qa DOM anchor appendix, or "" (non-qa role, no lines, no renderer).

        #667: ``qa.test_repair`` re-authors the suite with none of the anchor
        inventory the original qa.test dispatch carried (``_dom_anchor_section``
        in the qa_test handler) — the re-authored suite then asserts invented
        render details, the fay-6/fay-12 churn class replayed through the
        repair path. Same appendix asset, same threaded lines.
        """
        if self._role != "qa":
            return ""
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return ""
        lines = [str(line).strip() for line in (inputs.get("dom_testid_surface") or [])]
        lines = [line for line in lines if line]
        if not lines:
            return ""
        rendered = await renderer.render(
            "request.qa_test_dom_anchor_appendix",
            {"testid_lines": "\n".join(f"- {line}" for line in lines)},
        )
        return rendered.content

    def _build_user_prompt(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any] | None = None,
    ) -> str:
        inputs = inputs or {}
        parts = ["## Repair Task"]
        failed_type = inputs.get("failed_task_type")
        if failed_type:
            parts.append(
                f"You are repairing a failed `{failed_type}` task. Re-produce the "
                "named artifact(s) below so they satisfy the acceptance criteria. "
                "Do not produce a generic narrative."
            )

        focus = inputs.get("subtask_focus")
        if focus:
            parts.append(f"### Focus\n{focus}")
        desc = inputs.get("subtask_description")
        if desc:
            parts.append(f"### Description\n{desc}")

        expected = inputs.get("expected_artifacts")
        if expected:
            parts.append(
                "### Required Output Artifacts\n"
                "Emit each file with a fenced code block in the format "
                "` ```language:path/to/file `:\n" + _format_bullets(expected)
            )

        from squadops.cycles.contract_expectations import expectation_lines, prose_criteria

        criteria = inputs.get("acceptance_criteria") or []
        typed_lines = expectation_lines(criteria)
        if typed_lines:
            parts.append(
                "### Contract Expectations (authoritative — apply exactly)\n"
                + "\n".join(f"- {line}" for line in typed_lines)
            )
            criteria = prose_criteria(criteria)
        if criteria:
            parts.append("### Acceptance Criteria (narrative)\n" + _format_bullets(criteria))

        failure_summary = _format_failure_summary(
            inputs.get("failure_evidence"),
            inputs.get("failure_analysis"),
        )
        parts.append("### Why the Prior Attempt Failed\n" + failure_summary)

        decision = _format_correction_decision(inputs.get("correction_decision"))
        parts.append("### Correction Decision\n" + decision)

        parts.append(f"### Product Requirements Document\n\n{prd}")

        if prior_outputs:
            parts.append("### Prior Analysis from Upstream Roles")
            for role, summary in prior_outputs.items():
                parts.append(f"#### {role}\n{summary}")

        parts.append(
            "Produce the named artifacts now using fenced code blocks "
            "(` ```language:path/to/file `). Do not emit unrelated files."
        )
        return "\n\n".join(parts)


class DevelopmentCorrectionRepairHandler(_RepairPromptMixin, _CycleTaskHandler):
    """Correction-loop repair handler.

    Reads `failure_evidence`, `failure_analysis`, and `correction_decision`
    from inputs (set by the executor's correction protocol) and asks the
    LLM to author a repair. Distinct from the SIP-0070 pulse-check
    `DevelopmentRepairHandler`, which consumes `verification_context` from
    a different upstream chain.
    """

    _handler_name = "development_correction_repair_handler"
    _capability_id = "development.correction_repair"
    _role = "dev"
    _artifact_name = "repair_output.md"

    def _build_artifacts_from_content(self, content: str) -> list[dict[str, Any]]:
        return _artifacts_from_fenced_blocks(content, self._artifact_name)


class BuilderAssembleRepairHandler(_RepairPromptMixin, _CycleTaskHandler):
    """Correction-loop repair handler for failed builder.assemble tasks.

    Mirrors `DevelopmentCorrectionRepairHandler` but routed to the builder
    role so packaging/handoff failures (e.g. qa_handoff.md missing
    required sections, missing requirements.txt or package.json) get
    repaired by the builder role with the build-profile system prompt
    rather than by the dev role with the dev system prompt — the dev
    role has no useful context for builder.assemble outputs and simply
    ignores the assignment.
    """

    _handler_name = "builder_assemble_repair_handler"
    _capability_id = "builder.assemble_repair"
    _role = "builder"
    _artifact_name = "repair_output.md"

    def _build_artifacts_from_content(self, content: str) -> list[dict[str, Any]]:
        return _artifacts_from_fenced_blocks(content, self._artifact_name)


class QATestRepairHandler(_RepairPromptMixin, _CycleTaskHandler):
    """Correction-loop repair handler for failed qa.test tasks (#568).

    Reachable ONLY via the own-artifact failure locus (the test suite itself
    is missing, unparseable, or uncollectable — deterministic signals, never
    LLM judgment): the qa role re-authors its own test artifact(s). Behavioral
    failures (the suite ran and the app failed it) never route here — they
    stay on the default dev chain, because "repairing" an app bug by
    rewriting tests until they pass is a manufactured false green.

    Acceptance is the same deterministic pair as every correction repair:
    patch verification against the failed task's typed criteria (#389), then
    the behavioral retest executes the re-authored suite (#456).
    """

    _handler_name = "qa_test_repair_handler"
    _capability_id = "qa.test_repair"
    _role = "qa"
    _artifact_name = "repair_output.md"

    def _build_artifacts_from_content(self, content: str) -> list[dict[str, Any]]:
        """Fill blocks become ``type: "fill"`` artifacts keyed by slot id (#970).

        Left to the file extractor they parse as files named ``slot-…`` — the shape
        the shell guard discards and roll 6 of the 1.6.4 set banked eight of. The
        merge into the shells happens in :meth:`handle`, where the scaffold is known.
        """
        from squadops.capabilities.verification_scaffold_fill import (
            parse_fill_emission,
            strip_fill_blocks,
        )

        fills = parse_fill_emission(content)
        fill_artifacts = [
            {
                "name": f.slot_id,
                "content": f"not_applicable: {f.not_applicable_reason}"
                if f.is_not_applicable
                else f.body,
                "media_type": "text/plain",
                "type": "fill",
            }
            for f in fills.fills
        ]
        rest = strip_fill_blocks(content) if fills.fills else content
        if fill_artifacts and not extract_fenced_files(rest):
            return fill_artifacts
        return fill_artifacts + _artifacts_from_fenced_blocks(rest, self._artifact_name)

    async def _after_emission(self, inputs: dict[str, Any], result: HandlerResult) -> None:
        """Merge the fills into their shells first; the typed checks run on the merged set."""
        scaffold_input = inputs.get("verification_scaffold")
        if scaffold_input and isinstance(result.outputs, dict):
            artifacts, evidence = _merge_repair_fills(
                scaffold_input, list(result.outputs.get("artifacts") or [])
            )
            result.outputs["artifacts"] = artifacts
            result.outputs["fill_merge"] = evidence
            logger.info(
                "qa_test_repair_handler fill merge: applied=%s dropped_shell_rewrites=%s counts=%s",
                evidence.get("applied"),
                evidence.get("dropped_shell_rewrites"),
                evidence.get("counts"),
            )
        await super()._after_emission(inputs, result)


def _merge_repair_fills(
    scaffold_input: dict[str, Any], artifacts: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge a repair's fill artifacts into the task's current shells (#970, 1.6.5 D).

    The repair emits fill blocks for the failing slots; the shells it must produce
    are the task's CURRENT merged shells (``current_files``, threaded by the runner
    from the failed task's stored artifacts) with those slots replaced. Every other
    slot's fill is recovered from the current shell and kept byte for byte; the
    result passes the same merge gate the primary did (#1087 tables, #1094 element
    kinds) and is emitted at the shell path, so the patch overlay supersedes the
    failed shell by name and the retest runs it. A whole-shell rewrite emitted as a
    path fence is dropped and recorded, as on every other qa path.
    """
    from squadops.capabilities.verification_scaffold import VerificationScaffoldManifest
    from squadops.capabilities.verification_scaffold_fill import (
        apply_followup_fills,
        merge_fills,
        parse_fill_emission,
        recover_fills,
    )

    record = VerificationScaffoldManifest.from_dict(scaffold_input["manifest"])
    shell_paths = {f.path for f in record.files}
    fill_artifacts = [a for a in artifacts if a.get("type") == "fill"]
    dropped = sorted(a["name"] for a in artifacts if a.get("name") in shell_paths)
    kept = [a for a in artifacts if a.get("type") != "fill" and a.get("name") not in shell_paths]
    evidence: dict[str, Any] = {"dropped_shell_rewrites": dropped, "applied": [], "counts": {}}
    current = list(scaffold_input.get("current_files") or [])
    if not fill_artifacts:
        evidence["detail"] = "the repair emitted no fill block"
        return kept, evidence
    if not current:
        evidence["detail"] = "no current shells were threaded; fills could not be merged"
        return kept, evidence
    text = "".join(f"```fill:{a['name']}\n{a['content']}\n```\n" for a in fill_artifacts)
    repair_fills = parse_fill_emission(text)
    base, dispositions = recover_fills(current, record)
    folded = apply_followup_fills(base, repair_fills, dispositions, replace_filled=True)
    merged = merge_fills(
        list(scaffold_input["files"]),
        record,
        folded.emission,
        store_tables=scaffold_input.get("store_tables"),
        slot_element_kinds=scaffold_input.get("slot_element_kinds"),
    )
    touched_paths = {
        f.path for f in record.files if any(s.slot_id in folded.applied for s in f.slots)
    }
    merged_artifacts = [
        {
            "name": f.path,
            "content": f.content,
            "media_type": _classify_file(f.path)[1],
            "type": "test",
        }
        for f in merged.files
        if f.path in touched_paths
    ]
    evidence.update(
        {
            "applied": list(folded.applied),
            "counts": merged.disposition_counts(),
            "dispositions": [
                {"slot_id": d.slot_id, "disposition": d.disposition, "detail": d.detail}
                for d in merged.dispositions
                if d.slot_id in folded.applied
            ],
            "misaddressed": [
                {"slot_id": d.slot_id, "detail": d.detail} for d in merged.misaddressed
            ],
        }
    )
    return kept + merged_artifacts, evidence
