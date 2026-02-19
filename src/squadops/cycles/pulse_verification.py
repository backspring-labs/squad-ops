"""
Pulse verification runner (SIP-0070: Pulse Checks and Verification).

Standalone module called by the executor at pulse boundaries.
Evaluates bound suites, produces PulseVerificationRecord per suite,
and derives boundary-level PulseDecision from suite outcomes.

Executor owns dispatch timing; this module owns verification logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from squadops.capabilities.models import AcceptanceContext
from squadops.cycles.pulse_models import (
    PulseCheckDefinition,
    PulseDecision,
    PulseVerificationRecord,
    SuiteOutcome,
)
from squadops.tasks.models import TaskEnvelope

if TYPE_CHECKING:
    from squadops.capabilities.acceptance import AcceptanceCheckEngine

logger = logging.getLogger(__name__)


# =============================================================================
# Binding resolution
# =============================================================================


def resolve_milestone_bindings(
    pulse_checks: tuple[PulseCheckDefinition, ...],
    plan: list[TaskEnvelope],
) -> tuple[dict[int, list[PulseCheckDefinition]], list[PulseCheckDefinition]]:
    """Map plan index -> milestone-bound suites.

    For each milestone suite, resolves ``after_task_types`` via prefix matching:
    ``after_task_type`` ``'development'`` matches all tasks whose ``task_type``
    starts with ``'development.'`` (e.g., ``development.implement``,
    ``development.build``).

    Milestone boundary = the **last** plan index whose ``task_type``
    prefix-matches the bound family.  The emitted ``boundary_id`` is the
    suite's declared semantic label (e.g., ``'post_dev'``), NOT derived
    from the plan — the plan only determines *where* to fire.

    Returns:
        (bindings, unmatched):
        - bindings: ``dict[int, list[PulseCheckDefinition]]``
        - unmatched: suites whose ``after_task_types`` had no prefix match
    """
    milestone_suites = [s for s in pulse_checks if s.binding_mode == "milestone"]
    if not milestone_suites:
        return {}, []

    bindings: dict[int, list[PulseCheckDefinition]] = {}
    unmatched: list[PulseCheckDefinition] = []

    for suite in milestone_suites:
        # Find the last plan index whose task_type prefix-matches any after_task_type
        matched_index: int | None = None
        for prefix in suite.after_task_types:
            for idx, envelope in enumerate(plan):
                if envelope.task_type.startswith(prefix + "."):
                    if matched_index is None or idx > matched_index:
                        matched_index = idx
        if matched_index is not None:
            bindings.setdefault(matched_index, []).append(suite)
        else:
            unmatched.append(suite)

    return bindings, unmatched


def collect_cadence_bound_suites(
    pulse_checks: tuple[PulseCheckDefinition, ...],
) -> list[PulseCheckDefinition]:
    """Return suites with ``binding_mode='cadence'`` (heartbeat guardrails).

    These run at every cadence close regardless of boundary_id.
    """
    return [s for s in pulse_checks if s.binding_mode == "cadence"]


# =============================================================================
# Repair task builder (D17: exactly 4 steps in 0.9.9)
# =============================================================================

REPAIR_TASK_STEPS: list[tuple[str, str]] = [
    ("data.analyze_verification", "data"),
    ("governance.root_cause_analysis", "lead"),
    ("strategy.corrective_plan", "strat"),
    ("development.repair", "dev"),
]


def build_repair_task_envelopes(
    *,
    cycle_id: str,
    project_id: str,
    pulse_id: str,
    correlation_id: str,
    trace_id: str,
    causation_id: str,
    run_id: str,
    repair_attempt: int,
    boundary_id: str = "",
    cadence_interval_id: int = 0,
    failed_suite_ids: tuple[str, ...] = (),
    agent_resolver: dict[str, str] | None = None,
) -> list[TaskEnvelope]:
    """Build 4 repair envelopes sharing current trace/correlation context.

    Always exactly 4 steps per D17. Each envelope carries metadata
    identifying the repair chain, attempt number, and boundary context
    (boundary_id, cadence_interval_id, failed_suite_ids per D10).

    Args:
        cycle_id: Current cycle identifier.
        project_id: Current project identifier.
        pulse_id: Current pulse identifier (shared across repair chain).
        correlation_id: Shared correlation ID from the original plan.
        trace_id: Shared trace ID for LangFuse linking.
        causation_id: Task ID of the last completed task before repair.
        run_id: Current run identifier.
        repair_attempt: 1-based repair attempt number.
        boundary_id: Semantic boundary label (e.g. ``'post_dev'``).
        cadence_interval_id: Runtime cadence interval counter.
        failed_suite_ids: Suite IDs that triggered this repair chain.
        agent_resolver: Optional role→agent_id mapping. Defaults to role name.

    Returns:
        Ordered list of 4 TaskEnvelopes for the repair chain.
    """
    resolver = agent_resolver or {}
    envelopes: list[TaskEnvelope] = []
    prev_task_id: str | None = None

    for step_index, (task_type, role) in enumerate(REPAIR_TASK_STEPS):
        task_id = uuid4().hex
        span_id = uuid4().hex
        chain_causation = prev_task_id or causation_id

        envelope = TaskEnvelope(
            task_id=task_id,
            agent_id=resolver.get(role, role),
            cycle_id=cycle_id,
            pulse_id=pulse_id,
            project_id=project_id,
            task_type=task_type,
            correlation_id=correlation_id,
            causation_id=chain_causation,
            trace_id=trace_id,
            span_id=span_id,
            inputs={},
            metadata={
                "step_index": step_index,
                "role": role,
                "repair_attempt": repair_attempt,
                "repair_chain": True,
                "boundary_id": boundary_id,
                "cadence_interval_id": cadence_interval_id,
                "failed_suite_ids": list(failed_suite_ids),
            },
        )
        envelopes.append(envelope)
        prev_task_id = task_id

    return envelopes


# =============================================================================
# Verification execution
# =============================================================================


async def run_pulse_verification(
    suites: list[PulseCheckDefinition],
    context: AcceptanceContext,
    engine: AcceptanceCheckEngine,
    boundary_id: str,
    cadence_interval_id: int,
    run_id: str,
    repair_attempt_number: int = 0,
) -> list[PulseVerificationRecord]:
    """Execute all bound suites at a pulse boundary.

    Returns one ``PulseVerificationRecord`` per suite.  Each record carries
    ``suite_id``, ``boundary_id`` (semantic), ``cadence_interval_id``
    (runtime), and ``suite_outcome`` (SuiteOutcome).  No boundary-level
    decision on records — that is derived by ``determine_boundary_decision()``.
    """
    records: list[PulseVerificationRecord] = []

    for suite in suites:
        report = await engine.evaluate_all_async(
            suite.checks,
            context,
            max_suite_seconds=suite.max_suite_seconds,
            max_check_seconds=suite.max_check_seconds,
        )

        # Derive suite outcome from check results
        if report.all_passed:
            outcome = SuiteOutcome.PASS
        else:
            outcome = SuiteOutcome.FAIL

        # Serialize check results for record
        check_results: list[dict] = []
        for r in report.results:
            entry: dict = {
                "check_type": r.check.check_type.value,
                "target": r.resolved_path,
                "passed": r.passed,
            }
            if r.error:
                entry["error"] = r.error
            if r.reason_code:
                entry["reason_code"] = r.reason_code
            if r.metadata:
                entry["metadata"] = r.metadata
            check_results.append(entry)

        record = PulseVerificationRecord(
            suite_id=suite.suite_id,
            boundary_id=boundary_id,
            cadence_interval_id=cadence_interval_id,
            run_id=run_id,
            suite_outcome=outcome,
            check_results=tuple(check_results),
            repair_attempt_number=repair_attempt_number,
        )
        records.append(record)

    return records


# =============================================================================
# Boundary decision
# =============================================================================


def determine_boundary_decision(
    records: list[PulseVerificationRecord],
) -> PulseDecision:
    """Derive boundary-level decision from per-suite outcomes.

    - PASS if all ``suite_outcome == PASS``
    - FAIL if any ``suite_outcome == FAIL``
    - SKIP-only records → PASS (no guardrail evidence to block)

    EXHAUSTED is set by the caller when repair attempts are exhausted,
    not derived here.
    """
    if not records:
        return PulseDecision.PASS

    has_fail = any(r.suite_outcome == SuiteOutcome.FAIL for r in records)
    if has_fail:
        return PulseDecision.FAIL

    return PulseDecision.PASS
