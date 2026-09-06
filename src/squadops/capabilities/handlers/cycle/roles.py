"""Thin role handlers: strategy, development design, QA validation, data report.
Split from cycle_tasks.py (#152).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from squadops.tasks.task_types import TaskType

if TYPE_CHECKING:
    pass

from squadops.capabilities.handlers.cycle.base import _CycleTaskHandler

logger = logging.getLogger(__name__)


class StrategyAnalyzeHandler(_CycleTaskHandler):
    """Cycle task handler for strategy analysis (strat role)."""

    _handler_name = "strategy_analyze_handler"
    _task_type = TaskType.STRATEGY_ANALYZE_PRD
    _role = "strat"
    _artifact_name = "strategy_analysis.md"


class DevelopmentDesignHandler(_CycleTaskHandler):
    """Cycle task handler for development design (dev role)."""

    _handler_name = "development_design_handler"
    _task_type = TaskType.DEVELOPMENT_DESIGN
    _role = "dev"
    _artifact_name = "implementation_plan.md"


class QAValidateHandler(_CycleTaskHandler):
    """Cycle task handler for QA validation (qa role)."""

    _handler_name = "qa_validate_handler"
    _task_type = TaskType.QA_VALIDATE
    _role = "qa"
    _artifact_name = "validation_plan.md"


class DataReportHandler(_CycleTaskHandler):
    """Cycle task handler for data reporting (data role)."""

    _handler_name = "data_report_handler"
    _task_type = TaskType.DATA_REPORT
    _role = "data"
    _artifact_name = "data_report.md"
