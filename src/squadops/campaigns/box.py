"""The box: who holds it, and whether it is quiet (SIP-0109 §9.3; #1802).

Pure decisions. One owner of the Spark at a time, held as a lease with an expiry: the squad, the
supervisor at a campaign's increment gate, or, between campaigns, the operator (§24dw; #2287).
Every cycle launch and run start refuses while the supervisor or the operator holds it, and every
launch also needs a quiet box: every model an engine has loaded is a model the active deploy
record declares (#1720). An engine that cannot be read is not quiet: the check fails closed.

What is read, and by whom, is the caller's: the deploy record from the registry, each engine's
loaded-model listing through its port. This module never reads anything.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    ControlOperation,
    ControlOutcome,
    RefusalReason,
)

#: The box's floors, defined once: SIP-0111 §5.6 (Q7), the memory an engine switch requires
#: available before an engine loads and after it, and the disk floor the box runs under (the 2.0
#: day plan's disk policy). ``/health/host`` reports against them, and so will S's switch and the
#: console's Host panel (#2204).
MEMORY_FLOOR_BEFORE_LOAD_BYTES = 90 * 2**30
MEMORY_FLOOR_AFTER_LOAD_BYTES = 16 * 2**30
DISK_FLOOR_BYTES = 150 * 10**9


class LeaseHolder(StrEnum):
    SQUAD = "squad"
    SUPERVISOR = "supervisor"
    #: §24dw (#2287): the operator, for its own inference between campaigns, held by no campaign.
    OPERATOR = "operator"


@dataclass(frozen=True)
class BoxLease:
    """The box's one lease. The squad's holds no expiry; the supervisor's and the operator's
    always do, so a holder that crashes cannot hold the box forever (§9.3, §24dw). Only the
    supervisor's names a campaign."""

    holder: LeaseHolder
    held_by: str
    acquired_at: datetime
    expires_at: datetime | None = None
    #: The campaign whose checkpoint the supervisor holds the box for.
    campaign_id: str | None = None

    def __post_init__(self) -> None:
        if (self.holder is not LeaseHolder.SQUAD) != (self.expires_at is not None):
            raise ValueError("a supervisor's or operator's lease, and only one, carries an expiry")
        if self.holder is LeaseHolder.OPERATOR and self.campaign_id is not None:
            raise ValueError("the operator's lease is held outside every campaign")

    def holds(self, now: datetime) -> bool:
        """Whether someone other than the squad holds the box now."""
        return self.expires_at is not None and now < self.expires_at

    def supervisor_holds(self, now: datetime) -> bool:
        return self.holder is LeaseHolder.SUPERVISOR and self.holds(now)

    def operator_holds(self, now: datetime) -> bool:
        return self.holder is LeaseHolder.OPERATOR and self.holds(now)

    def expired(self, now: datetime) -> bool:
        return self.expires_at is not None and now >= self.expires_at


@dataclass(frozen=True)
class Model:
    """A model by name, and by digest where its engine reports one."""

    name: str
    digest: str | None = None

    def matches(self, declared: Model) -> bool:
        if self.name != declared.name:
            return False
        return self.digest is None or declared.digest is None or self.digest == declared.digest


@dataclass(frozen=True)
class EngineReading:
    """One engine's loaded models, or ``None`` when it could not be read (and ``error`` says
    why). ``in_flight`` is the requests it is serving now, where the engine reports them
    (SIP-0111 §5.5), and ``None`` where it does not. It is read, and an engine whose count
    cannot be read is unread, but a count above zero does not make the box loud: a shared
    engine serves the operator and the squad at once (SIP-0109 §24cu)."""

    engine: str
    loaded: tuple[Model, ...] | None
    error: str = ""
    in_flight: int | None = None


@dataclass(frozen=True)
class Quietness:
    quiet: bool
    reasons: tuple[str, ...] = ()


def box_quietness(declared: Iterable[Model], readings: Iterable[EngineReading]) -> Quietness:
    """Quiet when every engine was read and every model it has loaded is declared by the active
    deploy record. An engine serving requests is still quiet when it holds only declared models:
    the requests are the operator's or another run's on the same model, and the engine serves them
    side by side (SIP-0109 §24cu, which retired SIP-0111 §5.5's idle-only launch). Every reason
    is reported, not the first."""
    declared = tuple(declared)
    reasons: list[str] = []
    for reading in readings:
        if reading.loaded is None:
            reasons.append(f"engine {reading.engine} could not be read: {reading.error or '?'}")
            continue
        for model in reading.loaded:
            if not any(model.matches(d) for d in declared):
                reasons.append(
                    f"engine {reading.engine} has {model.name}"
                    + (f" ({model.digest[:12]})" if model.digest else "")
                    + " loaded, which the deploy record does not declare"
                )
    return Quietness(not reasons, tuple(reasons))


class LaunchRefusal(StrEnum):
    SUPERVISOR_HOLDS_THE_BOX = "supervisor_holds_the_box"
    #: §24dw (#2287): the operator holds the box between campaigns. A campaign's launch waits for
    #: the release or the expiry without spending its attempts (``launch_blocking``).
    OPERATOR_HOLDS_THE_BOX = "operator_holds_the_box"
    BOX_NOT_QUIET = "box_not_quiet"
    #: #3045: the cycle-create path refused the launch only because no worker is available for
    #: a tool its work requires. Not the box's own refusal: its attempts are counted on the
    #: launch (``launch_blocking.unavailable_launch``), and each is a fresh create.
    WORKER_UNAVAILABLE = "worker_unavailable"


@dataclass(frozen=True)
class LaunchVerdict:
    refusal: LaunchRefusal | None
    reasons: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.refusal is None


def launch_verdict(lease: BoxLease | None, quietness: Quietness, now: datetime) -> LaunchVerdict:
    """Whether a cycle may launch on the box (§9.3). The lease is read first: a supervisor or
    operator holding the box refuses whatever the box reads. An expired lease no longer holds
    it, but the launch still needs a quiet box, so an operator model left resident refuses it."""
    if lease is not None and lease.supervisor_holds(now):
        return LaunchVerdict(
            LaunchRefusal.SUPERVISOR_HOLDS_THE_BOX,
            (f"the supervisor ({lease.held_by}) holds the box until {lease.expires_at:%H:%M:%SZ}",),
        )
    if lease is not None and lease.operator_holds(now):
        return LaunchVerdict(
            LaunchRefusal.OPERATOR_HOLDS_THE_BOX,
            (f"the operator ({lease.held_by}) holds the box until {lease.expires_at:%H:%M:%SZ}",),
        )
    if not quietness.quiet:
        return LaunchVerdict(LaunchRefusal.BOX_NOT_QUIET, quietness.reasons)
    return LaunchVerdict(None)


# =============================================================================
# The lease's changes (§9.3; #1802): who may take it, who may give it back
# =============================================================================

#: Who holds the box between supervisor leases.
SQUAD_HOLDER_ID = "squadops"


def lease_refusal(
    operation: ControlOperation,
    current: BoxLease | None,
    campaign: Campaign,
    held_by: str,
    now: datetime,
    runs_in_flight: tuple[str, ...],
) -> RefusalReason | None:
    """Whether the lease may change as asked, read against the committed lease.

    - **Acquire:** only at the campaign's increment gate (its proposal run has ended); only
      while no run is in flight on the box; and only when no other supervisor, and not the
      operator, holds it. The same holder for the same campaign renews.
    - **Release:** only the holder of a live supervisor lease gives it back. A lease that has
      expired, or the squad's own, is released by anyone: it holds nothing.
    """
    held = current if current is not None and current.holds(now) else None
    holds = held is not None
    mine = (
        held is not None
        and held.holder is LeaseHolder.SUPERVISOR
        and held.campaign_id == campaign.campaign_id
        and held.held_by == held_by
    )
    if operation is ControlOperation.LEASE_ACQUIRE:
        if campaign.state is not CampaignState.AWAITING_RULING:
            return RefusalReason.GATE_NOT_OPEN
        if runs_in_flight:
            return RefusalReason.RUN_IN_FLIGHT
        if holds and not mine:
            return RefusalReason.BOX_HELD
        return None
    if operation is ControlOperation.LEASE_RELEASE:
        return RefusalReason.NOT_LEASE_HOLDER if holds and not mine else None
    raise ValueError(f"{operation} does not change the lease")


def leased(
    operation: ControlOperation,
    current: BoxLease | None,
    campaign_id: str,
    binding: dict,
    now: datetime,
) -> BoxLease:
    """The lease an applied change leaves. An acquire holds the box until ``expires_in_s`` from
    now; a renewal keeps its first acquisition time. A release returns the box to the squad."""
    if operation is ControlOperation.LEASE_ACQUIRE:
        renewing = (
            current
            if current is not None
            and current.supervisor_holds(now)
            and current.campaign_id == campaign_id
            and current.held_by == binding["held_by"]
            else None
        )
        return BoxLease(
            holder=LeaseHolder.SUPERVISOR,
            held_by=binding["held_by"],
            acquired_at=renewing.acquired_at if renewing is not None else now,
            expires_at=now + timedelta(seconds=int(binding["expires_in_s"])),
            campaign_id=campaign_id,
        )
    if operation is ControlOperation.LEASE_RELEASE:
        return BoxLease(holder=LeaseHolder.SQUAD, held_by=SQUAD_HOLDER_ID, acquired_at=now)
    raise ValueError(f"{operation} does not change the lease")


# =============================================================================
# The operator's lease, outside every campaign (§24dw; #2287)
# =============================================================================

#: The longest the operator may hold the box at one acquire: a renewal extends it from then.
OPERATOR_LEASE_MAX_S = 3600

#: The states a campaign launches nothing from by itself: not yet started, held for a person, or
#: ended. Any other is live, and could launch while the operator holds the box.
QUIESCENT_CAMPAIGN_STATES = frozenset(
    {CampaignState.DRAFT, CampaignState.PAUSED, CampaignState.ESCALATED, CampaignState.COMPLETED}
)


class OperatorLeaseOperation(StrEnum):
    ACQUIRE = "acquire"
    RELEASE = "release"


class OperatorLeaseRefusal(StrEnum):
    #: A run is running or queued on the box.
    RUN_IN_FLIGHT = "run_in_flight"
    #: A campaign is live: it could launch while the operator holds the box.
    CAMPAIGN_LIVE = "campaign_live"
    #: The supervisor, or another operator, holds it.
    BOX_HELD = "box_held"
    #: A release by someone who doesn't hold the box.
    NOT_LEASE_HOLDER = "not_lease_holder"
    #: The key was used for a different change.
    CONFLICTING_IDEMPOTENCY_KEY = "conflicting_idempotency_key"


@dataclass(frozen=True)
class OperatorLeaseChange:
    """An acquire or release the operator asks for. ``expires_in_s`` is an acquire's."""

    operation: OperatorLeaseOperation
    actor: str
    actor_role: str
    reason: str
    idempotency_key: str
    expires_in_s: int | None = None

    def __post_init__(self) -> None:
        acquiring = self.operation is OperatorLeaseOperation.ACQUIRE
        if acquiring != (self.expires_in_s is not None):
            raise ValueError("an acquire, and only an acquire, says how long it holds the box")
        if self.expires_in_s is not None and not 0 < self.expires_in_s <= OPERATOR_LEASE_MAX_S:
            raise ValueError(
                f"expires_in_s is 1 to {OPERATOR_LEASE_MAX_S}, not {self.expires_in_s}"
            )
        if not self.reason.strip():
            raise ValueError("a lease change says why")


@dataclass(frozen=True)
class OperatorLeaseEntry:
    """One row of the operator lease's log: the change asked for, applied or refused, with why."""

    seq: int
    operation: OperatorLeaseOperation
    outcome: ControlOutcome
    actor: str
    actor_role: str
    reason: str
    idempotency_key: str
    committed_at: datetime
    expires_in_s: int | None = None
    refusal: OperatorLeaseRefusal | None = None
    #: What the refusal read: the runs, the live campaigns, who holds the box.
    reasons: tuple[str, ...] = ()


def operator_lease_refusal(
    change: OperatorLeaseChange,
    current: BoxLease | None,
    now: datetime,
    *,
    runs_in_flight: tuple[str, ...],
    live_campaigns: tuple[tuple[str, CampaignState], ...],
) -> tuple[OperatorLeaseRefusal | None, tuple[str, ...]]:
    """Whether the operator's lease may change as asked, read against the committed lease, and
    what the refusal read.

    - **Acquire:** only while nobody else holds the box, no run is running or queued, and no
      campaign is live (``QUIESCENT_CAMPAIGN_STATES``). The same operator renews while it holds
      the box, whatever has queued behind it since: a run or launch that queued waits on it.
    - **Release:** only the operator holding a live lease gives it back. A lease that has
      expired, or the squad's own, is released by anyone: it holds nothing.
    """
    held = current if current is not None and current.holds(now) else None
    mine = held is not None and held.holder is LeaseHolder.OPERATOR and held.held_by == change.actor
    if change.operation is OperatorLeaseOperation.RELEASE:
        if held is not None and not mine:
            return OperatorLeaseRefusal.NOT_LEASE_HOLDER, (_holder_line(held),)
        return None, ()
    if mine:
        return None, ()
    if held is not None:
        return OperatorLeaseRefusal.BOX_HELD, (_holder_line(held),)
    if runs_in_flight:
        return OperatorLeaseRefusal.RUN_IN_FLIGHT, tuple(f"run {r}" for r in runs_in_flight)
    live = [(c, state) for c, state in live_campaigns if state not in QUIESCENT_CAMPAIGN_STATES]
    if live:
        return OperatorLeaseRefusal.CAMPAIGN_LIVE, tuple(f"campaign {c} is {s}" for c, s in live)
    return None, ()


def _holder_line(lease: BoxLease) -> str:
    return f"the {lease.holder} ({lease.held_by}) holds the box until {lease.expires_at:%H:%M:%SZ}"


def operator_leased(
    change: OperatorLeaseChange, current: BoxLease | None, now: datetime
) -> BoxLease:
    """The lease an applied change leaves. An acquire holds the box until ``expires_in_s`` from
    now; a renewal keeps its first acquisition time. A release returns the box to the squad."""
    if change.operation is OperatorLeaseOperation.RELEASE:
        return BoxLease(holder=LeaseHolder.SQUAD, held_by=SQUAD_HOLDER_ID, acquired_at=now)
    if change.expires_in_s is None:
        raise ValueError("an acquire says how long it holds the box")
    renewing = (
        current
        if current is not None and current.operator_holds(now) and current.held_by == change.actor
        else None
    )
    return BoxLease(
        holder=LeaseHolder.OPERATOR,
        held_by=change.actor,
        acquired_at=renewing.acquired_at if renewing is not None else now,
        expires_at=now + timedelta(seconds=change.expires_in_s),
    )


@dataclass(frozen=True)
class OperatorLeaseResult:
    """An applied, or replayed, change: its row and the lease it left (``None`` only for a
    replay on a box whose lease row has gone, as a truncated table would leave it)."""

    entry: OperatorLeaseEntry
    replayed: bool
    lease: BoxLease | None


class OperatorLeaseRefused(Exception):
    """The change was refused. ``entry`` is its row, recorded first, except for a key that was
    used for another change, which has no row of its own (``seq`` 0)."""

    def __init__(self, entry: OperatorLeaseEntry) -> None:
        super().__init__(f"{entry.operation} refused: {entry.refusal}")
        self.entry = entry


def operator_lease_entry(
    change: OperatorLeaseChange,
    seq: int,
    now: datetime,
    refusal: OperatorLeaseRefusal | None = None,
    reasons: tuple[str, ...] = (),
) -> OperatorLeaseEntry:
    return OperatorLeaseEntry(
        seq=seq,
        operation=change.operation,
        outcome=ControlOutcome.REFUSED if refusal else ControlOutcome.APPLIED,
        actor=change.actor,
        actor_role=change.actor_role,
        reason=change.reason,
        idempotency_key=change.idempotency_key,
        committed_at=now,
        expires_in_s=change.expires_in_s,
        refusal=refusal,
        reasons=reasons,
    )


def replays(entry: OperatorLeaseEntry, change: OperatorLeaseChange) -> bool:
    """Whether ``change`` asks for what its key's row recorded: a retry, not a new change."""
    return (entry.operation, entry.actor, entry.reason, entry.expires_in_s) == (
        change.operation,
        change.actor,
        change.reason,
        change.expires_in_s,
    )
