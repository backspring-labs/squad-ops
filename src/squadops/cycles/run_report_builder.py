"""Run-report markdown assembly (pure presentation, no I/O).

Hoisted verbatim from ``DispatchedFlowExecutor._generate_run_report`` and its
report-line builders (SIP-0097 §6.5 slice 1). The executor (``RunCompletion``
from slice 2 onward) fetches state, calls :func:`build_run_report`, and owns
the artifact-vault write; this module only formats.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from squadops.cycles.models import RunStatus
from squadops.cycles.pulse_models import PulseDecision
from squadops.cycles.verification_integrity import RunVerdict

if TYPE_CHECKING:
    from squadops.cycles.verification_integrity import RunVerificationSummary
    from squadops.tasks.models import TaskEnvelope

# terminal_status flows through the report pipeline as an UPPERCASE bare string
# (an untyped shadow of RunStatus — full unification tracked in #377). Source the
# compared values from the enum so it stays the single source of truth, and
# compare case-insensitively so a lowercase RunStatus value can't silently miss.
_COMPLETED = RunStatus.COMPLETED.value.upper()
_FAILED = RunStatus.FAILED.value.upper()
_CANCELLED = RunStatus.CANCELLED.value.upper()


def _build_report_metadata_lines(
    cycle_id: str,
    run_id: str,
    run: Any,
    terminal_status: str,
    cycle: Any,
) -> list[str]:
    """Build the metadata section lines for the run report."""
    lines = [
        "# Run Report",
        "",
        "## Metadata",
        f"- **Cycle ID:** {cycle_id}",
        f"- **Run ID:** {run_id}",
        f"- **Run Number:** {run.run_number}",
        f"- **Status:** {terminal_status}",
    ]
    if cycle:
        lines.append(f"- **Project ID:** {cycle.project_id}")
        lines.append(f"- **Build Strategy:** {cycle.build_strategy}")
        lines.append(f"- **Squad Profile:** {cycle.squad_profile_id}")
    if run.started_at:
        lines.append(f"- **Started:** {run.started_at.isoformat()}")
    if run.finished_at:
        lines.append(f"- **Finished:** {run.finished_at.isoformat()}")
    return lines


def _build_report_quality_lines(
    terminal_status: str, verification_summary: RunVerificationSummary | None = None
) -> list[str]:
    """Build the quality notes section for the run report.

    SIP-0096 §6.6(4), narrative-override prohibition: the narrative must not
    claim success when the structured verification verdict is ``rejected`` or
    ``blocked_unverified``. A run can reach COMPLETED with failed/unverified
    evidence — the verdict is deliberately not a ``RunStatus`` (§6.5) — so when
    it does, this note reflects the verdict instead of asserting all-clear.
    """
    lines = ["", "## Quality Notes"]
    status = (terminal_status or "").upper()
    verdict = verification_summary.verdict if verification_summary else None
    if status == _COMPLETED and verdict == RunVerdict.REJECTED:
        lines.append(
            "Tasks completed, but verification **REJECTED** — one or more executed "
            "checks failed. See Verification Integrity."
        )
    elif status == _COMPLETED and verdict == RunVerdict.BLOCKED_UNVERIFIED:
        lines.append(
            "Tasks completed, but verification **BLOCKED_UNVERIFIED** — a required "
            "check did not execute. See Verification Integrity."
        )
    elif status == _COMPLETED:
        lines.append("All tasks completed successfully.")
    elif status == _FAILED:
        lines.append("One or more tasks failed. Check task artifacts for details.")
    elif status == _CANCELLED:
        lines.append("Run was cancelled before completion.")
    else:
        lines.append(f"Terminal status: {terminal_status}")
    lines.append("")
    return lines


def _build_pulse_report_lines(pulse_report_entries: list[dict[str, Any]]) -> list[str]:
    """Build the pulse verification section for the run report."""
    lines: list[str] = []
    lines.append("")
    lines.append("## Pulse Verification")
    pass_count = sum(1 for e in pulse_report_entries if e["decision"] == PulseDecision.PASS.value)
    fail_count = sum(1 for e in pulse_report_entries if e["decision"] == PulseDecision.FAIL.value)
    exhausted_count = sum(
        1 for e in pulse_report_entries if e["decision"] == PulseDecision.EXHAUSTED.value
    )
    total = len(pulse_report_entries)
    lines.append(
        f"Total boundary checks: {total} "
        f"(PASS: {pass_count}, FAIL: {fail_count}, EXHAUSTED: {exhausted_count})"
    )
    repair_entries = [e for e in pulse_report_entries if e["repair_attempt"] > 0]
    if repair_entries:
        max_attempt = max(e["repair_attempt"] for e in repair_entries)
        lines.append(f"Repair attempts: {len(repair_entries)} (max attempt: {max_attempt})")
    lines.append("")
    for entry in pulse_report_entries:
        suites_str = ", ".join(f"{s['suite_id']}={s['outcome']}" for s in entry["suites"])
        repair_tag = f" (repair #{entry['repair_attempt']})" if entry["repair_attempt"] else ""
        lines.append(
            f"- **{entry['boundary_id']}** [{entry['decision'].upper()}]{repair_tag}: {suites_str}"
        )
    return lines


def _build_verification_lines(summary: RunVerificationSummary) -> list[str]:
    """Build the SIP-0096 verification-integrity section (honest evidence disclosure).

    Surfaces the run verdict, executed pass-rate, and — critically — every
    not-executed result, so silence is never presented as green (§6.6.3). In
    Phase 1 this is inert (no producers wired) and typically shows zero recorded
    checks; it becomes load-bearing as Phase 2 wires producers.
    """
    lines = ["", "## Verification Integrity"]
    lines.append(f"Verdict: **{summary.verdict.value}**")
    lines.append(
        f"Executed: {summary.executed_count} "
        f"(passed {summary.passed_count}, pass-rate {summary.pass_rate:.0%})"
    )
    if summary.failed:
        lines.append(f"Failed: {', '.join(summary.failed)}")
    if summary.unverified:
        lines.append("")
        lines.append("### Unverified (not executed)")
        for u in summary.unverified:
            tag = " [required]" if u.required else ""
            lines.append(f"- **{u.check_id}**: {u.reason}{tag}")
    if summary.required_unmet:
        lines.append("")
        lines.append(
            f"⚠️ {len(summary.required_unmet)} required check(s) unverified — "
            "this is a harness/evidence problem, not a product failure."
        )
    return lines


def build_run_report(
    cycle_id: str,
    run_id: str,
    run: Any,
    terminal_status: str,
    cycle: Any = None,
    plan: list[TaskEnvelope] | None = None,
    pulse_report_entries: list[dict[str, Any]] | None = None,
    verification_summary: RunVerificationSummary | None = None,
) -> str:
    """Assemble the full run_report.md markdown content (D10)."""
    lines = _build_report_metadata_lines(cycle_id, run_id, run, terminal_status, cycle)

    # Task breakdown
    if plan:
        lines.append("")
        lines.append("## Task Plan")
        lines.append(f"Total tasks: {len(plan)}")
        lines.append("")
        for i, envelope in enumerate(plan):
            role = envelope.metadata.get("role", "unknown")
            lines.append(
                f"{i + 1}. **{envelope.task_type}** (agent: {envelope.agent_id}, role: {role})"
            )

    # Gate decisions
    if run.gate_decisions:
        lines.append("")
        lines.append("## Gate Decisions")
        for gd in run.gate_decisions:
            lines.append(
                f"- **{gd.gate_name}:** {gd.decision}" + (f" — {gd.notes}" if gd.notes else "")
            )

    # Artifact inventory
    if run.artifact_refs:
        lines.append("")
        lines.append("## Artifacts")
        lines.append(f"Total artifacts: {len(run.artifact_refs)}")

    # Pulse verification summary
    if pulse_report_entries:
        lines.extend(_build_pulse_report_lines(pulse_report_entries))

    # SIP-0096 verification-integrity roll-up
    if verification_summary is not None:
        lines.extend(_build_verification_lines(verification_summary))

    # Quality notes
    lines.extend(_build_report_quality_lines(terminal_status, verification_summary))

    return "\n".join(lines)
