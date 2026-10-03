"""The framing gate's plan check — #1507 step 1 (docs/plans/1-9-0-completion-boundary-map.md).

The inter-workload gate's plan validation, moved out of ``DispatchedFlowExecutor`` as found: a
different reason to change (framing-gate policy) from the run spine it sat in. The executor keeps
``_reject_invalid_plan_before_workload_gate`` as a one-line delegate, so its call site and every
test that calls it are unchanged.

What it borrows it borrows late (defended-bespoke-decisions §38): the artifact vault and the three
loaders it shares with ``execute_run`` and the dispatch-time net stay on the executor and are read
through lambdas, so a test that replaces one after construction is still the one this calls. The
body below reads those under the executor's own names, which is why it moved byte for byte.

The decisions it carries are §47–§52 of the same register.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from squadops.cycles.contract_derivation import CONTRACT_ARTIFACT_TYPE, SEEDED_MANIFEST_FILENAME
from squadops.cycles.frozen_check_validation import frozen_check_violations
from squadops.cycles.manifest_authoring import MANIFEST_ARTIFACT_TYPE
from squadops.cycles.models import PLAN_JUDGED_WORKLOADS, ArtifactRef, Cycle
from squadops.cycles.rejection_baseline import (
    REJECTION_ARTIFACT_TYPE,
    REJECTION_FILENAME,
    RejectionClassifier,
)

logger = logging.getLogger(__name__)


class FramingGateCheck:
    """Validates the plan a completed framing run authored, before the gate promotes it."""

    def __init__(
        self,
        *,
        artifact_vault: Callable[[], Any],
        is_bind_mode: Callable[..., bool],
        load_seeded_manifest_content: Callable[..., Any],
        load_contract_for_run: Callable[..., Any],
    ) -> None:
        self._vault = artifact_vault
        self._is_bind_mode = is_bind_mode
        self._load_seeded_manifest_content = load_seeded_manifest_content
        self._load_contract_for_run = load_contract_for_run

    @property
    def _artifact_vault(self) -> Any:
        return self._vault()

    async def reject_invalid_plan_before_workload_gate(
        self,
        run: Any,
        cycle: Cycle,
        gate_name: str,
    ) -> list[str]:
        """#464: criteria-scope validation at the inter-workload plan gate.

        This is the gate path multi-workload cycles actually traverse (the
        framing run COMPLETES, then the sequence gates) — the mid-run
        ``_reject_unsatisfiable_plan_at_gate`` never fires here. Searches the
        completed run's artifacts for the authored plan; validation errors
        are RETURNED (#473) so the caller records a system REJECTED gate
        decision instead of the orchestrator dying silently (the 3.13
        stall). Role validation is not duplicated at this seam: it keeps its
        dispatch-time net in ``generate_task_plan``. Absent or unreadable
        plans defer to that same net — this check only ever adds an earlier
        rejection, never a pass.

        OWNERSHIP (#663 D5): this seam and ``_reject_unsatisfiable_plan_at_gate``
        are deliberately SEPARATE nets with different error channels — they are
        plan VALIDATION, not context assembly, and merging them would conflate
        #473's returns-vs-raises semantics. This one owns the inter-workload
        promotion decision: errors return, the caller records a system REJECTED
        gate decision, and the framing re-rolls for free. The other owns in-run
        dispatch admission and raises. A new plan-validation rule must pick its
        net by WHERE the reject must land (recorded re-roll vs run failure) —
        landing a rule on only one seam when both apply is the #718/#719 scar.
        Both call sites are pinned by
        ``tests/unit/cycles/test_plan_gate_seams.py``.
        """
        if not cycle.resolved_config().get("implementation_plan", False):
            return []
        # #1864: only a run whose gate judges the plan is judged by it. A proposal run at the
        # increment gate authors a change request, and would always read as a collapsed framing.
        if getattr(run, "workload_type", None) not in PLAN_JUDGED_WORKLOADS:
            return []

        from squadops.cycles.implementation_plan import ImplementationPlan

        errors: list[str] = []
        interface_content: str | None = None
        parsed_plan: ImplementationPlan | None = None
        plan_artifact_seen = False  # #424: exists-but-unreadable ≠ absent
        # #796: an authored cycle's contract was derived DURING this run, so it lives on the
        # run's refs rather than in execution_overrides. Without this the bind-mode nets —
        # frozen-artifact ownership, qa ownership, module existence, criteria binding — stay
        # switched off for exactly the plans that need them most (V4 roll 1: four tasks
        # claimed scaffold-frozen files and nothing caught it).
        run_contract_ref: str | None = None
        # B1 (#809): which validator rejected, recorded where it is known. The gate calls its
        # validators one at a time, so no signature changes and no prose to parse back — the
        # names are the same vocabulary the authoring-rules asset teaches.
        classifier = RejectionClassifier()
        contract = None  # set in bind mode below; feeds the soft-violation log
        for ref_id in tuple(run.artifact_refs or ()):
            try:
                ref, content_bytes = await self._artifact_vault.retrieve(ref_id)
            except Exception:
                continue
            artifact_type = getattr(ref, "artifact_type", None)
            if ref.filename == "implementation_plan.yaml" or (
                artifact_type == "control_implementation_plan"
            ):
                plan_artifact_seen = True
                try:
                    parsed_plan = ImplementationPlan.from_yaml(
                        content_bytes.decode(errors="replace")
                    )
                except Exception:
                    logger.warning(
                        "Plan artifact %s unreadable before gate %r — deferring to the "
                        "dispatch-time validation net",
                        ref_id,
                        gate_name,
                        exc_info=True,
                    )
                else:
                    errors.extend(
                        classifier.collect(
                            "validate_criteria_scope", parsed_plan.validate_criteria_scope()
                        )
                    )
                    # #645: contract-independent winnability nets — an
                    # unexecutable command check or a directory-shaped
                    # expected artifact dooms the roll deterministically;
                    # both are provable here in microseconds, and a system
                    # rejection re-rolls framing for free where a human
                    # rejection would end the cycle (#522).
                    errors.extend(
                        classifier.collect(
                            "validate_command_checks", parsed_plan.validate_command_checks()
                        )
                    )
                    errors.extend(
                        classifier.collect(
                            "validate_expected_artifact_shapes",
                            parsed_plan.validate_expected_artifact_shapes(),
                        )
                    )
                    # #673: a dual-claimed expected artifact aliases two tasks
                    # onto one file's fate (repair mis-scoping, last-wins
                    # emission) — provable plan-wide right here, and a system
                    # rejection re-rolls framing for free (#522).
                    errors.extend(
                        classifier.collect(
                            "validate_unique_expected_artifacts",
                            parsed_plan.validate_unique_expected_artifacts(),
                        )
                    )
                    # #1912: a qa.test task that declares no suite fails whatever it
                    # returns and ends the run blocked_unverified; a re-roll is free here.
                    errors.extend(
                        classifier.collect(
                            "validate_qa_tasks_author_a_suite",
                            parsed_plan.validate_qa_tasks_author_a_suite(),
                        )
                    )
                    # #715: a qa.test task whose declared artifacts can never
                    # satisfy required tests_pass fails on any content — shk-4
                    # burned three correction rounds on one. #426: builder
                    # tasks without a configured build_profile die at the #291
                    # dispatch guard — this seam (the one multi-workload
                    # cycles actually traverse) rejects both for a free
                    # framing re-roll.
                    errors.extend(
                        classifier.collect(
                            "validate_check_applicability",
                            parsed_plan.validate_check_applicability(cycle.resolved_config()),
                        )
                    )
                    # #1587: collected is not owned — the suite must sit where the stack
                    # says qa's files live, or nothing downstream treats it as qa's.
                    errors.extend(
                        classifier.collect(
                            "validate_qa_suite_namespace",
                            parsed_plan.validate_qa_suite_namespace(cycle.resolved_config()),
                        )
                    )
                    errors.extend(
                        classifier.collect(
                            "validate_build_config",
                            parsed_plan.validate_build_config(cycle.resolved_config()),
                        )
                    )
                    # Roll 15: a plan whose builder task under-covers the build
                    # profile's required_files converges its whole suite and then
                    # dies at the #291 completion gate — which has no repair path
                    # and no incomplete builder task left on resume. Provable
                    # here; rejection re-rolls framing for free.
                    errors.extend(
                        classifier.collect(
                            "validate_builder_floor",
                            parsed_plan.validate_builder_floor(cycle.resolved_config()),
                        )
                    )
            elif (
                ref.filename == SEEDED_MANIFEST_FILENAME or artifact_type == MANIFEST_ARTIFACT_TYPE
            ):
                interface_content = content_bytes.decode(errors="replace")
            elif artifact_type == CONTRACT_ARTIFACT_TYPE:
                run_contract_ref = ref_id

        # #424: this seam's precondition is implementation_plan=true, so a
        # COMPLETED framing run with no plan artifact at all means plan
        # authoring collapsed (manifest exhaustion / artifact lost) — the
        # profile's instrument does not exist, and letting the gate approve
        # spends a full implementation run to be caught by the SIP-0096
        # throttle at the very end. Reject here, where a re-roll costs
        # minutes; generate_task_plan's dispatch net is the raising backstop.
        # An unreadable plan (parse failure above) still defers — that
        # artifact exists and the dispatch net gives it a full diagnosis.
        if not plan_artifact_seen:
            errors.append(
                "plan_authoring_collapsed: this framing run produced no "
                "implementation_plan artifact, but the profile's instrumentation "
                "contract (typed_acceptance/implementation_plan) lives in the "
                "authored plan — re-roll framing rather than running "
                "uninstrumented."
            )

        # A framing-authored interface manifest is validated here — this is
        # its ONLY net; generate_task_plan's dispatch-time net validates the PLAN, never
        # the manifest. Errors join the same returned list, so they flow into the
        # identical system:plan_validation REJECTED recording.
        # Absent manifest → no-op = today's behavior (byte-identical for plan-only cycles).
        if interface_content is not None:
            errors.extend(self._validate_interface_manifest(interface_content, classifier))

        # #1013: manifest↔plan consistency + completeness — the two framing-internal
        # species that cost V38 counted rolls (roll 1's 201-vs-200 contradiction; slot
        # 6's manifest-only 201 the plan never stated). Needs BOTH artifacts, so it
        # runs after the collection loop; an unparseable manifest defers exactly like
        # an unreadable plan does (this check only ever adds an earlier rejection,
        # never a pass). Lands on THIS seam deliberately: the reject must re-roll
        # framing for free, not fail a run at dispatch (see the ownership note above).
        if interface_content is not None and parsed_plan is not None:
            try:
                from squadops.capabilities.scaffold import InterfaceManifest

                parsed_manifest = InterfaceManifest.from_yaml(interface_content)
            except Exception:
                logger.warning(
                    "Manifest unparseable before gate %r — #1013 consistency check "
                    "deferred to the manifest's own validation net",
                    gate_name,
                    exc_info=True,
                )
            else:
                errors.extend(
                    classifier.collect(
                        "validate_manifest_plan_consistency",
                        parsed_plan.validate_manifest_plan_consistency(parsed_manifest),
                    )
                )

        # SIP-0109 §7.3 (#1705 d): an increment's plan covers only its approved change. Its
        # candidate manifest is seeded (bind mode), so it is read from the cycle, not the run.
        # Only this seam: the plan is fixed once the gate promotes it, and a rejection here
        # re-rolls framing with the reason as authoring context (#669).
        if parsed_plan is not None:
            errors.extend(
                classifier.collect(
                    "validate_increment_footprint",
                    parsed_plan.validate_increment_footprint(
                        await self._increment_footprint(cycle, interface_content)
                    ),
                )
            )
            # SIP-0109 §8.1, §19 item 12e: no task writes an earlier criterion's frozen file.
            errors.extend(
                classifier.collect(
                    "validate_increment_frozen_files",
                    parsed_plan.validate_increment_frozen_files(
                        await self._increment_frozen_files(cycle)
                    ),
                )
            )
            # SIP-0109 §8.1: each new criterion's own test file is written by a qa task.
            errors.extend(
                classifier.collect(
                    "validate_increment_criterion_files",
                    parsed_plan.validate_increment_criterion_files(
                        await self._increment_criterion_files(cycle)
                    ),
                )
            )

        # SIP-0098 98.3: bind-mode contract validation. A seeded contract_ref switches the
        # cycle to bind mode — the plan must bind the contract's covered-file criteria by
        # id (validate_criteria_refs) rather than author them, and the contract must be
        # bound to this run's skeleton (hash check). A seeded-but-unparseable contract is
        # a hard rejection, never a silent fall-through to author mode (§10). Errors join
        # the same returned list → identical system:plan_validation REJECTED recording.
        # Contract absent (author mode) → no-op = today's behavior.
        if self._is_bind_mode(cycle) or run_contract_ref is not None:
            # #494/#496: the contract binds to a skeleton, so bind mode REQUIRES an
            # interface manifest — without one, no skeleton is expanded at the
            # implementation run and contract checks would measure from-scratch code
            # (the §10 stale-binding class through the front door). In bind mode the
            # manifest is normally operator-SEEDED via plan_artifact_refs (#496 —
            # framing cannot re-derive it from a product-only PRD without hash
            # drift; emission is author-mode only). A framing-emitted manifest, if
            # one appears anyway, still takes precedence and is still hash-checked.
            seeded_content: str | None = None
            if interface_content is None:
                seeded_content = await self._load_seeded_manifest_content(cycle)
            if interface_content is None and seeded_content is None:
                errors.append(
                    "verification_contract: bind mode requires an interface manifest "
                    "and none exists — this run emitted none and no seeded "
                    "interface_manifest.yaml is present in plan_artifact_refs; the "
                    "contract binds to a skeleton, and without a manifest the "
                    "implementation would run unscaffolded while claiming contract "
                    "verification (#494, #496)"
                )
            contract = await self._load_contract_for_run(cycle, run, ref=run_contract_ref)
            if contract is None:
                errors.append(
                    "verification_contract: contract_ref is seeded but the contract is "
                    "missing or unparseable — bind mode cannot validate the plan"
                )
            else:
                binding_content = (
                    interface_content if interface_content is not None else (seeded_content)
                )
                if binding_content is not None:
                    errors.extend(self._validate_contract_binding(contract, binding_content))
                if parsed_plan is not None:
                    # #509: bind the contract's covered-file criteria
                    # deterministically BEFORE validating — the descoping rule
                    # then guards against binding bugs instead of taxing every
                    # roll on the author's transcription. Dispatch applies the
                    # same normalization (generate_task_plan), so the validated
                    # plan and the executed plan cannot drift.
                    parsed_plan, auto_bound = parsed_plan.with_contract_criteria_bound(contract)
                    for note in auto_bound:
                        logger.info("criteria_auto_bound (gate %s): %s", gate_name, note)
                    # SIP-0108 §4.2: each bind-mode validator is classified under its own
                    # name, as the author-mode ones above are — the refusal is read by
                    # which validators refused, never by parsing this prefix back.
                    errors.extend(
                        classifier.collect(
                            "validate_criteria_refs",
                            [
                                f"verification_contract: {e}"
                                for e in parsed_plan.validate_criteria_refs(contract)
                            ],
                        )
                    )
                    errors.extend(
                        classifier.collect(
                            "validate_qa_artifact_ownership",
                            [
                                f"verification_contract: {e}"
                                for e in parsed_plan.validate_qa_artifact_ownership(contract)
                            ],
                        )
                    )
                    errors.extend(
                        classifier.collect(
                            "validate_frozen_artifact_ownership",
                            [
                                f"verification_contract: {e}"
                                for e in parsed_plan.validate_frozen_artifact_ownership(contract)
                            ],
                        )
                    )
                    # #671: import_present against a module the closed scaffold
                    # surface cannot provide is provably unwinnable here, in
                    # microseconds — a system rejection re-rolls framing for
                    # free where the doomed roll would burn its correction
                    # budget (#522).
                    errors.extend(
                        classifier.collect(
                            "validate_module_existence",
                            [
                                f"verification_contract: {e}"
                                for e in parsed_plan.validate_module_existence(contract)
                            ],
                        )
                    )
                    # pf-42: a typed check aimed at a frozen file is decidable right
                    # now — the skeleton those files will contain is deterministic.
                    # A failing one makes the plan unwinnable (frozen emissions are
                    # restored, so the repair loop can never converge), and it costs
                    # milliseconds to prove instead of a three-hour roll.
                    if binding_content is not None:
                        errors.extend(
                            f"verification_contract: {e}"
                            for e in await frozen_check_violations(
                                parsed_plan, contract, binding_content
                            )
                        )

        # Soft (warning/info-severity) structural violations are tolerated, not
        # rejected — but logged so the pass is never silent (a warning check can't
        # block a build per RC-9, so it must not kill the cycle at plan validation).
        if parsed_plan is not None:
            # #1254: reported beside the tolerated criteria, never fatal — the rule is
            # taught in the vocabulary and enforced by the dispatch strip; a framing
            # re-roll for a row dispatch drops would cost half an hour for nothing.
            soft = parsed_plan.soft_criteria_violations(contract) + [
                f"tolerated (derived): {note}" for note in parsed_plan.validate_derived_criteria()
            ]
            if soft:
                logger.warning(
                    "Plan for gate %r on run %s: tolerated %d soft criteria "
                    "violation(s) (warning/info severity — not rejecting): %s",
                    gate_name,
                    run.run_id,
                    len(soft),
                    "; ".join(soft),
                )
        await self._store_rejection_record(run, cycle, gate_name, classifier, errors)
        return errors

    async def _store_rejection_record(
        self,
        run: Any,
        cycle: Any,
        gate_name: str,
        classifier: Any,
        errors: list[str],
    ) -> None:
        """Persist which classes rejected this plan (#809, B1).

        Written at the moment of rejection because that is the only moment the producing
        validator is known without parsing prose back out of a joined error string. Nothing
        in 1.6 reads it — the pre-memory baseline is unrecoverable once Cross-Cycle Memory
        exists, so it is captured now and aggregated whenever the window is scored.

        Never raises. A baseline is a record, not a gate: losing one cycle's bookkeeping is a
        gap in a dataset, while failing the rejection path would turn it into a lost cycle.
        """
        payload = classifier.record(gate_name, errors)
        if not payload:
            return
        content = json.dumps(payload, indent=2).encode("utf-8")
        try:
            await self._artifact_vault.store(
                ArtifactRef(
                    artifact_id=f"art_{uuid4().hex[:12]}",
                    project_id=cycle.project_id,
                    artifact_type=REJECTION_ARTIFACT_TYPE,
                    filename=REJECTION_FILENAME,
                    content_hash=sha256(content).hexdigest(),
                    size_bytes=len(content),
                    media_type="application/json",
                    created_at=datetime.now(UTC),
                    cycle_id=cycle.cycle_id,
                    run_id=run.run_id,
                ),
                content,
            )
        except Exception:
            logger.warning(
                "Could not store the rejection record for run %s; the baseline loses this "
                "cycle's plan-validation classes",
                run.run_id,
                exc_info=True,
            )

    @staticmethod
    def _validate_contract_binding(contract: Any, interface_content: str) -> list[str]:
        """§10 decision — FAIL on interface-manifest hash mismatch.

        A contract binds to the exact skeleton it was authored against via
        ``skeleton.interface_manifest_hash``. If the run's manifest hashes to
        something else, the contract measures a different skeleton's fill against
        the wrong criteria (the stale-evidence-after-mutation class) — a hard
        rejection, not a warning read once and ignored. The manifest's own parse
        failures are already reported by ``_validate_interface_manifest``; here a
        parse failure is a no-op to avoid a duplicate rejection."""
        from squadops.capabilities.scaffold import InterfaceManifest

        try:
            manifest = InterfaceManifest.from_yaml(interface_content)
        except Exception:  # noqa: BLE001 — parse failure already surfaced elsewhere
            return []
        actual = manifest.content_hash()
        expected = contract.skeleton.interface_manifest_hash
        if actual != expected:
            return [
                f"contract bound to interface_manifest_hash {expected[:12]}… but the run's "
                f"manifest hashes to {actual[:12]}… — the contract was authored against a "
                f"different skeleton (stale binding, rejected)"
            ]
        return []

    @staticmethod
    def _validate_interface_manifest(
        content: str, classifier: RejectionClassifier | None = None
    ) -> list[str]:
        """Run both manifest gates over a framing-emitted manifest, returning errors
        prefixed for the REJECTED gate note.

        #791 (M1) widened this from ``lint()`` alone to the full M2/M3 assessment: the
        authoring stage runs the same two gates in-stage, and a manifest that exhausts
        its revision budget is emitted anyway (see ``DevelopmentAuthorManifestHandler``)
        precisely so this seam can reject it — a system rejection re-rolls framing for
        free (#522), where letting it through spends a whole implementation workload on a
        design already proven unwinnable.

        Only a *framing-emitted* manifest reaches here — the scan reads ``run.artifact_refs``,
        and a seeded manifest lives on the cycle's ``plan_artifact_refs`` rail — so bind-mode
        cycles are unaffected by the widening.

        The gate note is prose for the operator. The failed proofs are also recorded as values
        on ``classifier`` (SIP-0108 §4.2) — the blocking ones, since an advisory proof refuses
        nothing — so the refusal is read by which proofs failed, never by parsing this note.
        """
        from squadops.cycles.authoring_failure import assess_authoring_outcome

        outcome = assess_authoring_outcome(content)
        if not outcome.rejected:
            return []
        if classifier is not None:
            classifier.collect_proofs(f.proof for f in outcome.blocking_findings)
        logger.info("interface_manifest rejected at gate: classes=%s", outcome.class_counts())
        return [f"interface_manifest [{f.proof}]: {f.detail}" for f in outcome.findings]

    async def _increment_frozen_files(self, cycle: Cycle) -> tuple[tuple[str, str], ...]:
        """The frozen criteria files the plan may not write (§8.1): the launch's pins, less what
        the approved change retires. ``()`` for any other cycle; never raises (#473)."""
        from squadops.campaigns.increment_tree import (
            approved_change_request,
            increment_frozen_files,
        )

        try:
            document = await approved_change_request(self._artifact_vault, cycle)
            return increment_frozen_files(cycle.resolved_config(), document)
        except Exception:
            logger.warning(
                "increment frozen files unreadable for cycle %s; the rule is skipped",
                cycle.cycle_id,
                exc_info=True,
            )
            return ()

    async def _increment_criterion_files(self, cycle: Cycle) -> tuple[Any, ...]:
        """The increment's new criteria and their own test files, from the approved change
        request the run was forwarded; ``()`` for any other cycle. The gate never raises
        (#473): a framing run without its change request could not have been provisioned, so
        an unreadable one here is logged and the rule skipped."""
        from squadops.campaigns.increment_tree import (
            approved_change_request,
            increment_criterion_files,
        )
        from squadops.capabilities.scaffold import scaffold_stack_for

        try:
            document = await approved_change_request(self._artifact_vault, cycle)
            if document is None:
                return ()
            return increment_criterion_files(document, scaffold_stack_for(cycle.resolved_config()))
        except Exception:
            logger.warning(
                "increment criterion files unreadable for cycle %s; the rule is skipped",
                cycle.cycle_id,
                exc_info=True,
            )
            return ()

    async def _increment_footprint(self, cycle: Cycle, run_manifest: str | None) -> Any:
        """The increment's footprint, or ``None`` for a cycle that is not an increment (or
        whose candidate manifest cannot be read, which the manifest's own nets report)."""
        from squadops.campaigns.increment_tree import increment_baseline, increment_footprint
        from squadops.capabilities.scaffold import InterfaceManifest

        if increment_baseline(cycle.resolved_config()) is None:
            return None
        content = run_manifest or await self._load_seeded_manifest_content(cycle)
        if not content:
            return None
        try:
            return increment_footprint(
                cycle.resolved_config(), InterfaceManifest.from_yaml(content)
            )
        except Exception:
            # The gate never raises (#473). An unreadable manifest is reported by its own nets.
            logger.warning(
                "increment footprint unreadable for cycle %s; the footprint rule is skipped",
                cycle.cycle_id,
                exc_info=True,
            )
            return None
