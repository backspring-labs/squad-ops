"""The box: who holds it, and whether it is quiet (SIP-0109 §9.3; #1802).

Pure decisions. One owner of the Spark at a time, the squad or the supervisor, held as a lease
with an expiry. Every cycle launch and run start refuses while the supervisor holds it, and every
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

from squadops.campaigns.models import Campaign, CampaignState, ControlOperation, RefusalReason


class LeaseHolder(StrEnum):
    SQUAD = "squad"
    SUPERVISOR = "supervisor"


@dataclass(frozen=True)
class BoxLease:
    """The box's one lease. The squad's holds no expiry; the supervisor's always does, so a
    supervisor that crashes cannot hold the box forever (§9.3)."""

    holder: LeaseHolder
    held_by: str
    acquired_at: datetime
    expires_at: datetime | None = None
    #: The campaign whose checkpoint the supervisor holds the box for.
    campaign_id: str | None = None

    def __post_init__(self) -> None:
        if (self.holder is LeaseHolder.SUPERVISOR) != (self.expires_at is not None):
            raise ValueError("a supervisor's lease, and only one, carries an expiry")

    def supervisor_holds(self, now: datetime) -> bool:
        return self.holder is LeaseHolder.SUPERVISOR and now < self.expires_at

    def expired(self, now: datetime) -> bool:
        return self.holder is LeaseHolder.SUPERVISOR and now >= self.expires_at


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
    why)."""

    engine: str
    loaded: tuple[Model, ...] | None
    error: str = ""


@dataclass(frozen=True)
class Quietness:
    quiet: bool
    reasons: tuple[str, ...] = ()


def box_quietness(declared: Iterable[Model], readings: Iterable[EngineReading]) -> Quietness:
    """Quiet when every engine was read and every model it has loaded is declared by the active
    deploy record. Every reason is reported, not the first."""
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
    BOX_NOT_QUIET = "box_not_quiet"


@dataclass(frozen=True)
class LaunchVerdict:
    refusal: LaunchRefusal | None
    reasons: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.refusal is None


def launch_verdict(lease: BoxLease | None, quietness: Quietness, now: datetime) -> LaunchVerdict:
    """Whether a cycle may launch on the box (§9.3). The lease is read first: a supervisor
    holding the box refuses whatever the box reads. An expired supervisor lease no longer holds
    it, but the launch still needs a quiet box, so a crew model left resident refuses it."""
    if lease is not None and lease.supervisor_holds(now):
        return LaunchVerdict(
            LaunchRefusal.SUPERVISOR_HOLDS_THE_BOX,
            (f"the supervisor ({lease.held_by}) holds the box until {lease.expires_at:%H:%M:%SZ}",),
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
      while no run is in flight on the box; and only when no other supervisor holds it. The
      same holder for the same campaign renews.
    - **Release:** only the holder of a live supervisor lease gives it back. A lease that has
      expired, or the squad's own, is released by anyone: it holds nothing.
    """
    holds = current is not None and current.supervisor_holds(now)
    mine = holds and current.campaign_id == campaign.campaign_id and current.held_by == held_by
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
            current is not None
            and current.supervisor_holds(now)
            and current.campaign_id == campaign_id
            and current.held_by == binding["held_by"]
        )
        return BoxLease(
            holder=LeaseHolder.SUPERVISOR,
            held_by=binding["held_by"],
            acquired_at=current.acquired_at if renewing else now,
            expires_at=now + timedelta(seconds=int(binding["expires_in_s"])),
            campaign_id=campaign_id,
        )
    if operation is ControlOperation.LEASE_RELEASE:
        return BoxLease(holder=LeaseHolder.SQUAD, held_by=SQUAD_HOLDER_ID, acquired_at=now)
    raise ValueError(f"{operation} does not change the lease")
