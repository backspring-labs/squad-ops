"""QATestHandler — test generation + execution against build artifacts (D1).
Split from cycle_tasks.py (#152).
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from squadops.capabilities.dev_capabilities import (
    DEFAULT_DEV_CAPABILITY,
    effective_capability_name,
    get_capability,
)
from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.prompt_guard import _guard_prompt_size
from squadops.cycles.check_registry import (
    CHECK_FRONTEND_BUILD,
    CHECK_NO_SELF_MOCKING_TESTS,
    CHECK_NO_STUB_FALLBACK_TESTS,
)
from squadops.cycles.emission_integrity import emission_stats as _emission_stats
from squadops.cycles.verification_integrity import NotExecutedReason, ResultStatus
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

from squadops.capabilities.handlers.cycle.base import _CycleTaskHandler
from squadops.capabilities.handlers.cycle.validation import (
    _STUB_THRESHOLD_BYTES,
    ValidationResult,
    _classify_file,
    _detect_stubs,
    _is_test_file,
)
from squadops.capabilities.handlers.emission_log import log_emission_shape

logger = logging.getLogger(__name__)


def failing_check_names(checks: list[dict]) -> list[str]:
    """Which checks actually opened the self-eval branch (#946).

    Evidence-gap rows are excluded deliberately. They are honest non-passes that
    ``_validate_output`` already refuses to fail the task on — a correction cannot repair
    an evaluator limitation — so naming one as the trigger would send a reader chasing a
    check that did not cause anything.
    """
    return [
        str(c.get("check", "unnamed"))
        for c in checks
        if not c.get("passed", True) and not c.get("evidence_gap", False)
    ]


def _frontend_skip_reason(error: str) -> str:
    """Map a frontend-build skip error to a §7 not-executed reason (#407).

    ``run_frontend_build`` skips (``ran=False``) with the cause in ``error``: an
    absent Node toolchain (``npm/npx not found``) is ``missing_tooling`` — the
    #306 case a required frontend_build must block on; anything else (no frontend
    source) is ``subject_missing``.
    """
    e = (error or "").lower()
    if "not found" in e or "not installed" in e:
        return NotExecutedReason.MISSING_TOOLING
    return NotExecutedReason.SUBJECT_MISSING


def _authenticity_row(check: str, offenders: list[str], inspected: list[str]) -> dict[str, Any]:
    """Build a suite-authenticity check row that is banked pass OR fail (#986).

    The two authenticity detectors used to append a row only when they found
    something, so a clean suite left no trace and an absent row meant either "looked
    and found nothing" or "never looked" — an ambiguity that cost an hour of
    archaeology on `cyc_6651d552e06a` and still did not resolve. ``inspected`` names
    the files the detector actually read, so an empty inventory beside an executed
    suite reads as the defect it is instead of as a pass.
    """
    row: dict[str, Any] = {"check": check, "passed": not offenders, "inspected": inspected}
    if offenders:
        row["offenders"] = offenders
    return row


class QATestHandler(_CycleTaskHandler):
    """Build handler: generates test files from validation plan + source (D1).

    Reads the validation plan and source artifacts from
    ``inputs["artifact_contents"]`` and instructs the LLM to produce
    pytest test files.
    """

    _handler_name = "qa_test_handler"
    _capability_id = "qa.test"
    _role = "qa"
    _artifact_name = "test_output"  # overridden by multi-file output

    def validate_inputs(self, inputs: dict[str, Any], contract=None) -> list[str]:
        errors = super().validate_inputs(inputs, contract)
        if "artifact_contents" not in inputs and "artifact_vault" not in inputs:
            errors.append("'artifact_contents' or 'artifact_vault' is required for build tasks")
        return errors

    async def _validate_output(
        self,
        inputs: dict[str, Any],
        artifacts: list[dict],
        *,
        typed_error_counts: dict[str, int] | None = None,
    ) -> ValidationResult:
        """Validate QA handler output (SIP-0086 §6.4; #670 typed acceptance).

        #670 (owner-ruled fork 1, 2026-08-04): qa joins the shared
        typed-acceptance seam, retiring M1.3's dev-only scope note. Authored
        checks on qa.test tasks — including the SIP-0100 ``harness_boundary``
        bindings that were render-only until this change — AND framework
        injections (#689 ``undefined_names`` on ``.py`` emissions) both
        evaluate here, with the same RC-9 blocking matrix and #423
        evidence-gap accounting as the dev/builder surfaces.
        """
        if typed_error_counts is None:
            typed_error_counts = {}
        checks: list[dict] = []
        missing: list[str] = []

        if inputs.get("subtask_focus") is not None:
            # Focused mode: check expected artifacts
            expected = inputs.get("expected_artifacts", [])
            artifact_names = [a.get("name", "") for a in artifacts]
            missing_files = [f for f in expected if f not in artifact_names]
            checks.append(
                {
                    "check": "expected_artifacts",
                    "expected": expected,
                    "present": [f for f in expected if f in artifact_names],
                    "missing": missing_files,
                    "passed": len(missing_files) == 0,
                }
            )
            if missing_files:
                missing.extend(f"file:{f}" for f in missing_files)
        else:
            # Legacy mode: at least one test file with content
            test_files = [
                a
                for a in artifacts
                if "test" in a.get("name", "").lower()
                and len(a.get("content", "")) > _STUB_THRESHOLD_BYTES
            ]
            checks.append(
                {
                    "check": "test_file_presence",
                    "test_files_found": len(test_files),
                    "passed": len(test_files) > 0,
                }
            )
            if not test_files:
                missing.append("test_files")

        # Non-stub check (both modes)
        stubs = _detect_stubs(artifacts)
        checks.append(
            {
                "check": "non_stub_files",
                "stubs_found": stubs,
                "passed": len(stubs) == 0,
            }
        )

        # #670: typed acceptance on the qa surface — same seam as dev/builder.
        await self._evaluate_typed_acceptance(
            inputs, artifacts, checks, missing, typed_error_counts
        )

        # #423 parity with dev: evidence-gap rows are honest non-passes that
        # must not fail the task (a correction cannot repair an evaluator
        # limitation) — they block at the SIP-0096 roll-up instead.
        passed = (
            all(c.get("passed", True) or c.get("evidence_gap", False) for c in checks)
            and not missing
        )
        passed_count = sum(1 for c in checks if c.get("passed", True))
        coverage = passed_count / len(checks) if checks else 1.0

        summary_parts = []
        if missing:
            summary_parts.append(f"Missing: {', '.join(missing)}")
        if stubs:
            summary_parts.append(f"Stub files: {', '.join(stubs)}")
        # #670 diagnosability parity with dev (pf-33: name what failed)
        typed_failed = [
            c
            for c in checks
            if c.get("check", "").startswith("acceptance:")
            and c.get("status") in {ResultStatus.FAILED, ResultStatus.ERROR}
        ]
        if typed_failed:
            total_typed = sum(1 for c in checks if c.get("check", "").startswith("acceptance:"))
            summary_parts.append(f"Typed checks failed: {len(typed_failed)} of {total_typed}")

        return ValidationResult(
            passed=passed,
            checks=checks,
            missing_components=missing,
            coverage_ratio=coverage,
            summary="; ".join(summary_parts) or "All checks passed",
        )

    def _get_source_artifacts(self, inputs: dict[str, Any]) -> dict[str, str]:
        """Get source artifacts filtered by capability (D4, D9).

        Includes source files (by ``source_filter`` extension, non-test) AND the
        capability's ``build_support_files`` (config/entry files matched by
        basename — package.json, vite.config.js, index.html, …). Without the
        support files the QA build/test workspace can't build the deliverable and
        the frontend build check (#290) + vitest skip on "no package.json" (#296).
        """
        capability = get_capability(effective_capability_name(inputs.get("resolved_config")))
        contents = inputs.get("artifact_contents", {})
        support = set(getattr(capability, "build_support_files", ()))
        sources = {}
        for key, value in contents.items():
            basename = key.replace("\\", "/").rsplit("/", 1)[-1]
            is_source = any(
                key.endswith(ext) for ext in capability.source_filter
            ) and not _is_test_file(key, capability.test_file_patterns)
            if is_source or basename in support:
                sources[key] = value
        return sources

    @staticmethod
    def _fence_lang(path: str) -> str:
        """Return the appropriate code fence language for a file path."""
        if path.endswith((".js", ".jsx", ".mjs")):
            return "javascript"
        if path.endswith((".ts", ".tsx")):
            return "typescript"
        return "python"

    def _build_user_prompt(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        val_plan: str | None = None,
        sources: dict[str, str] | None = None,
        capability_name: str = DEFAULT_DEV_CAPABILITY,
    ) -> str:
        """Build prompt with validation plan + source code for test generation."""
        capability = get_capability(capability_name)
        parts = [f"## Product Requirements Document\n\n{prd}"]

        if val_plan:
            parts.append(f"\n\n## Validation Plan\n\n{val_plan}")

        if sources:
            parts.append("\n\n## Source Files to Test\n")
            for path, code in sources.items():
                lang = self._fence_lang(path)
                parts.append(f"\n### {path}\n```{lang}\n{code}\n```\n")

        parts.append(capability.test_prompt_supplement)

        # Prior analysis last — prompt guard truncates from this heading onward
        if prior_outputs:
            parts.append("\n\n## Prior Analysis from Upstream Roles\n")
            for role, summary in prior_outputs.items():
                parts.append(f"### {role}\n{summary}\n")

        return "\n".join(parts)

    async def _append_contract_probe_rows(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        patched_files: list[dict[str, Any]] | None = None,
    ) -> None:
        """Execute the seeded contract's behavioral probes (SIP-0098 §6.4, phase 98.5).

        Bind mode injects the contract's probe specs into this task's inputs
        (``contract_probes``, serialized ``Probe`` dicts). The app workspace is
        materialized from the same source artifacts the suite ran against, the
        runner boots it per the default execution profile, and each outcome lands
        as its own criterion-ID-stamped check row in ``validation_result`` — the
        rollup's contract-coverage accounting counts it like any other criterion.

        Additive evidence only, on both verdict paths (the #407 frontend_build
        pattern): a failed probe surfaces at the run verdict/rollup, not as a task
        failure here. A malformed entry is logged and skipped — the rollup then
        reports that criterion not-executed, never a silent pass.
        """
        raw = inputs.get("contract_probes")
        if not raw:
            return

        from squadops.capabilities.handlers.probe_runner import probe_check_rows, run_probes
        from squadops.capabilities.scaffold import scaffold_stack_for
        from squadops.cycles.patch_verification import materialize_artifacts
        from squadops.cycles.verification_contract import Probe

        probes = []
        for entry in raw:
            try:
                probes.append(Probe.from_dict(entry))
            except ValueError:
                logger.warning("Skipping malformed contract_probes entry: %r", entry)
        if not probes:
            return

        sources = self._get_source_artifacts(inputs)
        artifacts = [{"name": path, "content": content} for path, content in sources.items()]
        if patched_files:
            # #639: on the retest path the PATCHED tree must be under probe.
            # Sources are the dispatch-time workspace — probing only them
            # re-verifies the pre-repair app, and an accepted repair that
            # regresses probed behavior sails through (pf-50 shipped 200
            # against a pinned 201). materialize is last-wins, so the repaired
            # files overwrite their dispatch-time versions — the same overlay
            # order the retest suite run uses.
            artifacts.extend(
                {"name": f["filename"], "content": f.get("content", "")}
                for f in patched_files
                if isinstance(f, dict) and f.get("filename")
            )
        with tempfile.TemporaryDirectory(prefix="qa_probes_") as tmp:
            workspace = Path(tmp)
            materialize_artifacts(artifacts, workspace)
            # #822: boot the stack this cycle actually builds. Before this, `run_probes`
            # took the FastAPI profile as a default argument and nothing overrode it, so
            # every stack was booted with `uvicorn backend.main:app`.
            stack = scaffold_stack_for(inputs.get("resolved_config"))
            outcomes = await asyncio.to_thread(run_probes, workspace, probes, stack=stack)

        vr = outputs.setdefault("validation_result", {})
        vr.setdefault("checks", []).extend(probe_check_rows(outcomes))

    @staticmethod
    async def _run_test_suite(
        capability: Any,
        sources: dict[str, str],
        extracted: list[dict],
    ) -> tuple[Any, dict]:
        """Run the build-validation suite and return (result, report_artifact).

        Framework dispatch (pytest/vitest/both) and the #276 frontend build check
        live in ``test_runner`` (which owns test-framework knowledge). This handler
        stays framework-agnostic — it passes ``capability.test_framework`` through
        and reads only the generic ``RunTestsResult``.
        """
        from squadops.capabilities.handlers.test_runner import run_build_validation

        source_file_records = [{"path": p, "content": c} for p, c in sources.items()]
        test_file_records = [
            {"path": rec["filename"], "content": rec["content"]} for rec in extracted
        ]

        test_result = await run_build_validation(
            capability.test_framework,
            source_file_records,
            test_file_records,
            timeout_seconds=capability.test_timeout_seconds,
        )

        # #935: whether the suite actually RAN was recoverable only from an artifact a
        # human had to open. `tests_pass` is exit-code driven, so "did not execute" and
        # "executed and passed" are one keystroke apart in the record and neither leaves
        # a log line. This is the same class as #926's emission capture: when a window
        # roll needs triage, the first question is what the runner did, and the answer
        # should not require archaeology.
        #
        # `uncollected` is logged beside the counts on purpose. A file the runner never
        # collected verifies nothing while the collected ones read green — SIP-0104 roll 1
        # shipped exactly that, and a count of test FILES cannot distinguish the two.
        logger.info(
            "qa_test_handler suite: framework=%s executed=%s exit_code=%s tests_passed=%s "
            "test_files=%s source_files=%s uncollected=%s error=%r",
            capability.test_framework,
            test_result.executed,
            test_result.exit_code,
            test_result.tests_passed,
            test_result.test_file_count,
            test_result.source_file_count,
            list(test_result.uncollected_test_files or ()),
            test_result.error,
        )

        report_lines = [
            "# Test Execution Report\n",
            f"**Result:** {test_result.summary}\n",
            f"**Exit code:** {test_result.exit_code}\n",
            f"**Test files:** {test_result.test_file_count}\n",
            f"**Source files:** {test_result.source_file_count}\n",
        ]
        if test_result.uncollected_test_files:
            # SIP-0104 roll 1: a suite the runner never collected verifies nothing while
            # the collected ones read green. Named in the report a human actually reads.
            report_lines.append(
                "\n**NOT COLLECTED (these ran nothing):** "
                + ", ".join(f"`{p}`" for p in test_result.uncollected_test_files)
                + "\n"
            )
        if test_result.stdout:
            report_lines.append(f"\n## stdout\n\n```\n{test_result.stdout}\n```\n")
        if test_result.stderr:
            report_lines.append(f"\n## stderr\n\n```\n{test_result.stderr}\n```\n")
        if test_result.error:
            report_lines.append(f"\n## Error\n\n{test_result.error}\n")

        report_artifact = {
            "name": "test_report.md",
            "content": "\n".join(report_lines),
            "media_type": "text/markdown",
            "type": "test_report",
        }
        return test_result, report_artifact

    @staticmethod
    def _prompt_scoped_contents(
        artifact_contents: dict[str, str],
        expected_artifacts: list[Any],
    ) -> dict[str, str]:
        """pf-33: scope the focused prompt's source dump to the top-level
        package(s) the task's own artifacts live in (the RC2 package rule at
        the prompt seam). m007's prompt carried all 16 files (~18k tokens,
        every frontend .jsx included) into a backend suite task — prefill cost
        plus rambling pressure against the 8192 completion clamp, and the
        truncation crashed collection. No expected artifacts or no package
        match → contents unchanged (never starve the prompt).
        """
        packages = {
            str(e).strip().lstrip("./").partition("/")[0] for e in (expected_artifacts or []) if e
        }
        if not packages:
            return artifact_contents
        scoped = {
            name: content
            for name, content in artifact_contents.items()
            if str(name).strip().lstrip("./").partition("/")[0] in packages
        }
        return scoped or artifact_contents

    async def _behavior_contract_section(
        self, context: ExecutionContext, inputs: dict[str, Any]
    ) -> str:
        """Render the API BEHAVIOR CONTRACT block from executor-threaded lines, or "".

        #629 / pf-54: the contract pinned POST /runs → 201 and the error-code→status
        map, but only probes and repair prompts ever saw them — the INITIAL suite
        generation did not, and all five authored suite versions asserted 200-on-create
        (three added an undeclared /api prefix). The lines are contract-derived data
        (``VerificationContract.behavior_expectation_lines``); all instruction prose
        lives in the appendix asset (CLAUDE.md #448).
        """
        lines = [str(line).strip() for line in (inputs.get("api_behavior_contract") or [])]
        lines = [line for line in lines if line]
        if not lines:
            return ""
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return ""
        rendered = await renderer.render(
            "request.qa_test_behavior_contract_appendix",
            {"behavior_lines": "\n".join(f"- {line}" for line in lines)},
        )
        return rendered.content

    async def _dom_anchor_section(self, context: ExecutionContext, inputs: dict[str, Any]) -> str:
        """Render the DOM ANCHOR CONTRACT block from executor-threaded lines, or "".

        #659 / fay-6, fay-12: frontend suites churned every correction round on
        invented render details (roles, text, structure) because nothing
        arbitrates the DOM the way the api_behavior_contract arbitrates
        statuses. The lines are manifest-derived data
        (``scaffold.testid_surface_instructions``) and the view author receives
        the same inventory with an attach-and-preserve instruction; all prose
        lives in the appendix asset (CLAUDE.md #448).
        """
        lines = [str(line).strip() for line in (inputs.get("dom_testid_surface") or [])]
        lines = [line for line in lines if line]
        if not lines:
            return ""
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return ""
        rendered = await renderer.render(
            "request.qa_test_dom_anchor_appendix",
            {"testid_lines": "\n".join(f"- {line}" for line in lines)},
        )
        return rendered.content

    async def _frozen_surface_section(
        self, context: ExecutionContext, inputs: dict[str, Any]
    ) -> str:
        """Render the APPLICATION TREE block from executor-threaded lines, or "".

        Roll 9 (cyc_a92eaa4f4052): the suite author imports app modules and packages,
        but its prompt-scoped artifact view is cut to the suite's own package prefix —
        so the tree it imports FROM is exactly what it cannot see. The emitted suite
        opened with `import request from 'supertest'` against a package.json declaring
        no such package, and V2's wrote `from .store import reset` against a module
        reachable only as `backend.store` (#787). The lines are manifest-derived data
        (``scaffold.frozen_surface_index_lines``), the same index dev receives (#861);
        all instruction prose lives in the appendix asset (CLAUDE.md #448).
        """
        lines = [str(line).strip() for line in (inputs.get("frozen_surface") or [])]
        lines = [line for line in lines if line]
        if not lines:
            return ""
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return ""
        rendered = await renderer.render(
            "request.qa_test_frozen_surface_appendix",
            {"frozen_lines": "\n".join(lines)},
        )
        return rendered.content

    async def _fill_mode_section(self, context: ExecutionContext, inputs: dict[str, Any]) -> str:
        """Render the FILL MODE block when the envelope carries the scaffold, or "".

        SIP-0104 §4.5: the author receives the shells (read-only) and the coverage
        inventory — data derived from the slot table by the fill module; every
        instruction lives in the managed asset (#448). Coverage inventory only: no
        generated coaching (SIP §12 keeps richer briefs as follow-on work).
        """
        scaffold_input = inputs.get("verification_scaffold") or {}
        manifest_dict = scaffold_input.get("manifest")
        files = scaffold_input.get("files") or []
        if not manifest_dict or not files:
            return ""
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return ""
        from squadops.capabilities.scaffold import error_envelope_lines
        from squadops.capabilities.verification_scaffold import VerificationScaffoldManifest
        from squadops.capabilities.verification_scaffold_fill import coverage_inventory_lines

        record = VerificationScaffoldManifest.from_dict(manifest_dict)
        slot_lines = "\n".join(f"- {line}" for line in coverage_inventory_lines(record))
        shell_parts = [f"**{f['name']}:**\n```typescript\n{f['content']}\n```" for f in files]
        # #911: half the slots are error behaviors and nothing showed the author the
        # envelope, so it invented `body.error_code` on two consecutive window rolls.
        # Keyed on the scaffold record's own stack — the fact is the stack's, not the
        # run's, so it stays correct when the brief is rendered without a manifest.
        envelope = "\n".join(f"- {line}" for line in error_envelope_lines(record.stack))
        # #933: the plan's authored deliverable, reframed as additive by the asset that
        # owns the emission contract. The focused prompt no longer states it as an
        # expected output file, so this is the only place it appears — the intent is
        # kept, its precedence is not.
        additive = "\n".join(f"- `{f}`" for f in (inputs.get("expected_artifacts") or []))
        rendered = await renderer.render(
            "request.qa_test_fill_mode_appendix",
            {
                "slot_lines": slot_lines,
                "shell_files": "\n\n".join(shell_parts),
                "error_envelope": envelope,
                "additive_files": additive,
            },
        )
        return rendered.content

    def _merge_fill_artifacts(
        self,
        scaffold_input: dict[str, Any],
        fill_emission: Any,
        artifacts: list[dict],
    ) -> tuple[list[dict], list[dict], dict[str, Any]]:
        """Merge parsed fills into the scaffold and bound the additive surface.

        Returns ``(artifacts, merged_suite_files, fill_merge_evidence)``. A
        path-addressed emission at a scaffold shell path is DROPPED and recorded — in
        fill mode the slot protocol is the only way to touch a shell (the SIP §4.3
        posture; region-level enforcement itself lands in P4). Every declared slot ends
        in exactly one disposition; missing and rejected slots render as failing states
        inside the merged shells, attributed to the fill layer.
        """
        from squadops.capabilities.additive_containment import assess_additive_suite
        from squadops.capabilities.verification_scaffold import VerificationScaffoldManifest
        from squadops.capabilities.verification_scaffold_fill import (
            measure_assertion_strength,
            merge_fills,
        )

        record = VerificationScaffoldManifest.from_dict(scaffold_input["manifest"])
        shell_paths = {f.path for f in record.files}
        dropped = sorted(a["name"] for a in artifacts if a["name"] in shell_paths)
        kept = [a for a in artifacts if a["name"] not in shell_paths]
        merged = merge_fills(list(scaffold_input["files"]), record, fill_emission)
        merged_artifacts = [
            {
                "name": f.path,
                "content": f.content,
                "media_type": _classify_file(f.path)[1],
                "type": "test",
            }
            for f in merged.files
        ]
        evidence = {
            "dispositions": [
                {"slot_id": d.slot_id, "disposition": d.disposition, "detail": d.detail}
                for d in merged.dispositions
            ],
            "counts": merged.disposition_counts(),
            "misaddressed": [
                {"slot_id": d.slot_id, "detail": d.detail} for d in merged.misaddressed
            ],
            "dropped_shell_rewrites": dropped,
            # #980: what the fills ASSERT, not just that slots were filled. The shakedown
            # banked a retreat as a clean success because the record could not tell 8 rich
            # fills from 8 that had dropped every store assertion. Banked rather than logged
            # so the per-roll record reads it from stored state.
            "assertion_strength": {
                **measure_assertion_strength(fill_emission),
                # The retreat had TWO halves and the fills are only one. Shakedown #1's
                # passing attempt also dropped an entire additive suite — 81 store calls
                # through TABLES, no mocking — and ran 8 test files where the failing
                # attempt ran 9. `extracted_files` went 1 -> 0 in a log line nobody read.
                "additive_files": sorted(a["name"] for a in kept),
            },
            # #1022: containment findings for the additive surface, banked and NOT
            # enforced. Every V7 counted red was additive-suite-side while all nine
            # delivered apps passed independent boot audits — the apps were fine, the
            # tests were not. The gate's shape is a design-review question (#1022), so
            # this records what a gate WOULD flag across real rolls first. Deploying a
            # rejection whose premise was never checked against real traffic is what
            # #1049 cost tonight.
            "additive_containment": assess_additive_suite(kept),
        }
        merged_suite_files = [{"filename": f.path, "content": f.content} for f in merged.files]
        return kept + merged_artifacts, merged_suite_files, evidence

    def _append_scaffold_evidence(
        self,
        outputs: dict[str, Any],
        test_result: Any,
        merged_suite_files: list[dict[str, Any]],
        fill_merge_evidence: dict[str, Any],
        scaffold_input: dict[str, Any],
        artifacts: list[dict],
    ) -> None:
        """Run the P5 pipeline and land its summary (SIP-0104 §5/§6).

        ONE landing: ``outputs["scaffold_evidence"]`` — the full summary, which
        ``build_failure_evidence`` threads into the correction loop's evidence (the same
        transport ``emission_failure`` and ``app_tracebacks`` ride) and the locus
        classifier reads from there.

        Deliberately NOT a ``validation_result.checks`` row. Roll 1 (cyc_04d36309d793)
        measured the cost of that: ``normalize_task_checks`` records any row carrying a
        ``status`` key, so an informational row aggregated as a verification check and
        surfaced in the cycle outcome's ``unverified`` list with reason ``unspecified``.
        Non-blocking, but a diagnostic is not evidence and must not be counted as one
        (SIP-0096 §6.1).
        """
        from squadops.capabilities.verification_scaffold import VerificationScaffoldManifest
        from squadops.cycles.scaffold_evidence import (
            build_scaffold_evidence_summary,
            classify_shell_failures,
            correlate,
        )

        record = VerificationScaffoldManifest.from_dict(scaffold_input["manifest"])
        dispositions = {
            d["slot_id"]: d["disposition"]
            for d in fill_merge_evidence.get("dispositions", [])
            if isinstance(d, dict)
        }
        merged_contents = {m["filename"]: m["content"] for m in merged_suite_files}
        observations = classify_shell_failures(
            list(getattr(test_result, "test_failures", ()) or ()),
            merged_contents,
            record,
            dispositions,
            runner_executed=bool(getattr(test_result, "executed", False)),
        )
        probe_rows = [
            row
            for row in (outputs.get("validation_result") or {}).get("checks") or []
            if isinstance(row, dict) and row.get("criterion_id")
        ]
        correlations = correlate(observations, probe_rows)
        shell_paths = set(merged_contents)
        additive_count = sum(
            1
            for a in artifacts
            if a.get("type") == "test"
            and str(a.get("name", "")).endswith((".test.ts", ".spec.ts"))
            and a.get("name") not in shell_paths
        )
        summary = build_scaffold_evidence_summary(
            record,
            dispositions,
            observations,
            correlations,
            additive_count,
            tuple(getattr(test_result, "uncollected_test_files", ()) or ()),
        )
        outputs["scaffold_evidence"] = summary.to_dict()

    def _build_focused_prompt(self, inputs: dict[str, Any]) -> str:
        """Build a focused prompt for manifest-driven QA subtasks (SIP-0086).

        RC-6: When subtask_focus is present, this path is used exclusively.
        """
        prd = inputs.get("prd", "")
        focus = inputs["subtask_focus"]
        description = inputs.get("subtask_description", "")
        expected_files = inputs.get("expected_artifacts", [])
        acceptance_criteria = inputs.get("acceptance_criteria", [])
        artifact_contents = self._prompt_scoped_contents(
            inputs.get("artifact_contents", {}), expected_files
        )

        # SIP-0104 (#933): in fill mode the deliverable is fills, and the appendix —
        # a managed asset — is the sole owner of the emission contract. Rendering an
        # authored filename here as "Expected Output Files" states a SECOND, competing
        # deliverable, and the closing directive below then makes it exclusive.
        fill_mode = bool(inputs.get("verification_scaffold"))

        parts = [f"## QA Task: {focus}\n\n{description}\n"]

        if not fill_mode:
            parts.append("### Expected Output Files\n")
            parts.extend(f"- `{f}`\n" for f in expected_files)

        # pf-36: typed criteria render ONLY through the authoritative expectations
        # block; the narrative section carries prose alone. The raw dump rendered
        # TypedChecks as dict-repr soup, so the corrected harness_boundary line
        # (and every other exact expectation) never reached the INITIAL suite
        # generation — eve self-built TestClient(app) on every fresh roll and only
        # her repairs (which get the block) complied. Same A2 treatment the repair
        # prompt received in pf-31 Fix A / pf-33.
        from squadops.cycles.contract_expectations import expectation_lines, prose_criteria

        typed_lines = expectation_lines(acceptance_criteria)
        if typed_lines:
            parts.append("\n### Contract Expectations (authoritative — apply exactly)\n")
            parts.extend(f"- {line}\n" for line in typed_lines)
            acceptance_criteria = prose_criteria(acceptance_criteria)
        if acceptance_criteria:
            parts.append("\n### Acceptance Criteria (narrative)\n")
            parts.extend(f"- {c}\n" for c in acceptance_criteria)

        parts.append(f"\n### Context\nPRD:\n{prd}\n")

        if artifact_contents:
            parts.append("\n### Source Artifacts to Test\n")
            for name, content in artifact_contents.items():
                lang = self._fence_lang(name)
                parts.append(f"**{name}:**\n```{lang}\n{content}\n```\n")

        # The "ONLY" clause is the direct negation of fill mode: it forbids emitting
        # anything but the authored file, and the fill appendix is appended AFTER it.
        # Roll 6 obeyed it exactly — one path-addressed file, zero fills, 8,192
        # completion tokens spent on the wrong deliverable. The rest of this
        # directive is orthogonal to fill mode and stays: the fence format is how
        # additive files are emitted, and the source-artifact guard has no
        # equivalent in the appendix.
        if not fill_mode:
            parts.append("\nProduce ONLY the files listed in Expected Output Files. ")
        else:
            parts.append("\n")
        parts.append(
            "Use fenced code blocks with ```language:path/to/file``` format. "
            "Do not reproduce source artifacts."
        )
        return "".join(parts)

    async def _handle_retest(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        capability: Any,
        start_time: float,
        retest_files: list[dict[str, Any]],
    ) -> HandlerResult:
        """Execute-only mode (#456): re-run a repaired test suite as-is.

        The correction loop's patch verification covers typed criteria only;
        ``tests_pass`` evidence is behavioral and must come from an actual
        execution of the repaired suite in this (the QA agent's) environment.
        No LLM is involved — the suite is provided in ``retest_files``, the
        source workspace comes from ``artifact_contents`` exactly as the
        original run saw it, and success is exactly "the suite passed".
        """
        del context  # no LLM/prompt ports in execute-only mode

        extracted = []
        for f in retest_files:
            if not isinstance(f, dict):
                continue
            filename = f.get("filename") or f.get("name") or f.get("path")
            if isinstance(filename, str) and filename:
                extracted.append({"filename": filename, "content": f.get("content", "")})
        if not extracted:
            return self._fail_result(start_time, inputs, "retest_files contained no usable files")

        sources = self._get_source_artifacts(inputs)
        test_result, test_report_artifact = await self._run_test_suite(
            capability, sources, extracted
        )

        artifacts = [
            {
                "name": f["filename"],
                "content": f["content"],
                "media_type": _classify_file(f["filename"])[1],
                "type": "test",
            }
            for f in extracted
        ]
        artifacts.append(test_report_artifact)

        checks: list[dict[str, Any]] = []
        missing: list[str] = []
        passed = bool(test_result.executed and test_result.tests_passed)
        if not passed:
            if test_result.executed:
                detail = f"tests_failed:exit_{test_result.exit_code}"
                summary = f"Repaired suite still fails (exit {test_result.exit_code})"
            else:
                reason = test_result.error or "runner_error"
                detail = f"tests_not_executed:{reason}"
                summary = f"Repaired suite not executed: {reason}"
            from squadops.capabilities.handlers.test_runner import failed_tests_pass_row

            checks.append(failed_tests_pass_row(test_result))
            missing.append(detail)
        else:
            summary = "Repaired suite passed"

        # #276 guard holds on the retest path too: a repair must not smuggle a
        # stub-fallback past the correction loop.
        from squadops.capabilities.handlers.stub_detection import (
            detect_self_mocking_tests,
            detect_stub_fallback_tests,
            inspected_js_test_paths,
            inspected_python_test_paths,
        )

        stub_offenders = detect_stub_fallback_tests(artifacts)
        checks.append(
            _authenticity_row(
                CHECK_NO_STUB_FALLBACK_TESTS, stub_offenders, inspected_python_test_paths(artifacts)
            )
        )
        if stub_offenders:
            passed = False
            missing.append(f"stub_fallback_tests:{','.join(stub_offenders)}")
            summary = f"{summary}; repaired test masks the entrypoint: {', '.join(stub_offenders)}"

        # #915 on the retest path for the same reason: a repair told to make the suite
        # pass can satisfy that instruction by mocking the subject, and mocking is the
        # cheapest way to make any assertion true.
        mock_offenders = detect_self_mocking_tests(artifacts)
        mock_paths = [path for path, _ in mock_offenders]
        checks.append(
            _authenticity_row(
                CHECK_NO_SELF_MOCKING_TESTS, mock_paths, inspected_js_test_paths(artifacts)
            )
        )
        if mock_offenders:
            passed = False
            missing.append(f"self_mocking_tests:{','.join(mock_paths)}")
            summary = (
                f"{summary}; repaired test never invokes the application: {', '.join(mock_paths)}"
            )

        passed_count = sum(1 for c in checks if c.get("passed"))
        outputs: dict[str, Any] = {
            "summary": f"[qa] Re-executed repaired suite ({len(extracted)} file(s)): {summary}",
            "role": self._role,
            "artifacts": artifacts,
            "test_result": {
                "executed": test_result.executed,
                "exit_code": test_result.exit_code,
                "tests_passed": test_result.tests_passed,
                "test_file_count": test_result.test_file_count,
                "source_file_count": test_result.source_file_count,
                "summary": test_result.summary,
            },
            "validation_result": {
                "passed": passed,
                "checks": checks,
                "missing_components": missing,
                "coverage_ratio": (passed_count / len(checks)) if checks else 1.0,
                "summary": summary,
            },
        }

        if passed:
            from squadops.cycles.task_outcome import TaskOutcome

            outputs["outcome_class"] = TaskOutcome.SUCCESS
        else:
            from squadops.cycles.task_outcome import FailureClassification, TaskOutcome

            outputs["outcome_class"] = TaskOutcome.SEMANTIC_FAILURE
            outputs["failure_classification"] = FailureClassification.WORK_PRODUCT

        # #407: frontend build is first-class evidence on this path too.
        fb = test_result.frontend_build
        if fb is not None:
            if fb.ran:
                fb_row: dict[str, Any] = {"check": CHECK_FRONTEND_BUILD, "passed": fb.ok}
            else:
                fb_row = {
                    "check": CHECK_FRONTEND_BUILD,
                    "executed": False,
                    "reason": _frontend_skip_reason(fb.error),
                }
            outputs["validation_result"]["checks"].append(fb_row)

        # SIP-0098 98.5: probe evidence rides the retest path too — a repaired
        # suite's run must not under-count contract-criterion coverage. The
        # patched files overlay the dispatch-time sources (#639).
        await self._append_contract_probe_rows(inputs, outputs, patched_files=extracted)

        duration_ms = (time.perf_counter() - start_time) * 1000
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
            metadata={"retest": True},
        )
        return HandlerResult(
            success=passed,
            outputs=outputs,
            _evidence=evidence,
            error=None if passed else summary,
        )

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        from squadops.capabilities.handlers.fenced_parser import extract_fenced_files

        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")
        resolved_config = inputs.get("resolved_config", {})
        capability_name = effective_capability_name(resolved_config)

        # Resolve capability (fail fast on unknown dev_capability)
        try:
            capability = get_capability(capability_name)
        except ValueError as exc:
            return self._fail_result(start_time, inputs, str(exc))

        # #456 execute-only mode: the correction loop re-runs a repaired suite
        # verbatim — no generation, no LLM. The verdict is the execution.
        if inputs.get("retest_files"):
            return await self._handle_retest(
                context, inputs, capability, start_time, inputs["retest_files"]
            )

        # SIP-0086 RC-6: focused prompt path for manifest-driven subtasks
        if inputs.get("subtask_focus") is not None:
            user_prompt = self._build_focused_prompt(inputs)
            behavior_section = await self._behavior_contract_section(context, inputs)
            if behavior_section:
                user_prompt = f"{user_prompt}\n{behavior_section}"
            dom_anchor_section = await self._dom_anchor_section(context, inputs)
            if dom_anchor_section:
                user_prompt = f"{user_prompt}\n{dom_anchor_section}"
            frozen_section = await self._frozen_surface_section(context, inputs)
            if frozen_section:
                user_prompt = f"{user_prompt}\n{frozen_section}"
            rendered = None
            sources = self._get_source_artifacts(inputs)
        else:
            # Legacy monolithic prompt path (unchanged)

            # Resolve plan artifacts with vault fallback (D3)
            val_plan = await self._resolve_with_vault_fallback(inputs, "validation_plan")
            sources = self._get_source_artifacts(inputs)

            # Check required artifacts (fail only when vault was available but empty)
            if val_plan is None and inputs.get("artifact_vault") is not None:
                return self._fail_result(
                    start_time, inputs, "Required plan artifacts not available"
                )

            rendered, user_prompt = await self._build_qa_prompt(
                context,
                prd,
                prior_outputs,
                capability,
                val_plan,
                sources,
                capability_name,
            )

        # SIP-0104 P3: fill mode rides both prompt paths, presence-gated on the
        # scaffold input — absent input renders nothing and stays byte-identical.
        fill_section = await self._fill_mode_section(context, inputs)
        if fill_section:
            user_prompt = f"{user_prompt}\n{fill_section}"

        # #448: include the qa.test task_type fragment (dependency constraint,
        # scope discipline) in the assembled system prompt. The fragment is the
        # externalized owner of task-content guidance — not inline literals.
        assembled = context.ports.prompt_service.assemble(
            self._role, "agent_start", task_type="qa.test"
        )
        system_prompt = assembled.content

        # Resolve model, token budget, and prompt guard
        model_name, max_tokens, context_window = self._resolve_model_budget(
            inputs, capability.max_completion_tokens, context.ports.llm.default_model
        )

        # #566: a re-dispatch after a zero-extraction failure carries the prior
        # marker — tell the model exactly what was discarded and the required
        # fence format instead of re-rolling blind.
        user_prompt = await self._apply_emission_retry_feedback(context, inputs, user_prompt)

        try:
            user_prompt = _guard_prompt_size(
                system_prompt,
                user_prompt,
                max_tokens,
                context_window,
            )
        except ValueError as exc:
            return self._fail_result(start_time, inputs, str(exc))

        generation_timeout = resolved_config.get("generation_timeout", 300)
        agent_overrides = inputs.get("agent_config_overrides", {})
        agent_model = inputs.get("agent_model") or None

        chat_kwargs: dict[str, Any] = {
            "max_tokens": max_tokens,
            "timeout_seconds": generation_timeout,
        }
        if agent_model:
            chat_kwargs["model"] = agent_model
        if "temperature" in agent_overrides:
            chat_kwargs["temperature"] = agent_overrides["temperature"]

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

        try:
            response = await context.ports.llm.chat_stream_with_usage(messages, **chat_kwargs)
        except LLMError as exc:
            logger.warning("LLM call failed for %s: %s", self._handler_name, exc)
            return self._fail_result(start_time, inputs, str(exc))

        content = response.content
        log_emission_shape(self._handler_name, content, response.completion_tokens)
        llm_duration_ms = (time.perf_counter() - start_time) * 1000
        self._record_generation(
            context,
            user_prompt,
            content,
            llm_duration_ms,
            model_name,
            rendered=rendered,
            chat_response=response,
        )

        scaffold_input = inputs.get("verification_scaffold")
        fill_emission = None
        extraction_source = content
        if scaffold_input:
            from squadops.capabilities.verification_scaffold_fill import (
                parse_fill_emission,
                strip_fill_blocks,
            )

            # Fill fences would otherwise extract as files named "slot-…" — the fill
            # protocol and the additive-file surface must not compete for bytes.
            fill_emission = parse_fill_emission(content)
            extraction_source = strip_fill_blocks(content)

        extracted = extract_fenced_files(
            extraction_source, expected_artifacts=inputs.get("expected_artifacts")
        )
        # #924: the three outcomes below are indistinguishable afterwards, and P3 renders
        # a REJECTED fill as the same failing state as a MISSING one — so "the author
        # emitted nothing", "the author emitted fills that were refused", and "the author
        # emitted a file instead of fills" all present identically as unfilled slots.
        # Window rolls 3 and 5 were each diagnosed twice from the result rather than the
        # emission, wrongly, for exactly this reason.
        logger.info(
            "%s emission parse: fills=%d duplicate_slots=%d extracted_files=%d "
            "expected=%s scaffold_bound=%s",
            self._handler_name,
            len(fill_emission.fills) if fill_emission else 0,
            len(fill_emission.duplicates) if fill_emission else 0,
            len(extracted),
            inputs.get("expected_artifacts"),
            bool(scaffold_input),
        )
        if not extracted and not (fill_emission and fill_emission.fills):
            from squadops.cycles.emission_integrity import no_fenced_blocks_failure

            self._log_no_fenced_blocks(content)
            return self._fail_result(
                start_time,
                inputs,
                "No valid fenced code blocks found",
                outputs={
                    "artifacts": [
                        {
                            "name": "build_warnings.md",
                            "content": content,
                            "media_type": "text/markdown",
                            "type": "document",
                        }
                    ],
                    # #566: machine-readable marker — the executor's retry path
                    # turns it into aimed feedback; the correction loop's locus
                    # classifier reads it as a test-artifact-locus signal.
                    "emission_failure": no_fenced_blocks_failure(
                        len(content), inputs.get("expected_artifacts")
                    ),
                },
            )

        artifacts = [
            {
                "name": f["filename"],
                "content": f["content"],
                "media_type": _classify_file(f["filename"])[1],
                "type": "test",
            }
            for f in extracted
        ]

        # SIP-0086: Output validation + self-evaluation
        evidence_extra: dict[str, Any] = {}
        output_validation_enabled = resolved_config.get("output_validation", False)

        # SIP-0104 P3: merge fills into the scaffold. The merged shells join BOTH the
        # stored artifacts and the suite-execution set; shell-path rewrites are dropped
        # and recorded. shell_drop_paths also guards the self-eval merge below.
        shell_drop_paths: set[str] = set()
        if scaffold_input:
            artifacts, merged_suite_files, fill_merge_evidence = self._merge_fill_artifacts(
                scaffold_input, fill_emission, artifacts
            )
            merged_names = {m["filename"] for m in merged_suite_files}
            shell_drop_paths = merged_names
            extracted = [
                f for f in extracted if f["filename"] not in merged_names
            ] + merged_suite_files
            evidence_extra["fill_merge"] = fill_merge_evidence

        # #670 / RC-9b: shared across self-eval passes so per-criterion
        # evaluator-error counts accumulate (2-strikes escalation), dev parity
        typed_error_counts: dict[str, int] = {}

        if output_validation_enabled:
            validation = await self._validate_output(
                inputs, artifacts, typed_error_counts=typed_error_counts
            )

            # Self-evaluation loop
            if not validation.passed:
                # #946: this branch is the SOLE trigger for a second model call, and
                # nothing recorded which check opened it. The run summary afterwards
                # showed 29/29 accepted, so the failure was unreadable from stored state
                # — a whole extra generation, invisible in the record it produced. Roll 1
                # burned 3,574 tokens here (68% of the qa task's wall clock) and the only
                # way to learn why was to reconstruct it by hand from artifacts.
                #
                # Log the failing checks by name, not the count. "1 check failed" sends a
                # reader back to the artifacts, which is the state this exists to end.
                # `expected_artifacts` in particular fails for a reason fill mode makes
                # invisible (#947): the plan's chosen filename is demoted while the check
                # still hard-requires it.
                failing = failing_check_names(validation.checks)
                logger.info(
                    "qa_test_handler self_eval trigger: failing_checks=%s missing=%s summary=%r",
                    failing or ["<none named>"],
                    validation.missing_components,
                    validation.summary,
                )
                max_self_eval = resolved_config.get("max_self_eval_passes", 1)
                self_eval_count = 0

                while not validation.passed and self_eval_count < max_self_eval:
                    self_eval_count += 1
                    followup_prompt = self._build_self_eval_prompt(validation, artifacts)

                    try:
                        followup_response = await context.ports.llm.chat_stream_with_usage(
                            [
                                ChatMessage(role="system", content=system_prompt),
                                ChatMessage(role="user", content=user_prompt),
                                ChatMessage(role="assistant", content=content),
                                ChatMessage(role="user", content=followup_prompt),
                            ],
                            **chat_kwargs,
                        )
                    except LLMError as exc:
                        logger.warning(
                            "Self-eval LLM call failed for %s: %s",
                            self._handler_name,
                            exc,
                        )
                        break

                    log_emission_shape(
                        f"{self._handler_name}:self_eval",
                        followup_response.content,
                        followup_response.completion_tokens,
                    )
                    new_extracted = extract_fenced_files(followup_response.content)
                    new_artifacts = [
                        {
                            "name": f["filename"],
                            "content": f["content"],
                            "media_type": _classify_file(f["filename"])[1],
                            "type": "test",
                        }
                        for f in new_extracted
                        # SIP-0104 P3: a self-eval pass must not rewrite merged shells
                        # either — the slot protocol is the only shell surface.
                        if f["filename"] not in shell_drop_paths
                    ]
                    artifacts = self._merge_artifacts(artifacts, new_artifacts, evidence_extra)
                    validation = await self._validate_output(
                        inputs, artifacts, typed_error_counts=typed_error_counts
                    )

                evidence_extra["self_eval_passes"] = self_eval_count
        else:
            validation = ValidationResult(passed=True, summary="Validation disabled")

        # Run generated tests and build report
        test_result, test_report_artifact = await self._run_test_suite(
            capability, sources, extracted
        )
        artifacts.append(test_report_artifact)

        # Fold test-execution outcome into validation. The qa.test handler's
        # objective is "produce tests that pass against the dev artifacts";
        # artifacts-present-and-non-stub is necessary but not sufficient. A
        # passing test file count with exit_code != 0 (e.g., import errors
        # causing pytest to collect 0 tests) must surface as SEMANTIC_FAILURE
        # so the correction protocol activates.
        if output_validation_enabled and not (test_result.executed and test_result.tests_passed):
            if test_result.executed:
                detail = f"tests_failed:exit_{test_result.exit_code}"
                fail_note = f"Tests failed (exit {test_result.exit_code})"
            else:
                reason = test_result.error or "runner_error"
                detail = f"tests_not_executed:{reason}"
                fail_note = f"Tests not executed: {reason}"

            from squadops.capabilities.handlers.test_runner import failed_tests_pass_row

            validation.checks.append(failed_tests_pass_row(test_result))
            validation.passed = False
            validation.missing_components.append(detail)
            validation.summary = (
                fail_note
                if validation.summary in ("", "All checks passed")
                else f"{validation.summary}; {fail_note}"
            )
            if validation.checks:
                passed_count = sum(1 for c in validation.checks if c["passed"])
                validation.coverage_ratio = passed_count / len(validation.checks)

        if output_validation_enabled:
            # #276: a generated test that hides a broken entrypoint import behind
            # an ImportError fallback validates a stub app, not the deliverable —
            # so `tests_passed` above can be falsely green (the stub collects and
            # passes). Flag it so acceptance fails and the correction loop
            # regenerates the test against the real module.
            from squadops.capabilities.handlers.stub_detection import (
                detect_self_mocking_tests,
                detect_stub_fallback_tests,
                inspected_js_test_paths,
                inspected_python_test_paths,
            )

            stub_offenders = detect_stub_fallback_tests(artifacts)
            validation.checks.append(
                _authenticity_row(
                    CHECK_NO_STUB_FALLBACK_TESTS,
                    stub_offenders,
                    inspected_python_test_paths(artifacts),
                )
            )
            if stub_offenders:
                validation.passed = False
                validation.missing_components.append(
                    f"stub_fallback_tests:{','.join(stub_offenders)}"
                )
                note = (
                    "Generated test masks the real entrypoint behind an "
                    f"ImportError stub: {', '.join(stub_offenders)}"
                )
                validation.summary = (
                    note
                    if validation.summary in ("", "All checks passed")
                    else f"{validation.summary}; {note}"
                )

            # #915: the TypeScript sibling, and worse — a stub-fallback suite fails
            # loudly because a reconstruction misbehaves, while a self-mocking suite
            # asserts what it told its own mock to return and therefore PASSES. Fills
            # cannot do this (the frozen spine invokes the handler and enforcement
            # rejects edits to it); additive files carried the rule only as prose.
            mock_offenders = detect_self_mocking_tests(artifacts)
            mock_paths = [path for path, _ in mock_offenders]
            validation.checks.append(
                _authenticity_row(
                    CHECK_NO_SELF_MOCKING_TESTS, mock_paths, inspected_js_test_paths(artifacts)
                )
            )
            if mock_offenders:
                validation.passed = False
                validation.missing_components.append(f"self_mocking_tests:{','.join(mock_paths)}")
                note = "Generated test never invokes the application: " + "; ".join(
                    f"{path} {reason}" for path, reason in mock_offenders
                )
                validation.summary = (
                    note
                    if validation.summary in ("", "All checks passed")
                    else f"{validation.summary}; {note}"
                )

            # Both authenticity rows now bank unconditionally, so the ratio moves on a
            # clean pass too — recompute once here rather than only on the failure legs.
            if validation.checks:
                passed_count = sum(1 for c in validation.checks if c.get("passed"))
                validation.coverage_ratio = passed_count / len(validation.checks)

            evidence_extra["validation_result"] = {
                "passed": validation.passed,
                "checks": validation.checks,
                "missing_components": validation.missing_components,
                "coverage_ratio": validation.coverage_ratio,
                "summary": validation.summary,
            }

            # Issue #114: emit per-task typed-check evaluation artifact for
            # the gate evaluator. Same shape/semantics as the dev handler.
            tce_artifact = self._build_typed_check_evaluation_artifact(
                validation.checks,
                inputs.get("subtask_index"),
                self._capability_id,
                inputs.get("workspace_revision_id"),
            )
            if tce_artifact is not None:
                artifacts.append(tce_artifact)

        if test_result.tests_passed:
            test_suffix = ", all tests passed"
        elif test_result.executed:
            test_suffix = f", tests failed (exit code {test_result.exit_code})"
        else:
            test_suffix = f", tests not run: {test_result.error}" if test_result.error else ""

        # SIP-0084 §10: build prompt provenance for artifact traceability
        provenance: dict[str, Any] = {
            "system_prompt_bundle_hash": assembled.assembly_hash,
        }
        if rendered is not None:
            provenance["request_template_id"] = rendered.template_id
            provenance["request_template_version"] = rendered.template_version
            provenance["request_render_hash"] = rendered.render_hash
            provenance["prompt_environment"] = "production"

        outputs: dict[str, Any] = {
            "summary": f"[qa] Generated {len(artifacts) - 1} test file(s){test_suffix}",
            "role": self._role,
            "artifacts": artifacts,
            # #431: generated-vs-stored accounting for extraction-loss diagnosis
            "emission_stats": _emission_stats(len(content), artifacts),
            "test_result": {
                "executed": test_result.executed,
                "exit_code": test_result.exit_code,
                "tests_passed": test_result.tests_passed,
                "test_file_count": test_result.test_file_count,
                "source_file_count": test_result.source_file_count,
                "summary": test_result.summary,
            },
            "prompt_provenance": provenance,
        }

        # Phase 6: Outcome classification
        if validation.passed:
            from squadops.cycles.task_outcome import TaskOutcome

            outputs["outcome_class"] = TaskOutcome.SUCCESS
        else:
            from squadops.cycles.task_outcome import (
                FailureClassification,
                TaskOutcome,
            )

            outputs["outcome_class"] = TaskOutcome.SEMANTIC_FAILURE
            outputs["failure_classification"] = FailureClassification.WORK_PRODUCT
            outputs["validation_result"] = evidence_extra.get("validation_result", {})

        # #407: record the fullstack frontend build as a first-class SIP-0096
        # check on BOTH the pass and fail paths. run_build_validation folds a
        # frontend skip/failure into the combined result, so without this a
        # required frontend_build that never executed (Node absent, #306) would
        # read green — the SIP-0070 D13 false-green. A *passing* fullstack run
        # must record frontend_build=passed too, or requiring it would false-block.
        # Runs after the classification above so it isn't overwritten by the
        # failure-path validation_result assignment.
        fb = test_result.frontend_build
        if fb is not None:
            if fb.ran:
                fb_row: dict[str, Any] = {"check": CHECK_FRONTEND_BUILD, "passed": fb.ok}
            else:
                fb_row = {
                    "check": CHECK_FRONTEND_BUILD,
                    "executed": False,
                    "reason": _frontend_skip_reason(fb.error),
                }
            vr = outputs.setdefault("validation_result", {})
            vr.setdefault("checks", []).append(fb_row)

        # SIP-0098 98.5: execute seeded behavioral probes and append their rows
        # (both verdict paths, like frontend_build above — additive evidence).
        await self._append_contract_probe_rows(inputs, outputs)

        # SIP-0104 P5: classify shell failures, correlate with the probe rows just
        # appended, and bank the evidence summary. After the probes on purpose —
        # correlation joins on the shared criterion id.
        if scaffold_input:
            self._append_scaffold_evidence(
                outputs,
                test_result,
                merged_suite_files,
                fill_merge_evidence,
                scaffold_input,
                artifacts,
            )

        duration_ms = (time.perf_counter() - start_time) * 1000
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
            metadata=evidence_extra if evidence_extra else None,
        )

        return HandlerResult(
            success=validation.passed,
            outputs=outputs,
            _evidence=evidence,
            error=validation.summary if not validation.passed else None,
        )

    async def _build_qa_prompt(
        self,
        context: ExecutionContext,
        prd: str,
        prior_outputs: dict | None,
        capability: Any,
        val_plan: str | None,
        sources: dict[str, str],
        capability_name: str,
    ) -> tuple[Any, str]:
        """Build the QA prompt via renderer or fallback. Returns (rendered, user_prompt)."""
        rendered = None
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables: dict[str, str] = {
                "prd": prd,
                "test_supplement": capability.test_prompt_supplement,
            }
            if val_plan:
                variables["validation_plan"] = f"\n\n## Validation Plan\n\n{val_plan}"
            if sources:
                source_parts = ["\n\n## Source Files to Test\n"]
                for path, code in sources.items():
                    lang = self._fence_lang(path)
                    source_parts.append(f"\n### {path}\n```{lang}\n{code}\n```\n")
                variables["source_files"] = "\n".join(source_parts)
            variables["prior_outputs"] = self._format_prior_outputs(prior_outputs)
            rendered = await renderer.render(
                "request.qa_test.test_validate",
                variables,
            )
            return rendered, rendered.content

        user_prompt = self._build_user_prompt(
            prd,
            prior_outputs,
            val_plan=val_plan,
            sources=sources,
            capability_name=capability_name,
        )
        return None, user_prompt
