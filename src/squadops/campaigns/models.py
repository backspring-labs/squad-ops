"""Campaign domain models (SIP-0109 §15, §17).

Frozen dataclasses beside ``Cycle`` and ``Run``. This module holds the shapes that step 1 (#1799)
gives behaviour: the campaign, its objective and policy, its lifecycle states, the control-log
entry and the launch intent. The shapes later steps give behaviour (the change request, the
increment ruling, the box lease, the proposal ledger, the frozen criterion, the failure record, the
continuation decision, the verifier bundle) arrive with those steps, so none of them is a shape
without a consumer.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import StrEnum

from squadops.cycles.models import GateDecisionValue

# =============================================================================
# Enums
# =============================================================================


class CampaignState(StrEnum):
    """The campaign's lifecycle state (§17). The legal moves between them are in ``lifecycle``."""

    DRAFT = "draft"
    CALIBRATING = "calibrating"
    AT_PROPOSAL = "at_proposal"
    AWAITING_RULING = "awaiting_ruling"
    BUILDING = "building"
    EVALUATING = "evaluating"
    PROMOTING = "promoting"
    REPAIRING = "repairing"
    RETRYING = "retrying"
    LAUNCH_BLOCKED = "launch_blocked"
    PAUSED = "paused"
    ESCALATED = "escalated"
    COMPLETED = "completed"


class CampaignOutcome(StrEnum):
    """How a completed campaign ended (§17: ``completed (success | failure | aborted | exhausted)``)."""

    SUCCESS = "success"
    FAILURE = "failure"
    ABORTED = "aborted"
    EXHAUSTED = "exhausted"


class CycleKind(StrEnum):
    """Why a campaign launched a cycle: ``cycles.kind`` (§16). A cycle no campaign launched has none."""

    CALIBRATION = "calibration"
    INCREMENT = "increment"
    REPAIR = "repair"
    RETRY = "retry"


class ControlOperation(StrEnum):
    """A control operation, each one a control-log row (§13).

    Every member is an operation the SIP names: the supervision surface's create, pause, resume
    and abort (§13), the owner's start (draft → calibrating, launching the calibration cycle), a proposal submitted to the increment gate and the ruling on it (§9.2), the
    continuation decision (§10), the promotion transition (§10), and the launcher marking an
    intent launched (§12b), the box lease's acquisition and release, and a launch the box
    refused and its retry (§9.3, #1802).
    """

    CREATE = "create"
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    ABORT = "abort"
    SUBMIT = "submit"
    RULE = "rule"
    DECIDE = "decide"
    PROMOTE = "promote"
    MARK_LAUNCHED = "mark_launched"
    #: The supervisor's classification of what went wrong with a proposal (§9.4). A record.
    CLASSIFY = "classify"
    #: The increment gate has waited past a seat's ruling bound (§9.2, §9.5; §24ae). The campaign
    #: stays ``awaiting_ruling``, which is the bound's pause; nothing proceeds unapproved.
    RULING_OVERDUE = "ruling_overdue"
    #: The supervisor takes the box at the increment gate, or gives it back (§9.3; #1802). A
    #: record of the lease's change, committed with it; the campaign's state does not move.
    LEASE_ACQUIRE = "lease_acquire"
    LEASE_RELEASE = "lease_release"
    #: The box refused a launch: the campaign waits in ``launch_blocked``, re-attempted at the
    #: policy's interval, and escalates after its count (§9.3). The unblock returns it to the
    #: state its launch was written from, and the launcher launches the held intent.
    LAUNCH_BLOCKED = "launch_blocked"
    LAUNCH_UNBLOCKED = "launch_unblocked"

    @property
    def records_only(self) -> bool:
        """An operation that records a fact without moving the campaign's state.

        It is the one kind accepted on a completed campaign: a launch the launcher had already
        made before an abort committed is still a cycle that exists, and its record must say so;
        a proposal's classification is read the morning after, when the campaign may have ended.
        """
        return self in (
            ControlOperation.MARK_LAUNCHED,
            ControlOperation.CLASSIFY,
            ControlOperation.LEASE_ACQUIRE,
            ControlOperation.LEASE_RELEASE,
        )

    @property
    def changes_the_lease(self) -> bool:
        """An operation committed with the box lease's change, by ``change_box_lease`` alone."""
        return self in (ControlOperation.LEASE_ACQUIRE, ControlOperation.LEASE_RELEASE)


class ProposalClassification(StrEnum):
    """What went wrong with a proposal, in the supervisor's reading (§9.4)."""

    SCOPE_TOO_LARGE = "scope_too_large"
    CRITERIA_NOT_CHECKABLE = "criteria_not_checkable"
    CONFLICTS_WITH_AN_EARLIER_INCREMENT = "conflicts_with_an_earlier_increment"
    AMBIGUOUS_MANIFEST_DELTA = "ambiguous_manifest_delta"
    #: A sound proposal implemented badly: not a feature-writing defect (§9.4).
    SOUND_PROPOSAL_BUILT_BADLY = "sound_proposal_built_badly"


class ControlOutcome(StrEnum):
    """Whether a control operation took effect. A refused operation is recorded too (§12a)."""

    APPLIED = "applied"
    REFUSED = "refused"


class RefusalReason(StrEnum):
    """Why a control operation was refused. Each refusal is a control-log row naming one."""

    #: The idempotency key was already used by an applied operation with different content.
    CONFLICTING_IDEMPOTENCY_KEY = "conflicting_idempotency_key"
    #: The caller acted on a state the campaign is no longer in.
    STALE_STATE = "stale_state"
    #: The lifecycle has no such move from the current state (§17).
    ILLEGAL_TRANSITION = "illegal_transition"
    #: The campaign has completed: nothing but a record-only operation follows (§12a, abort).
    CAMPAIGN_COMPLETED = "campaign_completed"
    #: A ruling bound to a proposal or an accepted tree that is no longer current (§9.2): an old
    #: approval cannot authorize changed scope.
    STALE_BINDING = "stale_binding"
    #: A ruling the increment gate does not take: ``approved_with_refinements`` would make the
    #: supervisor an author (§9.2).
    ILLEGAL_RULING = "illegal_ruling"
    #: The box lease (§9.3; #1802). The supervisor takes it only at the increment gate, while no
    #: run is in flight on the box, and only when no other supervisor holds it; only its holder
    #: gives it back.
    GATE_NOT_OPEN = "gate_not_open"
    RUN_IN_FLIGHT = "run_in_flight"
    BOX_HELD = "box_held"
    NOT_LEASE_HOLDER = "not_lease_holder"


class LaunchIntentState(StrEnum):
    """A launch intent's state (§15): written ``pending``, marked ``launched`` with its cycle."""

    PENDING = "pending"
    LAUNCHED = "launched"


# =============================================================================
# Exceptions
# =============================================================================


class CampaignError(Exception):
    """Base exception for campaign domain errors."""


class CampaignNotFoundError(CampaignError):
    """Raised when a campaign_id cannot be found."""


class CampaignExistsError(CampaignError):
    """Raised when a campaign is created under an id another creation already holds."""


class LaunchIntentNotFoundError(CampaignError):
    """Raised when a launch_id cannot be found."""


class ControlOperationRefused(CampaignError):
    """A control operation the registry refused, and recorded. ``entry`` is the refusal's row."""

    def __init__(self, entry: ControlLogEntry) -> None:
        self.entry = entry
        super().__init__(
            f"{entry.operation} on campaign {entry.campaign_id} refused: {entry.refusal}"
        )


# =============================================================================
# The campaign
# =============================================================================


def _require_text(owner: str, **values: str | None) -> None:
    for name, value in values.items():
        if not value or not value.strip():
            raise ValueError(f"{owner}.{name} is required")


@dataclass(frozen=True)
class CampaignObjective:
    """What the campaign is for (§15): the statement, the scope it may touch, how success reads.

    ``measurement`` is the success criterion in words; ``target_accepted_increments`` is its one
    machine reading: the accepted increments that meet it, read by §10 row 3 (§24ah). It is
    required of every new campaign; ``None`` only on a campaign stored before it existed, whose
    measurement has no reader and so never stops in success.
    """

    statement: str
    allowed_scope: tuple[str, ...]
    measurement: str
    target_accepted_increments: int | None

    def __post_init__(self) -> None:
        _require_text("CampaignObjective", statement=self.statement, measurement=self.measurement)
        target = self.target_accepted_increments
        if target is not None and (isinstance(target, bool) or not isinstance(target, int)):
            raise ValueError(
                f"CampaignObjective.target_accepted_increments must be an integer, got {target!r}"
            )
        if target is not None and target < 1:
            raise ValueError(
                f"CampaignObjective.target_accepted_increments must be >= 1, got {target}"
            )


#: Policy fields that must be at least 1: a campaign with no cycles, a zero ruling bound or a zero
#: interval cannot run, and a count the decision reads as reached at its value (§10) would be
#: reached before the first cycle. The others are counts a campaign may set to zero (no repair
#: cycles, say).
_POSITIVE_POLICY_FIELDS = frozenset(
    {
        "max_cycles",
        "max_elapsed_s",
        "budget_tokens",
        "max_rejected_proposals_in_row",
        "max_unaccepted_increments",
        "crew_ruling_bound_s",
        "owner_ruling_bound_s",
        "lease_expiry_s",
        "launch_blocked_interval_s",
        "launch_blocked_attempts",
    }
)


@dataclass(frozen=True)
class CampaignPolicy:
    """The campaign's limits and bounds (§9.5, §15). Every field is required: a limit is set from
    its basis and recorded, never defaulted (the 2.0 plan's limits ruling)."""

    # §9.5's limits
    max_cycles: int
    max_elapsed_s: int
    budget_tokens: int
    max_repair_cycles_per_increment: int
    max_retry_cycles_per_increment: int
    max_proposal_run_retries: int
    max_proposal_revisions: int
    max_rejected_proposals_in_row: int
    max_unaccepted_increments: int
    # §9.2's ruling bounds
    crew_ruling_bound_s: int
    owner_ruling_bound_s: int
    # §9.3's lease and launch-blocked handling
    lease_expiry_s: int
    launch_blocked_interval_s: int
    launch_blocked_attempts: int
    # The request profiles the calibration cycle and the proposal run use, and the squad that
    # runs every cycle the campaign launches
    calibration_profile: str
    proposal_profile: str
    squad_profile: str

    def __post_init__(self) -> None:
        for f in fields(self):
            if (
                f.type != "int"
            ):  # annotations are strings under `from __future__ import annotations`
                continue
            value = getattr(self, f.name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"CampaignPolicy.{f.name} must be an integer, got {value!r}")
            floor = 1 if f.name in _POSITIVE_POLICY_FIELDS else 0
            if value < floor:
                raise ValueError(f"CampaignPolicy.{f.name} must be >= {floor}, got {value}")
        _require_text(
            "CampaignPolicy",
            calibration_profile=self.calibration_profile,
            proposal_profile=self.proposal_profile,
            squad_profile=self.squad_profile,
        )


@dataclass(frozen=True)
class AcceptedTree:
    """The campaign's accepted tree (§7.1, §7.4): its verified identity and the cycle whose
    candidate it is. Every increment is proposed against it and every ruling binds to it; it
    changes only by a promotion (§12a)."""

    identity: str
    cycle_id: str

    def __post_init__(self) -> None:
        _require_text("AcceptedTree", identity=self.identity, cycle_id=self.cycle_id)


@dataclass(frozen=True)
class ProposalBinding:
    """What a ruling binds to (§9.2): the proposal's identity and the tree it was proposed
    against. A ruling whose binding is not the campaign's current one is refused as stale."""

    proposal_id: str
    version: int
    content_hash: str
    baseline_tree: str

    def __post_init__(self) -> None:
        _require_text(
            "ProposalBinding",
            proposal_id=self.proposal_id,
            content_hash=self.content_hash,
            baseline_tree=self.baseline_tree,
        )


@dataclass(frozen=True)
class SubmittedProposal:
    """The proposal at the increment gate: its binding, and the run that produced it."""

    binding: ProposalBinding
    cycle_id: str
    run_id: str


#: The rulings the increment gate takes, and the state each moves the campaign to (§9.2, §17).
#: ``approved_with_refinements`` is absent: refining would make the supervisor an author.
RULING_MOVES: dict[GateDecisionValue, CampaignState] = {
    GateDecisionValue.APPROVED: CampaignState.BUILDING,
    GateDecisionValue.RETURNED_FOR_REVISION: CampaignState.AT_PROPOSAL,
    GateDecisionValue.REJECTED: CampaignState.AT_PROPOSAL,
}


@dataclass(frozen=True)
class IncrementRuling:
    """A ruling at the increment gate: the gate decision, the binding it was made on, and the
    run whose gate it decides (the submitted proposal's)."""

    decision: GateDecisionValue
    binding: ProposalBinding
    run_id: str


@dataclass(frozen=True)
class Campaign:
    """A campaign (§15). Its ``state`` is always its last applied control-log row's next state:
    both are written in one transaction, so on restart the row read is the state (§12a)."""

    campaign_id: str
    project_id: str
    objective: CampaignObjective
    policy: CampaignPolicy
    state: CampaignState
    created_at: datetime
    created_by: str
    updated_at: datetime
    outcome: CampaignOutcome | None = None
    #: ``None`` until the calibration cycle's tree is promoted.
    accepted: AcceptedTree | None = None
    #: The proposal last submitted to the increment gate: the one a ruling binds to, and the
    #: one a repair or retry re-checks (§10a).
    proposal: SubmittedProposal | None = None

    def __post_init__(self) -> None:
        if (self.state is CampaignState.COMPLETED) != (self.outcome is not None):
            raise ValueError(
                f"campaign {self.campaign_id}: an outcome is set exactly when it is completed "
                f"(state {self.state}, outcome {self.outcome})"
            )


# =============================================================================
# The control log and launch intents
# =============================================================================


@dataclass(frozen=True)
class ControlLogEntry:
    """One control-log row (§13): written in the transaction of the state change it records.

    A refused operation is a row too, with ``outcome = refused``, its ``refusal``, and the state
    unchanged. ``seq`` orders a campaign's rows; ``launch_id`` names the intent this row wrote or
    marked, when it did.
    """

    entry_id: str
    campaign_id: str
    seq: int
    operation: ControlOperation
    actor: str
    actor_role: str
    reason: str
    target: str | None
    idempotency_key: str
    request_hash: str
    binding: dict
    outcome: ControlOutcome
    refusal: RefusalReason | None
    prior_state: CampaignState | None
    next_state: CampaignState
    committed_at: datetime
    launch_id: str | None = None


@dataclass(frozen=True)
class LaunchRequest:
    """The cycle a decision launches (§12b): its kind and the inputs it is created from."""

    cycle_kind: CycleKind
    cycle_request: dict = field(default_factory=dict)


@dataclass(frozen=True)
class LaunchIntent:
    """An outbox row (§12b, §15): written with its decision, drained by the launcher.

    ``launch_id`` is derived from the deciding row's id. The launcher creates the cycle with
    ``source_launch_id = launch_id``, then marks the intent ``launched`` with that cycle's id in a
    control-log transition of its own.
    """

    launch_id: str
    campaign_id: str
    decision_entry_id: str
    cycle_kind: CycleKind
    cycle_request: dict
    state: LaunchIntentState
    created_at: datetime
    cycle_id: str | None = None
    launched_at: datetime | None = None


@dataclass(frozen=True)
class CampaignTransition:
    """A control operation as its caller asks for it.

    ``next_state`` is ``None`` exactly for a record-only operation. ``expected_state`` is the
    state the caller acted on; when the campaign has moved since, the operation is refused as
    stale. ``launch`` writes a launch intent in the same transaction (§12b). ``accepted`` is the
    tree a promotion makes the campaign's accepted tree, and only a promotion carries one.
    ``submitted`` is the proposal a submission puts at the increment gate, and ``ruling`` the
    ruling on it; each operation, and only it, carries its own.
    """

    operation: ControlOperation
    actor: str
    actor_role: str
    reason: str
    idempotency_key: str
    next_state: CampaignState | None
    outcome: CampaignOutcome | None = None
    target: str | None = None
    binding: dict = field(default_factory=dict)
    expected_state: CampaignState | None = None
    launch: LaunchRequest | None = None
    accepted: AcceptedTree | None = None
    submitted: SubmittedProposal | None = None
    ruling: IncrementRuling | None = None

    def __post_init__(self) -> None:
        _require_text(
            "CampaignTransition",
            actor=self.actor,
            actor_role=self.actor_role,
            reason=self.reason,
            idempotency_key=self.idempotency_key,
        )
        if self.operation is ControlOperation.CREATE:
            raise ValueError("a campaign is created by create_campaign, not by a transition")
        if self.operation.records_only != (self.next_state is None):
            raise ValueError(
                f"{self.operation}: a record-only operation, and only one, leaves next_state unset"
            )
        if (self.next_state is CampaignState.COMPLETED) != (self.outcome is not None):
            raise ValueError(
                "an outcome is given exactly when the transition completes the campaign"
            )
        if self.launch is not None and self.operation.records_only:
            raise ValueError(f"{self.operation} records a fact; it cannot launch")
        if (self.operation is ControlOperation.PROMOTE) != (self.accepted is not None):
            raise ValueError("a promotion, and only a promotion, names the tree it accepts")
        if (self.operation is ControlOperation.SUBMIT) != (self.submitted is not None):
            raise ValueError("a submission, and only a submission, names the proposal it submits")
        if (self.operation is ControlOperation.RULE) != (self.ruling is not None):
            raise ValueError("a ruling, and only a ruling, carries its decision and binding")


@dataclass(frozen=True)
class TransitionResult:
    """What an applied (or replayed) control operation left: its row, the campaign after it, and
    the launch intent it wrote or marked. ``replayed`` is true when the idempotency key had
    already been applied with the same content, and nothing new happened."""

    entry: ControlLogEntry
    campaign: Campaign
    intent: LaunchIntent | None
    replayed: bool
