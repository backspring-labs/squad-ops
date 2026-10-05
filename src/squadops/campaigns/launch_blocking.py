"""A launch the box refused, and its retries (SIP-0109 §9.3; #1802); and a launch the
cycle-create path refused, which escalates at once (§24e item 5, §24ba; #1971).

Pure decisions. When the box refuses a campaign's launch (the supervisor holds it, or it is not
quiet), the campaign waits in ``launch_blocked`` with the intent still pending. The sweep
re-attempts at the policy's ``launch_blocked_interval_s``: a box that now allows it returns the
campaign to the state its launch was written from, and the launcher launches the intent; a box
that still refuses writes the next attempt's row; and the attempt that reaches
``launch_blocked_attempts`` escalates. After an escalation only the owner resumes, and that
resume returns the campaign to ``launch_blocked`` with its attempts counted afresh.

Every attempt is a control-log row carrying its attempt number, the refusal and its reasons, so
the guarantee "no launch beside a crew model" is read from the log.

**A refusal by the cycle-create path is different in kind.** Its preflight refuses a squad that
cannot run the workloads, a model the backend has not pulled or a sandbox out of step, and its
build refuses a project or profile that does not exist. Re-draining the same intent refuses it
again, so there is no interval to wait out: the campaign escalates on the first refusal, with the
intent still pending. The owner fixes what the refusal names and resumes without an action, which
returns the campaign to the state the launch was written from and re-attempts it; or aborts.
Before #1971 such an intent stayed pending and every drain refused it again, logged and unasked.
"""

from __future__ import annotations

from datetime import datetime

from squadops.campaigns.box import LaunchVerdict
from squadops.campaigns.lifecycle import LAUNCHER_ROLE
from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
    LaunchIntent,
)


def _applied(log: list[ControlLogEntry]) -> list[ControlLogEntry]:
    return [e for e in log if e.outcome is ControlOutcome.APPLIED]


def _episode(log: list[ControlLogEntry]) -> list[ControlLogEntry]:
    """The blocked rows since the campaign last entered ``launch_blocked`` from outside it: an
    owner's resume after an escalation starts the count afresh."""
    rows: list[ControlLogEntry] = []
    for entry in reversed(_applied(log)):
        if entry.operation is ControlOperation.LAUNCH_BLOCKED:
            rows.append(entry)
            continue
        if entry.operation.records_only:
            continue
        break
    return list(reversed(rows))


def _last_blocked(log: list[ControlLogEntry]) -> ControlLogEntry | None:
    return next(
        (e for e in reversed(_applied(log)) if e.operation is ControlOperation.LAUNCH_BLOCKED),
        None,
    )


def _blocked(
    campaign: Campaign,
    verdict: LaunchVerdict,
    *,
    launch_id: str,
    blocked_from: str,
    attempt: int,
    actor: str,
    key_seq: int,
) -> CampaignTransition:
    escalates = attempt >= campaign.policy.launch_blocked_attempts
    return CampaignTransition(
        operation=ControlOperation.LAUNCH_BLOCKED,
        actor=actor,
        actor_role=LAUNCHER_ROLE,
        reason=(
            f"the box refused launch {launch_id} ({verdict.refusal}), attempt {attempt} of "
            f"{campaign.policy.launch_blocked_attempts}"
            + ("; escalated to the owner" if escalates else "")
        ),
        idempotency_key=f"{launch_id}:blocked:{key_seq}",
        next_state=CampaignState.ESCALATED if escalates else CampaignState.LAUNCH_BLOCKED,
        expected_state=campaign.state,
        target=launch_id,
        binding={
            "launch_id": launch_id,
            "attempt": attempt,
            "blocked_from": blocked_from,
            "refusal": str(verdict.refusal),
            "reasons": list(verdict.reasons),
        },
    )


def first_refusal(
    campaign: Campaign, intent: LaunchIntent, verdict: LaunchVerdict, *, actor: str
) -> CampaignTransition:
    """The box refused a pending intent's launch: attempt 1, from the state that wrote it."""
    if verdict.allowed:
        raise ValueError("an allowed launch is not blocked")
    return _blocked(
        campaign,
        verdict,
        launch_id=intent.launch_id,
        blocked_from=campaign.state.value,
        attempt=1,
        actor=actor,
        key_seq=1,
    )


def retry_due(campaign: Campaign, log: list[ControlLogEntry], now: datetime) -> bool:
    """A blocked campaign's next attempt is due: at once after the owner's resume, otherwise
    ``launch_blocked_interval_s`` after the last attempt."""
    if campaign.state is not CampaignState.LAUNCH_BLOCKED:
        return False
    episode = _episode(log)
    if not episode:
        return True
    elapsed = (now - episode[-1].committed_at).total_seconds()
    return elapsed >= campaign.policy.launch_blocked_interval_s


def blocked_launch_step(
    campaign: Campaign, log: list[ControlLogEntry], verdict: LaunchVerdict, *, actor: str
) -> CampaignTransition:
    """The due attempt's row: the unblock when the box now allows the launch, otherwise the
    next refused attempt, which escalates at the policy's count."""
    last = _last_blocked(log)
    if last is None:
        raise ValueError(f"campaign {campaign.campaign_id} is blocked with no blocked launch")
    launch_id = str(last.binding["launch_id"])
    blocked_from = str(last.binding["blocked_from"])
    seq = sum(1 for e in _applied(log) if e.operation is ControlOperation.LAUNCH_BLOCKED) + 1
    if verdict.allowed:
        return CampaignTransition(
            operation=ControlOperation.LAUNCH_UNBLOCKED,
            actor=actor,
            actor_role=LAUNCHER_ROLE,
            reason=f"the box now allows launch {launch_id}",
            idempotency_key=f"{launch_id}:unblocked:{seq}",
            next_state=CampaignState(blocked_from),
            expected_state=CampaignState.LAUNCH_BLOCKED,
            target=launch_id,
            binding={"launch_id": launch_id, "blocked_from": blocked_from},
        )
    return _blocked(
        campaign,
        verdict,
        launch_id=launch_id,
        blocked_from=blocked_from,
        attempt=len(_episode(log)) + 1,
        actor=actor,
        key_seq=seq,
    )


#: A refusal recorded on its row is cut to this many characters: a preflight joins every
#: blocking finding, and the row only has to say what to fix.
REFUSAL_LIMIT = 500


def refused_launch(
    campaign: Campaign,
    log: list[ControlLogEntry],
    intent: LaunchIntent,
    refusal: str,
    *,
    actor: str,
) -> CampaignTransition:
    """The cycle-create path refused ``intent``'s cycle: the campaign escalates, from the state
    the launch was written from, with the intent still pending. Keyed by the launch and its
    refusal count, so a drain that dies before the row commits replays it, and a refusal after
    the owner's resume is a new row."""
    seq = 1 + sum(
        1
        for e in _applied(log)
        if e.operation is ControlOperation.LAUNCH_REFUSED and e.target == intent.launch_id
    )
    recorded = refusal[:REFUSAL_LIMIT]
    return CampaignTransition(
        operation=ControlOperation.LAUNCH_REFUSED,
        actor=actor,
        actor_role=LAUNCHER_ROLE,
        reason=(
            f"the cycle-create path refused launch {intent.launch_id}: {recorded}; "
            "escalated to the owner"
        ),
        idempotency_key=f"{intent.launch_id}:refused:{seq}",
        next_state=CampaignState.ESCALATED,
        expected_state=campaign.state,
        target=intent.launch_id,
        binding={
            "launch_id": intent.launch_id,
            "refused_from": campaign.state.value,
            "refusal": recorded,
        },
    )


def escalated_by_a_refused_launch(
    campaign: Campaign, log: list[ControlLogEntry]
) -> tuple[CampaignState, str] | None:
    """The state a refused launch was written from, and its launch id, when the campaign is
    escalated because the cycle-create path refused it (#1971); otherwise ``None``. The owner's
    resume returns it there, and the next drain re-attempts the launch still pending."""
    if campaign.state is not CampaignState.ESCALATED:
        return None
    moved = [e for e in _applied(log) if not e.operation.records_only]
    if moved and moved[-1].operation is ControlOperation.LAUNCH_REFUSED:
        return CampaignState(moved[-1].binding["refused_from"]), str(moved[-1].binding["launch_id"])
    return None


def escalated_by_a_blocked_launch(campaign: Campaign, log: list[ControlLogEntry]) -> bool:
    """The campaign is escalated because its launch stayed blocked past the policy's count. The
    owner's resume then returns it to ``launch_blocked`` rather than naming an action: the
    intent it would launch is still pending."""
    if campaign.state is not CampaignState.ESCALATED:
        return False
    moved = [e for e in _applied(log) if not e.operation.records_only]
    return bool(moved) and moved[-1].operation is ControlOperation.LAUNCH_BLOCKED
