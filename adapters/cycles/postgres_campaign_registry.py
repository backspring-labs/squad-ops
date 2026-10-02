"""Campaigns in Postgres (SIP-0109 §16, #1799), over the runtime's one pool (#577).

Each control operation runs in one transaction that holds the campaign's row lock, so its state
change, its control-log row and any launch intent commit together or not at all, and operations
on one campaign serialize (§13). A refusal's row commits before the refusal is raised. Every rule
is ``squadops.campaigns.lifecycle``'s; this adapter only stores.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import asyncpg

from squadops.campaigns import lifecycle
from squadops.campaigns.models import (
    AcceptedTree,
    Campaign,
    CampaignExistsError,
    CampaignNotFoundError,
    CampaignObjective,
    CampaignOutcome,
    CampaignPolicy,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOperationRefused,
    ControlOutcome,
    CycleKind,
    LaunchIntent,
    LaunchIntentNotFoundError,
    LaunchIntentState,
    RefusalReason,
    TransitionResult,
)
from squadops.ports.cycles.campaign_registry import CampaignRegistryPort

_CAMPAIGN_COLUMNS = (
    "campaign_id, project_id, objective, policy, state, outcome, created_at, created_by, "
    "updated_at, accepted_identity, accepted_cycle_id"
)
_ENTRY_COLUMNS = (
    "entry_id, campaign_id, seq, operation, actor, actor_role, reason, target, idempotency_key, "
    "request_hash, binding, outcome, refusal, prior_state, next_state, committed_at, launch_id"
)
_INTENT_COLUMNS = (
    "launch_id, campaign_id, decision_entry_id, cycle_kind, cycle_request, state, created_at, "
    "cycle_id, launched_at"
)


def _now() -> datetime:
    return datetime.now(UTC)


def _placeholders(columns: str) -> str:
    return ",".join(f"${i}" for i in range(1, len(columns.split(",")) + 1))


class PostgresCampaignRegistry(CampaignRegistryPort):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # --- reads ---

    async def get_campaign(self, campaign_id: str) -> Campaign:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_CAMPAIGN_COLUMNS} FROM campaigns WHERE campaign_id = $1", campaign_id
            )
        if row is None:
            raise CampaignNotFoundError(f"Campaign not found: {campaign_id}")
        return _row_to_campaign(row)

    async def list_campaigns(self, project_id: str) -> list[Campaign]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_CAMPAIGN_COLUMNS} FROM campaigns WHERE project_id = $1 "
                "ORDER BY created_at DESC",
                project_id,
            )
        return [_row_to_campaign(r) for r in rows]

    async def control_log(self, campaign_id: str) -> list[ControlLogEntry]:
        async with self._pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM campaigns WHERE campaign_id = $1", campaign_id
            )
            if not exists:
                raise CampaignNotFoundError(f"Campaign not found: {campaign_id}")
            rows = await conn.fetch(
                f"SELECT {_ENTRY_COLUMNS} FROM campaign_control_log WHERE campaign_id = $1 "
                "ORDER BY seq",
                campaign_id,
            )
        return [_row_to_entry(r) for r in rows]

    async def pending_launch_intents(self) -> list[LaunchIntent]:
        columns = ", ".join(f"i.{c.strip()}" for c in _INTENT_COLUMNS.split(","))
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {columns} FROM campaign_launch_intents i "
                "JOIN campaigns c ON c.campaign_id = i.campaign_id "
                "WHERE i.state = 'pending' AND c.state <> 'completed' "
                "ORDER BY i.created_at, i.launch_id"
            )
        return [_row_to_intent(r) for r in rows]

    async def launch_intents(self, campaign_id: str) -> list[LaunchIntent]:
        async with self._pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM campaigns WHERE campaign_id = $1", campaign_id
            )
            if not exists:
                raise CampaignNotFoundError(f"Campaign not found: {campaign_id}")
            rows = await conn.fetch(
                f"SELECT {_INTENT_COLUMNS} FROM campaign_launch_intents WHERE campaign_id = $1 "
                "ORDER BY created_at, launch_id",
                campaign_id,
            )
        return [_row_to_intent(r) for r in rows]

    async def get_launch_intent(self, launch_id: str) -> LaunchIntent:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_INTENT_COLUMNS} FROM campaign_launch_intents WHERE launch_id = $1",
                launch_id,
            )
        if row is None:
            raise LaunchIntentNotFoundError(f"Launch intent not found: {launch_id}")
        return _row_to_intent(row)

    # --- control operations ---

    async def create_campaign(
        self,
        campaign: Campaign,
        *,
        actor: str,
        actor_role: str,
        reason: str,
        idempotency_key: str,
    ) -> TransitionResult:
        entry = lifecycle.creation_entry(
            campaign,
            actor=actor,
            actor_role=actor_role,
            reason=reason,
            idempotency_key=idempotency_key,
            entry_id=lifecycle.new_entry_id(),
            committed_at=_now(),
        )
        async with self._pool.acquire() as conn, conn.transaction():
            inserted = await conn.fetchval(
                f"INSERT INTO campaigns ({_CAMPAIGN_COLUMNS}) "
                f"VALUES ({_placeholders(_CAMPAIGN_COLUMNS)}) "
                "ON CONFLICT (campaign_id) DO NOTHING RETURNING campaign_id",
                *_campaign_args(campaign),
            )
            if inserted is None:
                recorded = _row_to_entry(
                    await conn.fetchrow(
                        f"SELECT {_ENTRY_COLUMNS} FROM campaign_control_log "
                        "WHERE campaign_id = $1 AND seq = 1",
                        campaign.campaign_id,
                    )
                )
                if not lifecycle.is_creation_replay(recorded, entry):
                    raise CampaignExistsError(
                        f"campaign {campaign.campaign_id} exists with a different creation"
                    )
                stored = await _locked_campaign(conn, campaign.campaign_id)
                return TransitionResult(entry=recorded, campaign=stored, intent=None, replayed=True)
            await _insert_entry(conn, entry)
        return TransitionResult(entry=entry, campaign=campaign, intent=None, replayed=False)

    async def transition(
        self, campaign_id: str, transition: CampaignTransition
    ) -> TransitionResult:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                campaign = await _locked_campaign(conn, campaign_id)
                outcome = await _commit(conn, campaign, transition, marks=None)
        return _result_or_raise(outcome)

    async def mark_launch_intent_launched(
        self, launch_id: str, cycle_id: str, *, actor: str
    ) -> TransitionResult:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                campaign_id = await conn.fetchval(
                    "SELECT campaign_id FROM campaign_launch_intents WHERE launch_id = $1",
                    launch_id,
                )
                if campaign_id is None:
                    raise LaunchIntentNotFoundError(f"Launch intent not found: {launch_id}")
                # The campaign's lock first, as every control operation takes it, then the intent's.
                campaign = await _locked_campaign(conn, campaign_id)
                intent = _row_to_intent(
                    await conn.fetchrow(
                        f"SELECT {_INTENT_COLUMNS} FROM campaign_launch_intents "
                        "WHERE launch_id = $1 FOR UPDATE",
                        launch_id,
                    )
                )
                transition = lifecycle.mark_launched_transition(intent, cycle_id, actor=actor)
                outcome = await _commit(conn, campaign, transition, marks=(intent, cycle_id))
        return _result_or_raise(outcome)


# =============================================================================
# The transaction's body
# =============================================================================


def _result_or_raise(outcome: TransitionResult | ControlLogEntry) -> TransitionResult:
    """Raise a refusal only after its row's transaction has committed."""
    if isinstance(outcome, ControlLogEntry):
        raise ControlOperationRefused(outcome)
    return outcome


async def _locked_campaign(conn: asyncpg.Connection, campaign_id: str) -> Campaign:
    row = await conn.fetchrow(
        f"SELECT {_CAMPAIGN_COLUMNS} FROM campaigns WHERE campaign_id = $1 FOR UPDATE",
        campaign_id,
    )
    if row is None:
        raise CampaignNotFoundError(f"Campaign not found: {campaign_id}")
    return _row_to_campaign(row)


async def _commit(
    conn: asyncpg.Connection,
    campaign: Campaign,
    transition: CampaignTransition,
    *,
    marks: tuple[LaunchIntent, str] | None,
) -> TransitionResult | ControlLogEntry:
    """Adjudicate and write, inside the caller's transaction and under the campaign's lock.
    Returns the result, or the refusal's row for the caller to raise after commit."""
    recorded_row = await conn.fetchrow(
        f"SELECT {_ENTRY_COLUMNS} FROM campaign_control_log "
        "WHERE campaign_id = $1 AND idempotency_key = $2 AND outcome = 'applied'",
        campaign.campaign_id,
        transition.idempotency_key,
    )
    recorded = _row_to_entry(recorded_row) if recorded_row else None
    verdict = lifecycle.adjudicate(campaign, transition, recorded)
    if verdict.replay is not None:
        intent = None
        if verdict.replay.launch_id:
            intent = _row_to_intent(
                await conn.fetchrow(
                    f"SELECT {_INTENT_COLUMNS} FROM campaign_launch_intents WHERE launch_id = $1",
                    verdict.replay.launch_id,
                )
            )
        return TransitionResult(
            entry=verdict.replay, campaign=campaign, intent=intent, replayed=True
        )

    now = _now()
    entry_id = lifecycle.new_entry_id()
    seq = await conn.fetchval(
        "SELECT COALESCE(MAX(seq), 0) + 1 FROM campaign_control_log WHERE campaign_id = $1",
        campaign.campaign_id,
    )
    if verdict.refusal is not None:
        entry = lifecycle.control_log_entry(
            campaign,
            transition,
            entry_id=entry_id,
            seq=seq,
            committed_at=now,
            refusal=verdict.refusal,
            launch_id=None,
        )
        await _insert_entry(conn, entry)
        return entry

    if marks is not None:
        intent = lifecycle.launched_intent(marks[0], marks[1], now)
    else:
        intent = lifecycle.new_launch_intent(campaign.campaign_id, transition, entry_id, now)
    entry = lifecycle.control_log_entry(
        campaign,
        transition,
        entry_id=entry_id,
        seq=seq,
        committed_at=now,
        refusal=None,
        launch_id=intent.launch_id if intent is not None else None,
    )
    updated = lifecycle.applied_campaign(campaign, transition, now)

    await _insert_entry(conn, entry)
    if updated is not campaign:
        await conn.execute(
            "UPDATE campaigns SET state = $2, outcome = $3, updated_at = $4, "
            "accepted_identity = $5, accepted_cycle_id = $6 WHERE campaign_id = $1",
            updated.campaign_id,
            updated.state.value,
            updated.outcome.value if updated.outcome else None,
            updated.updated_at,
            *_accepted_args(updated.accepted),
        )
    if marks is not None:
        await conn.execute(
            "UPDATE campaign_launch_intents SET state = $2, cycle_id = $3, launched_at = $4 "
            "WHERE launch_id = $1",
            intent.launch_id,
            intent.state.value,
            intent.cycle_id,
            intent.launched_at,
        )
    elif intent is not None:
        await conn.execute(
            f"INSERT INTO campaign_launch_intents ({_INTENT_COLUMNS}) "
            f"VALUES ({_placeholders(_INTENT_COLUMNS)})",
            *_intent_args(intent),
        )
    return TransitionResult(entry=entry, campaign=updated, intent=intent, replayed=False)


async def _insert_entry(conn: asyncpg.Connection, entry: ControlLogEntry) -> None:
    await conn.execute(
        f"INSERT INTO campaign_control_log ({_ENTRY_COLUMNS}) "
        f"VALUES ({_placeholders(_ENTRY_COLUMNS)})",
        entry.entry_id,
        entry.campaign_id,
        entry.seq,
        entry.operation.value,
        entry.actor,
        entry.actor_role,
        entry.reason,
        entry.target,
        entry.idempotency_key,
        entry.request_hash,
        entry.binding,
        entry.outcome.value,
        entry.refusal.value if entry.refusal else None,
        entry.prior_state.value if entry.prior_state else None,
        entry.next_state.value,
        entry.committed_at,
        entry.launch_id,
    )


# =============================================================================
# Row mapping
# =============================================================================


def _campaign_args(campaign: Campaign) -> tuple:
    return (
        campaign.campaign_id,
        campaign.project_id,
        dataclasses.asdict(campaign.objective),
        dataclasses.asdict(campaign.policy),
        campaign.state.value,
        campaign.outcome.value if campaign.outcome else None,
        campaign.created_at,
        campaign.created_by,
        campaign.updated_at,
        *_accepted_args(campaign.accepted),
    )


def _accepted_args(accepted: AcceptedTree | None) -> tuple[str | None, str | None]:
    return (accepted.identity, accepted.cycle_id) if accepted else (None, None)


def _intent_args(intent: LaunchIntent) -> tuple:
    return (
        intent.launch_id,
        intent.campaign_id,
        intent.decision_entry_id,
        intent.cycle_kind.value,
        intent.cycle_request,
        intent.state.value,
        intent.created_at,
        intent.cycle_id,
        intent.launched_at,
    )


def _row_to_campaign(row: asyncpg.Record) -> Campaign:
    objective = row["objective"]
    return Campaign(
        campaign_id=row["campaign_id"],
        project_id=row["project_id"],
        objective=CampaignObjective(
            statement=objective["statement"],
            allowed_scope=tuple(objective["allowed_scope"]),
            measurement=objective["measurement"],
        ),
        policy=CampaignPolicy(**row["policy"]),
        state=CampaignState(row["state"]),
        created_at=row["created_at"],
        created_by=row["created_by"],
        updated_at=row["updated_at"],
        outcome=CampaignOutcome(row["outcome"]) if row["outcome"] else None,
        accepted=(
            AcceptedTree(row["accepted_identity"], row["accepted_cycle_id"])
            if row["accepted_identity"]
            else None
        ),
    )


def _row_to_entry(row: asyncpg.Record) -> ControlLogEntry:
    return ControlLogEntry(
        entry_id=row["entry_id"],
        campaign_id=row["campaign_id"],
        seq=row["seq"],
        operation=ControlOperation(row["operation"]),
        actor=row["actor"],
        actor_role=row["actor_role"],
        reason=row["reason"],
        target=row["target"],
        idempotency_key=row["idempotency_key"],
        request_hash=row["request_hash"],
        binding=dict(row["binding"]),
        outcome=ControlOutcome(row["outcome"]),
        refusal=RefusalReason(row["refusal"]) if row["refusal"] else None,
        prior_state=CampaignState(row["prior_state"]) if row["prior_state"] else None,
        next_state=CampaignState(row["next_state"]),
        committed_at=row["committed_at"],
        launch_id=row["launch_id"],
    )


def _row_to_intent(row: asyncpg.Record) -> LaunchIntent:
    return LaunchIntent(
        launch_id=row["launch_id"],
        campaign_id=row["campaign_id"],
        decision_entry_id=row["decision_entry_id"],
        cycle_kind=CycleKind(row["cycle_kind"]),
        cycle_request=dict(row["cycle_request"]),
        state=LaunchIntentState(row["state"]),
        created_at=row["created_at"],
        cycle_id=row["cycle_id"],
        launched_at=row["launched_at"],
    )
