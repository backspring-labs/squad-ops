"""Run-completion collaborator (SIP-0097 §6.4).

Owns everything that happens once, at the end of a run: the terminal-status
mapping (exception → ``RunStatus``/event/log), observability closeout
(LangFuse trace close + Prefect terminal state), and run-report generation
(formatting lives in the domain ``run_report_builder``; this collaborator
owns the vault write).

Per the SIP-0097 observability ownership rule: per-run observability starts
in the executor (``_init_run_observability``) and closes here; per-task
observability belongs to the dispatch path.

**The 1.4 socket (SIP-0096 §6.4):** ``finalize`` is the single call site
that sees the run's ``RunLedger`` at run end. In v1.3 it computes the
existing completion/report surface — no new semantics. In v1.4, SIP-0096
wires its pure ``aggregate_verification`` function here as this
collaborator's first client.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from adapters.cycles.execution_errors import (
    _CancellationError,
    _ExecutionError,
    _PausedError,
    _RecruitmentRejectedError,
)
from squadops.cycles.models import ArtifactRef, RunStatus
from squadops.cycles.run_report_builder import build_run_report
from squadops.cycles.verification_integrity import (
    RunVerificationSummary,
    aggregate_verification,
)
from squadops.events.types import EventType

if TYPE_CHECKING:
    from squadops.cycles.models import Cycle
    from squadops.cycles.run_ledger import RunLedger
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.cycles.workflow_tracker import WorkflowTrackerPort
    from squadops.ports.telemetry.llm_observability import LLMObservabilityPort
    from squadops.tasks.models import TaskEnvelope

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TerminalOutcome:
    """The run-end consequence of an exception (SIP-0097 §6.4).

    Pure data: the executor's single except-block persists the status,
    emits the event, and logs — this mapping decides what.
    """

    terminal_status: str
    run_status: RunStatus
    event_type: str
    event_payload: dict[str, Any] | None
    log_kind: Literal["info", "error", "exception"]
    log_message: str


def resolve_terminal_outcome(exc: BaseException, run_id: str) -> TerminalOutcome:
    """Map an execute_run exception to its terminal outcome.

    Moved from execute_run's per-class exception handlers; the mapping —
    including event payload shapes and log wording — is behavior-preserving:
    cancellation → CANCELLED, recruitment deferral / BLOCKED pause → PAUSED,
    execution error / unexpected → FAILED.
    """
    if isinstance(exc, _CancellationError):
        return TerminalOutcome(
            terminal_status="CANCELLED",
            run_status=RunStatus.CANCELLED,
            event_type=EventType.RUN_CANCELLED,
            event_payload=None,
            log_kind="info",
            log_message=f"Run {run_id} cancelled",
        )
    if isinstance(exc, _RecruitmentRejectedError):
        # SIP-0089 §2.5: deferral, not failure. PAUSED has a first-class
        # resume affordance (squadops runs resume → RUN_RESUMED); the reason
        # rides in the payload so operators can distinguish a duty deferral
        # from a BLOCKED-outcome pause.
        return TerminalOutcome(
            terminal_status="PAUSED",
            run_status=RunStatus.PAUSED,
            event_type=EventType.RUN_PAUSED,
            event_payload={"reason": exc.reason, "deferred_for_agent": exc.agent_id},
            log_kind="info",
            log_message=(
                f"Run {run_id} paused — recruitment deferred "
                f"(agent={exc.agent_id}, reason={exc.reason})"
            ),
        )
    if isinstance(exc, _PausedError):
        return TerminalOutcome(
            terminal_status="PAUSED",
            run_status=RunStatus.PAUSED,
            event_type=EventType.RUN_PAUSED,
            event_payload=None,
            log_kind="info",
            log_message=f"Run {run_id} paused",
        )
    if isinstance(exc, _ExecutionError):
        return TerminalOutcome(
            terminal_status="FAILED",
            run_status=RunStatus.FAILED,
            event_type=EventType.RUN_FAILED,
            event_payload={"error": str(exc)},
            log_kind="error",
            log_message=f"Run {run_id} failed: {exc}",
        )
    return TerminalOutcome(
        terminal_status="FAILED",
        run_status=RunStatus.FAILED,
        event_type=EventType.RUN_FAILED,
        event_payload={"error": str(exc)},
        log_kind="exception",
        log_message=f"Run {run_id} failed with unexpected error: {exc}",
    )


class RunCompletion:
    """Composes the executor's run-end path (SIP-0097 §6.4).

    Plain injected collaborator, not a port — a decomposition seam inside
    the existing adapter, not an alternate runtime strategy.
    """

    def __init__(
        self,
        cycle_registry: CycleRegistryPort | None = None,
        artifact_vault: ArtifactVaultPort | None = None,
        llm_observability: LLMObservabilityPort | None = None,
        workflow_tracker: WorkflowTrackerPort | None = None,
    ) -> None:
        self._cycle_registry = cycle_registry
        self._artifact_vault = artifact_vault
        self._llm_observability = llm_observability
        self._workflow_tracker = workflow_tracker

    async def finalize(
        self,
        cycle_id: str,
        run_id: str,
        terminal_status: str,
        obs_ctx: Any,
        flow_run_id: str | None,
        cycle: Cycle | None = None,
        plan: list[TaskEnvelope] | None = None,
        ledger: RunLedger | None = None,
    ) -> None:
        """Close observability traces and generate run report."""
        # LangFuse: close cycle trace
        if self._llm_observability and obs_ctx:
            from squadops.telemetry.models import StructuredEvent

            self._llm_observability.record_event(
                obs_ctx,
                StructuredEvent(
                    name="cycle.completed",
                    message=f"Cycle {cycle_id} reached {terminal_status}",
                ),
            )
            self._llm_observability.end_cycle_trace(obs_ctx)
            self._llm_observability.flush()

        # Prefect: set terminal state
        if self._workflow_tracker and flow_run_id:
            try:
                await self._workflow_tracker.set_flow_run_state(
                    flow_run_id, terminal_status, terminal_status.title()
                )
            except Exception:
                logger.warning("Prefect terminal state update failed", exc_info=True)

        # SIP-0096 §6.4: the pure verification-integrity choke point. finalize is
        # the single site that sees the run's RunLedger at run end; run the
        # aggregation over every recorded check result against the profile's
        # declared required set. Phase 1 is inert — no producer records results
        # and no shipped profile declares required_checks — so this computes
        # `accepted` with zero recorded evidence and discloses it in the report.
        # Phase 2 wires the producers and per-profile required lists (the throttle).
        summary = self._aggregate_verification(cycle, ledger, terminal_status)

        # SIP-0096 Phase 3 (§10): persist the run's verdict as durable structured
        # evidence so the CycleOutcome roll-up can read it back — until now the
        # summary was only rendered into run_report.md and discarded. Best-effort:
        # a persistence failure is logged, never affects the run's terminal status
        # (same contract as the run report below).
        if run_id:
            try:
                await self._cycle_registry.record_run_verification_summary(run_id, summary)
            except Exception:
                logger.warning("Verification summary persistence failed", exc_info=True)

        # Run report: best-effort (D10)
        try:
            if cycle_id and run_id:
                await self.generate_run_report(
                    cycle_id,
                    run_id,
                    terminal_status,
                    cycle=cycle,
                    plan=plan,
                    ledger=ledger,
                    verification_summary=summary,
                )
        except Exception:
            logger.warning("Run report generation failed", exc_info=True)

    @staticmethod
    def _aggregate_verification(
        cycle: Cycle | None, ledger: RunLedger | None, terminal_status: str
    ) -> RunVerificationSummary:
        """Run the SIP-0096 aggregation over the ledger against the cycle's required set.

        Requiredness comes only from the cycle's ``applied_defaults['required_checks']``
        (an explicit profile declaration, §6.3 / AC#5) — never inferred. Both the
        results and the required list default to empty, so a pre-SIP-0096 cycle or
        a Phase-1 (throttle-off) cycle that *completes* aggregates to an honest
        `accepted`.

        ``terminal_status`` supplies the run-level context the pure verdict cannot
        see: only a ``COMPLETED`` run is eligible for `accepted` (#388). A run that
        FAILED/cancelled/paused with no failed check would otherwise fall through to
        `accepted` on zero evidence — the `Status: FAILED` / `Verdict: accepted`
        contradiction — so we pass ``run_succeeded`` and let the choke point resolve
        it to `blocked_unverified`.
        """
        required_check_ids: tuple[str, ...] = ()
        if cycle is not None:
            declared = cycle.applied_defaults.get("required_checks")
            if declared:
                required_check_ids = tuple(declared)
        results = ledger.check_results if ledger else ()
        run_succeeded = (terminal_status or "").upper() == RunStatus.COMPLETED.value.upper()
        summary = aggregate_verification(results, required_check_ids, run_succeeded=run_succeeded)
        logger.info(
            "Verification integrity: verdict=%s executed=%d passed=%d unverified=%d required_unmet=%d",
            summary.verdict.value,
            summary.executed_count,
            summary.passed_count,
            len(summary.unverified),
            len(summary.required_unmet),
        )
        return summary

    async def generate_run_report(
        self,
        cycle_id: str,
        run_id: str,
        terminal_status: str,
        cycle: Cycle | None = None,
        plan: list[TaskEnvelope] | None = None,
        ledger: RunLedger | None = None,
        verification_summary: RunVerificationSummary | None = None,
    ) -> None:
        """Generate run_report.md and store as a documentation artifact (D10).

        Best-effort: called from finalize's try/except, failures are logged
        but never affect the run's terminal status.
        """
        # Fetch latest run state for gate decisions and artifact refs
        run = await self._cycle_registry.get_run(run_id)

        content = build_run_report(
            cycle_id,
            run_id,
            run,
            terminal_status,
            cycle=cycle,
            plan=plan,
            pulse_report_entries=list(ledger.pulse_entries) if ledger else None,
            verification_summary=verification_summary,
        )
        content_bytes = content.encode("utf-8")

        # Note: uses direct vault.store() because the report is generated
        # outside of any task context (no TaskEnvelope).
        ref = ArtifactRef(
            artifact_id=f"art_{uuid4().hex[:12]}",
            project_id=cycle.project_id if cycle else "unknown",
            artifact_type="document",
            filename="run_report.md",
            content_hash=sha256(content_bytes).hexdigest(),
            size_bytes=len(content_bytes),
            media_type="text/markdown",
            created_at=datetime.now(UTC),
            cycle_id=cycle_id,
            run_id=run_id,
            metadata={"report_type": "run_report"},
        )

        await self._artifact_vault.store(ref, content_bytes)
        await self._cycle_registry.append_artifact_refs(run_id, (ref.artifact_id,))
        logger.info("Run report generated for %s", run_id)
