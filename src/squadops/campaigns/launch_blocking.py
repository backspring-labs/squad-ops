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
the guarantee "no launch beside an operator model" is read from the log.

**A refusal by the cycle-create path is different in kind.** Its preflight refuses a squad that
cannot run the workloads, a model the backend has not pulled or a sandbox out of step, and its
build refuses a project or profile that does not exist. Re-draining the same intent refuses it
again, so there is no interval to wait out: the campaign escalates on the first refusal, with the
intent still pending. The owner fixes what the refusal names and resumes without an action, which
returns the campaign to the state the launch was written from and re-attempts it; or aborts.
Before #1971 such an intent stayed pending and every drain refused it again, logged and unasked.

**The operator's lease is waited out without counting (§24dw, #2287).** The operator took the box
between campaigns and said for how long, so a launch that meets it is a handover, not a fault: the
campaign waits in ``launch_blocked`` with one row saying so, spends none of its attempts, never
escalates for it, and each sweep reads the box until the lease is released or expires. A refusal
after that (a model the operator left resident) is the box's first counted attempt.

**One create refusal is waited out instead (#3045):** no worker available for a tool the work
requires, every blocking finding ``skillset_availability``. A worker comes back, so the campaign waits
in ``launch_blocked`` as for the box, and each due attempt's create reads it afresh. Its attempts are
counted on the launch since the owner last resumed (``unavailable_launch``), because each attempt's
unblock ends the box's episode.
"""

from __future__ import annotations

from datetime import datetime

from squadops.campaigns.box import LaunchRefusal, LaunchVerdict
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


def _held(entry: ControlLogEntry) -> bool:
    """A row recording a launch that waits on the operator's lease, which counts no attempt."""
    return entry.binding.get("refusal") == str(LaunchRefusal.OPERATOR_HOLDS_THE_BOX)


def _counted(rows: list[ControlLogEntry]) -> int:
    return sum(1 for e in rows if not _held(e))


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
    refused_by: str = "the box",
) -> CampaignTransition:
    held = verdict.refusal is LaunchRefusal.OPERATOR_HOLDS_THE_BOX
    escalates = not held and attempt >= campaign.policy.launch_blocked_attempts
    reason = (
        f"launch {launch_id} waits for the operator's lease to be released or expire; it "
        f"counts no attempt ({attempt} of {campaign.policy.launch_blocked_attempts} spent)"
        if held
        else f"{refused_by} refused launch {launch_id} ({verdict.refusal}), attempt {attempt} of "
        f"{campaign.policy.launch_blocked_attempts}"
        + ("; escalated to the owner" if escalates else "")
    )
    return CampaignTransition(
        operation=ControlOperation.LAUNCH_BLOCKED,
        actor=actor,
        actor_role=LAUNCHER_ROLE,
        reason=reason,
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
    """The box refused a pending intent's launch: attempt 1, from the state that wrote it, or,
    when the operator holds the box, a wait that counts none (§24dw)."""
    if verdict.allowed:
        raise ValueError("an allowed launch is not blocked")
    return _blocked(
        campaign,
        verdict,
        launch_id=intent.launch_id,
        blocked_from=campaign.state.value,
        attempt=0 if verdict.refusal is LaunchRefusal.OPERATOR_HOLDS_THE_BOX else 1,
        actor=actor,
        key_seq=1,
    )


def retry_due(campaign: Campaign, log: list[ControlLogEntry], now: datetime) -> bool:
    """A blocked campaign's next attempt is due: at once after the owner's resume, at every
    sweep while it waits on the operator's lease (a release resumes it within one), otherwise
    ``launch_blocked_interval_s`` after the last attempt."""
    if campaign.state is not CampaignState.LAUNCH_BLOCKED:
        return False
    episode = _episode(log)
    if not episode or _held(episode[-1]):
        return True
    elapsed = (now - episode[-1].committed_at).total_seconds()
    return elapsed >= campaign.policy.launch_blocked_interval_s


def blocked_launch_step(
    campaign: Campaign, log: list[ControlLogEntry], verdict: LaunchVerdict, *, actor: str
) -> CampaignTransition | None:
    """The due attempt's row: the unblock when the box now allows the launch, otherwise the
    next refused attempt, which escalates at the policy's count. ``None`` while it still waits
    on the operator's lease and its last row already says so: a wait is one row, not one a
    sweep (§24dw)."""
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
    episode = _episode(log)
    if verdict.refusal is LaunchRefusal.OPERATOR_HOLDS_THE_BOX:
        if episode and _held(episode[-1]):
            return None
        attempt = _counted(episode)
    else:
        attempt = _counted(episode) + 1
    return _blocked(
        campaign,
        verdict,
        launch_id=launch_id,
        blocked_from=blocked_from,
        attempt=attempt,
        actor=actor,
        key_seq=seq,
    )


#: A refusal recorded on its row is cut to this many characters: a preflight joins every
#: blocking finding, and the row only has to say what to fix.
REFUSAL_LIMIT = 500


def unavailable_launch(
    campaign: Campaign,
    log: list[ControlLogEntry],
    intent: LaunchIntent,
    refusal: str,
    *,
    actor: str,
) -> CampaignTransition:
    """#3045: the cycle-create path refused ``intent``'s cycle only because no worker is
    available for a tool its work requires. The campaign waits in ``launch_blocked``, as for a
    box that refuses, and the sweep's due attempt unblocks it for the next drain to create the
    cycle again, which reads the worker afresh.

    **Its attempts are counted on the launch, not the episode.** Each attempt unblocks the
    campaign before the create that refuses it, which ends the box's episode, so an episode's
    count would restart at every attempt and never escalate. So every such row for this launch
    since the owner last resumed the campaign counts, and the attempt that reaches the policy's
    ``launch_blocked_attempts`` escalates. The owner's resume starts the count afresh, as it
    does a box's."""
    applied = _applied(log)
    since = next(
        (i for i in range(len(applied) - 1, -1, -1)
         if applied[i].operation is ControlOperation.RESUME),
        -1,
    )  # fmt: skip
    earlier = sum(
        1
        for e in applied[since + 1 :]
        if e.operation is ControlOperation.LAUNCH_BLOCKED
        and e.target == intent.launch_id
        and e.binding.get("refusal") == str(LaunchRefusal.WORKER_UNAVAILABLE)
    )
    seq = sum(1 for e in applied if e.operation is ControlOperation.LAUNCH_BLOCKED) + 1
    return _blocked(
        campaign,
        LaunchVerdict(LaunchRefusal.WORKER_UNAVAILABLE, (refusal[:REFUSAL_LIMIT],)),
        launch_id=intent.launch_id,
        blocked_from=campaign.state.value,
        attempt=earlier + 1,
        actor=actor,
        key_seq=seq,
        refused_by="the cycle-create path",
    )


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
