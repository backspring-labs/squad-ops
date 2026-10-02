"""The campaign lifecycle and the control log's rules (SIP-0109 §12a, §12b, §13, §17).

Pure functions, shared by every ``CampaignRegistryPort`` adapter, so the memory and Postgres
registries cannot disagree about what a control operation does. An adapter's only job is to
persist what these return atomically: the campaign, its control-log row and its launch intent in
one transaction.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
    LaunchIntent,
    LaunchIntentState,
    RefusalReason,
)

# =============================================================================
# The state machine (§17)
# =============================================================================

#: The states in which a campaign is doing its own work.
WORKING_STATES: frozenset[CampaignState] = frozenset(
    {
        CampaignState.CALIBRATING,
        CampaignState.AT_PROPOSAL,
        CampaignState.AWAITING_RULING,
        CampaignState.BUILDING,
        CampaignState.EVALUATING,
        CampaignState.PROMOTING,
        CampaignState.REPAIRING,
        CampaignState.RETRYING,
    }
)

#: The states in which a campaign waits on something outside it: a quiet box, or the owner's word.
#: §17: any state may enter one, and leaving one resumes work (the held action, the blocked launch,
#: or the action an escalation ruling names), which may be any working state.
HOLDING_STATES: frozenset[CampaignState] = frozenset(
    {CampaignState.LAUNCH_BLOCKED, CampaignState.PAUSED, CampaignState.ESCALATED}
)

#: §17's forward edges, one per arrow of its diagram.
_FORWARD: dict[CampaignState, frozenset[CampaignState]] = {
    CampaignState.DRAFT: frozenset({CampaignState.CALIBRATING}),
    CampaignState.CALIBRATING: frozenset({CampaignState.AT_PROPOSAL}),
    CampaignState.AT_PROPOSAL: frozenset({CampaignState.AWAITING_RULING}),
    # approve → building; returned_for_revision and rejected_at_gate → a proposal again
    CampaignState.AWAITING_RULING: frozenset({CampaignState.BUILDING, CampaignState.AT_PROPOSAL}),
    CampaignState.BUILDING: frozenset({CampaignState.EVALUATING}),
    # promote; repair; retry; or abandon the increment and propose
    CampaignState.EVALUATING: frozenset(
        {
            CampaignState.PROMOTING,
            CampaignState.REPAIRING,
            CampaignState.RETRYING,
            CampaignState.AT_PROPOSAL,
        }
    ),
    CampaignState.PROMOTING: frozenset({CampaignState.AT_PROPOSAL}),
    CampaignState.REPAIRING: frozenset({CampaignState.EVALUATING}),
    CampaignState.RETRYING: frozenset({CampaignState.EVALUATING}),
}


def _legal_targets(current: CampaignState) -> frozenset[CampaignState]:
    if current is CampaignState.COMPLETED:
        return frozenset()
    if current is CampaignState.DRAFT:
        # Nothing runs in a draft, so there is nothing to pause or escalate: it starts (its
        # calibration launch, which may be blocked by a busy box) or it is abandoned.
        return frozenset(
            {
                CampaignState.DRAFT,
                CampaignState.CALIBRATING,
                CampaignState.LAUNCH_BLOCKED,
                CampaignState.COMPLETED,
            }
        )
    # Every live state may stay put (a control operation that records without moving, such as a
    # second launch-blocked attempt or a proposal run's retry), enter a holding state, or complete.
    targets = set(_FORWARD.get(current, frozenset())) | HOLDING_STATES
    targets |= {CampaignState.COMPLETED, current}
    if current in HOLDING_STATES:
        targets |= WORKING_STATES
    return frozenset(targets)


#: current state → the states a control operation may move it to. Derived, so a state added to
#: the enum is either placed in the diagram's sets or has no moves at all.
LEGAL_TRANSITIONS: dict[CampaignState, frozenset[CampaignState]] = {
    state: _legal_targets(state) for state in CampaignState
}


# =============================================================================
# Ids and request identity
# =============================================================================


def new_campaign_id() -> str:
    return f"cmp_{uuid.uuid4().hex[:12]}"


def new_entry_id() -> str:
    return f"ctl_{uuid.uuid4().hex[:12]}"


def launch_id_for(entry_id: str) -> str:
    """The launch id derived from the deciding row's id (§12b): one decision, one launch id."""
    if not entry_id.startswith("ctl_"):
        raise ValueError(f"not a control-log entry id: {entry_id!r}")
    return f"lnc_{entry_id.removeprefix('ctl_')}"


def _digest(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def transition_request_hash(transition: CampaignTransition) -> str:
    """The content an idempotency key stands for: every field the caller supplied but the key.

    A repeat with the same key and the same hash is a replay; the same key with any other content
    is a conflict, refused and recorded (§12a).

    A record-only operation's content is the fact it records, its target and binding, and not
    who reported it: two launchers marking one launch with the same cycle are one fact, and the
    second replays. The same launch marked with a different cycle is still a conflict.
    """
    payload = dataclasses.asdict(transition)
    payload.pop("idempotency_key")
    if transition.operation.records_only:
        payload = {k: payload[k] for k in ("operation", "target", "binding")}
    return _digest(payload)


def creation_request_hash(campaign: Campaign, *, actor: str, actor_role: str, reason: str) -> str:
    return _digest(
        {
            "operation": ControlOperation.CREATE,
            "campaign_id": campaign.campaign_id,
            "project_id": campaign.project_id,
            "objective": dataclasses.asdict(campaign.objective),
            "policy": dataclasses.asdict(campaign.policy),
            "created_by": campaign.created_by,
            "actor": actor,
            "actor_role": actor_role,
            "reason": reason,
        }
    )


# =============================================================================
# Adjudication: replay, refuse, or apply
# =============================================================================


@dataclass(frozen=True)
class Adjudication:
    """What a control operation does. Exactly one of: replay the recorded row, refuse with a
    reason, or (both ``None``) apply."""

    replay: ControlLogEntry | None = None
    refusal: RefusalReason | None = None


def adjudicate(
    campaign: Campaign,
    transition: CampaignTransition,
    applied_with_key: ControlLogEntry | None,
) -> Adjudication:
    """Decide a control operation against the campaign's committed state.

    ``applied_with_key`` is the applied row already holding the transition's idempotency key in
    this campaign, if any. The idempotency check comes first, so a repeat that arrives after the
    campaign has moved on returns the recorded row instead of a stale refusal: a repeated ruling
    changes nothing (§12a).
    """
    if applied_with_key is not None:
        if applied_with_key.request_hash == transition_request_hash(transition):
            return Adjudication(replay=applied_with_key)
        return Adjudication(refusal=RefusalReason.CONFLICTING_IDEMPOTENCY_KEY)
    if transition.operation.records_only:
        return Adjudication()
    if campaign.state is CampaignState.COMPLETED:
        return Adjudication(refusal=RefusalReason.CAMPAIGN_COMPLETED)
    if transition.expected_state is not None and transition.expected_state is not campaign.state:
        return Adjudication(refusal=RefusalReason.STALE_STATE)
    assert transition.next_state is not None  # guaranteed by CampaignTransition for non-record ops
    if transition.next_state not in LEGAL_TRANSITIONS[campaign.state]:
        return Adjudication(refusal=RefusalReason.ILLEGAL_TRANSITION)
    return Adjudication()


def control_log_entry(
    campaign: Campaign,
    transition: CampaignTransition,
    *,
    entry_id: str,
    seq: int,
    committed_at: datetime,
    refusal: RefusalReason | None,
    launch_id: str | None,
) -> ControlLogEntry:
    """The row a control operation writes, applied or refused. A refusal leaves the state as it was."""
    applied = refusal is None
    next_state = (
        transition.next_state if applied and transition.next_state is not None else campaign.state
    )
    return ControlLogEntry(
        entry_id=entry_id,
        campaign_id=campaign.campaign_id,
        seq=seq,
        operation=transition.operation,
        actor=transition.actor,
        actor_role=transition.actor_role,
        reason=transition.reason,
        target=transition.target,
        idempotency_key=transition.idempotency_key,
        request_hash=transition_request_hash(transition),
        binding=dict(transition.binding),
        outcome=ControlOutcome.APPLIED if applied else ControlOutcome.REFUSED,
        refusal=refusal,
        prior_state=campaign.state,
        next_state=next_state,
        committed_at=committed_at,
        launch_id=launch_id,
    )


def creation_entry(
    campaign: Campaign,
    *,
    actor: str,
    actor_role: str,
    reason: str,
    idempotency_key: str,
    entry_id: str,
    committed_at: datetime,
) -> ControlLogEntry:
    """The campaign's first row: from no state to ``draft``.

    Raises:
        ValueError: If the campaign is not a fresh draft, or a required field is blank.
    """
    if campaign.state is not CampaignState.DRAFT or campaign.outcome is not None:
        raise ValueError(f"a campaign is created in draft, not {campaign.state}")
    for name, value in (
        ("actor", actor),
        ("actor_role", actor_role),
        ("reason", reason),
        ("idempotency_key", idempotency_key),
    ):
        if not value or not value.strip():
            raise ValueError(f"create_campaign: {name} is required")
    return ControlLogEntry(
        entry_id=entry_id,
        campaign_id=campaign.campaign_id,
        seq=1,
        operation=ControlOperation.CREATE,
        actor=actor,
        actor_role=actor_role,
        reason=reason,
        target=None,
        idempotency_key=idempotency_key,
        request_hash=creation_request_hash(
            campaign, actor=actor, actor_role=actor_role, reason=reason
        ),
        binding={},
        outcome=ControlOutcome.APPLIED,
        refusal=None,
        prior_state=None,
        next_state=CampaignState.DRAFT,
        committed_at=committed_at,
    )


def is_creation_replay(recorded: ControlLogEntry, candidate: ControlLogEntry) -> bool:
    """A second creation of an existing campaign replays it only when its key and content match."""
    return (
        recorded.idempotency_key == candidate.idempotency_key
        and recorded.request_hash == candidate.request_hash
    )


def applied_campaign(campaign: Campaign, transition: CampaignTransition, at: datetime) -> Campaign:
    """The campaign after an applied transition."""
    if transition.next_state is None:
        return campaign
    return dataclasses.replace(
        campaign,
        state=transition.next_state,
        outcome=transition.outcome,
        updated_at=at,
        # The accepted tree changes here and nowhere else (§12a).
        accepted=transition.accepted or campaign.accepted,
    )


def new_launch_intent(
    campaign_id: str, transition: CampaignTransition, entry_id: str, at: datetime
) -> LaunchIntent | None:
    """The outbox row an applied transition writes with its decision, when it launches (§12b)."""
    if transition.launch is None:
        return None
    return LaunchIntent(
        launch_id=launch_id_for(entry_id),
        campaign_id=campaign_id,
        decision_entry_id=entry_id,
        cycle_kind=transition.launch.cycle_kind,
        cycle_request=dict(transition.launch.cycle_request),
        state=LaunchIntentState.PENDING,
        created_at=at,
    )


#: The launcher's role on its own control-log rows.
LAUNCHER_ROLE = "launcher"


def mark_launched_transition(
    intent: LaunchIntent, cycle_id: str, *, actor: str
) -> CampaignTransition:
    """The control operation that marks an intent ``launched`` with its cycle (§12b).

    Keyed by the launch id, so a second launcher marking the same cycle replays, and a mark naming
    a different cycle is a conflict, refused and recorded: it would mean two cycles for one intent.
    """
    return CampaignTransition(
        operation=ControlOperation.MARK_LAUNCHED,
        actor=actor,
        actor_role=LAUNCHER_ROLE,
        reason="the launcher created the intent's cycle",
        idempotency_key=f"{intent.launch_id}:launched",
        next_state=None,
        target=intent.launch_id,
        binding={"cycle_id": cycle_id},
    )


def launched_intent(intent: LaunchIntent, cycle_id: str, at: datetime) -> LaunchIntent:
    return dataclasses.replace(
        intent, state=LaunchIntentState.LAUNCHED, cycle_id=cycle_id, launched_at=at
    )
