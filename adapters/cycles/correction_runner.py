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
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from squadops.cycles.agent_config import resolve_agent_config
from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.failure_evidence import build_failure_evidence, compose_failure_trigger
from squadops.cycles.models import ArtifactRef
from squadops.cycles.plan_delta import PlanDelta
from squadops.events.types import EventType
from squadops.tasks.models import TaskEnvelope

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from adapters.cycles.task_dispatcher import TaskDispatcher
    from squadops.cycles.models import Cycle
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.events.cycle_event_bus import CycleEventBusPort
    from squadops.tasks.models import TaskResult

logger = logging.getLogger(__name__)


def _top_level_package(path: str) -> str:
    """First path segment of a repo-relative artifact path.

    ``backend/tests/x.py`` → ``backend``; a bare filename is its own package.
    """
    head, _, _ = str(path).strip().lstrip("./").partition("/")
    return head


def _scope_to_shared_packages(candidates: list[str], anchors: list[str]) -> list[str]:
    """Keep ``candidates`` whose top-level package matches some ``anchor``'s.

    RC2 (pf-24) blast-radius control: a failing ``backend/tests/…`` test retargets
    ``backend/…`` source but leaves ``frontend/…`` untouched, so a backend failure
    can never regress frontend source. No anchors → nothing (the caller falls back
    to the failed artifacts alone).
    """
    anchor_pkgs = {_top_level_package(a) for a in anchors if a}
    if not anchor_pkgs:
        return []
    return [c for c in candidates if c and _top_level_package(c) in anchor_pkgs]


def _scope_to_shared_language(candidates: list[str], anchors: list[str]) -> list[str]:
    """Keep ``candidates`` on the same side of the frontend/backend line as ``anchors``.

    The guarantee RC2 was actually written to give — "a backend failure can never
    regress frontend source" — expressed against the source language instead of the
    directory tree, so it holds wherever the suite was authored.
    """
    from squadops.cycles.acceptance_check_spec import is_frontend_source

    anchor_sides = {is_frontend_source(a) for a in anchors if a}
    if len(anchor_sides) != 1:
        # No anchors, or anchors straddling both sides — nothing is excluded, so
        # scoping would not be bounding anything. Stay silent rather than widen.
        return []
    side = anchor_sides.pop()
    return [c for c in candidates if c and is_frontend_source(c) is side]


def _scoped_implementation_surface(candidates: list[str], anchors: list[str]) -> list[str]:
    """The implementation source a failure in ``anchors`` may legitimately retarget.

    Package scoping first — pf-24's rule, unchanged whenever it matches anything.
    When it comes back EMPTY the anchor was uninformative, not exclusive, and #688
    measured what that costs: shk-2's qa suite was authored at root-level ``tests/``,
    so its anchor package was ``tests``, ``backend/routes.py`` was filtered out, and
    the correction loop had no route to app source at all. fay-16…19 authored
    ``backend/tests/…``, which matched — so whether pf-24 and pf-27 worked at all
    depended on where the squad happened to put its tests.

    So the empty case falls back to the language boundary, which bounds the blast
    radius the way RC2 intended (a backend failure still cannot reach frontend
    source) without depending on the authored layout. A non-empty package match is
    strictly narrower, so it keeps winning.
    """
    scoped = _scope_to_shared_packages(candidates, anchors)
    if scoped:
        return scoped
    widened = _scope_to_shared_language(candidates, anchors)
    if widened:
        logger.info(
            "correction_repair_target: package scoping matched nothing for anchors %s — "
            "falling back to same-language implementation source %s (#688)",
            ", ".join(anchors),
            ", ".join(widened),
        )
    return widened


def _frontend_build_failed(failure_evidence: Any) -> bool:
    """#650 (fay-8): the failed task's validation shows the frontend build failing.

    A failing ``frontend_build`` row places the defect in frontend source no
    matter which task reported it — the check runs inside the backend qa.test
    task, so ownership-anchored targeting never reaches the broken view.
    """
    from squadops.cycles.check_registry import CHECK_FRONTEND_BUILD

    if not isinstance(failure_evidence, dict):
        return False
    checks = (failure_evidence.get("validation_result") or {}).get("checks") or []
    return any(
        isinstance(row, dict)
        and row.get("check") == CHECK_FRONTEND_BUILD
        and row.get("passed") is False
        for row in checks
    )


def _widen_target_for_frontend_build(
    target: list[str], failure_evidence: Any, failed_inputs: dict[str, Any]
) -> list[str]:
    """#650 minimal provenance targeting: a failing ``frontend_build`` unions the
    plan's frontend implementation source into the repair target.

    fay-8 (cyc_7f5f1b8b1790): five correction rounds, four identical
    ``frontend_build`` failures, every repair emitted backend/test files only —
    RC2's package scoping is deliberately conservative (``backend/tests/*`` →
    ``backend/*``, never ``frontend/*``), which is exactly the trap: the loop
    polished a passing backend while the build-breaking view sat outside every
    target. The general provenance-driven scope seam stays deferred (1.5);
    this widens exactly the measured case, derived from the same
    ``implementation_artifacts`` surface RC2 already threads.
    """
    if not _frontend_build_failed(failure_evidence):
        return target
    frontend_source = [
        p
        for p in (failed_inputs.get("implementation_artifacts") or [])
        if isinstance(p, str) and p.startswith("frontend/")
    ]
    return list(dict.fromkeys([*target, *frontend_source]))


def _failed_probe_ids(failure_evidence: Any) -> list[str]:
    """Ids of the behavioral probes that FAILED, in evidence order (#688).

    Probe rows enter ``validation_result.checks`` from ``probe_check_rows`` with
    ``check`` == ``criterion_id`` == the probe id and a ``status`` of
    passed/failed/skipped. Only ``failed`` counts: ``skipped`` means the subject
    never booted, which indicts no particular endpoint.
    """
    if not isinstance(failure_evidence, dict):
        return []
    rows = (failure_evidence.get("validation_result") or {}).get("checks") or []
    return [
        str(row.get("check"))
        for row in rows
        if isinstance(row, dict) and row.get("status") == "failed" and row.get("check")
    ]


def _probe_owned_slots(failure_evidence: Any, failed_inputs: dict[str, Any]) -> list[str]:
    """Fill-slot files owning the endpoints whose behavioral probes failed (#688).

    The deterministic chain the shk-2 loss chain needed and did not have:
    failed probe row → the probe's declared ``METHOD /path`` → the contract's
    endpoint→fill-slot map → the file that owns the failing endpoint.

    shk-2 (cyc_88162ecfd895): ``vc-probe-runs`` answered 500 because
    ``backend/routes.py`` used ``RunEvent`` without importing it. Both repairs
    emitted ``backend/main.py`` (named by interface-drift evidence) plus the
    failed qa task's own suite, and never ``routes.py`` — the target set could
    not name the defect site, so the loop reproduced the identical 500 and
    exhausted. This resolution names it from contract data alone, independent of
    the drift evidence and of where the squad chose to put its tests.

    Empty whenever the inputs are absent (author mode, probe-less contracts,
    pre-#688 envelopes) or no probe failed — the caller's target is then
    byte-identical to its prior behavior.
    """
    owners = failed_inputs.get("contract_endpoint_owners") or {}
    probes = failed_inputs.get("contract_probes") or []
    if not owners or not probes:
        return []
    failed_ids = _failed_probe_ids(failure_evidence)
    if not failed_ids:
        return []

    from squadops.cycles.verification_contract import Probe

    tokens_by_id: dict[str, str] = {}
    for raw in probes:
        try:
            probe = Probe.from_dict(raw)
        except ValueError:  # a malformed row indicts nothing; it must not raise here
            continue
        token = probe.endpoint_token()
        if token:
            tokens_by_id[probe.id] = token

    slots: list[str] = []
    for probe_id in failed_ids:
        owner = owners.get(tokens_by_id.get(probe_id, ""))
        if owner and owner not in slots:
            slots.append(owner)
    if slots:
        logger.info(
            "correction_repair_target: probe-owned fill slots %s (failed probes: %s)",
            ", ".join(slots),
            ", ".join(failed_ids),
        )
    return slots


def _resolve_repair_target(
    failure_evidence: Any, failed_inputs: dict[str, Any]
) -> tuple[list[str], str | None, str | None]:
    """Choose ``(expected_artifacts, focus, description)`` for a patch-path repair.

    #531: the target defaults to the *failed task's own* artifacts — but the
    ``tests_pass`` check lives on the qa test task, so anchoring there regenerates
    the tests (the symptom) while the drifted source (the cause) is never rewritten
    and the loop can't converge. When the correction carries deterministic
    interface-drift evidence (an AST diff, not the free-text ``affected_task_types``),
    the drifted files ARE part of the target so the dev repair rewrites the source.

    pf-21 (cyc_2aac58b9f03d): drift is not always the *whole* story — the failing
    check's OWN artifact can carry an independent bug too (there: models.py drift
    AND a broken pytest ``client`` fixture in the test file). #532 targeted the
    drift files EXCLUSIVELY, orphaning that file so the loop re-patched already-fixed
    source every attempt and never touched the real test bug → non-convergence. So
    when drift is present, target the UNION (drift files first, then the failed
    task's artifacts): the drifted source is always in the set (no masking — the
    cause is always fixable, the #531/#532 win holds), and the failing artifact's
    own bug is fixable too.

    pf-24 (cyc_38415226ad82) — RC2: a ``tests_pass``/probe failure with NO interface
    drift (a behavioral/runtime bug — there a missing ``/api`` router prefix in
    main.py) has its fix in the *source under test*, which the failing qa.test does
    NOT own (its artifacts are the test files). Anchoring on the failed task then
    edits only the test and the loop exhausts. So with no drift, extend the target
    with the plan's implementation source (``implementation_artifacts``, threaded
    onto qa.test envelopes by task_plan) that shares a top-level package with a
    failing artifact — ``backend/tests/*`` failure → ``backend/*`` source, never
    ``frontend/*`` (package-scoping bounds the blast radius). Absent that surface
    (author mode, non-build corrections) the target is byte-identical to the #531
    fallback below.

    shk-2 (cyc_88162ecfd895) — #688: every surface above is *indirect*. The drift branch
    names whatever files the drift evidence happened to name; the package-scoped union
    reaches app source only when the failed qa task's own artifacts share a top-level
    package with it. Both missed a one-line defect in ``backend/routes.py`` — drift
    pointed at ``backend/main.py``, and the suite was authored at root-level ``tests/``,
    so the scoped union came back empty (it matches on ``backend/tests/…``, which is what
    fay-16…19 happened to author: the reach depended on an authoring coincidence). Two
    changes, one per half of that:

    * The target now LEADS with the fill slots that own the FAILING PROBES' endpoints,
      resolved from contract data (``_probe_owned_slots``). Drift files and the failed
      task's own artifacts still ride — they carry real defects too, the pf-21 lesson —
      but they can no longer displace the defect site.
    * The scoped implementation surface falls back from package to language when the
      package anchor matches nothing (``_scoped_implementation_surface``), so a
      SUITE-ONLY failure — one with no probe evidence to resolve — can still reach the
      source under test on a root-level-``tests/`` layout.
    """
    probe_slots = _probe_owned_slots(failure_evidence, failed_inputs)
    drift = failure_evidence.get("interface_drift") if isinstance(failure_evidence, dict) else None
    drift_files = sorted(
        {d["file"] for d in (drift or []) if isinstance(d, dict) and d.get("file")}
    )
    failed_artifacts = failed_inputs.get("expected_artifacts", []) or []
    if drift_files:
        # Union, drift first, de-duplicated preserving order. The instructional "how"
        # is NOT authored here — it is the interface-drift `instruction`, already a
        # managed/authored asset surfaced into the repair prompt's failure summary
        # as the "INTERFACE CONFORMANCE" section, plus the failure summary itself for
        # the failing artifact's bug. So focus/description stay unset (no inline
        # prompt content — CLAUDE.md #448); the named artifacts + that instruction
        # redirect the repair onto both the drifted source and the failing file.
        # pf-27 (cyc_d01810b2922f): a ``tests_pass`` failure can CO-OCCUR with
        # interface drift on a scaffold-FROZEN file (there: backend/main.py — its
        # /health route + the repair's own un-restored inline routes), which pins the
        # target to this drift branch. But the behavioral fix still lives in the
        # fill-slot source under test (routes.py), which is neither a drift file nor
        # the failing qa.test's own artifact — so without the same package-scoped
        # implementation surface the no-drift branch already unions (RC2), the repair
        # edits only the drifted file + the test and NEVER reaches routes.py →
        # non-convergence. Union it here too; empty surface (author mode) → the scoped
        # set is empty and the target is byte-identical to the pre-pf-27 union.
        scoped_source = _scoped_implementation_surface(
            failed_inputs.get("implementation_artifacts", []) or [], failed_artifacts
        )
        target = list(
            dict.fromkeys([*probe_slots, *drift_files, *failed_artifacts, *scoped_source])
        )
        target = _widen_target_for_frontend_build(target, failure_evidence, failed_inputs)
        return (target, None, None)
    # RC2 no-drift path: union the failing task's own artifacts with the
    # package-scoped implementation surface so a behavioral failure can reach the
    # source under test. Empty surface → byte-identical to the #531 fallback
    # (failed_artifacts, focus, description).
    scoped_source = _scoped_implementation_surface(
        failed_inputs.get("implementation_artifacts", []) or [], failed_artifacts
    )
    target = list(dict.fromkeys([*probe_slots, *failed_artifacts, *scoped_source]))
    target = _widen_target_for_frontend_build(target, failure_evidence, failed_inputs)
    return (
        target,
        failed_inputs.get("subtask_focus"),
        failed_inputs.get("subtask_description"),
    )


def _inject_deterministic_evidence(
    failure_evidence: dict[str, Any],
    *,
    envelope: TaskEnvelope,
    interface_manifest: Any,
    artifact_contents: dict[str, str] | None,
    scaffold_enforcement_carry: list[str] | None,
    bound_record: Any = None,
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

    expectations = expectation_lines((envelope.inputs or {}).get("acceptance_criteria"))
    if expectations:
        failure_evidence["contract_expectations"] = expectations

    error_lines = error_seam_instructions(interface_manifest)
    if error_lines:
        failure_evidence["error_contract"] = error_lines

    model_lines = model_surface_instructions(interface_manifest)
    if model_lines:
        failure_evidence["model_surface"] = model_lines


def _locus_and_repair_target(
    failed_task_type: str,
    failure_evidence: Any,
    failed_inputs: dict[str, Any],
) -> tuple[str, list[str], str | None, str | None]:
    """#568: classify the failure locus and choose the repair target for it.

    Returns ``(locus, expected_artifacts, focus, description)``. An
    OWN_ARTIFACT failure (the failed task's own emission is missing or
    uncollectable) targets the failed task's own contract — pointing
    ``_resolve_repair_target``'s subject-implementation union at a test
    re-author would aim it at app source files. Every other locus keeps the
    existing target resolution unchanged.
    """
    from squadops.cycles.failure_evidence import FailureLocus, classify_failure_locus

    failure_locus = classify_failure_locus(failure_evidence)
    own_expected = [str(e) for e in (failed_inputs.get("expected_artifacts") or []) if e]
    if failure_locus == FailureLocus.OWN_ARTIFACT and own_expected:
        logger.info(
            "correction_repair_locus: own_artifact — %s re-produces %s",
            failed_task_type,
            ", ".join(own_expected),
        )
        return (
            failure_locus,
            own_expected,
            failed_inputs.get("subtask_focus"),
            failed_inputs.get("subtask_description"),
        )
    expected, focus, description = _resolve_repair_target(failure_evidence, failed_inputs)
    return (failure_locus, expected, focus, description)


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
    ) -> None:
        self._cycle_registry = cycle_registry
        self._artifact_vault = artifact_vault
        self._event_bus = event_bus
        self._task_dispatcher = task_dispatcher
        self._store_artifact = store_artifact

    async def _store_correction_task_artifacts(
        self,
        result: TaskResult,
        envelope: TaskEnvelope,
        cycle: Cycle,
        run_id: str,
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
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
        """
        new_refs: list[str] = []
        for art in (result.outputs or {}).get("artifacts", []):
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
                frozen_emission_instruction,
            )
            from squadops.cycles.task_outcome import ContractComplianceViolation

            enforced, integrity_evidence = enforce_frozen_ownership(
                step_artifacts, bound_record, step_envelope
            )
            if integrity_evidence:
                result.outputs["artifacts"] = enforced
                step_artifacts = enforced
                for record in integrity_evidence:
                    self._emit_scaffold_integrity_evidence(record, step_envelope)
                    if (
                        enforcement_carry is not None
                        and record.violation_code
                        == ContractComplianceViolation.FROZEN_PATH_EMISSION
                    ):
                        instruction = frozen_emission_instruction(record)
                        if instruction not in enforcement_carry:
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
    ) -> TaskResult:
        """Dispatch one correction/repair step and handle its outcome.

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

        if result.status == "SUCCEEDED":
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
            self._event_bus.emit(
                EventType.TASK_FAILED,
                entity_type="task",
                entity_id=step_envelope.task_id,
                context=task_context,
                payload={"task_type": step_envelope.task_type, "error": result.error or ""},
            )
        return result

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
    ) -> CorrectionProtocolResult:
        """Run the correction protocol: analyze → decide → act.

        Returns the correction_path chosen by the governance handler plus,
        on the patch path, the repair steps' emitted artifacts (#389).
        Side effects: dispatches correction/repair tasks, stores plan delta,
        emits correction events.

        ``scaffold_enforcement_carry`` is an executor-owned, run-lived list
        (3.4b restore+signal): instructions from prior attempts' frozen-path
        restores are injected into this attempt's ``failure_evidence``, and
        this attempt's restores append new instructions for the next.
        """
        from uuid import uuid4

        from squadops.cycles.scaffold_enforcement import bound_record_or_none
        from squadops.cycles.task_plan import CORRECTION_TASK_STEPS, repair_steps_for

        # SIP-0100 3.4b: repair emissions are subject to the same frozen-ownership
        # enforcement as regular task storage — None on unbound runs (no-op).
        bound_record = bound_record_or_none(interface_manifest, run_id)

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
            }
            if analysis_outputs:
                corr_inputs["failure_analysis"] = analysis_outputs

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
            )

            # Collect correction task outputs into the right named bucket so
            # downstream PlanDelta construction reads each field from the
            # handler that owns it (issue #95).
            step_outputs = {
                k: v for k, v in (corr_result.outputs or {}).items() if k != "artifacts"
            }
            if task_type == "data.analyze_failure":
                analysis_outputs = step_outputs
            elif task_type == "governance.correction_decision":
                decision_outputs = step_outputs

        # 4. Read correction_path — bounded by the deterministic policy guard
        # (#447): `continue` may not discard a required check that executed
        # and failed while this chain's repair slot is unspent. The model's
        # original rationale stays intact in the decision artifact; the
        # override is disclosed in the event payload below.
        from squadops.cycles.correction_policy import resolve_correction_path

        resolution = resolve_correction_path(
            decision_outputs.get("correction_path", "abort"),
            failure_evidence,
            cycle.applied_defaults,
            # pf-45: the rewind anchor keys on the analyzer's classification — a
            # work_product rewind dies as a run failure with the repair budget unspent,
            # so the guard substitutes the patch the classification says is possible.
            classification=str(analysis_outputs.get("classification", "")),
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

        # 7. Handle patch path: dispatch repair tasks
        # Repair-step selection is keyed on the failed task's task_type
        # (authoritative) rather than the LLM-emitted `affected_task_types`
        # field, which is free-text and previously caused builder failures
        # (`affected_task_types: ["QA Handoff"]`) to silently route to the
        # dev repair handler.
        #
        # #568: selection is additionally keyed on the deterministic failure
        # locus — a task whose OWN artifact is missing/uncollectable is repaired
        # by its own role re-producing that artifact (qa.test → qa.test_repair),
        # and the repair target is the failed task's own contract, not the
        # subject-implementation surface (_resolve_repair_target aims repairs at
        # the SUBJECT and would point a test re-author at app source files).
        repair_artifacts: list[dict[str, Any]] = []
        if correction_path == "patch":
            from squadops.capabilities.scaffold import testid_surface_instructions

            failed_inputs = envelope.inputs or {}
            testid_lines = testid_surface_instructions(interface_manifest)
            (
                failure_locus,
                repair_expected_artifacts,
                repair_focus,
                repair_description,
            ) = _locus_and_repair_target(envelope.task_type, failure_evidence, failed_inputs)

            for step_idx, (task_type, role) in enumerate(
                repair_steps_for(envelope.task_type, failure_locus)
            ):
                repair_task_id = f"repair-{run_id[:12]}-{correction_attempts:02d}-{task_type}"
                resolved = resolve_agent_config(role, profile)
                agent_id = resolved.agent_id
                agent_model = resolved.model
                agent_overrides = resolved.config_overrides

                # Plumb the (retargeted) task contract through to the repair
                # envelope. Without this the repair handler only sees the PRD +
                # failure evidence and produces a generic "repair_output.md" rather
                # than re-emitting the named artifact that must actually be fixed.
                repair_inputs: dict[str, Any] = {
                    "prd": cycle.prd_ref,
                    "failed_task_type": envelope.task_type,
                    "failure_evidence": failure_evidence,
                    "failure_analysis": analysis_outputs,
                    "correction_decision": decision_outputs,
                    "prior_outputs": prior_outputs,
                    "artifact_refs": list(all_artifact_refs),
                    "agent_model": agent_model,
                    "agent_config_overrides": agent_overrides,
                    # The repair handler's scaffold fill-only appendix gates on
                    # resolved_config.build_profile (is_scaffoldable_stack) — without
                    # this the gate sees an empty profile and silently no-ops, and
                    # repairs freely rewrite scaffold-owned interface (pf-30:
                    # attempts 1-3 re-emitted routes.py with relative decorator
                    # paths against a correct diagnosis). Mirrors the retest
                    # threading in reexecute_repaired_suite below.
                    "resolved_config": failed_inputs.get("resolved_config", {}),
                    "subtask_focus": repair_focus,
                    "subtask_description": repair_description,
                    "expected_artifacts": repair_expected_artifacts,
                    "acceptance_criteria": failed_inputs.get("acceptance_criteria", []),
                }
                # #667: the anchor surface must survive the correction loop —
                # fay-14's first fill complied with the manifest convention and
                # every repair regenerated the view blind, stripping the anchors.
                # Re-derived from the manifest (same deriver as initial dispatch)
                # rather than copied from the failed envelope: the dev repair
                # chain is routinely reached from a failed qa.test task (SUBJECT
                # locus), whose envelope carries only the qa-keyed variant. Both
                # keys ride every repair envelope; each handler reads its own.
                if testid_lines:
                    repair_inputs["testid_surface"] = testid_lines
                    repair_inputs["dom_testid_surface"] = testid_lines

                repair_envelope = TaskEnvelope(
                    task_id=repair_task_id,
                    agent_id=agent_id,
                    cycle_id=cycle.cycle_id,
                    pulse_id=uuid4().hex,
                    project_id=cycle.project_id,
                    task_type=task_type,
                    correlation_id=corr_correlation_id,
                    causation_id=envelope.task_id,
                    trace_id=uuid4().hex,
                    span_id=uuid4().hex,
                    inputs=repair_inputs,
                    metadata={"role": role, "step_index": step_idx},
                )

                # Dispatch the repair step (task_run creation + task events
                # live in _dispatch_protocol_step, SIP-0087 B2 — so
                # correction-driven repairs appear in the Prefect UI).
                repair_result = await self._dispatch_protocol_step(
                    repair_envelope,
                    run_id,
                    cycle,
                    flow_run_id,
                    prior_outputs=prior_outputs,
                    all_artifact_refs=all_artifact_refs,
                    stored_artifacts=stored_artifacts,
                    completed_task_ids=completed_task_ids,
                    plan_delta_refs=plan_delta_refs,
                    # 3.4b: repair emissions get the same frozen-ownership
                    # enforcement as regular storage (restore + carry signal).
                    bound_record=bound_record,
                    enforcement_carry=scaffold_enforcement_carry,
                )

                # Collect repair outputs under the role key, matching the
                # regular fan-in convention (summaries only — `artifacts` are
                # surfaced to the overlay below, not through prompt context).
                role_key = repair_envelope.metadata.get("role", "unknown")
                prior_outputs[role_key] = {
                    k: v for k, v in (repair_result.outputs or {}).items() if k != "artifacts"
                }

                # #389: surface the repair's emitted files to the executor for
                # behavioral patch verification.
                step_artifacts = (repair_result.outputs or {}).get("artifacts") or []
                # #507: re-home repair files onto the failed task's expected
                # paths before they reach the overlay — a repair emitted under
                # the wrong directory otherwise lands as a net-new file, patch
                # verification runs on the un-patched original, and the
                # validated repair is discarded by re-dispatch.
                from squadops.cycles.patch_verification import rebase_artifact_paths

                repair_artifacts.extend(
                    rebase_artifact_paths(
                        [a for a in step_artifacts if isinstance(a, dict)],
                        failed_inputs.get("expected_artifacts") or [],
                    )
                )

        # 8. Emit CORRECTION_COMPLETED
        self._event_bus.emit(
            EventType.CORRECTION_COMPLETED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload={"correction_path": correction_path},
        )

        return CorrectionProtocolResult(
            correction_path=correction_path, repair_artifacts=repair_artifacts
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
        retest_inputs: dict[str, Any] = {
            "prd": cycle.prd_ref,
            "resolved_config": failed_inputs.get("resolved_config", {}),
            "artifact_contents": failed_inputs.get("artifact_contents", {}),
            "retest_files": retest_files,
            "agent_model": resolved.model,
            "agent_config_overrides": resolved.config_overrides,
            "subtask_focus": failed_inputs.get("subtask_focus"),
            "expected_artifacts": failed_inputs.get("expected_artifacts", []),
            "acceptance_criteria": failed_inputs.get("acceptance_criteria", []),
        }
        # #639: probes ride the retest or the final verdict carries stale
        # probe evidence for a tree the repair changed. Presence-keyed, like
        # the bind-mode injection (probe-less contracts thread no key).
        if failed_inputs.get("contract_probes"):
            retest_inputs["contract_probes"] = failed_inputs["contract_probes"]
        # #643: same presence-keyed threading for the typed-acceptance
        # workspace — the retest's evaluation needs the scaffold siblings
        # exactly like the original dispatch did.
        if failed_inputs.get("acceptance_workspace_files"):
            retest_inputs["acceptance_workspace_files"] = failed_inputs[
                "acceptance_workspace_files"
            ]
        # #667: the retest re-dispatches qa.test, which re-authors the suite
        # from scratch (the fay-6 new-dice path) — without the anchor surface
        # the retest author works blind to the DOM contract the original
        # dispatch carried. Presence-keyed like the probes above.
        if failed_inputs.get("dom_testid_surface"):
            retest_inputs["dom_testid_surface"] = failed_inputs["dom_testid_surface"]

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
        )
