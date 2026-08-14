"""Structured task outcome classification and failure taxonomy (SIP-0079 §7.3, §7.7).

Constants classes for routing task results to retry, correction, or escalation.
Follows the WorkloadType / ArtifactType / EventType constants-class pattern (not enum).
"""

from __future__ import annotations

from dataclasses import dataclass


class TaskOutcome:
    """Structured outcome classification for task results.

    Used by the executor to route recovery: retry for mechanical failures,
    correction protocol for semantic failures, pause for blocked tasks.
    """

    SUCCESS = "success"
    RETRYABLE_FAILURE = "retryable_failure"
    SEMANTIC_FAILURE = "semantic_failure"
    BLOCKED = "blocked"
    NEEDS_REPAIR = "needs_repair"
    NEEDS_REPLAN = "needs_replan"


class FailureClassification:
    """Failure taxonomy for correction protocol RCA (SIP-0079 §7.7).

    Used by DataAnalyzeFailureHandler to classify the root cause
    of a task or pulse check failure.
    """

    EXECUTION = "execution"
    WORK_PRODUCT = "work_product"
    ALIGNMENT = "alignment"
    DECISION = "decision"
    MODEL_LIMITATION = "model_limitation"
    # SIP-0100: a producer response that violates scaffold write-ownership. This is a malformed
    # correction, NOT an implementation defect — routed to a targeted correction and a separate
    # bounded compliance counter (plan D6), never the convergence counter.
    CONTRACT_COMPLIANCE = "contract_compliance"


class ContractComplianceViolation:
    """SIP-0100 scaffold write-authority violation reason codes (plan Task 0.5 / review #15).

    Distinct codes because each has a distinct corrective action (``CONTRACT_COMPLIANCE_ACTIONS``);
    they share the ``FailureClassification.CONTRACT_COMPLIANCE`` family but must never collapse
    into one correction message. Constants-class pattern (not enum), like ``TaskOutcome``.
    """

    # Producer emitted a scaffold-owned frozen path.
    FROZEN_PATH_EMISSION = "frozen_path_emission"
    # Path is writable in principle but outside THIS producer's grant.
    UNAUTHORIZED_SLOT_EMISSION = "unauthorized_slot_emission"
    # Path is neither frozen nor in any declared writable surface.
    UNDECLARED_PATH_EMISSION = "undeclared_path_emission"
    # Frozen bytes changed AFTER materialization despite no accepted frozen emission — a system
    # enforcement fault (bypass / concurrent writer / bug), NOT producer misconduct (plan D4).
    POST_WRITE_INTEGRITY_FAULT = "post_write_integrity_fault"
    # SIP-0104 P4: an emission to a verification-scaffold shell that mutates its frozen
    # spine or slot structure (moved/nested/duplicated markers, edited imports/invocation/
    # status assertion). The adversarial class the region canonicalization exists to catch.
    SCAFFOLD_REGION_VIOLATION = "scaffold_region_violation"
    # SIP-0104 P4: a shell emission whose spine is intact but whose slot BODY smuggles
    # prohibited content (imports, require(), live-server access). Correctable by the fill
    # author — SIP §5's prohibited-fill class, distinct from the adversarial one above.
    PROHIBITED_FILL_EMISSION = "prohibited_fill_emission"


# Reason code -> corrective disposition. The producer-fault codes are correctable; the
# integrity fault is a system fault that STOPS the attempt (plan D4 / review #16). Only this
# code's action halts the attempt — that separation is the point of the taxonomy.
CONTRACT_COMPLIANCE_ACTIONS: dict[str, str] = {
    ContractComplianceViolation.FROZEN_PATH_EMISSION: "reject_and_use_slots",
    ContractComplianceViolation.UNAUTHORIZED_SLOT_EMISSION: "reject_and_route_to_owner",
    ContractComplianceViolation.UNDECLARED_PATH_EMISSION: "reject_and_update_plan",
    ContractComplianceViolation.POST_WRITE_INTEGRITY_FAULT: "restore_and_stop_attempt",
    ContractComplianceViolation.SCAFFOLD_REGION_VIOLATION: "reject_and_edit_slot_bodies_only",
    ContractComplianceViolation.PROHIBITED_FILL_EMISSION: "reject_and_fix_fill_content",
}


class CorrectionTerminationReason:
    """Why a correction chain stopped (1.5 A4; the #557 SIP and the exhaustion
    path adopt the rest of this vocabulary later — only ``PLAN_DEFECT`` is
    produced by the A4 lever). Constants-class pattern, like ``TaskOutcome``."""

    PLAN_DEFECT = "plan_defect"
    EXHAUSTED = "exhausted"
    CONVERGED = "converged"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"


@dataclass(frozen=True)
class CorrectionTermination:
    """The typed record of a correction chain's early termination (1.5 A4).

    Persisted as a ``correction_termination`` artifact on the run and named in
    the run's ``failure_reason`` (#427), so wrap-up (#683), replay, and the
    operator all read the same structured answer to "why did correction stop?".
    Owned here beside the SIP-0079 §7.7 vocabulary it extends. It does not
    alter cycle status — the run fails through the normal path.
    """

    reason: str  # CorrectionTerminationReason value
    failed_task_id: str
    repeated_signature: tuple[str, ...]
    structural_candidate: str
    first_seen_round: int
    terminal_round: int
    supporting_artifact_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "reason": self.reason,
            "failed_task_id": self.failed_task_id,
            "repeated_signature": list(self.repeated_signature),
            "structural_candidate": self.structural_candidate,
            "first_seen_round": self.first_seen_round,
            "terminal_round": self.terminal_round,
            "supporting_artifact_ids": list(self.supporting_artifact_ids),
        }
