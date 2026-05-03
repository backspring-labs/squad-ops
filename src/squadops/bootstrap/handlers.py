"""Handler bootstrap - Auto-registration of capability handlers.

Provides factory functions for creating handler registries
with all handlers auto-discovered and registered.

Part of SIP-0.8.8 Phase 7.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from squadops.capabilities.handlers.cycle_tasks import (
    BuilderAssembleHandler,
    DataReportHandler,
    DevelopmentDesignHandler,
    DevelopmentDevelopHandler,
    GovernanceReviewHandler,
    QATestHandler,
    QAValidateHandler,
    StrategyAnalyzeHandler,
)
from squadops.capabilities.handlers.data import (
    DataAnalysisHandler,
    MetricsCollectionHandler,
)
from squadops.capabilities.handlers.development import (
    CodeAnalysisHandler,
    CodeGenerationHandler,
)

# Import handlers
from squadops.capabilities.handlers.governance import (
    TaskAnalysisHandler,
    TaskDelegationHandler,
)
from squadops.capabilities.handlers.impl.analyze_failure import (
    DataAnalyzeFailureHandler,
)
from squadops.capabilities.handlers.impl.correction_decision import (
    GovernanceCorrectionDecisionHandler,
)
from squadops.capabilities.handlers.impl.establish_contract import (
    GovernanceEstablishContractHandler,
)
from squadops.capabilities.handlers.impl.repair_handlers import (
    BuilderAssembleRepairHandler,
    DevelopmentCorrectionRepairHandler,
    QAValidateRepairHandler,
)
from squadops.capabilities.handlers.planning_tasks import (
    DataResearchContextHandler,
    DevelopmentDesignPlanHandler,
    GovernanceAssessReadinessHandler,
    GovernanceIncorporateFeedbackHandler,
    QADefineTestStrategyHandler,
    QAValidateRefinementHandler,
    StrategyFrameObjectiveHandler,
)
from squadops.capabilities.handlers.qa import (
    TestExecutionHandler,
    ValidationHandler,
)
from squadops.capabilities.handlers.repair_tasks import (
    DataAnalyzeVerificationHandler,
    DevelopmentRepairHandler,
    GovernanceRootCauseHandler,
    StrategyCorrectivePlanHandler,
)
from squadops.capabilities.handlers.warmboot import (
    ContextSyncHandler,
    WarmbootHandler,
)
from squadops.capabilities.handlers.wrapup_tasks import (
    DataClassifyUnresolvedHandler,
    DataGatherEvidenceHandler,
    GovernanceCloseoutDecisionHandler,
    GovernancePublishHandoffHandler,
    QAAssessOutcomesHandler,
)
from squadops.orchestration.handler_registry import HandlerRegistry

if TYPE_CHECKING:
    from squadops.capabilities.handlers.base import CapabilityHandler

logger = logging.getLogger(__name__)


# All handler classes with their role assignments
HANDLER_CONFIGS: list[tuple[type[CapabilityHandler], tuple[str, ...]]] = [
    # Governance handlers (lead role)
    (TaskAnalysisHandler, ("lead",)),
    (TaskDelegationHandler, ("lead",)),
    # Development handlers (dev role)
    (CodeGenerationHandler, ("dev",)),
    (CodeAnalysisHandler, ("dev", "lead")),  # Lead can also review code
    # QA handlers (qa role)
    (TestExecutionHandler, ("qa",)),
    (ValidationHandler, ("qa", "lead")),  # Lead can validate too
    # Data handlers (data role)
    (DataAnalysisHandler, ("data",)),
    (MetricsCollectionHandler, ("data",)),
    # Warmboot handlers (all roles can warmboot)
    (WarmbootHandler, ("lead", "dev", "qa", "strat", "data", "builder")),
    (ContextSyncHandler, ("lead", "dev", "qa", "strat", "data", "builder")),
    # Cycle task handlers (SIP-0066: pinned task_types for cycle execution pipeline)
    (StrategyAnalyzeHandler, ("strat",)),
    (DevelopmentDesignHandler, ("dev",)),
    (QAValidateHandler, ("qa",)),
    (DataReportHandler, ("data",)),
    (GovernanceReviewHandler, ("lead",)),
    # Build handlers (SIP-Enhanced-Agent-Build-Capabilities)
    (DevelopmentDevelopHandler, ("dev",)),
    (QATestHandler, ("qa",)),
    # Builder handlers (SIP-0071: Builder Role)
    (BuilderAssembleHandler, ("builder",)),
    # Repair handlers (SIP-0070: Pulse Check Verification)
    (DataAnalyzeVerificationHandler, ("data",)),
    (GovernanceRootCauseHandler, ("lead",)),
    (StrategyCorrectivePlanHandler, ("strat",)),
    (DevelopmentRepairHandler, ("dev",)),
    # Implementation handlers (SIP-0079: Implementation Run Contract)
    (GovernanceEstablishContractHandler, ("lead",)),
    (DataAnalyzeFailureHandler, ("data",)),
    (GovernanceCorrectionDecisionHandler, ("lead",)),
    # Correction-loop repair pair (SIP-0079 §7.7). Distinct from the
    # SIP-0070 `development.repair` registered above via
    # handlers.repair_tasks.DevelopmentRepairHandler — see issue #100 for
    # the rationale behind the split into `development.correction_repair`.
    (DevelopmentCorrectionRepairHandler, ("dev",)),
    (BuilderAssembleRepairHandler, ("builder",)),
    (QAValidateRepairHandler, ("qa",)),
    # Planning handlers (SIP-0078: Planning Workload Protocol)
    (DataResearchContextHandler, ("data",)),
    (StrategyFrameObjectiveHandler, ("strat",)),
    (DevelopmentDesignPlanHandler, ("dev",)),
    (QADefineTestStrategyHandler, ("qa",)),
    (GovernanceAssessReadinessHandler, ("lead",)),
    # Refinement handlers (SIP-0078: Planning Workload Protocol)
    (GovernanceIncorporateFeedbackHandler, ("lead",)),
    (QAValidateRefinementHandler, ("qa",)),
    # Wrap-up handlers (SIP-0080: Wrap-Up Workload Protocol)
    (DataGatherEvidenceHandler, ("data",)),
    (QAAssessOutcomesHandler, ("qa",)),
    (DataClassifyUnresolvedHandler, ("data",)),
    (GovernanceCloseoutDecisionHandler, ("lead",)),
    (GovernancePublishHandoffHandler, ("lead",)),
]


def get_all_handlers() -> list[tuple[type[CapabilityHandler], tuple[str, ...]]]:
    """Get all handler classes with their role assignments.

    Returns:
        List of (handler_class, roles) tuples
    """
    return list(HANDLER_CONFIGS)


def create_handler_registry(
    roles: list[str] | None = None,
) -> HandlerRegistry:
    """Create a handler registry with auto-registered handlers.

    Args:
        roles: Optional list of roles to include handlers for.
               If None, includes all handlers.

    Returns:
        HandlerRegistry with handlers registered
    """
    registry = HandlerRegistry()

    for handler_class, handler_roles in HANDLER_CONFIGS:
        # Filter by roles if specified
        if roles is not None:
            if not any(r in roles for r in handler_roles):
                continue

        try:
            handler = handler_class()
            registry.register(handler, roles=handler_roles)
            logger.debug(f"Registered handler: {handler.capability_id} for roles {handler_roles}")
        except Exception as e:
            logger.warning(f"Failed to register handler {handler_class}: {e}")

    logger.info(f"Created handler registry with {len(registry.list_capabilities())} handlers")

    return registry
