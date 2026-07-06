"""Cycle task handlers package (SIP-0066) — split from cycle_tasks.py (#152).

One module per handler plus shared base/validation. The legacy import path
``squadops.capabilities.handlers.cycle_tasks`` re-exports this package's
names and remains the compatibility surface for existing importers.
"""

from squadops.capabilities.handlers.cycle.base import _CycleTaskHandler
from squadops.capabilities.handlers.cycle.builder import BuilderAssembleHandler
from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
from squadops.capabilities.handlers.cycle.governance import GovernanceReviewHandler
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.cycle.roles import (
    DataReportHandler,
    DevelopmentDesignHandler,
    QAValidateHandler,
    StrategyAnalyzeHandler,
)
from squadops.capabilities.handlers.cycle.validation import (
    _DEFAULT_TYPE,
    _EXT_MAP,
    _FILENAME_MAP,
    _PRD_COVERAGE_DISCIPLINE_SECTION,
    _STACK_INDICATORS,
    _STUB_PATTERNS,
    _STUB_THRESHOLD_BYTES,
    ValidationResult,
    _build_typed_check_evaluation_artifact,
    _classify_file,
    _detect_expected_layers,
    _detect_stubs,
    _estimate_min_artifacts,
    _is_test_file,
    _rewrite_manifest_identifiers,
)

__all__ = [
    "_DEFAULT_TYPE",
    "_EXT_MAP",
    "_FILENAME_MAP",
    "_PRD_COVERAGE_DISCIPLINE_SECTION",
    "_STACK_INDICATORS",
    "_STUB_PATTERNS",
    "_STUB_THRESHOLD_BYTES",
    "BuilderAssembleHandler",
    "DataReportHandler",
    "DevelopmentDesignHandler",
    "DevelopmentDevelopHandler",
    "GovernanceReviewHandler",
    "QATestHandler",
    "QAValidateHandler",
    "StrategyAnalyzeHandler",
    "ValidationResult",
    "_build_typed_check_evaluation_artifact",
    "_classify_file",
    "_CycleTaskHandler",
    "_detect_expected_layers",
    "_detect_stubs",
    "_estimate_min_artifacts",
    "_is_test_file",
    "_rewrite_manifest_identifiers",
]
