"""Correction-protocol collaborator (SIP-0097 §6.3).

Owns the four-step correction protocol — analyze → decide → (patch) → done —
moved verbatim from ``DispatchedFlowExecutor._run_correction_protocol`` plus
its two helpers (``_store_correction_task_artifacts``,
``_checkpoint_correction_task``). Outcome *routing* (what the run does with
the returned correction path) stays with the executor's orchestration loop.

Task transport goes through the injected ``TaskDispatcher`` (§6.3 final
state — slice 5 retired the interim executor-supplied dispatch callables
per AC#9). ``store_artifact`` remains a narrow executor-supplied callable:
artifact plumbing is §6.7 executor residual, residual-but-watched.

Cancellation: the protocol performs no cancellation checks of its own; it
relies on the dispatch path's check per the §6 cancellation ownership rule.
That check now exists — ``TaskDispatcher.dispatch_task`` probes before every
publish (#586). Until it was wired, this delegation pointed at nothing: the
transport documented the probe as "deliberately not wired" while this module
documented itself as relying on it, so a run cancelled mid-correction ran to
attempt exhaustion (2h20m, five attempts, observed 2026-07-25).

Repair acceptance is deterministic-only (#556): the repair sequence has no
LLM validation step — patch verification (#389) re-runs the typed criteria
and ``reexecute_repaired_suite`` (#456) re-runs the behavioral suite, and
those two signals decide convergence. If LLM judgment ever returns to this
loop it goes AFTER the retest, on the governance role, fail-closed — it may
reject or flag a deterministic green but never approve past a deterministic
red (#557). The retest ``TaskResult`` returned by
``reexecute_repaired_suite`` is the evidence feed such a step would consume.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from adapters.cycles.correction_repair import CorrectionRepair
from adapters.cycles.execution_errors import _ExecutionError
from squadops.capabilities.context_assembly import (
    retest_forwarded_inputs,
)
from squadops.cycles.agent_config import resolve_agent_config
from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.correction_signature import (
    classify_movement,
    failure_signature,
    render_signature,
    repair_refused_in_round,
    should_terminate_plan_defect,
)
from squadops.cycles.failure_evidence import build_failure_evidence, compose_failure_trigger
from squadops.cycles.models import ArtifactRef
from squadops.cycles.plan_delta import PlanDelta
from squadops.cycles.task_outcome import CorrectionTermination, CorrectionTerminationReason
from squadops.events.types import EventType
from squadops.tasks.models import TaskEnvelope, TaskResultStatus
from squadops.tasks.task_types import TaskType

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from adapters.cycles.task_dispatcher import TaskDispatcher
    from squadops.cycles.models import Cycle
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.events.cycle_event_bus import CycleEventBusPort
    from squadops.tasks.models import TaskResult

logger = logging.getLogger(__name__)

#: Which named bucket each correction step's outputs land in, so PlanDelta reads each
#: field from the handler that owns it (#95) — a table, not an if/elif on type names (#559).
_CORRECTION_STEP_OUTPUT_BUCKET: dict[str, str] = {
    TaskType.DATA_ANALYZE_FAILURE: "analysis",
    TaskType.GOVERNANCE_CORRECTION_DECISION: "decision",
}


#: A repository-relative path as it appears inside prose: at least one slash, a file
#: extension, no whitespace. Deliberately narrow — the point is to find the file names a
#: claim is ABOUT, not to parse English.
_PROSE_PATH = re.compile(r"[\w.\-/@]*[\w\-]+/[\w.\-/@]*[\w\-]+\.[A-Za-z0-9]{1,6}")


def refuted_source_claims(
    failure_analysis: dict[str, Any] | None, failed_inputs: dict[str, Any]
) -> list[dict[str, str]]:
    """Claims in the analyzer's PROSE that name a file the workspace does not have (#968).

    ``_verified_implicated_files`` already refutes the structured half — the file list —
    and drops what the workspace cannot confirm. The prose half travelled unchecked, and
    the prose is what the correction decision inherits: SIP-0104 P6 roll 6 carried round
    1's diagnosis word for word into a decision that instructed the squad to "correct the
    store imports" that line 3 of the named file already had right. Three false factual
    claims in one roll, and the subject oscillated app → tests → app on identical evidence.

    The cheap mechanical question is the one #968 asks for: a claim about source has to be
    about source that exists. A sentence naming a path the failed task's envelope does not
    know is not a defect site the loop can act on, and the decision is told so instead of
    inheriting it.

    Returns one entry per refuted path — the path, and the sentence that named it — so the
    decision prompt can quote what was refuted rather than merely counting it. Deliberately
    NOT a rewrite of the analysis: the analyzer's text stands as it was written, and the
    contradiction rides beside it.
    """
    if not isinstance(failure_analysis, dict):
        return []
    known: set[str] = set()
    for key in ("implementation_artifacts", "expected_artifacts"):
        known.update(str(x) for x in (failed_inputs.get(key) or []) if x)
    known.update(str(x) for x in (failed_inputs.get("contract_endpoint_owners") or {}).values())
    if not known:
        # Nothing to check against. Refuting every path here would indict a whole analysis
        # on missing inputs, which is the opposite of the failure this guards.
        return []
    known_basenames = {p.rsplit("/", 1)[-1] for p in known}

    prose: list[str] = []
    summary = failure_analysis.get("analysis_summary")
    if isinstance(summary, str):
        prose.append(summary)
    for factor in failure_analysis.get("contributing_factors") or []:
        if isinstance(factor, str):
            prose.append(factor)

    refuted: dict[str, str] = {}
    for text in prose:
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            for match in _PROSE_PATH.finditer(sentence):
                path = match.group(0)
                if path in known or path.rsplit("/", 1)[-1] in known_basenames:
                    continue
                refuted.setdefault(path, sentence.strip())
    return [{"path": path, "claim": claim} for path, claim in refuted.items()]


def _attach_refuted_claims(
    corr_inputs: dict[str, Any], analysis_outputs: dict[str, Any], envelope: Any
) -> None:
    """Ride the refutation beside the analysis the decision inherits (#968).

    The analyzer's text is NOT rewritten: an analysis silently edited is a second
    unverifiable claim, and the point is that the decision can see both what was asserted
    and what the workspace says about it.
    """
    refuted = refuted_source_claims(analysis_outputs, getattr(envelope, "inputs", None) or {})
    if not refuted:
        return
    corr_inputs["refuted_source_claims"] = refuted
    logger.warning(
        "analyzer_claim_refuted task=%s paths=%s — the workspace has no such file; the "
        "decision is told rather than inheriting it (#968)",
        getattr(envelope, "task_id", "?"),
        ", ".join(entry["path"] for entry in refuted),
    )


def _inject_deterministic_evidence(
    failure_evidence: dict[str, Any],
    *,
    envelope: TaskEnvelope,
    interface_manifest: Any,
    artifact_contents: dict[str, str] | None,
    scaffold_enforcement_carry: list[str] | None,
    bound_record: Any = None,
    repair_rejections: list[str] | None = None,
    stored_artifacts: list[tuple[str, Any]] | None = None,
) -> None:
    """Deterministic authoritative-evidence injection for the correction chain.

    Every entry is data-derived (manifest / typed criteria / prior enforcement),
    never LLM output, and each travels the same failure_evidence →
    authoritative-prompt-block transport. Additive: absent sources inject nothing.

    - ``interface_drift`` (piece 1): exact renamed identifiers vs the manifest,
      with the bound record's frozen paths excluded (#691 — a scaffold-owned file
      cannot drift, and reporting that it does aims repairs at bytes the producer
      may not write; shk-2 lost three attempts to exactly that).
    - ``scaffold_enforcement`` (3.4b): prior attempts' frozen-emission instructions.
    - ``prior_repair_rejections`` (#870): what happened to this task's previous
      repair — patch-verification's named failed checks or the retest verdict.
    - ``contract_expectations`` (pf-31 Fix A): the failed task's typed criteria
      as exact expectation lines.
    - ``error_contract`` (pf-34): the ApiError raise convention + code→status
      map — scaffold-owned knowledge that dies with the fill-slot stub's
      docstring; without it dev repairs guess ``ApiError(status_code=...,
      detail=...)`` and 500 every error path at the behavioral retest despite
      passing all typed checks (pf-33 corr-01, pf-34 corr-00).
    - ``model_surface`` (pf-41): the exact importable names from the frozen
      ``models.py``. Repairs invented them on three consecutive attempts,
      degrading working imports into unimportable ones; the unresolved-import
      gate rejects such a patch but never says what the right names are, so the
      next attempt guesses again.
    """
    from squadops.capabilities.scaffold import (
        error_seam_instructions,
        model_surface_instructions,
    )
    from squadops.cycles.contract_expectations import expectation_lines
    from squadops.cycles.interface_conformance import detect_interface_drift

    drift = detect_interface_drift(
        interface_manifest,
        artifact_contents,
        frozen_paths=bound_record.frozen_paths() if bound_record is not None else None,
    )
    if drift:
        failure_evidence["interface_drift"] = [
            {
                "kind": f.kind,
                "file": f.file,
                "extra": list(f.extra),
                "missing": list(f.missing),
                "instruction": f.instruction,
            }
            for f in drift
        ]

    if scaffold_enforcement_carry:
        failure_evidence["scaffold_enforcement"] = list(scaffold_enforcement_carry)

    # #870: the fate of this task's previous repair(s) — same transport as
    # scaffold_enforcement, same reason: the loop must be TOLD an attempt was
    # rejected (and by which named evidence) rather than silently re-deriving.
    if repair_rejections:
        failure_evidence["prior_repair_rejections"] = list(repair_rejections)

    # #995: what this task had already emitted before the round being analysed. A task
    # killed by the wall clock has a history, and the result the executor holds is only
    # its last read — V7 roll 1's two substantive emissions were erased and the analysis
    # named a mechanism the logs disprove. Same transport as the two above, same reason:
    # the loop must be TOLD rather than left to infer from an absence.
    from squadops.cycles.failure_evidence import prior_emission_history

    history = prior_emission_history(
        str(getattr(envelope, "task_id", "") or ""), stored_artifacts or ()
    )
    if history:
        failure_evidence["prior_emissions"] = history

    expectations = expectation_lines((envelope.inputs or {}).get("acceptance_criteria"))
    if expectations:
        failure_evidence["contract_expectations"] = expectations

    error_lines = error_seam_instructions(interface_manifest)
    if error_lines:
        failure_evidence["error_contract"] = error_lines

    model_lines = model_surface_instructions(interface_manifest)
    if model_lines:
        failure_evidence["model_surface"] = model_lines


@dataclass(frozen=True)
class CorrectionProtocolResult:
    """Outcome of one correction-protocol run.

    ``repair_artifacts`` carries the repair steps' emitted files (handler
    ``artifacts`` dicts, validate step excluded) so the executor can verify
    the patch behaviorally against them (#389) instead of re-dispatching
    the generative task and re-rolling its output.
    """

    correction_path: str
    repair_artifacts: list[dict[str, Any]] = field(default_factory=list)
    #: #1256: the rows each repair step evaluated on its own patch, in step order (rule B,
    #: #1229) — the handler's ``repair_typed_checks`` output, one entry per step that
    #: produced any, each carrying its own environment (a round may run a dev step and a
    #: qa step). Until this, the executor read the rows off the FAILED task's result and
    #: found none: the 1.7.1 React shakeout's dev repairs reported ``rows=10 executed=10``
    #: and runtime-api logged ``agent_rows=0`` on both rounds.
    repair_typed_checks: tuple[dict[str, Any], ...] = ()
    #: #1053: repair steps ran and produced no content at all. Distinct from "produced
    #: a bad repair" and from "no repair step ran": arm B of the 2026-08-23 pair banked
    #: `repair_output.md` at ZERO bytes on two of its three rounds, under the handler's
    #: generic fallback name, while holding a correct and stable diagnosis. Each was
    #: counted as a spent attempt, so `Max correction attempts (3) exhausted` described
    #: a loop that had actually tried once. An emission containing nothing is an
    #: emission failure (`FailureEvidenceCategory.EMISSION_ABSENT`'s shape), not an
    #: attempt at the fix.
    emission_empty: bool = False
    #: #998: the SIGNATURE of each empty repair emission this round, in step order —
    #: ``cap_exhausted`` (the model spent its whole completion budget and closed no
    #: content), ``empty`` (fewer tokens than the budget, nothing returned), or
    #: ``unextractable``. Two empties with opposite remedies must not read the same on
    #: the correction event; before this they did not read at all.
    empty_emission_signatures: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Diagnosis:
    """What the diagnosis step produced, for the four steps after it (map §4 step 4).

    ``correlation_id`` rides here rather than being re-derived: every correction and
    repair envelope of one chain shares it, so a repair that minted its own would break
    the lineage a trace is read by. It is the clearest instance of the rule the step
    boundaries enforce — a later step reaching backward into the diagnosis's locals for
    it would compile and read fine, and the drift would only show in a trace.
    """

    failure_evidence: dict[str, Any]
    analysis_outputs: dict[str, Any]
    decision_outputs: dict[str, Any]
    correlation_id: str


class CorrectionRunner:
    """Runs the correction protocol for a failed task (SIP-0079 semantics).

    Plain injected collaborator (not a port); the executor composes a
    default from its own deps. Independently unit-testable without a
    ``DispatchedFlowExecutor`` instance.
    """

    def __init__(
        self,
        cycle_registry: CycleRegistryPort,
        artifact_vault: ArtifactVaultPort,
        event_bus: CycleEventBusPort,
        *,
        task_dispatcher: TaskDispatcher,
        store_artifact: Callable[..., Awaitable[ArtifactRef]],
        correction_repair: CorrectionRepair | None = None,
    ) -> None:
        self._cycle_registry = cycle_registry
        self._artifact_vault = artifact_vault
        self._event_bus = event_bus
        self._task_dispatcher = task_dispatcher
        self._store_artifact = store_artifact
        # 1.7.5 recovery extraction map §4 step 5: the repair half. Composed at the
        # executor's seam and handed in; the default here is the same shape the executor
        # uses for this runner itself (SIP-0097 §6.3) so a direct construction still
        # works. It borrows `_dispatch_protocol_step` rather than owning a dispatch of
        # its own — that method owns task-run creation and the SIP-0087 task events, so
        # a second dispatch path would take correction repairs out of the Prefect UI.
        self._correction_repair = correction_repair or CorrectionRepair(
            # A lambda, not the bound method: the dispatch seam is patched by the
            # correction-context golden and by several suites, and a reference captured
            # here would keep calling the original past the patch — silently, since the
            # collaborator would still dispatch and the golden would diff the real
            # envelope against the stub's.
            dispatch_step=lambda *args, **kw: self._dispatch_protocol_step(*args, **kw)
        )

    async def _store_correction_task_artifacts(
        self,
        result: TaskResult,
        envelope: TaskEnvelope,
        cycle: Cycle,
        run_id: str,
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        only_types: tuple[str, ...] | None = None,
    ) -> None:
        """Persist a correction-task or repair-task's output artifacts.

        Mirrors the artifact-storage loop in the executor's
        ``_collect_artifacts_and_checkpoint`` but is split out so the
        correction/repair success branches can call it before
        ``_checkpoint_correction_task`` — which only snapshots existing
        ``all_artifact_refs`` into a checkpoint and does not itself
        persist new artifacts. Without this call, repaired deliverables
        (e.g. the ``qa_handoff.md`` produced by ``builder.assemble_repair``
        or the ``correction_decision.md`` from the correction protocol)
        never reach the artifact registry, even though the cycle marks
        completed and the run_report counts them as repaired. This was
        observed across cycles 4b, 6, and prior gate-batch runs as the
        recurring "silent artifact-drop" pattern.

        ``only_types`` (#1017) restricts storage to the named artifact types —
        the FAILED branch stores evidence only (``test_report``), never the
        step's workspace files: a failed retest's re-emitted ``test``-typed
        copies would otherwise enter the vault under the failed task's own
        ``producing_task_type`` and read as legitimate qa output to every
        workspace view, quietly defeating the rejected-candidate exclusion.
        """
        new_refs: list[str] = []
        for art in (result.outputs or {}).get("artifacts", []):
            if only_types is not None and art.get("type") not in only_types:
                continue
            ref = await self._store_artifact(
                art,
                cycle,
                run_id,
                envelope,
                producing_task_type=envelope.task_type,
            )
            new_refs.append(ref.artifact_id)
            all_artifact_refs.append(ref.artifact_id)
            stored_artifacts.append((ref.artifact_id, ref))

        if new_refs:
            await self._cycle_registry.append_artifact_refs(run_id, tuple(new_refs))

    async def _checkpoint_correction_task(
        self,
        task_id: str,
        run_id: str,
        cycle: Cycle,
        completed_task_ids: list[str],
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        plan_delta_refs: list[str],
    ) -> None:
        """Checkpoint a correction or repair task after successful dispatch."""
        completed_task_ids.append(task_id)
        checkpoint_index = len(completed_task_ids)
        new_checkpoint = RunCheckpoint(
            run_id=run_id,
            checkpoint_index=checkpoint_index,
            completed_task_ids=tuple(completed_task_ids),
            prior_outputs=dict(prior_outputs),
            artifact_refs=tuple(all_artifact_refs),
            plan_delta_refs=tuple(plan_delta_refs),
            created_at=datetime.now(UTC),
        )
        # SIP-0101 Slice 2: correction-chain checkpoints are iteration state, not
        # replay boundaries — deliberately unretained (retain defaults False) so a
        # correction storm cannot pin unbounded rows past the prune window.
        await self._cycle_registry.save_checkpoint(new_checkpoint)
        self._event_bus.emit(
            EventType.CHECKPOINT_CREATED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload={
                "checkpoint_index": checkpoint_index,
                "completed_task_id": task_id,
            },
        )

    def _emit_scaffold_integrity_evidence(self, record: Any, envelope: TaskEnvelope) -> None:
        """SIP-0100 3.3/3.4b: surface one repair-path enforcement as a structured event + log
        (best-effort — observability must never break the correction loop). Mirrors the
        executor's emitter for the regular storage path."""
        payload = record.to_dict()
        logger.warning("SIP-0100 scaffold_integrity (repair path): %s", payload)
        try:
            self._event_bus.emit(
                EventType.ARTIFACT_OWNERSHIP_ENFORCED,
                entity_type="artifact",
                entity_id=record.normalized_path or record.attempted_path,
                context={"cycle_id": envelope.cycle_id, "run_id": record.bound_run_id},
                payload=payload,
            )
        except Exception:
            logger.debug("SIP-0100: scaffold_integrity event emit failed", exc_info=True)

    def _enforce_step_emissions(
        self,
        result: TaskResult,
        step_envelope: TaskEnvelope,
        run_id: str,
        bound_record: Any,
        enforcement_carry: list[str] | None,
    ) -> None:
        """Apply the 3.4b frozen-ownership restore and the pf-31 Fix D syntax
        gate to a protocol step's emitted artifacts, in place (both landing
        paths read ``result.outputs``), with evidence events and next-attempt
        carry instructions for every enforcement."""
        # SIP-0100 3.4b: enforce frozen ownership on the step's emissions
        # before ANY landing point (registry store below, the caller's
        # repair overlay, patch verification). In-place replacement of
        # the artifacts list is deliberate — both consumers read
        # result.outputs.
        step_artifacts = (result.outputs or {}).get("artifacts") or []
        if bound_record is not None and step_artifacts:
            from squadops.cycles.scaffold_enforcement import (
                enforce_frozen_ownership,
                enforcement_instruction,
            )

            enforced, integrity_evidence = enforce_frozen_ownership(
                step_artifacts, bound_record, step_envelope
            )
            if integrity_evidence:
                result.outputs["artifacts"] = enforced
                step_artifacts = enforced
                for record in integrity_evidence:
                    self._emit_scaffold_integrity_evidence(record, step_envelope)
                    # SIP-0104 P4: one selector covers the frozen-file AND the
                    # region-level codes — the next attempt is TOLD what enforcement
                    # rejected instead of fighting it blind (#691; the #884 repair
                    # class §4.3 prohibits).
                    instruction = enforcement_instruction(record)
                    if (
                        instruction is not None
                        and enforcement_carry is not None
                        and instruction not in enforcement_carry
                    ):
                        enforcement_carry.append(instruction)

        # pf-31 Fix D: drop syntactically invalid .py emissions (truncation
        # guard) — the prior stored version (last known parseable) stays
        # current for RC3 and the retest; the next attempt is told what was
        # discarded via the same carry transport as the frozen restores.
        if step_artifacts:
            from squadops.cycles.emission_integrity import (
                emission_integrity_instruction,
                syntax_gate_python_artifacts,
            )

            kept, rejected = syntax_gate_python_artifacts(step_artifacts)
            if rejected:
                result.outputs["artifacts"] = kept
                for art, error in rejected:
                    name = art.get("name") or art.get("path") or "(unnamed)"
                    payload = {
                        "producer_task_id": step_envelope.task_id,
                        "producer_task_type": step_envelope.task_type,
                        "artifact": name,
                        "error": error,
                        "disposition": "dropped",
                    }
                    logger.warning("pf-31 emission_integrity (repair path): %s", payload)
                    try:
                        self._event_bus.emit(
                            EventType.ARTIFACT_EMISSION_REJECTED,
                            entity_type="artifact",
                            entity_id=name,
                            context={
                                "cycle_id": step_envelope.cycle_id,
                                "run_id": run_id,
                            },
                            payload=payload,
                        )
                    except Exception:
                        logger.debug("emission_integrity event emit failed", exc_info=True)
                    if enforcement_carry is not None:
                        instruction = emission_integrity_instruction(name, error)
                        if instruction not in enforcement_carry:
                            enforcement_carry.append(instruction)

    async def _dispatch_protocol_step(
        self,
        step_envelope: TaskEnvelope,
        run_id: str,
        cycle: Cycle,
        flow_run_id: str | None,
        *,
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        completed_task_ids: list[str],
        plan_delta_refs: list[str],
        bound_record: Any = None,
        enforcement_carry: list[str] | None = None,
        budget_guard: Callable[[], None] | None = None,
    ) -> TaskResult:
        """Dispatch one correction/repair step and handle its outcome.

        ``budget_guard`` (#511) fires FIRST — this is the correction lanes'
        single dispatch boundary, so raising here is what "the budget gates
        every dispatch decision" means for analyze/decision/repair/retest.

        The shared per-step sequence both protocol loops used verbatim:
        create the Prefect task_run (SIP-0087 B2), emit TASK_DISPATCHED,
        dispatch, then on success emit TASK_SUCCEEDED + persist the step's
        output artifacts BEFORE checkpointing (the silent-artifact-drop
        guard), or on failure emit TASK_FAILED. Returns the step's result;
        output collection stays with the caller (the two loops bucket
        outputs differently — issue #95 vs. repair prior_outputs).

        SIP-0100 3.4b: when ``bound_record`` is set, the step's emitted
        artifacts pass through the same frozen-ownership enforcement as
        regular task storage BEFORE they land anywhere — the enforced list
        replaces ``result.outputs["artifacts"]`` in place, so registry
        storage, the caller's repair overlay, and patch verification all
        see restored bytes, never the clobber. Each restore appends its
        authoritative instruction to ``enforcement_carry`` for the next
        attempt's evidence (restore+signal).
        """
        if budget_guard is not None:
            budget_guard()
        task_run_id = await self._task_dispatcher.create_task_run_if_enabled(
            flow_run_id, step_envelope
        )
        task_context = {
            "cycle_id": cycle.cycle_id,
            "run_id": run_id,
            "flow_run_id": flow_run_id or "",
            "task_run_id": task_run_id or "",
        }
        self._event_bus.emit(
            EventType.TASK_DISPATCHED,
            entity_type="task",
            entity_id=step_envelope.task_id,
            context=task_context,
            payload={"task_type": step_envelope.task_type},
        )

        result = await self._task_dispatcher.dispatch_task(
            step_envelope,
            run_id,
            flow_run_id=flow_run_id,
            task_run_id=task_run_id,
        )

        if result.status == TaskResultStatus.SUCCEEDED:
            self._event_bus.emit(
                EventType.TASK_SUCCEEDED,
                entity_type="task",
                entity_id=step_envelope.task_id,
                context=task_context,
                payload={"task_type": step_envelope.task_type},
            )
            # SIP-0100 3.4b + pf-31 Fix D: frozen-ownership restore and the
            # invalid-emission syntax gate, applied before ANY landing point.
            self._enforce_step_emissions(
                result, step_envelope, run_id, bound_record, enforcement_carry
            )
            # Persist the step's output artifacts BEFORE checkpointing —
            # _checkpoint_correction_task only snapshots existing refs and
            # would otherwise drop these silently.
            await self._store_correction_task_artifacts(
                result,
                step_envelope,
                cycle,
                run_id,
                all_artifact_refs,
                stored_artifacts,
            )
            await self._checkpoint_correction_task(
                step_envelope.task_id,
                run_id,
                cycle,
                completed_task_ids,
                prior_outputs,
                all_artifact_refs,
                plan_delta_refs,
            )
        else:
            # #1017: a failed step's EVIDENCE survives, its workspace files do not.
            # The failed retest is the motivating case: its test_report.md carries
            # the runner stdout naming exactly which tests rejected the repair —
            # the fact that adjudicates a red retest — and was previously built by
            # the handler and dropped here (the V38 slot-6 #1012 adjudication
            # required a full offline replay to recover what this one artifact
            # would have said). Report-typed artifacts only; see the helper's
            # ``only_types`` docstring for why the rest must never be stored.
            await self._store_correction_task_artifacts(
                result,
                step_envelope,
                cycle,
                run_id,
                all_artifact_refs,
                stored_artifacts,
                only_types=("test_report",),
            )
            self._event_bus.emit(
                EventType.TASK_FAILED,
                entity_type="task",
                entity_id=step_envelope.task_id,
                context=task_context,
                payload={"task_type": step_envelope.task_type, "error": result.error or ""},
            )
        return result

    async def _check_progress_termination(
        self,
        *,
        signature_state: dict[str, Any],
        envelope: TaskEnvelope,
        failure_evidence: dict[str, Any],
        delta: PlanDelta,
        delta_artifact_id: str,
        correction_attempts: int,
        cycle: Cycle,
        run_id: str,
        all_artifact_refs: list[str],
        repair_rejections: list[str] | None = None,
    ) -> None:
        """#435 A4.3: terminate the chain as ``plan_defect`` on an exact
        adjacent repeat with structural candidates on both rounds.

        An infra round (no product signature — A3 owns its routing) CLEARS the
        task's chain state: adjacency is strict, per the decision table. On
        termination the typed ``CorrectionTermination`` record is persisted as
        a ``correction_termination`` artifact and the chain aborts through the
        normal ``_ExecutionError`` path, so ``failure_reason`` (#427) names it.

        #1129: a round whose repair patch verification REFUSED is not a round
        this rule may count. Nothing was applied, no retest ran, and the failed
        task re-ran against the unrepaired tree, so its signature repeats by
        construction — "the repair did not help" and "the repair was never
        applied" were indistinguishable here, and two 1.6.5 rolls ended
        ``plan_defect`` after zero applied repairs. The previous round's
        signature is treated as absent (the same clearing an infra round gets)
        and this round becomes the chain's first-seen; the attempt cap still
        bounds a repair that keeps being refused.
        """
        current_sig = failure_signature(failure_evidence)
        state = signature_state.get(envelope.task_id)
        if current_sig is None:
            signature_state.pop(envelope.task_id, None)
            return
        if state and repair_refused_in_round(repair_rejections, int(state.get("round", -1))):
            logger.info(
                "plan_defect terminal: round %s's repair for task=%s was refused by patch "
                "verification and never applied — its signature is not counted as a "
                "repeat (#1129)",
                state.get("round"),
                envelope.task_id,
            )
            state = None
        prev_sig = state["signature"] if state else None
        prev_candidate = state["candidate"] if state else None
        candidate = delta.structural_plan_change_candidate

        if should_terminate_plan_defect(prev_sig, current_sig, prev_candidate, candidate):
            termination = CorrectionTermination(
                reason=CorrectionTerminationReason.PLAN_DEFECT,
                failed_task_id=envelope.task_id,
                repeated_signature=render_signature(current_sig),
                structural_candidate=candidate,
                first_seen_round=int(state["first_seen_round"]),
                terminal_round=correction_attempts,
                supporting_artifact_ids=tuple(
                    x for x in (state.get("delta_artifact_id"), delta_artifact_id) if x
                ),
            )
            content = json.dumps(termination.to_dict()).encode()
            ref = ArtifactRef(
                artifact_id=f"term_{envelope.task_id[-8:]}_{correction_attempts:02d}",
                project_id=cycle.project_id,
                artifact_type="correction_termination",
                filename="correction_termination.json",
                content_hash=sha256(content).hexdigest(),
                size_bytes=len(content),
                media_type="application/json",
                created_at=datetime.now(UTC),
                cycle_id=cycle.cycle_id,
                run_id=run_id,
            )
            await self._artifact_vault.store(ref, content)
            all_artifact_refs.append(ref.artifact_id)
            logger.warning(
                "correction_terminated_plan_defect task=%s rounds=%d..%d candidate=%s signature=%s",
                envelope.task_id,
                termination.first_seen_round,
                termination.terminal_round,
                candidate,
                "; ".join(termination.repeated_signature),
            )
            # #878 rider: the rule needs a structural candidate PRESENT on both
            # decisions, not the same one — naming only the terminal candidate
            # "on both" misstated roll 14's add_task/tighten_acceptance pair.
            raise _ExecutionError(
                f"plan_defect: correction terminated at round {correction_attempts} — "
                f"failure signature repeated from round {termination.first_seen_round}, "
                f"structural plan-change candidates on both decisions "
                f"(terminal: {candidate!r}); "
                f"the plan, not the work product, is the defect "
                f"(see {ref.artifact_id})"
            )

        movement = classify_movement(prev_sig, current_sig)
        first_seen = (
            int(state["first_seen_round"])
            if state and movement == "repeat"
            else correction_attempts
        )
        signature_state[envelope.task_id] = {
            "signature": current_sig,
            "candidate": candidate,
            "first_seen_round": first_seen,
            "round": correction_attempts,
            "delta_artifact_id": delta_artifact_id,
        }

    async def run_correction_protocol(
        self,
        run_id: str,
        cycle: Cycle,
        envelope: TaskEnvelope,
        result: TaskResult,
        correction_attempts: int,
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        completed_task_ids: list[str],
        plan_delta_refs: list[str],
        profile: Any = None,
        flow_run_id: str | None = None,
        interface_manifest: Any = None,
        artifact_contents: dict[str, str] | None = None,
        scaffold_enforcement_carry: list[str] | None = None,
        budget_guard: Callable[[], None] | None = None,
        signature_state: dict[str, Any] | None = None,
        repair_rejections: list[str] | None = None,
        has_accepted_repair: bool = False,
    ) -> CorrectionProtocolResult:
        """Run the correction protocol: analyze → decide → act.

        ``signature_state`` (#435, 1.5 A4) is the executor-owned, run-lived
        chain state (failed task id → last signature/candidate/first-seen
        round). After the decision step, an exact adjacent signature repeat
        with structural candidates on both rounds terminates the chain as
        ``plan_defect`` BEFORE any repair dispatch — decision table on #435.

        ``budget_guard`` (#511) raises at the dispatch choke point when the
        run's time budget is spent — correction chains previously bypassed
        the budget entirely and could overrun the run's contract
        indefinitely.

        Returns the correction_path chosen by the governance handler plus,
        on the patch path, the repair steps' emitted artifacts (#389).
        Side effects: dispatches correction/repair tasks, stores plan delta,
        emits correction events.

        ``scaffold_enforcement_carry`` is an executor-owned, run-lived list
        (3.4b restore+signal): instructions from prior attempts' frozen-path
        restores are injected into this attempt's ``failure_evidence``, and
        this attempt's restores append new instructions for the next.

        ``repair_rejections`` (#870) is this task's slice of the executor-owned
        rejected-repair record: what happened to the PREVIOUS attempt's repair
        (patch verification named checks, or the behavioral retest verdict).
        Injected as an authoritative evidence block so analysis and the next
        repair reason about the rejection instead of re-deriving the failure
        blind — roll 12's non-compiling repair was rejected honestly and
        nothing downstream was ever told why.
        """

        from squadops.cycles.scaffold_enforcement import bound_record_or_none

        # SIP-0100 3.4b: repair emissions are subject to the same frozen-ownership
        # enforcement as regular task storage — None on unbound runs (no-op).
        bound_record = bound_record_or_none(interface_manifest, run_id)
        # The five protocol steps, each a method consuming the previous step's returned
        # value (1.7.5 recovery extraction map §4 step 4). The orchestration below reads
        # as diagnose → resolve → bank-and-terminate → repair → judge, with a typed value
        # across each arrow — a helper that was shorter only because it read twenty
        # attributes off ``self`` would not have become structurally better.
        diagnosis = await self._diagnose(
            run_id,
            cycle,
            envelope,
            result,
            correction_attempts,
            prior_outputs=prior_outputs,
            all_artifact_refs=all_artifact_refs,
            stored_artifacts=stored_artifacts,
            completed_task_ids=completed_task_ids,
            plan_delta_refs=plan_delta_refs,
            profile=profile,
            flow_run_id=flow_run_id,
            interface_manifest=interface_manifest,
            artifact_contents=artifact_contents,
            scaffold_enforcement_carry=scaffold_enforcement_carry,
            budget_guard=budget_guard,
            repair_rejections=repair_rejections,
            bound_record=bound_record,
        )

        correction_path = self._resolve_correction_path(
            diagnosis, cycle, run_id, has_accepted_repair=has_accepted_repair
        )

        await self._bank_delta_and_check_termination(
            diagnosis,
            correction_path,
            envelope,
            cycle,
            run_id,
            correction_attempts,
            all_artifact_refs=all_artifact_refs,
            plan_delta_refs=plan_delta_refs,
            signature_state=signature_state,
            repair_rejections=repair_rejections,
        )

        repair = await self._correction_repair.dispatch(
            correction_path,
            diagnosis,
            envelope,
            result,
            cycle,
            run_id,
            correction_attempts,
            prior_outputs=prior_outputs,
            all_artifact_refs=all_artifact_refs,
            stored_artifacts=stored_artifacts,
            completed_task_ids=completed_task_ids,
            plan_delta_refs=plan_delta_refs,
            profile=profile,
            flow_run_id=flow_run_id,
            interface_manifest=interface_manifest,
            scaffold_enforcement_carry=scaffold_enforcement_carry,
            budget_guard=budget_guard,
            bound_record=bound_record,
        )

        emission_empty = self._correction_repair.judge_emission(repair, correction_attempts)

        # 8. Emit CORRECTION_COMPLETED
        self._event_bus.emit(
            EventType.CORRECTION_COMPLETED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            # Disclosed on the event, not only in a log line: "converged in 3" and
            # "converged in 3 after two empty emissions" must not read the same.
            payload={
                "correction_path": correction_path,
                "emission_empty": emission_empty,
                # #998: "converged in 3 after two empty emissions" must also say WHICH
                # nothing — the two shapes have opposite remedies.
                "empty_emission_signatures": (
                    list(repair.empty_signatures) if emission_empty else []
                ),
            },
        )

        return CorrectionProtocolResult(
            correction_path=correction_path,
            repair_artifacts=repair.artifacts,
            repair_typed_checks=tuple(repair.typed_checks),
            emission_empty=emission_empty,
            empty_emission_signatures=(tuple(repair.empty_signatures) if emission_empty else ()),
        )

    async def _diagnose(
        self,
        run_id: str,
        cycle: Cycle,
        envelope: TaskEnvelope,
        result: TaskResult,
        correction_attempts: int,
        *,
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        completed_task_ids: list[str],
        plan_delta_refs: list[str],
        profile: Any,
        flow_run_id: str | None,
        interface_manifest: Any,
        artifact_contents: dict[str, str] | None,
        scaffold_enforcement_carry: list[str] | None,
        budget_guard: Callable[[], None] | None,
        repair_rejections: list[str] | None,
        bound_record: Any,
    ) -> _Diagnosis:
        """Step 1 — build the failure evidence and run ``CORRECTION_TASK_STEPS``.

        Each step's outputs are captured in their own bucket (#95): reusing one variable
        masked the analyzer's classification with defaults at PlanDelta time, because the
        decision step does not carry those fields forward.
        """
        from uuid import uuid4

        from squadops.cycles.task_plan import CORRECTION_TASK_STEPS

        # 1. Emit CORRECTION_INITIATED
        self._event_bus.emit(
            EventType.CORRECTION_INITIATED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload={
                "failed_task_id": envelope.task_id,
                "failed_task_type": envelope.task_type,
                "correction_attempt": correction_attempts + 1,
            },
        )

        # 2. Build correction task envelopes (deterministic IDs)
        failure_evidence = build_failure_evidence(
            envelope, result, prior_plan_deltas_count=len(plan_delta_refs)
        )
        _inject_deterministic_evidence(
            failure_evidence,
            envelope=envelope,
            interface_manifest=interface_manifest,
            artifact_contents=artifact_contents,
            scaffold_enforcement_carry=scaffold_enforcement_carry,
            bound_record=bound_record,
            repair_rejections=repair_rejections,
            stored_artifacts=stored_artifacts,
        )

        # Issue #95: capture each correction step's outputs in its own variable
        # so the analyzer's classification/analysis_summary survive past the
        # subsequent governance.correction_decision step (which doesn't carry
        # those fields forward). Reusing a single variable used to mask the
        # analyzer's diagnosis with defaults at PlanDelta time.
        analysis_outputs: dict[str, Any] = {}
        decision_outputs: dict[str, Any] = {}
        corr_correlation_id = uuid4().hex

        for step_idx, (task_type, role) in enumerate(CORRECTION_TASK_STEPS):
            corr_task_id = f"corr-{run_id[:12]}-{correction_attempts:02d}-{task_type}"
            resolved = resolve_agent_config(role, profile)
            agent_id = resolved.agent_id
            agent_model = resolved.model
            agent_overrides = resolved.config_overrides

            # Issue #110: propagate squad-profile model + overrides so
            # correction-loop reasoning runs on the cycle's specified model
            # (e.g. the `full` profile pins data/lead to qwen3.6:27b)
            # rather than the agent container's instance default.
            corr_inputs: dict[str, Any] = {
                "prd": cycle.prd_ref,
                "failure_evidence": failure_evidence,
                "prior_outputs": prior_outputs,
                "artifact_refs": list(all_artifact_refs),
                "agent_model": agent_model,
                "agent_config_overrides": agent_overrides,
                # 1.7.4 plan §3.1: the cycle's resolved config rides the analysis and
                # decision envelopes as it does every other cycle task's, so a fault
                # declared on the cycle reaches the analyzer's emission seam (#968's
                # diagnostic). Neither handler reads anything else from it — model and
                # overrides arrive on their own keys above (#110).
                "resolved_config": cycle.resolved_config(),
            }
            if analysis_outputs:
                corr_inputs["failure_analysis"] = analysis_outputs
                _attach_refuted_claims(corr_inputs, analysis_outputs, envelope)

            corr_envelope = TaskEnvelope(
                task_id=corr_task_id,
                agent_id=agent_id,
                cycle_id=cycle.cycle_id,
                pulse_id=uuid4().hex,
                project_id=cycle.project_id,
                task_type=task_type,
                correlation_id=corr_correlation_id,
                causation_id=envelope.task_id,
                trace_id=uuid4().hex,
                span_id=uuid4().hex,
                inputs=corr_inputs,
                metadata={"role": role, "step_index": step_idx},
            )

            # 3. Dispatch correction task (task_run creation + task events
            # live in _dispatch_protocol_step, SIP-0087 B2).
            corr_result = await self._dispatch_protocol_step(
                corr_envelope,
                run_id,
                cycle,
                flow_run_id,
                prior_outputs=prior_outputs,
                all_artifact_refs=all_artifact_refs,
                stored_artifacts=stored_artifacts,
                completed_task_ids=completed_task_ids,
                plan_delta_refs=plan_delta_refs,
                budget_guard=budget_guard,
            )

            # Collect correction task outputs into the right named bucket so
            # downstream PlanDelta construction reads each field from the
            # handler that owns it (issue #95).
            step_outputs = {
                k: v for k, v in (corr_result.outputs or {}).items() if k != "artifacts"
            }
            bucket = _CORRECTION_STEP_OUTPUT_BUCKET.get(task_type)
            if bucket == "analysis":
                analysis_outputs = step_outputs
            elif bucket == "decision":
                decision_outputs = step_outputs
        return _Diagnosis(
            failure_evidence=failure_evidence,
            analysis_outputs=analysis_outputs,
            decision_outputs=decision_outputs,
            correlation_id=corr_correlation_id,
        )

    def _resolve_correction_path(
        self,
        diagnosis: _Diagnosis,
        cycle: Cycle,
        run_id: str,
        *,
        has_accepted_repair: bool,
    ) -> str:
        """Step 2 — the deterministic policy guard, then ``CORRECTION_DECIDED``.

        The model's original rationale stays intact in the decision artifact; an override
        is disclosed in the event payload rather than silently replacing it (#447).
        """
        # What the earlier steps produced, read off the value they returned —
        # never reached backward into their locals (map §4 step 4).
        failure_evidence = diagnosis.failure_evidence
        analysis_outputs = diagnosis.analysis_outputs
        decision_outputs = diagnosis.decision_outputs
        # 4. Read correction_path — bounded by the deterministic policy guard
        # (#447): `continue` may not discard a required check that executed
        # and failed while this chain's repair slot is unspent. The model's
        # original rationale stays intact in the decision artifact; the
        # override is disclosed in the event payload below.
        from squadops.cycles.correction_policy import resolve_correction_path

        resolution = resolve_correction_path(
            decision_outputs.get("correction_path", "abort"),
            failure_evidence,
            cycle.resolved_config(),
            # pf-45: the rewind anchor keys on the analyzer's classification — a
            # work_product rewind dies as a run failure with the repair budget unspent,
            # so the guard substitutes the patch the classification says is possible.
            classification=str(analysis_outputs.get("classification", "")),
            # #994: a rewind re-authors from the checkpoint, so it cannot preserve a
            # repair that landed after it. Threaded from the executor, which is the only
            # place that knows a prior round of THIS task was accepted.
            has_accepted_repair=has_accepted_repair,
        )
        correction_path = resolution.path
        if resolution.overridden_from:
            logger.warning(
                "correction_policy_override: %s -> %s (%s%s)",
                resolution.overridden_from,
                resolution.path,
                resolution.override_reason,
                (
                    "; checks: " + ", ".join(resolution.failed_required_checks)
                    if resolution.failed_required_checks
                    else ""
                ),
            )

        # 5. Emit CORRECTION_DECIDED
        decided_payload: dict[str, Any] = {
            "correction_path": correction_path,
            "decision_rationale": decision_outputs.get("decision_rationale", ""),
        }
        if resolution.overridden_from:
            decided_payload["policy_override"] = {
                "from": resolution.overridden_from,
                "reason": resolution.override_reason,
                "checks": list(resolution.failed_required_checks),
            }
        self._event_bus.emit(
            EventType.CORRECTION_DECIDED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload=decided_payload,
        )
        return correction_path

    async def _bank_delta_and_check_termination(
        self,
        diagnosis: _Diagnosis,
        correction_path: str,
        envelope: TaskEnvelope,
        cycle: Cycle,
        run_id: str,
        correction_attempts: int,
        *,
        all_artifact_refs: list[str],
        plan_delta_refs: list[str],
        signature_state: dict[str, Any] | None,
        repair_rejections: list[str] | None,
    ) -> None:
        """Step 3 — store the plan delta, then the progress-aware termination check.

        Order is the contract (#435, 1.5 A4): after the delta is stored, so the decision
        evidence survives the termination, and before any repair dispatch, so the maximum
        budget is honoured.
        """
        from uuid import uuid4

        # What the earlier steps produced, read off the value they returned —
        # never reached backward into their locals (map §4 step 4).
        failure_evidence = diagnosis.failure_evidence
        analysis_outputs = diagnosis.analysis_outputs
        decision_outputs = diagnosis.decision_outputs
        # 6. Store plan delta as artifact
        delta = PlanDelta(
            delta_id=uuid4().hex,
            run_id=run_id,
            correction_path=correction_path,
            trigger=compose_failure_trigger(envelope, failure_evidence),
            failure_classification=analysis_outputs.get("classification", "unknown"),
            analysis_summary=analysis_outputs.get("analysis_summary", "N/A"),
            decision_rationale=decision_outputs.get("decision_rationale", "N/A"),
            changes=tuple(decision_outputs.get("affected_task_types", [])),
            affected_task_types=tuple(decision_outputs.get("affected_task_types", [])),
            created_at=datetime.now(UTC),
            # SIP-0092 M2 → M3 gate diagnostic.
            structural_plan_change_candidate=str(
                decision_outputs.get("structural_plan_change_candidate", "none")
            ),
            structural_plan_change_rationale=str(
                decision_outputs.get("structural_plan_change_rationale", "")
            ),
        )
        delta_content = json.dumps(delta.to_dict(), default=str).encode()
        delta_ref = ArtifactRef(
            artifact_id=f"delta_{delta.delta_id[:12]}",
            project_id=cycle.project_id,
            artifact_type="plan_delta",
            filename=f"plan_delta_{correction_attempts}.json",
            content_hash=sha256(delta_content).hexdigest(),
            size_bytes=len(delta_content),
            media_type="application/json",
            created_at=datetime.now(UTC),
            cycle_id=cycle.cycle_id,
            run_id=run_id,
        )
        await self._artifact_vault.store(delta_ref, delta_content)
        all_artifact_refs.append(delta_ref.artifact_id)
        plan_delta_refs.append(delta_ref.artifact_id)

        # 6b. #435 (1.5 A4): progress-aware termination. Placed after the
        # delta is stored (the decision evidence survives) and before any
        # repair dispatch (maximum budget honored).
        if signature_state is not None:
            await self._check_progress_termination(
                signature_state=signature_state,
                envelope=envelope,
                failure_evidence=failure_evidence,
                delta=delta,
                delta_artifact_id=delta_ref.artifact_id,
                correction_attempts=correction_attempts,
                cycle=cycle,
                run_id=run_id,
                all_artifact_refs=all_artifact_refs,
                repair_rejections=repair_rejections,
            )

    # Artifact types a qa.test task emits *about* its run, not *into* its
    # workspace — excluded from re-execution so the repaired suite matches
    # the original workspace composition (#456).
    _NON_WORKSPACE_ARTIFACT_TYPES = frozenset({"test_report", "typed_check_evaluation"})

    async def reexecute_repaired_suite(
        self,
        run_id: str,
        cycle: Cycle,
        envelope: TaskEnvelope,
        patched_artifacts: list[dict[str, Any]],
        correction_attempts: int,
        *,
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        completed_task_ids: list[str],
        plan_delta_refs: list[str],
        profile: Any = None,
        flow_run_id: str | None = None,
        budget_guard: Callable[[], None] | None = None,
    ) -> TaskResult | None:
        """Re-execute a repaired qa.test suite in the QA agent's environment (#456).

        Patch verification (#389) covers typed criteria only; a qa.test failure's
        real evidence is behavioral (``tests_pass`` is synthesized from the
        task's executed ``test_result``). A repaired suite that is never re-run
        leaves the pre-repair failure as the check's final state — the
        run_8c14a430ad1c false-red. This dispatches the failed task's own
        task_type back to the QA agent in execute-only mode (``retest_files``
        set, no generation): same workspace, same runner, honestly fresh
        evidence for §6.5 final-state resolution to supersede with.

        Returns the retest ``TaskResult`` (its Prefect task_run, events,
        artifacts and checkpoint are handled by ``_dispatch_protocol_step``),
        or ``None`` when no runnable suite files survive the patch overlay.
        """
        from uuid import uuid4

        retest_files = [
            {"filename": art["name"], "content": art.get("content", "")}
            for art in patched_artifacts
            if isinstance(art, dict)
            and isinstance(art.get("name"), str)
            and art.get("type") not in self._NON_WORKSPACE_ARTIFACT_TYPES
        ]
        if not retest_files:
            return None

        failed_inputs = envelope.inputs or {}
        if not failed_inputs.get("artifact_contents") and "artifact_vault" not in failed_inputs:
            # No workspace to test against — the handler would reject the
            # envelope at input validation anyway (the 3.11 instant-fail).
            # Skip the doomed dispatch; the caller falls back to re-dispatch.
            logger.warning(
                "retest for %s skipped: failed envelope carries no workspace "
                "(artifact_contents/artifact_vault) — was the enriched envelope threaded?",
                envelope.task_id,
            )
            return None

        resolved = resolve_agent_config("qa", profile)
        # #663 S2: which failed-envelope context survives into the retest is a
        # registry-owned declaration — the workspace/contract identity
        # unconditionally, plus RETEST_PRESENCE_KEYS presence-keyed (#639
        # probes: stale probe evidence for a tree the repair changed; #643
        # acceptance workspace: the scaffold siblings exactly like the original
        # dispatch; #667 anchor surface: the fay-6 new-dice re-author works
        # blind to the DOM contract without it).
        retest_inputs: dict[str, Any] = {
            "prd": cycle.prd_ref,
            "retest_files": retest_files,
            "agent_model": resolved.model,
            "agent_config_overrides": resolved.config_overrides,
            **retest_forwarded_inputs(failed_inputs),
        }

        retest_envelope = TaskEnvelope(
            task_id=f"retest-{run_id[:12]}-{correction_attempts:02d}-{envelope.task_type}",
            agent_id=resolved.agent_id,
            cycle_id=cycle.cycle_id,
            pulse_id=uuid4().hex,
            project_id=cycle.project_id,
            task_type=envelope.task_type,
            correlation_id=uuid4().hex,
            causation_id=envelope.task_id,
            trace_id=uuid4().hex,
            span_id=uuid4().hex,
            inputs=retest_inputs,
            metadata={"role": "qa", "retest": True},
        )

        return await self._dispatch_protocol_step(
            retest_envelope,
            run_id,
            cycle,
            flow_run_id,
            prior_outputs=prior_outputs,
            all_artifact_refs=all_artifact_refs,
            stored_artifacts=stored_artifacts,
            completed_task_ids=completed_task_ids,
            plan_delta_refs=plan_delta_refs,
            budget_guard=budget_guard,
        )
