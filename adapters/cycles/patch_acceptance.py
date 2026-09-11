"""Candidate acceptance — turn a proposed repair into an accepted or rejected patch.

The accepted-patch path, lifted out of ``DispatchedFlowExecutor`` by step 2 of the 1.7.5
recovery extraction map. One sentence of responsibility: *turn a proposed repair into an
accepted or rejected candidate under grants, verification, retest and evidence rules.*

**The authority split this seam is one half of.** Two authorisation moments exist and
they stay distinct. *Repair authority* — what the repairing producer is permitted to
attempt — is a ``WriteGrant`` (``write_authorization.py``) resolved before generation by
``scaffold_enforcement``. *Candidate authorisation* — whether the emitted candidate lies
inside that authority — is what block 1 here checks, with the REPAIRING step's grants
(#1323, #1350). This module consumes the grant the repair resolved; it does not re-derive
one, and a second derivation of the same rule is the inconsistency Scoped Code Revision
exists to remove.

**The name.** ``PatchAcceptance`` is the current domain vocabulary — the thing accepted is
a patch everywhere the code and the records speak of it. When Scoped Code Revision lands
the accepted thing will not always originate as a file patch and ``CandidateAcceptance``
will age better; the name is not changed speculatively here, and the pressure is recorded
so the 1.8 plan renames it deliberately or explains why not (map §4 step 2).
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from adapters.cycles.execution_errors import _ExecutionError
from squadops.cycles.acceptance_evaluation import resolve_check_stack
from squadops.cycles.check_registry import (
    CHECK_TESTS_PASS,
    OWED_DERIVED,
    OWED_PRODUCED,
    OWED_UNDECLARED,
    compose_owed_framework_rows,
)
from squadops.cycles.correction_signature import REPAIR_REFUSED_MARKER
from squadops.cycles.patch_verification import (
    EXECUTED_IN_RUNTIME_API,
    FILE_ABSENT_REASONS,
    PATCH_PASSED,
    PATCH_UNVERIFIABLE,
    STRUCTURALLY_UNEVALUABLE_REASONS,
    overlay_artifacts,
    skip_reasons,
    supersede_evidence_artifacts,
    verify_patched_artifacts,
)
from squadops.cycles.scaffold_integrity_evidence import STAGE_PATCH_VERIFICATION
from squadops.tasks.models import TaskResultStatus
from squadops.tasks.task_types import emits_required_files

if TYPE_CHECKING:
    from squadops.cycles.models import ArtifactRef, Cycle
    from squadops.tasks.models import TaskEnvelope, TaskResult

logger = logging.getLogger(__name__)


def correction_is_deadlocked(
    verification_status: str, verification_reason: str | None, *, retest_decides: bool
) -> bool:
    """True when no further round could ever produce a verdict (#1221).

    The invariant: **a repair loop must never re-dispatch a task whose verification
    cannot, even in principle, return a verdict.** pf-47/pf-49 asserted exactly that and
    implemented it for one task type — its `retest_decides` escape needs a `test_result`,
    which only ``qa.test`` produces. A ``development.develop`` repair has none, so on a
    stack whose criteria cannot execute in this environment (runtime-api has no node, so
    stack #2's compile checks skip) every dev repair is refused unheard and the loop
    spends its whole budget learning nothing. `cyc_05abfc7c1f00` burned all three rounds
    on `app/api/runs/route.ts`, re-dispatching an identical task after two identical
    unverifiable verdicts.

    Terminating does not fix the inability to verify — the checks belong where their
    toolchain exists, which is a larger change deliberately taken after the 1.7.0 cut.
    It replaces three rounds of silence with one named reason.
    """
    return (
        verification_status == PATCH_UNVERIFIABLE
        and verification_reason in STRUCTURALLY_UNEVALUABLE_REASONS
        and not retest_decides
    )


#: #870: the rejected-repair carry is bounded — three entries per task, 500 characters
#: each. An unbounded carry would put a whole rejected emission into the next repair's
#: prompt, which is how a "tell the next round why" fact becomes the round's whole budget.
_REPAIR_REJECTION_ENTRY_LIMIT = 3
_REPAIR_REJECTION_CHAR_LIMIT = 500


def _record_repair_rejection(carry: dict[str, list[str]] | None, task_id: str, entry: str) -> None:
    """Append a rejected-repair fact to the run-lived carry (#870), bounded.

    ``None`` carry (legacy call paths, tests) is a no-op — recording evidence is
    additive and must never fail the acceptance path it documents.
    """
    if carry is None:
        return
    entries = carry.setdefault(task_id, [])
    entries.append(entry[:_REPAIR_REJECTION_CHAR_LIMIT])
    del entries[:-_REPAIR_REJECTION_ENTRY_LIMIT]


def _repaired_suite_files(
    patched_artifacts: Sequence[Mapping[str, Any]], resolved_config: Mapping[str, Any]
) -> list[str]:
    """The patched files this stack's runner would collect as a suite (#1269).

    Read through the stack's declared test-file conventions
    (``test_file_patterns_for``/``matches_test_file_patterns``, #846) rather than through
    the artifact's ``type``: a repair's files are typed by extension, so a repaired
    ``backend/tests/test_runs.py`` arrives as ``code`` and a ``type``-keyed rule would
    miss exactly the case this exists for.
    """
    from squadops.capabilities.development_profiles import (
        matches_test_file_patterns,
        test_file_patterns_for,
    )

    patterns = test_file_patterns_for(resolved_config)
    if not patterns:
        return []
    return [
        name
        for artifact in patched_artifacts
        if isinstance(artifact, Mapping) and (name := str(artifact.get("name") or ""))
        if matches_test_file_patterns(name, patterns)
    ]


#: The values the accepted-patch path hands from one of its steps to the next (the 1.7.5
#: recovery extraction map §4 step 1). A 511-line method carried these as locals; naming
#: them is what makes the step boundaries checkable — each step declares what it consumes
#: rather than reading whatever the one before happened to leave behind.


@dataclasses.dataclass(frozen=True)
class _PatchSubject:
    """What the patch verification runs against.

    ``patched_artifacts`` is what an accepted patch RE-STORES; ``workspace_files`` rides
    as a separate base and is never re-stored under the repaired task's type (#643).
    """

    resolved_config: dict[str, Any]
    criteria: list[Any]
    patched_artifacts: list[dict[str, Any]]
    workspace_files: dict[str, Any]
    file_owned: list[Any]


@dataclasses.dataclass(frozen=True)
class _PatchVerdict:
    """What the verification said, plus the two readings the not-passed path turns on.

    ``retest_decides``: structurally unevaluable checks with behavioural evidence to
    re-run instead (pf-47/pf-49). ``unrepairable_here``: no further round can produce a
    verdict at all, which is terminated with a named reason rather than rejected
    unheard (#1221).
    """

    verification: Any
    failed_records: list[Any]
    retest_decides: bool
    unrepairable_here: bool


@dataclasses.dataclass(frozen=True)
class _RetestOutcome:
    """The corrected outputs after the retest, and what it produced.

    ``evidence is None`` means no retest ran — distinct from a retest that produced no
    artifacts, which ``supersede_evidence_artifacts`` treats the same way (drop).
    """

    corrected_outputs: dict[str, Any]
    rows: list[dict[str, Any]]
    evidence: list[dict[str, Any]] | None


class PatchAcceptance:
    """The accepted-patch path (map §4 step 2).

    Holds no ports. Four late-bound callables, following the ``store_artifact=lambda …``
    precedent already on ``CorrectionRunner`` (SIP-0097 §6.3, "executor residual,
    residual-but-watched"): three SIP-0100 enforcement helpers the executor also calls
    from two other seams — one of which, ``_emit_scaffold_integrity_evidence``, is
    already duplicated on ``CorrectionRunner``, so a third copy here is the obvious wrong
    move — and ``reexecute_repaired_suite``, which map §4 step 4 leaves on
    ``CorrectionRunner`` untouched.

    Run-lived records (the bound scaffold record, the rejected-repair carry, the
    compliance counter) arrive at call time, never on the instance: this object is built
    once per executor and a run's state must not outlive its run.
    """

    def __init__(
        self,
        *,
        reexecute_repaired_suite: Callable[..., Any],
        enforce_frozen_ownership: Callable[..., tuple[list[dict], list[Any]]],
        emit_integrity_evidence: Callable[[Any, Any], None],
        enforce_compliance_budget: Callable[..., None],
    ) -> None:
        self._reexecute_repaired_suite = reexecute_repaired_suite
        self._enforce_frozen_ownership = enforce_frozen_ownership
        self._emit_integrity_evidence = emit_integrity_evidence
        self._enforce_compliance_budget = enforce_compliance_budget

    async def accept(
        self,
        envelope: TaskEnvelope,
        result: TaskResult,
        repair_artifacts: list[dict[str, Any]],
        patched_result_holder: dict[str, Any] | None,
        *,
        run_id: str = "",
        cycle: Cycle | None = None,
        correction_attempts: int = 0,
        prior_outputs: dict[str, Any] | None = None,
        all_artifact_refs: list[str] | None = None,
        stored_artifacts: list[tuple[str, ArtifactRef]] | None = None,
        completed_task_ids: list[str] | None = None,
        plan_delta_refs: list[str] | None = None,
        profile: Any = None,
        flow_run_id: str | None = None,
        enriched_envelope: TaskEnvelope | None = None,
        budget_guard: Callable[[], None] | None = None,
        interface_manifest: Any = None,
        repair_rejection_carry: dict[str, list[str]] | None = None,
        repair_typed_checks: Sequence[dict[str, Any]] = (),
        bound_record: Any = None,
        compliance_counter: dict[str, int] | None = None,
    ) -> str:
        """Behaviorally verify a patch (#389); return "accept_patch" or "continue".

        Verification itself is the pure ``patch_verification`` module; this
        method only assembles its inputs from the failed task and renders the
        corrected result. Any non-pass (failed, unverifiable, no repair
        artifacts, no holder) falls back to the pre-#389 re-dispatch path —
        conservative by construction, never a false accept.

        #456: typed criteria are necessary but not sufficient when the failed
        task carries behavioral evidence — ``tests_pass`` is synthesized from
        the task's executed ``test_result``, so a patched result that keeps the
        stale pre-repair ``test_result`` records the failure as the check's
        final state no matter what the typed rows say. When the failed outputs
        carry a ``test_result``, the repaired suite is re-executed in the QA
        agent's environment (via the correction runner) and the corrected
        result takes the retest's fresh behavioral evidence. A retest that
        fails — or can't run — falls back to "continue", same as a typed miss.
        """
        if not repair_artifacts or patched_result_holder is None:
            return "continue"

        # The seven steps this path has always run, in order. They were the comment
        # headers of a 511-line method on the executor until #1152 step 1 made each a
        # method, and step 2 moved the set here. The data crossing each boundary is
        # declared (the three carriers above) rather than left in a shared local, which
        # is what makes a step's inputs checkable rather than merely conventional.
        authorized = self._authorize_repair_artifacts(
            repair_artifacts,
            envelope,
            bound_record=bound_record,
            cycle=cycle,
            compliance_counter=compliance_counter,
        )
        if authorized is None:
            return "continue"
        repair_artifacts = authorized

        subject = self._build_patch_subject(
            envelope,
            result,
            repair_artifacts,
            enriched_envelope=enriched_envelope,
            interface_manifest=interface_manifest,
        )

        verdict = await self._verify_patch(
            envelope, result, repair_artifacts, subject, repair_typed_checks=repair_typed_checks
        )

        refusal = self._refuse_unpassed_patch(
            envelope,
            verdict,
            correction_attempts=correction_attempts,
            repair_rejection_carry=repair_rejection_carry,
        )
        if refusal is not None:
            return refusal

        retest = await self._retest_patched_suite(
            envelope,
            result,
            subject,
            run_id=run_id,
            cycle=cycle,
            correction_attempts=correction_attempts,
            prior_outputs=prior_outputs,
            all_artifact_refs=all_artifact_refs,
            stored_artifacts=stored_artifacts,
            completed_task_ids=completed_task_ids,
            plan_delta_refs=plan_delta_refs,
            profile=profile,
            flow_run_id=flow_run_id,
            enriched_envelope=enriched_envelope,
            budget_guard=budget_guard,
            repair_rejection_carry=repair_rejection_carry,
        )
        if retest is None:
            return "continue"

        patched_artifacts, spine_rows = self._settle_patch_evidence(
            envelope, subject, verdict, retest
        )

        return self._accept_patch(
            result, patched_result_holder, verdict, retest, patched_artifacts, spine_rows
        )

    def _authorize_repair_artifacts(
        self,
        repair_artifacts: list[dict[str, Any]],
        envelope: TaskEnvelope,
        *,
        bound_record: Any,
        cycle: Cycle | None,
        compliance_counter: dict[str, int] | None,
    ) -> list[dict[str, Any]] | None:
        """Block 1 — the repairing step's grants, before the overlay.

        Returns the artifacts that may be verified, or ``None`` when nothing survives
        and the caller must fall back to re-dispatch. Raises ``_ExecutionError`` on an
        artifact naming no producer: judged under the failed task's grants that would be
        the #1350 defect again, silently.
        """
        # #1323: the verified set must be the set that will be stored. Storage enforces the
        # producer's grants (``_collect_artifacts_and_checkpoint``); verification did not,
        # so a repair that rewrote a path the producer may not write was verified on the
        # overlay WITH the file, reported passed, and had the file dropped at storage —
        # the failing row superseded, the defect still in the tree (1.7.2 React roll 1,
        # ``docker/serve.py``). Enforce here with the same grants, before the overlay.
        #
        # #1350: "the same grants" are the REPAIRING step's, which every repair artifact
        # names for itself (``name_producer`` in the correction runner) — the failed task's
        # grants judged a dev repair of a dev slot as a QA write to it and refused the
        # patch (``cyc_375bdea6e140``). An artifact naming no producer is refused loudly:
        # judged under the failed task's grants it would be that defect again, silently.
        if bound_record is not None:
            from squadops.cycles.scaffold_enforcement import named_producer

            unnamed = [
                str(a.get("name") or a.get("path") or "(unnamed)")
                for a in repair_artifacts
                if named_producer(a) is None
            ]
            if unnamed:
                raise _ExecutionError(
                    f"patch authorization task={envelope.task_id}: {len(unnamed)} repaired "
                    f"path(s) name no producer ({', '.join(unnamed)}) — a repair's grants are "
                    "the repairing step's, and the correction runner names that step on every "
                    "repair emission (#1350)"
                )
            repair_artifacts, dropped = self._enforce_frozen_ownership(
                repair_artifacts, bound_record, envelope, stage=STAGE_PATCH_VERIFICATION
            )
            for record in dropped:
                self._emit_integrity_evidence(record, envelope)
            if dropped:
                logger.warning(
                    "patch authorization task=%s: %d repaired path(s) dropped before "
                    "verification, %d retained — %s (#1323)",
                    envelope.task_id,
                    len(dropped),
                    len(repair_artifacts),
                    ", ".join(str(r.normalized_path) for r in dropped),
                )
                if compliance_counter is not None and cycle is not None:
                    self._enforce_compliance_budget(dropped, cycle, envelope, compliance_counter)
            if not repair_artifacts:
                logger.warning(
                    "patch_verification task=%s refused: every repaired path was one the "
                    "producer may not write — nothing to verify (#1323)",
                    envelope.task_id,
                )
                return None

        return repair_artifacts

    def _build_patch_subject(
        self,
        envelope: TaskEnvelope,
        result: TaskResult,
        repair_artifacts: list[dict[str, Any]],
        *,
        enriched_envelope: TaskEnvelope | None,
        interface_manifest: Any,
    ) -> _PatchSubject:
        """Block 2 — what the verification runs against: the overlay, the accepted
        workspace tree beside it, and the criteria the repaired files own."""
        resolved_config = (envelope.inputs or {}).get("resolved_config") or {}
        criteria = (envelope.inputs or {}).get("acceptance_criteria") or []
        patched_artifacts = overlay_artifacts(
            (result.outputs or {}).get("artifacts") or [], repair_artifacts
        )
        # #643: verify against the accepted workspace tree, not just the task's
        # own files — module_imports and the #591 import pre-gate need the
        # scaffold siblings present or a correct repair can never be accepted
        # (fay-1: both candidates rejected in a routes.py-only workspace).
        # Workspace rides as a separate base: patched_artifacts is what an
        # accepted patch RE-STORES (#389 swap below), and the tree must never
        # be re-stored under the repaired task's type.
        workspace_files = ((enriched_envelope or envelope).inputs or {}).get(
            "acceptance_workspace_files"
        ) or {}
        # #870: the criteria OWNED by the files the repair rewrote, derived from the
        # canonical contract emission (M0a: emission equals the pinned artifact).
        # Presence-keyed on the manifest like every other manifest surface; a
        # derivation failure disables the gate rather than the verification.
        file_owned: list[Any] = []
        if interface_manifest is not None:
            try:
                from squadops.capabilities.scaffold_contract import emit_contract_dict
                from squadops.cycles.implementation_plan import resolve_criteria_for_files
                from squadops.cycles.verification_contract import VerificationContract

                file_owned = resolve_criteria_for_files(
                    VerificationContract.from_dict(emit_contract_dict(interface_manifest)),
                    [a.get("name") for a in patched_artifacts if isinstance(a, dict)],
                )
            except Exception as exc:
                logger.warning("patch file-owned gate unavailable: %s", exc)
        if file_owned:
            logger.info(
                "patch file-owned gate: %d criteria own the repaired files (task=%s)",
                len(file_owned),
                envelope.task_id,
            )
        return _PatchSubject(
            resolved_config=resolved_config,
            criteria=criteria,
            patched_artifacts=patched_artifacts,
            workspace_files=workspace_files,
            file_owned=file_owned,
        )

    async def _verify_patch(
        self,
        envelope: TaskEnvelope,
        result: TaskResult,
        repair_artifacts: list[dict[str, Any]],
        subject: _PatchSubject,
        *,
        repair_typed_checks: Sequence[dict[str, Any]],
    ) -> _PatchVerdict:
        """Block 3 — verify, and say why nothing executed rather than only that nothing
        did. Carries the two derived readings the not-passed path turns on: whether the
        retest decides alone, and whether further rounds can produce a verdict at all."""
        verification = await verify_patched_artifacts(
            subject.criteria,
            subject.patched_artifacts,
            workspace_files=subject.workspace_files,
            stack=resolve_check_stack(subject.resolved_config),
            typed_acceptance_enabled=subject.resolved_config.get("typed_acceptance", True),
            command_acceptance_enabled=subject.resolved_config.get(
                "command_acceptance_checks", True
            ),
            file_owned_criteria=subject.file_owned,
            # #1229: what the repair executed on its own patch, in its own container —
            # carried on the protocol result (#1256). ``result`` here is the FAILED task's;
            # reading the rows off it found none in every live round (cyc_c6db3ffc1f4e).
            agent_checks=repair_typed_checks,
            # #1264: the repair's own files, not the overlay's (which carries the failed
            # task's artifacts too) — what #1259's absent-file rule is keyed on.
            repaired=[a.get("name") for a in repair_artifacts if isinstance(a, dict)],
            # #1312: the deliverable set is the BUILDER repair's blocking criterion, now
            # that the handoff's `sections_present` row is gone. Guarded by the same
            # predicate the spine row uses — a dev or qa repair is judged by its contract
            # criteria, and handing it a file list would charge it for files another role
            # owns (the #1259 class).
            required_files=(
                (envelope.inputs or {}).get("expected_artifacts") or []
                if emits_required_files(envelope.task_type)
                else []
            ),
        )
        # pf-33: name the failed checks — "status=failed reason= checks=7" forced
        # a by-hand artifact replay to learn WHICH check rejected the patch.
        # (#870: the rows are PatchCheckRecord dataclasses; the original dict-shaped
        # comprehension matched nothing and logged "failed=-" on every rejection.)
        failed_records = [
            record
            for record in verification.checks
            if record.severity == "error" and record.status in ("failed", "error")
        ]
        failed_checks = [record.check for record in failed_records]
        agent_rows = [r for r in verification.checks if r.executed_in != EXECUTED_IN_RUNTIME_API]
        # #1276: why nothing executed, not just that nothing did. "unverifiable /
        # no_executed_blocking_checks" reads as an absent toolchain and is equally
        # produced by an absent FILE — the 1.7.1 Next.js roll 1 shape, where the R7
        # readout could not tell the two apart because the line carried neither reason.
        logger.info(
            "patch_verification task=%s task_type=%s status=%s reason=%s checks=%d failed=%s "
            "decided_by_agent=%d agent_rows=%d agent_executed=%d skips=%s",
            envelope.task_id,
            envelope.task_type,
            verification.status,
            verification.reason or "",
            len(verification.checks),
            ",".join(failed_checks) or "-",
            verification.decided_by_agent,
            len(agent_rows),
            sum(1 for r in agent_rows if r.status in ("passed", "failed")),
            skip_reasons(verification.checks) or "-",
        )
        # pf-47/pf-49: when a task's checks are structurally unevaluable (a frontend
        # test file — every AST check skips by design), "unverifiable" is not caution,
        # it is a deterministic repair deadlock: no repair can EVER produce an executed
        # verdict, so the loop burns its whole budget rejecting repairs unheard. The
        # behavioral retest below re-runs the actual failing suite against the patched
        # workspace — stronger evidence than the checks it stands in for — so for
        # exactly these reasons, and only with behavioral evidence to re-run, the
        # retest verdict decides alone. Evaluator errors, parse failures, and real
        # check failures keep failing closed, unchanged.
        retest_decides = (
            verification.status == PATCH_UNVERIFIABLE
            and verification.reason in STRUCTURALLY_UNEVALUABLE_REASONS
            and isinstance((result.outputs or {}).get("test_result"), dict)
        )
        if retest_decides:
            logger.info(
                "patch_verification task=%s structurally unevaluable (%s) — "
                "behavioral retest decides",
                envelope.task_id,
                verification.reason,
            )
        # #1221: structurally unevaluable AND no behavioral evidence to stand in for the
        # checks is a deadlock, not a rejection. pf-47/pf-49 named this exactly — "no
        # repair can EVER produce an executed verdict, so the loop burns its whole budget
        # rejecting repairs unheard" — and answered it with `retest_decides`, which needs
        # a `test_result` only `qa.test` produces. A `development.develop` repair has
        # none, so on a stack whose criteria cannot execute here (runtime-api has no node,
        # so stack #2's compile checks skip) every dev repair is refused unheard.
        # cyc_05abfc7c1f00 spent all three rounds on `app/api/runs/route.ts` this way,
        # re-dispatching an identical task after two identical unverifiable verdicts.
        #
        # Terminating is not a fix for the inability to verify — the toolchain belongs
        # where the checks can run, which is #1221's option C and deliberately after the
        # cut. It stops the waste and, more importantly, replaces three rounds of silence
        # with one named reason a reader can act on.
        unrepairable_here = correction_is_deadlocked(
            verification.status, verification.reason, retest_decides=retest_decides
        )
        return _PatchVerdict(
            verification=verification,
            failed_records=failed_records,
            retest_decides=retest_decides,
            unrepairable_here=unrepairable_here,
        )

    def _refuse_unpassed_patch(
        self,
        envelope: TaskEnvelope,
        verdict: _PatchVerdict,
        *,
        correction_attempts: int,
        repair_rejection_carry: dict[str, list[str]] | None,
    ) -> str | None:
        """Block 4 — a rejected patch is recorded with its reason, never discarded.

        Returns the action the caller must take (``"continue"``, or
        ``"break_correction"`` when no further round can produce a verdict), or ``None``
        when the patch passed and acceptance proceeds.
        """
        verification = verdict.verification
        failed_records = verdict.failed_records
        retest_decides = verdict.retest_decides
        unrepairable_here = verdict.unrepairable_here
        if verification.status != PATCH_PASSED and not retest_decides:
            # #870: tell the next round WHY this repair was rejected — the named
            # failed checks with reasons, not just a status in the log.
            failed_detail = "; ".join(
                f"{record.check}: {record.reason or 'failed'}" for record in failed_records
            )
            _record_repair_rejection(
                repair_rejection_carry,
                envelope.task_id,
                f"correction attempt {correction_attempts}: {REPAIR_REFUSED_MARKER} "
                f"({verification.reason or 'failed checks'})"
                + (f" — {failed_detail}" if failed_detail else ""),
            )
            if unrepairable_here:
                # #1273: say WHICH absence this was. `no_executed_blocking_checks` is
                # produced by an absent toolchain AND by an absent file — every row
                # skipping `file_not_found` because the repair wrote prose instead of the
                # file — and the two have opposite remedies. Next.js roll 1 terminated
                # under the toolchain wording for a file that was never written.
                absent_files = sorted(
                    {
                        str((record.params or {}).get("file"))
                        for record in verification.checks
                        if record.reason in FILE_ABSENT_REASONS
                        and (record.params or {}).get("file")
                    }
                )
                logger.warning(
                    "correction_terminated_unverifiable task=%s task_type=%s reason=%s — %s; "
                    "further rounds cannot produce a verdict (#1221, #1273)",
                    envelope.task_id,
                    envelope.task_type,
                    verification.reason,
                    (
                        "every check that could decide names a file the repair did not "
                        f"write ({', '.join(absent_files)})"
                        if absent_files
                        else "no check owning the repaired files can execute in this "
                        "environment and the task carries no behavioral evidence to "
                        "decide instead"
                    ),
                )
                return "break_correction"
            return "continue"
        return None

    async def _retest_patched_suite(
        self,
        envelope: TaskEnvelope,
        result: TaskResult,
        subject: _PatchSubject,
        *,
        run_id: str,
        cycle: Cycle | None,
        correction_attempts: int,
        prior_outputs: dict[str, Any] | None,
        all_artifact_refs: list[str] | None,
        stored_artifacts: list[tuple[str, ArtifactRef]] | None,
        completed_task_ids: list[str] | None,
        plan_delta_refs: list[str] | None,
        profile: Any,
        flow_run_id: str | None,
        enriched_envelope: TaskEnvelope | None,
        budget_guard: Callable[[], None] | None,
        repair_rejection_carry: dict[str, list[str]] | None,
    ) -> _RetestOutcome | None:
        """Block 5 — the retest, keyed on what the patch contains.

        Returns the corrected outputs with the retest's fresh evidence folded in, or
        ``None`` when the caller must fall back to re-dispatch (no retest context, or a
        retest that did not pass). ``_RetestOutcome.evidence`` is ``None`` when no retest
        ran — distinct from a retest that produced no artifacts.
        """
        resolved_config = subject.resolved_config
        patched_artifacts = subject.patched_artifacts
        corrected_outputs = dict(result.outputs or {})

        # #456: behavioral-evidence-backed task — re-execute the repaired
        # suite before accepting; fresh test_result supersedes the stale one.
        #
        # #1269: keyed on what the PATCH CONTAINS, not on the failed result already
        # carrying a `test_result`. A qa.test that failed at EMISSION never had one — it
        # emitted a preamble and no fenced block — so the repair that finally produced the
        # suite was accepted on typed rows alone, no retest ran, and `tests_pass` and
        # `frontend_build` ended `subject_missing`: the run blocked with the delivered app
        # booting fine (React roll 2, cyc_9c085ec2e9e5). The evidence families synthesised
        # from `test_result` can only ever be produced by running the suite, so the
        # question is whether there IS a suite to run — which the patch answers.
        #
        # Owner's ruling (2026-09-03): key on the patch rather than on a per-task-type
        # evidence-contract table. The artifacts already carry the fact, and a table would
        # be a second home for it. "Will the runner discover this?" is the stack's own
        # question, asked through the stack's own declared conventions (#846).
        retest_rows: list[dict[str, Any]] = []
        # None means "no retest ran" — distinct from a retest that produced no
        # artifacts, which supersede_evidence_artifacts treats the same way (drop).
        retest_evidence: list[dict[str, Any]] | None = None
        repaired_suites = _repaired_suite_files(patched_artifacts, resolved_config)
        if isinstance(corrected_outputs.get("test_result"), dict) or repaired_suites:
            if cycle is None:
                logger.warning(
                    "patch_verification task=%s carries test_result but no retest "
                    "context — falling back to re-dispatch",
                    envelope.task_id,
                )
                return None
            # The retest needs the dispatch-time workspace: artifact_contents
            # is added by _enrich_envelope and never exists on the base
            # envelope (3.11: the retest instant-failed input validation
            # because it was built from the un-enriched envelope).
            retest_result = await self._reexecute_repaired_suite(
                run_id,
                cycle,
                enriched_envelope if enriched_envelope is not None else envelope,
                patched_artifacts,
                correction_attempts,
                prior_outputs=prior_outputs if prior_outputs is not None else {},
                all_artifact_refs=all_artifact_refs if all_artifact_refs is not None else [],
                stored_artifacts=stored_artifacts if stored_artifacts is not None else [],
                completed_task_ids=completed_task_ids if completed_task_ids is not None else [],
                plan_delta_refs=plan_delta_refs if plan_delta_refs is not None else [],
                profile=profile,
                flow_run_id=flow_run_id,
                budget_guard=budget_guard,
            )
            retest_outputs = (retest_result.outputs or {}) if retest_result else {}
            fresh_test_result = retest_outputs.get("test_result")
            retest_passed = (
                retest_result is not None
                and retest_result.status == TaskResultStatus.SUCCEEDED
                and isinstance(fresh_test_result, dict)
                and fresh_test_result.get("tests_passed") is True
            )
            # #870: the retest's own verdict text — previously only a bare
            # status; roll 12's non-compiling repair died as "status=FAILED
            # passed=False" and nothing downstream ever learned it didn't build.
            retest_validation_rows = (retest_outputs.get("validation_result") or {}).get(
                "checks"
            ) or []
            failing_rows = "; ".join(
                f"{row.get('check', '?')}: {row.get('reason') or 'failed'}"
                for row in retest_validation_rows
                if isinstance(row, dict) and row.get("passed") is False
            )
            retest_reason = str(
                (retest_outputs.get("validation_result") or {}).get("summary")
                or (fresh_test_result or {}).get("summary")
                or (retest_result.error if retest_result else "")
                or ""
            )
            if failing_rows:
                retest_reason = (
                    f"{retest_reason} [{failing_rows}]" if retest_reason else failing_rows
                )
            logger.info(
                "patch_retest task=%s status=%s passed=%s reason=%s",
                envelope.task_id,
                retest_result.status if retest_result else "not_dispatched",
                retest_passed,
                retest_reason or "-",
            )
            if not retest_passed:
                _record_repair_rejection(
                    repair_rejection_carry,
                    envelope.task_id,
                    f"correction attempt {correction_attempts}: repaired suite retest "
                    f"FAILED — {retest_reason or 'no verdict detail'}",
                )
                return None
            corrected_outputs["test_result"] = fresh_test_result
            retest_validation = retest_outputs.get("validation_result")
            if isinstance(retest_validation, dict):
                retest_rows = [
                    row for row in retest_validation.get("checks", []) if isinstance(row, dict)
                ]
            # #1111: the passing retest is what the task stores. Without this the
            # failed run's test_report.md and typed-check evaluation were re-stored
            # under the task id seconds AFTER the retest banked its passing report —
            # and the next analysis read the failure (1.6.5 FastAPI+React roll 1).
            retest_evidence = retest_outputs.get("artifacts")
        return _RetestOutcome(
            corrected_outputs=corrected_outputs,
            rows=retest_rows,
            evidence=retest_evidence,
        )

    def _settle_patch_evidence(
        self,
        envelope: TaskEnvelope,
        subject: _PatchSubject,
        verdict: _PatchVerdict,
        retest: _RetestOutcome,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Block 6 — the failed attempt's evidence never survives beside the accepted
        patch's, and every framework row the task type owes by contract is re-derived
        from the patched set.

        Returns ``(artifacts, spine_rows)``. Pure with respect to the caller's corrected
        outputs: the artifacts assignment the old block made in the middle is the
        caller's, made after this returns — nothing between it and the spine derivation
        read it.
        """
        verification = verdict.verification
        patched_artifacts = subject.patched_artifacts
        corrected_outputs = retest.corrected_outputs
        retest_rows = retest.rows
        retest_evidence = retest.evidence
        # #1111, generalized by #1318: the failed attempt's own evidence must never be
        # re-stored under the repaired task, whether or not a behavioral retest ran. Gated
        # inside the retest branch it only covered tasks with a suite; a builder task has
        # none, so 1.7.2 roll 1 re-stored the pre-patch typed-check evaluation eleven
        # milliseconds before the patch's own file landed — same evaluated_at, same
        # workspace revision, and the triage read the failure. A retest's fresh evidence
        # replaces; with no retest the stale file is dropped, because the corrected result
        # already carries the patch verification's rows.
        supersession = supersede_evidence_artifacts(patched_artifacts, retest_evidence)
        patched_artifacts = supersession.artifacts
        if supersession.replaced or supersession.dropped:
            logger.info(
                "patch task=%s failed-attempt evidence superseded: replaced=%s dropped=%s "
                "(retest=%s) (#1111/#1318)",
                envelope.task_id,
                ",".join(supersession.replaced) or "-",
                ",".join(supersession.dropped) or "-",
                "yes" if retest_evidence is not None else "no",
            )

        # #1318: the ledger supersedes on ``(check_id, subject, criterion_id)``, so a
        # framework-spine row the patch verification never reproduces keeps the FAILED
        # attempt's value as the run's final state. Nothing but the builder handler writes
        # ``required_files``, so on 1.7.2 roll 1 the patch supplied ``qa_handoff.md``,
        # ``patch_verification`` passed, and the run was still rejected on the pre-patch row.
        # Re-derive it from the PATCHED set through the handler's own rule — for the task
        # types whose emission carries the row by contract (``emits_required_files``: the
        # builder's), or when the failed attempt actually emitted it. Never invent evidence
        # for a task type that never carries the check. #1364: a CONTENTLESS builder attempt
        # carries no rows at all, so "only when it carried one" left the required check with
        # no executed row anywhere — the accepted patch supplied the files, the app booted,
        # and the roll-up read ``subject_missing`` → ``blocked_unverified`` (1.7.3 roll 1).
        # #1374: every framework row this task type owes BY CONTRACT is present in the
        # corrected result, or the patch is not accepted. Two void counted rolls on two
        # lines were one mechanism patched twice: this seam composed the corrected result
        # from the failed attempt's rows plus whatever the verifier produced, so a
        # framework row survived only if some earlier stage happened to write one. #1318
        # re-derived `required_files` when the attempt HAD carried it (1.7.2 roll 1: a
        # booting app rejected on the pre-patch row); #1364 found the next shape, a
        # contentless attempt carrying no rows at all (1.7.3 roll 1: a booting app read
        # `blocked_unverified`). The contract says what a task owes; its attempt's history
        # does not.
        # #1374/#1318/#1364: every framework row this task type owes BY CONTRACT is
        # present in the corrected result, or the patch is not accepted. The composition
        # lives beside ``framework_rows_owed`` in ``check_registry`` — that module already
        # owned the owed/producer half of the same concept, and the other candidate,
        # ``patch_verification``, is 863 lines and on the plan's growth watch list.
        # This seam keeps the logging, because the log lines name the task and the seam.
        produced = {
            str(row.get("check"))
            for row in ([r.to_check_row() for r in verification.checks] + retest_rows)
            if isinstance(row, Mapping) and row.get("check")
        }
        # `tests_pass` is the one owed row that is never a check ROW on a passing result:
        # `verification_normalize` skips the failure-only row and synthesizes the check
        # from `test_result`, which is richer and present on a green run. Presence here
        # means "the evidence the roll-up reads exists", not "a dict with this key" — a
        # readout keyed on the key alone would refuse every retested qa patch.
        if corrected_outputs.get("test_result"):
            produced.add(CHECK_TESTS_PASS)
        spine_rows: list[dict[str, Any]] = []
        for owed in compose_owed_framework_rows(
            envelope.task_type,
            produced=produced,
            expected_artifacts=(envelope.inputs or {}).get("expected_artifacts") or [],
            patched_names=[a.get("name") for a in patched_artifacts if isinstance(a, dict)],
        ):
            if owed.disposition == OWED_PRODUCED:
                logger.info(
                    "patch task=%s owes %s and %s produced it (#1374)",
                    envelope.task_id,
                    owed.check_id,
                    owed.producer,
                )
            elif owed.disposition == OWED_UNDECLARED:
                # Nothing declared: there is no set to check the patched tree against,
                # and inventing a passing row would credit a deliverable nobody named.
                logger.warning(
                    "patch task=%s owes %s but declares no expected_artifacts — the "
                    "row cannot be derived and the pre-patch state decides (#1318)",
                    envelope.task_id,
                    owed.check_id,
                )
            elif owed.disposition == OWED_DERIVED and owed.row is not None:
                spine_rows.append(owed.row)
                logger.info(
                    "patch task=%s re-derived %s on the patched set: passed=%s required=%s "
                    "missing=%s (#1318, #1364, #1374)",
                    envelope.task_id,
                    owed.check_id,
                    owed.row["passed"],
                    ",".join(owed.row["required"]) or "-",
                    ",".join(owed.row["missing"]) or "-",
                )
            else:
                # Owed, not produced by its stage, and not derivable at this seam. That is
                # the state SIP-0096 reads as `subject_missing`, and it is what put #1364's
                # booting app at `blocked_unverified`.
                #
                # **Reported, not refused.** Every measured instance of this defect is a
                # `required_files` row, which is derived unconditionally above; refusing on
                # the unmeasured half would change what a verdict MEANS in the middle of a
                # measurement window, on a class no roll has yet exhibited. The gap is
                # named on the line so a record can count it, and promoting it to a
                # refusal is a separate, deliberate call with evidence behind it.
                logger.warning(
                    "patch task=%s owes %s and has none: %s produced no row and it cannot "
                    "be derived here — the roll-up will read subject_missing (#1374, "
                    "reporting-only)",
                    envelope.task_id,
                    owed.check_id,
                    owed.producer,
                )
        return patched_artifacts, spine_rows

    def _accept_patch(
        self,
        result: TaskResult,
        patched_result_holder: dict[str, Any],
        verdict: _PatchVerdict,
        retest: _RetestOutcome,
        patched_artifacts: list[dict[str, Any]],
        spine_rows: list[dict[str, Any]],
    ) -> str:
        """Block 7 — render the corrected result and accept it."""
        verification = verdict.verification
        corrected_outputs = retest.corrected_outputs
        retest_rows = retest.rows
        corrected_outputs["artifacts"] = patched_artifacts
        prior_validation = corrected_outputs.get("validation_result")
        corrected_outputs["validation_result"] = {
            **(prior_validation if isinstance(prior_validation, dict) else {}),
            "passed": True,
            "patch_verified": True,
            # #734 Slice A: the repair-acceptance verdict names the workspace
            # tree it verified against (verify_patched_artifacts computes it
            # from the exact mapping it materialized).
            "workspace_revision_id": verification.workspace_revision_id,
            "checks": [r.to_check_row() for r in verification.checks] + retest_rows + spine_rows,
        }
        corrected_outputs.pop("outcome_class", None)
        patched_result_holder["patched_result"] = dataclasses.replace(
            result,
            status=TaskResultStatus.SUCCEEDED,
            outputs=corrected_outputs,
            error=None,
            outcome_class=None,
        )
        return "accept_patch"
