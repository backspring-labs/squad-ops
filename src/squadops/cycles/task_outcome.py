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
