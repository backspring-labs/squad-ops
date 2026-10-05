"""SIP-0109 step 1 against real Postgres (#1799): migrations 1600 and 1610, the campaign registry
and exactly-once launch.

The unit tests run the memory twins. Only a real database proves what step 1 claims: a control
operation commits atomically with its state change, a refusal's row survives the refusal, a
restart reads the state from the log, and a crash or a race on either side of cycle creation
leaves exactly one cycle per launch intent (SIP-0109 §18 step 1, criteria 1 and 12c).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlparse

import pytest
import pytest_asyncio

from adapters.cycles import postgres_campaign_registry
from adapters.cycles.postgres_campaign_registry import PostgresCampaignRegistry
from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
from adapters.persistence.pool import create_pool
from squadops.campaigns.gate import ruling_transition, submission
from squadops.campaigns.launcher import CampaignLauncher
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignOutcome,
    CampaignState,
    ControlOperation,
    ControlOperationRefused,
    ControlOutcome,
    CycleKind,
    LaunchIntentState,
    LaunchRequest,
    ProposalBinding,
    RefusalReason,
    SubmittedProposal,
)
from squadops.cycles.models import GateDecisionValue
from tests.integration.conftest import integration_postgres_dsn
from tests.unit.campaigns.builders import campaign, cycle_for, move, quiet_box

pytestmark = [pytest.mark.docker, pytest.mark.domain_orchestration]

POSTGRES_URL = integration_postgres_dsn()  # #1099: never the deployment DB

asyncpg = pytest.importorskip("asyncpg")

S = CampaignState
CID = "cmp_it0000000001"
PROJECT = "campaign_it"


def _pg_available() -> bool:
    import socket

    url = urlparse(POSTGRES_URL)
    try:
        with socket.create_connection((url.hostname or "localhost", url.port or 5432), timeout=2):
            return True
    except OSError:
        return False


if not _pg_available():
    pytest.skip("Postgres not reachable at the integration DSN", allow_module_level=True)


@pytest_asyncio.fixture
async def pool():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=6)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    async with pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE campaign_launch_intents, campaign_control_log, campaigns CASCADE"
        )
        await conn.execute("DELETE FROM cycle_registry WHERE project_id = $1", PROJECT)
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def campaigns(pool):
    reg = PostgresCampaignRegistry(pool=pool)
    await reg.create_campaign(
        campaign(CID, project_id=PROJECT),
        actor="owner",
        actor_role="owner",
        reason="r",
        idempotency_key="create-1",
    )
    await reg.transition(CID, move(S.CALIBRATING, "k-cal"))
    return reg


def _launching(key: str):
    return move(S.AT_PROPOSAL, key, launch=LaunchRequest(CycleKind.INCREMENT, {"p": 1}))


async def _build(intent):
    await asyncio.sleep(0)
    return cycle_for(intent, project_id=PROJECT)


async def _cycle_rows(pool, launch_id: str) -> list:
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT cycle_id, campaign_id, kind FROM cycle_registry WHERE source_launch_id = $1",
            launch_id,
        )


async def test_a_restart_reads_the_campaign_its_log_and_its_intent_back(campaigns):
    """§12a: on restart the state is the log's last committed transition. A second registry on
    a second pool is the restart."""
    decided = await campaigns.transition(CID, _launching("k-decide"))

    fresh_pool = await create_pool(POSTGRES_URL, min_size=1, max_size=2)
    try:
        restarted = PostgresCampaignRegistry(pool=fresh_pool)
        stored = await restarted.get_campaign(CID)
        log = await restarted.control_log(CID)
        intent = await restarted.get_launch_intent(decided.intent.launch_id)
    finally:
        await fresh_pool.close()

    assert stored == decided.campaign
    assert stored.state is S.AT_PROPOSAL is log[-1].next_state
    assert log[-1] == decided.entry
    assert intent == decided.intent
    assert [e.seq for e in log] == [1, 2, 3]


async def test_the_definition_file_is_stored_on_the_creation_row_and_a_retry_replays(pool):
    """#1954, through the real registry: the creation row's binding carries the file, read back,
    and a retry with the same file replays while one with another file is refused."""
    from squadops.campaigns.models import CampaignDefinition, CampaignExistsError

    reg = PostgresCampaignRegistry(pool=pool)
    made = campaign("cmp_definition01", project_id=PROJECT)
    sent = CampaignDefinition("examples/03_group_run/campaigns/set-1.yaml", "d" * 64)

    async def create(definition):
        return await reg.create_campaign(
            made,
            actor="owner",
            actor_role="admin",
            reason="r",
            idempotency_key="create-def",
            definition=definition,
        )

    await create(sent)
    replay = await create(sent)
    with pytest.raises(CampaignExistsError):
        await create(CampaignDefinition(sent.path, "e" * 64))

    [created] = await reg.control_log("cmp_definition01")
    assert replay.replayed
    assert CampaignDefinition.from_binding(created.binding) == sent


async def test_a_refused_launch_is_stored_and_escalates(campaigns):
    """#1971, migration 1695: the control log's CHECK list admits ``launch_refused``. Bug caught:
    the operation added in Python but not in the schema, so the first refusal on a deploy fails
    its own row and the campaign stalls exactly as before."""
    from squadops.campaigns.launch_blocking import refused_launch

    decided = await campaigns.transition(CID, _launching("k-decide"))
    stored = await campaigns.get_campaign(CID)
    log = await campaigns.control_log(CID)

    result = await campaigns.transition(
        CID,
        refused_launch(stored, log, decided.intent, "PREFLIGHT_REJECTED: no model", actor="l"),
    )

    assert result.campaign.state is S.ESCALATED
    assert (await campaigns.control_log(CID))[-1].binding["refusal"] == (
        "PREFLIGHT_REJECTED: no model"
    )


async def test_a_promoted_tree_survives_a_restart_and_is_stored_whole(campaigns, pool):
    """§12a. Bug caught: the accepted columns left out of the transition's UPDATE, so the tree
    reads ``None`` after a restart; or half a tree stored."""
    tree = AcceptedTree("sha-cal", "cyc_cal000000001")
    await campaigns.transition(
        CID, move(S.CALIBRATING, "k-promote", operation=ControlOperation.PROMOTE, accepted=tree)
    )
    await campaigns.transition(CID, move(S.AT_PROPOSAL, "k-prop"))

    fresh_pool = await create_pool(POSTGRES_URL, min_size=1, max_size=2)
    try:
        stored = await PostgresCampaignRegistry(pool=fresh_pool).get_campaign(CID)
    finally:
        await fresh_pool.close()

    assert stored.accepted == tree
    async with pool.acquire() as conn:
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "UPDATE campaigns SET accepted_cycle_id = NULL WHERE campaign_id = $1", CID
            )


async def test_a_submitted_proposal_and_a_stale_rulings_refusal_are_stored(campaigns):
    """§9.2 on the database: the submission's proposal survives a restart, and the refusal
    values 1640 adds are accepted by the control log's CHECK. Bug caught: a migration whose list
    omits the new value, so every stale ruling fails at the database instead of being recorded."""
    binding = ProposalBinding("prop_1", 1, "hash-v1", "sha-cal")
    await campaigns.transition(
        CID,
        move(
            S.CALIBRATING,
            "k-promote",
            operation=ControlOperation.PROMOTE,
            accepted=AcceptedTree("sha-cal", "cyc_cal000000001"),
        ),
    )
    await campaigns.transition(CID, move(S.AT_PROPOSAL, "k-prop"))
    await campaigns.transition(
        CID, submission(S.AT_PROPOSAL, SubmittedProposal(binding, "cyc_inc", "run_p1"))
    )
    stale = ProposalBinding("prop_1", 1, "hash-edited", "sha-cal")
    with pytest.raises(ControlOperationRefused):
        await campaigns.transition(
            CID,
            ruling_transition(
                GateDecisionValue.APPROVED,
                stale,
                run_id="run_p1",
                actor="crew",
                actor_role="campaign-supervisor",
                reason="r",
                idempotency_key="k-rule",
            ),
        )

    fresh_pool = await create_pool(POSTGRES_URL, min_size=1, max_size=2)
    try:
        restarted = PostgresCampaignRegistry(pool=fresh_pool)
        stored = await restarted.get_campaign(CID)
        log = await restarted.control_log(CID)
    finally:
        await fresh_pool.close()

    assert stored.proposal == SubmittedProposal(binding, "cyc_inc", "run_p1")
    assert stored.state is S.AWAITING_RULING
    assert (log[-2].operation, log[-1].refusal) == (
        ControlOperation.SUBMIT,
        RefusalReason.STALE_BINDING,
    )


async def test_a_refusal_row_survives_the_refusal(campaigns):
    """Bug caught: the refusal raised inside the transaction, rolling its own row back."""
    await campaigns.transition(CID, _launching("k-decide"))
    with pytest.raises(ControlOperationRefused):
        await campaigns.transition(CID, move(S.AT_PROPOSAL, "k-decide", reason="other"))

    log = await campaigns.control_log(CID)
    assert (log[-1].outcome, log[-1].refusal) == (
        ControlOutcome.REFUSED,
        RefusalReason.CONFLICTING_IDEMPOTENCY_KEY,
    )


async def test_a_failure_inside_the_transaction_leaves_no_partial_write(campaigns, monkeypatch):
    """§13: the state change, its row and its intent commit together or not at all. The intent's
    insert fails after the row and the state are written; nothing of the three may remain."""

    def broken(intent):
        raise RuntimeError("injected: the intent insert fails")

    monkeypatch.setattr(postgres_campaign_registry, "_intent_args", broken)
    with pytest.raises(RuntimeError, match="injected"):
        await campaigns.transition(CID, _launching("k-decide"))

    assert (await campaigns.get_campaign(CID)).state is S.CALIBRATING
    assert [e.seq for e in await campaigns.control_log(CID)] == [1, 2]
    assert await campaigns.pending_launch_intents() == []


async def test_the_control_log_refuses_a_rewrite(campaigns, pool):
    async with pool.acquire() as conn:
        with pytest.raises(asyncpg.RaiseError, match="append-only"):
            await conn.execute("UPDATE campaign_control_log SET reason = 'rewritten'")
        with pytest.raises(asyncpg.RaiseError, match="append-only"):
            await conn.execute("DELETE FROM campaign_control_log")


async def test_one_key_from_two_connections_applies_once(campaigns, monkeypatch):
    """Two callers racing one ruling: the campaign's row lock serializes them, and the second
    replays the first's row.

    The race is forced: each caller waits, after taking the campaign, for the other to arrive.
    Under the row lock the second cannot arrive until the first has committed, so the first's
    wait times out and it proceeds alone. Without the lock both arrive, both read no applied
    row for the key, and both write one.
    """
    take_campaign = postgres_campaign_registry._locked_campaign
    arrivals: list[str] = []
    both_in = asyncio.Event()

    async def rendezvous(conn, campaign_id):
        taken = await take_campaign(conn, campaign_id)
        arrivals.append(campaign_id)
        if len(arrivals) == 2:
            both_in.set()
        try:
            await asyncio.wait_for(both_in.wait(), timeout=0.5)
        except TimeoutError:
            pass
        return taken

    monkeypatch.setattr(postgres_campaign_registry, "_locked_campaign", rendezvous)
    first, second = await asyncio.gather(
        campaigns.transition(CID, _launching("k-race")),
        campaigns.transition(CID, _launching("k-race")),
    )
    assert {first.replayed, second.replayed} == {False, True}
    assert first.entry == second.entry
    assert len(await campaigns.pending_launch_intents()) == 1


async def test_two_launchers_on_their_own_connections_create_one_cycle(campaigns, pool):
    """Criterion 12c: the unique source_launch_id decides the race between real connections."""
    decided = await campaigns.transition(CID, _launching("k-decide"))
    other_pool = await create_pool(POSTGRES_URL, min_size=1, max_size=2)
    try:
        launchers = [
            CampaignLauncher(
                campaigns,
                PostgresCycleRegistry(pool=pool),
                _build,
                actor="l1",
                box_verdict=quiet_box,
            ),
            CampaignLauncher(
                PostgresCampaignRegistry(pool=other_pool),
                PostgresCycleRegistry(pool=other_pool),
                _build,
                actor="l2",
                box_verdict=quiet_box,
            ),
        ]
        results = await asyncio.gather(*(launcher.drain() for launcher in launchers))
    finally:
        await other_pool.close()

    rows = await _cycle_rows(pool, decided.intent.launch_id)
    assert len(rows) == 1
    assert (rows[0]["campaign_id"], rows[0]["kind"]) == (CID, "increment")
    assert {r.cycle_id for batch in results for r in batch} == {rows[0]["cycle_id"]}
    intent = await campaigns.get_launch_intent(decided.intent.launch_id)
    assert (intent.state, intent.cycle_id) == (LaunchIntentState.LAUNCHED, rows[0]["cycle_id"])


class _CrashAfterCreate(PostgresCycleRegistry):
    crashed = False

    async def create_cycle_for_launch(self, cycle, launch_id):
        stored = await super().create_cycle_for_launch(cycle, launch_id)
        if not self.crashed:
            self.crashed = True
            raise RuntimeError("injected: crash after the cycle is created")
        return stored


async def test_a_crash_after_creation_is_found_by_the_next_drain(campaigns, pool):
    decided = await campaigns.transition(CID, _launching("k-decide"))
    cycles = _CrashAfterCreate(pool=pool)

    with pytest.raises(RuntimeError, match="injected"):
        await CampaignLauncher(campaigns, cycles, _build, actor="l1", box_verdict=quiet_box).drain()
    [first] = await _cycle_rows(pool, decided.intent.launch_id)

    [launched] = await CampaignLauncher(
        campaigns, cycles, _build, actor="l1", box_verdict=quiet_box
    ).drain()

    assert [r["cycle_id"] for r in await _cycle_rows(pool, decided.intent.launch_id)] == [
        first["cycle_id"]
    ]
    assert launched.cycle_id == first["cycle_id"] and not launched.created


async def test_a_cycle_no_campaign_launched_is_stored_as_before(pool):
    """§19: a cycle without a campaign gains only null columns."""
    cycles = PostgresCycleRegistry(pool=pool)
    plain = cycle_for(
        type("I", (), {"campaign_id": None, "cycle_kind": CycleKind.INCREMENT})(),
        project_id=PROJECT,
    )
    plain = type(plain)(**{**plain.__dict__, "kind": None})
    await cycles.create_cycle(plain)

    stored = await cycles.get_cycle(plain.cycle_id)
    async with pool.acquire() as conn:
        launch = await conn.fetchval(
            "SELECT source_launch_id FROM cycle_registry WHERE cycle_id = $1", plain.cycle_id
        )
    assert (stored.campaign_id, stored.kind, launch) == (None, None, None)
    assert stored == plain


async def test_no_launch_is_drained_after_an_abort(campaigns):
    await campaigns.transition(CID, _launching("k-decide"))
    await campaigns.transition(
        CID,
        move(
            S.COMPLETED,
            "k-abort",
            operation=ControlOperation.ABORT,
            outcome=CampaignOutcome.ABORTED,
        ),
    )
    assert await campaigns.pending_launch_intents() == []


async def test_a_campaigns_launch_intents_read_back_in_order_in_any_state(campaigns, pool):
    """An abort reads these to cancel what the campaign launched (§12a)."""
    first = await campaigns.transition(CID, _launching("k-1"))
    await CampaignLauncher(
        campaigns, PostgresCycleRegistry(pool=pool), _build, actor="l1", box_verdict=quiet_box
    ).drain()
    await campaigns.transition(CID, move(S.AWAITING_RULING, "k-2"))
    await campaigns.transition(
        CID, move(S.AT_PROPOSAL, "k-3", launch=LaunchRequest(CycleKind.INCREMENT))
    )

    intents = await campaigns.launch_intents(CID)

    assert [(i.launch_id == first.intent.launch_id, i.state) for i in intents] == [
        (True, LaunchIntentState.LAUNCHED),
        (False, LaunchIntentState.PENDING),
    ]


async def test_a_ruling_overdue_row_is_stored_and_the_gate_is_listed_by_state(campaigns):
    """§9.2, §9.5 on the database (§24ae): the sweep reads the campaigns waiting on a ruling,
    and writes the bound's row. Bugs caught: a migration whose CHECK omits ``ruling_overdue``, so
    every overdue gate fails at the database; a listing that misses a campaign in the state, or
    returns one that is not."""
    from datetime import timedelta

    from squadops.campaigns.gate import gate_opened_at, ruling_overdue_transitions

    binding = ProposalBinding("prop_1", 1, "hash-v1", "sha-cal")
    await campaigns.transition(
        CID,
        move(
            S.CALIBRATING,
            "k-promote",
            operation=ControlOperation.PROMOTE,
            accepted=AcceptedTree("sha-cal", "cyc_cal000000001"),
        ),
    )
    await campaigns.transition(CID, move(S.AT_PROPOSAL, "k-prop"))
    await campaigns.transition(
        CID, submission(S.AT_PROPOSAL, SubmittedProposal(binding, "cyc_inc", "run_p1"))
    )

    [waiting] = await campaigns.campaigns_in_state(S.AWAITING_RULING)
    log = await campaigns.control_log(CID)
    [row] = ruling_overdue_transitions(
        waiting, log, gate_opened_at(log) + timedelta(seconds=waiting.policy.ruling_bound_s)
    )
    result = await campaigns.transition(CID, row)

    assert (result.entry.operation, result.entry.binding["bound_s"]) == (
        ControlOperation.RULING_OVERDUE,
        waiting.policy.ruling_bound_s,
    )
    assert [c.campaign_id for c in await campaigns.campaigns_in_state(S.AWAITING_RULING)] == [CID]
    assert await campaigns.campaigns_in_state(S.BUILDING) == []


# --- the box lease (SIP-0109 §9.3; #1802, migration 1690) -----------------------------------------


def _lease_change(op, held_by: str, key: str):
    from squadops.campaigns.models import CampaignTransition, ControlOperation

    binding = {"held_by": held_by}
    if op is ControlOperation.LEASE_ACQUIRE:
        binding["expires_in_s"] = 900
    return CampaignTransition(
        operation=op,
        actor=held_by,
        actor_role="campaign-supervisor",
        reason="the increment gate",
        idempotency_key=key,
        next_state=None,
        binding=binding,
    )


async def _two_at_the_gate(pool) -> PostgresCampaignRegistry:
    reg = PostgresCampaignRegistry(pool=pool)
    for cid in ("cmp_lease0000001", "cmp_lease0000002"):
        await reg.create_campaign(
            campaign(cid, project_id=PROJECT),
            actor="o",
            actor_role="o",
            reason="r",
            idempotency_key=cid,
        )
        for i, state in enumerate((S.CALIBRATING, S.AT_PROPOSAL, S.AWAITING_RULING)):
            await reg.transition(cid, move(state, f"{cid}-{i}"))
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO box_lease (box_id, holder, held_by, acquired_at) "
            "VALUES ('box', 'squad', 'squadops', now()) ON CONFLICT (box_id) DO NOTHING"
        )
    return reg


async def test_two_supervisors_racing_for_the_box_leave_exactly_one_holding_it(pool):
    """Bug caught: two acquires that both read a free box and both commit, so two supervisors
    each believe they hold it. The lease's row lock serializes them: one applies, the other is
    refused as box_held and recorded."""
    from squadops.campaigns.models import ControlOperation, ControlOperationRefused

    reg = await _two_at_the_gate(pool)
    other = PostgresCampaignRegistry(pool=pool)
    outcomes = await asyncio.gather(
        reg.change_box_lease(
            "cmp_lease0000001",
            _lease_change(ControlOperation.LEASE_ACQUIRE, "crew-a", "a"),
            runs_in_flight=(),
        ),
        other.change_box_lease(
            "cmp_lease0000002",
            _lease_change(ControlOperation.LEASE_ACQUIRE, "crew-b", "b"),
            runs_in_flight=(),
        ),
        return_exceptions=True,
    )

    refused = [o for o in outcomes if isinstance(o, ControlOperationRefused)]
    assert len(refused) == 1 and str(refused[0].entry.refusal) == "box_held"
    holder = (await reg.box_lease()).held_by
    winner = "cmp_lease0000001" if holder == "crew-a" else "cmp_lease0000002"
    assert (await reg.box_lease()).campaign_id == winner


async def test_the_holder_gives_the_box_back_and_the_lease_reads_back_as_the_squads(pool):
    """Bug caught: a release that records its row but leaves the stored lease as it was."""
    from squadops.campaigns.box import LeaseHolder
    from squadops.campaigns.models import ControlOperation

    reg = await _two_at_the_gate(pool)
    await reg.change_box_lease(
        "cmp_lease0000001",
        _lease_change(ControlOperation.LEASE_ACQUIRE, "crew", "a"),
        runs_in_flight=(),
    )
    await reg.change_box_lease(
        "cmp_lease0000001",
        _lease_change(ControlOperation.LEASE_RELEASE, "crew", "r"),
        runs_in_flight=(),
    )
    lease = await PostgresCampaignRegistry(pool=pool).box_lease()
    assert (lease.holder, lease.held_by, lease.expires_at) == (LeaseHolder.SQUAD, "squadops", None)
