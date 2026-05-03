"""Repair handlers for the SIP-0079 correction protocol.

Thin subclasses of _CycleTaskHandler used by REPAIR_TASK_STEPS in
cycles/task_plan.py: development.correction_repair (dev) and
qa.validate_repair (qa).

Issue #100: this file used to define a `DevelopmentRepairHandler` with
`_capability_id = "development.repair"`. That collided with the SIP-0070
pulse-check `DevelopmentRepairHandler` in handlers/repair_tasks.py. The
correction-loop variant is now `DevelopmentCorrectionRepairHandler` with
`_capability_id = "development.correction_repair"` so the pulse-check and
correction-loop flows have distinct, non-overlapping capability ids.
"""

from __future__ import annotations

from squadops.capabilities.handlers.cycle_tasks import _CycleTaskHandler


class DevelopmentCorrectionRepairHandler(_CycleTaskHandler):
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


class QAValidateRepairHandler(_CycleTaskHandler):
    """Validate repair handler: verifies the repair was successful."""

    _handler_name = "qa_validate_repair_handler"
    _capability_id = "qa.validate_repair"
    _role = "qa"
    _artifact_name = "repair_validation.md"
