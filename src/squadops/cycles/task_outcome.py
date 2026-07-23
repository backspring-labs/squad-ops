"""Structured task outcome classification and failure taxonomy (SIP-0079 §7.3, §7.7).

Constants classes for routing task results to retry, correction, or escalation.
Follows the WorkloadType / ArtifactType / EventType constants-class pattern (not enum).
"""

from __future__ import annotations


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


# Reason code -> corrective disposition. The producer-fault codes are correctable; the
# integrity fault is a system fault that STOPS the attempt (plan D4 / review #16). Only this
# code's action halts the attempt — that separation is the point of the taxonomy.
CONTRACT_COMPLIANCE_ACTIONS: dict[str, str] = {
    ContractComplianceViolation.FROZEN_PATH_EMISSION: "reject_and_use_slots",
    ContractComplianceViolation.UNAUTHORIZED_SLOT_EMISSION: "reject_and_route_to_owner",
    ContractComplianceViolation.UNDECLARED_PATH_EMISSION: "reject_and_update_plan",
    ContractComplianceViolation.POST_WRITE_INTEGRITY_FAULT: "restore_and_stop_attempt",
}
