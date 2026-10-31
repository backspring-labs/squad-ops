"""The intervention ledger (SIP-0113 §4.3; #2417).

Every action taken on a campaign by a person, or by the supervisor seat, is an entry, with its
reason and its severity. Most are control-log rows already (SIP-0109 §13), so the ledger is a
projection of that one authority: it never writes a control-log row. It adds only the two
classifications, kept in Outcome Evaluation's own record and keyed by the row.

An action outside the interface (a manual repair, a restart) can't be a row. It is a declared
entry, so the void it makes in a campaign's claim of unattended operation is counted, not only
stated. "Could the squad have resolved it?" is the supervisor's reading, recorded as an opinion.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from squadops.campaigns.escalation import EscalationState
from squadops.campaigns.gate import EXECUTOR_ROLE, SWEEP_ROLE
from squadops.campaigns.lifecycle import LAUNCHER_ROLE
from squadops.campaigns.models import ControlLogEntry, ControlOperation, ControlOutcome
from squadops.campaigns.progress import COMPLETION_ROLE
from squadops.cycles.models import GateDecisionValue


class InterventionReason:
    """Why it was needed (§4.3, the idea's §8 list). Constants, not an enum: several of these
    words are other vocabularies' too (a workload's ``implementation``), and #380's guard would
    read every such literal as this one's shadow."""

    CLARIFICATION = "clarification"
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    VERIFICATION = "verification"
    ENVIRONMENT = "environment"
    TOOL = "tool"
    COORDINATION = "coordination"
    MEMORY_OR_CONTEXT = "memory_or_context"
    JUDGEMENT_OR_ESCALATION = "judgement_or_escalation"
    AUTHORIZATION = "authorization"

    ALL = frozenset(
        {
            CLARIFICATION,
            PLANNING,
            IMPLEMENTATION,
            VERIFICATION,
            ENVIRONMENT,
            TOOL,
            COORDINATION,
            MEMORY_OR_CONTEXT,
            JUDGEMENT_OR_ESCALATION,
            AUTHORIZATION,
        }
    )


class InterventionSeverity:
    ADVISORY = "advisory"
    UNBLOCK = "unblock"
    RECOVERY = "recovery"
    ABORT = "abort"

    ALL = frozenset({ADVISORY, UNBLOCK, RECOVERY, ABORT})


def _check_kinds(reason: str, severity: str) -> None:
    if reason not in InterventionReason.ALL:
        raise LedgerInvalid(f"reason {reason!r} is not one of {sorted(InterventionReason.ALL)}")
    if severity not in InterventionSeverity.ALL:
        raise LedgerInvalid(
            f"severity {severity!r} is not one of {sorted(InterventionSeverity.ALL)}"
        )


class LedgerInvalid(ValueError):
    """A classification or a declared entry the ledger can't hold as given."""


#: The roles the system writes rows under: their rows are the campaign running, never an
#: intervention in it.
SYSTEM_ROLES = frozenset({EXECUTOR_ROLE, SWEEP_ROLE, LAUNCHER_ROLE, COMPLETION_ROLE})
#: Operations that are an intervention whenever a person or the supervisor seat applies one.
_ACTED = frozenset(
    {
        ControlOperation.PAUSE,
        ControlOperation.RESUME,
        ControlOperation.ABORT,
        ControlOperation.CLASSIFY,
        ControlOperation.ESCALATION_ANSWERED,
        ControlOperation.REBIND,
        ControlOperation.INSTRUCT,
    }
)
#: A ruling that returns a proposal intervenes. An approval is the gate as designed.
_RETURNING = frozenset({GateDecisionValue.RETURNED_FOR_REVISION, GateDecisionValue.REJECTED})


def is_intervention(entry: ControlLogEntry) -> bool:
    """Whether an applied control-log row is an intervention in its campaign (§4.3)."""
    if entry.outcome is not ControlOutcome.APPLIED:
        return False
    if entry.operation is ControlOperation.RULE:
        return entry.binding.get("decision") in _RETURNING
    if entry.operation is ControlOperation.ESCALATION_CLOSED:
        # An escalated plan gate that a person decided: the design question was answered.
        return entry.binding.get("state") == EscalationState.RESOLVED
    return entry.operation in _ACTED and entry.actor_role not in SYSTEM_ROLES


@dataclass(frozen=True)
class Classification:
    """A control-log row's two classifications, and the supervisor's opinion."""

    entry_id: str
    campaign_id: str
    reason: str
    severity: str
    classified_by: str
    classified_at: datetime
    squad_could_resolve: bool | None = None  # an opinion, labelled as one
    note: str = ""

    def __post_init__(self) -> None:
        _check_kinds(self.reason, self.severity)


@dataclass(frozen=True)
class DeclaredIntervention:
    """An action outside the interface, which no row can record (§4.3)."""

    declared_id: str
    campaign_id: str
    reason: str
    severity: str
    description: str
    occurred_at: datetime
    declared_by: str
    declared_at: datetime
    squad_could_resolve: bool | None = None

    def __post_init__(self) -> None:
        _check_kinds(self.reason, self.severity)
        if not self.description.strip():
            raise LedgerInvalid("a declared intervention says what was done")


@dataclass(frozen=True)
class LedgerEntry:
    """One intervention: its row (or its declaration), and its classification when it has one."""

    entry_id: str | None
    operation: str
    actor: str
    at: datetime
    classification: Classification | None = None
    declared: DeclaredIntervention | None = None


@dataclass(frozen=True)
class Ledger:
    """A campaign's ledger, with §7 prediction 5's two gaps: intervention rows not yet classified,
    and classifications that name no intervention row of this campaign."""

    campaign_id: str
    entries: tuple[LedgerEntry, ...]
    unclassified: tuple[str, ...]
    orphaned: tuple[str, ...]

    @property
    def matches_the_control_log(self) -> bool:
        return not self.unclassified and not self.orphaned


def check_classifiable(entry: ControlLogEntry | None, campaign_id: str) -> ControlLogEntry:
    """A classification names one of this campaign's intervention rows."""
    if entry is None or entry.campaign_id != campaign_id:
        raise LedgerInvalid(f"campaign {campaign_id} has no such control-log row")
    if not is_intervention(entry):
        raise LedgerInvalid(
            f"row {entry.entry_id} ({entry.operation}) is not an intervention: only a person's or "
            "the supervisor's action is classified (§4.3)"
        )
    return entry


def ledger(
    campaign_id: str,
    control_log: Sequence[ControlLogEntry],
    classifications: Iterable[Classification],
    declared: Iterable[DeclaredIntervention],
) -> Ledger:
    """The campaign's interventions in order, each with its classification, and the gaps."""
    rows = [e for e in control_log if is_intervention(e)]
    by_entry = {c.entry_id: c for c in classifications}
    entries = [
        LedgerEntry(
            e.entry_id, e.operation.value, e.actor, e.committed_at, by_entry.get(e.entry_id)
        )
        for e in rows
    ] + [LedgerEntry(None, "declared", d.declared_by, d.occurred_at, declared=d) for d in declared]
    known = {e.entry_id for e in rows}
    return Ledger(
        campaign_id=campaign_id,
        entries=tuple(sorted(entries, key=lambda e: e.at)),
        unclassified=tuple(e.entry_id for e in rows if e.entry_id not in by_entry),
        orphaned=tuple(sorted(set(by_entry) - known)),
    )
