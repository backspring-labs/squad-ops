"""Repair handlers for correction protocol (SIP-0079 §7.7).

Thin subclasses of _CycleTaskHandler that handle the repair phase
of the correction protocol: development.repair (dev) and
qa.validate_repair (qa).
"""

from __future__ import annotations

from squadops.capabilities.handlers.cycle_tasks import _CycleTaskHandler


class DevelopmentRepairHandler(_CycleTaskHandler):
    """Repair handler: applies fixes based on failure analysis."""

    _handler_name = "development_repair_handler"
    _capability_id = "development.repair"
    _role = "dev"
    _artifact_name = "repair_output.md"


class QAValidateRepairHandler(_CycleTaskHandler):
    """Validate repair handler: verifies the repair was successful."""

    _handler_name = "qa_validate_repair_handler"
    _capability_id = "qa.validate_repair"
    _role = "qa"
    _artifact_name = "repair_validation.md"
