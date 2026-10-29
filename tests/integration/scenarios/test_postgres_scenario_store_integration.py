"""#2413 against real Postgres: migration 1900's tables hold a suite and a campaign's pin.

The unit tests run the memory twin; only this proves the adapter's columns, the JSONB round trip
of a suite's content, the digest recomputed on read, the pin's foreign key and the approval's
check constraint agree with the tables the migration creates.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio

from adapters.persistence.pool import create_pool
from adapters.scenarios.postgres_scenario_store import PostgresScenarioStore
from squadops.scenarios.models import CampaignSuitePin, SuiteState, parse_suite
from squadops.scenarios.quality import (
    LintReading,
    NotMeasured,
    PageMeasure,
    QualityReading,
    QualityStatus,
)
from squadops.scenarios.suites import approve_suite, draft_suite, pin_campaign_suite
from tests.integration.conftest import integration_postgres_dsn
from tests.unit.scenarios.suite_fixtures import SUITE

pytestmark = [pytest.mark.docker, pytest.mark.domain_orchestration]

POSTGRES_URL = integration_postgres_dsn()  # #1099: never the deployment DB

asyncpg = pytest.importorskip("asyncpg")


def _pg_available() -> bool:
    import socket

    try:
        with socket.create_connection(("localhost", 5432), timeout=2):
            return True
    except OSError:
        return False


if not _pg_available():
    pytest.skip("Postgres not reachable on localhost:5432", allow_module_level=True)

T0 = datetime(2026, 10, 18, 20, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def store():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=4)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    async with pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE scenario_evidence, quality_remeasures, scenario_evaluations, "
            "campaign_scenario_suites, scenario_suites"
        )
    yield PostgresScenarioStore(pool=pool), pool
    await pool.close()


async def test_a_suite_is_drafted_approved_and_pinned_and_reads_back_whole(store):
    scenarios, _ = store
    suite = parse_suite(SUITE)

    await draft_suite(scenarios, suite, actor="supervisor", at=T0)
    approved = await approve_suite(scenarios, suite.digest, actor="owner", at=T0)
    pin = await pin_campaign_suite(
        scenarios, "cmp_pg0000000001", suite.digest, draft=True, actor="owner", at=T0
    )

    assert await scenarios.get_suite(suite.digest) == approved
    assert approved.state is SuiteState.APPROVED and approved.suite == suite
    assert [r.digest for r in await scenarios.list_suites()] == [suite.digest]
    assert await scenarios.get_pin("cmp_pg0000000001") == pin


async def test_a_row_whose_content_no_longer_hashes_to_its_key_is_refused(store):
    """Bug caught: a suite edited in place in the table served under its old digest, so a
    pinned campaign ran checks its digest no longer names."""
    scenarios, pool = store
    suite = parse_suite(SUITE)
    await draft_suite(scenarios, suite, actor="supervisor", at=T0)
    edited = suite.content()
    edited["scenarios"][1]["checks"][0]["equals"] = 422
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE scenario_suites SET content = $1 WHERE digest = $2", edited, suite.digest
        )

    with pytest.raises(ValueError, match="no longer hashes to its key"):
        await scenarios.get_suite(suite.digest)


async def test_the_tables_refuse_a_pin_to_nothing_and_an_approval_without_its_approver(store):
    """The migration's own constraints, beneath the rules: a pin naming no stored suite, and an
    approved row that names no approver."""
    scenarios, _ = store
    suite = parse_suite(SUITE)
    record = await draft_suite(scenarios, suite, actor="supervisor", at=T0)

    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await scenarios.save_pin(CampaignSuitePin("cmp_pg0000000002", "f" * 64, "owner", T0))
    with pytest.raises(asyncpg.CheckViolationError):
        await scenarios.save_suite(replace(record, state=SuiteState.APPROVED))


async def test_an_evaluation_reads_back_whole_and_the_table_refuses_a_commit_for_a_tree(store):
    """#2415. Bug caught: outcomes lost in the JSONB round trip, a cycle's runs read out of order,
    or a Git commit stored where a tree identity belongs (SIP-0112 §8.2.1)."""
    from squadops.scenarios.evaluation import (
        Applicability,
        BlockedReason,
        ScenarioOutcome,
        ScenarioResult,
        evaluation_record,
    )

    scenarios, pool = store
    suite = parse_suite(SUITE)
    await draft_suite(scenarios, suite, actor="supervisor", at=T0)
    first, second = suite.scenarios
    outcomes = (
        ScenarioOutcome(
            first.scenario_id,
            first.version,
            first.goal,
            Applicability.APPLICABLE,
            ScenarioResult.FAILED,
            steps_taken=2,
            first_failing_step=2,
            elapsed_seconds=1.5,
        ),
        ScenarioOutcome(
            second.scenario_id,
            second.version,
            second.goal,
            Applicability.APPLICABLE,
            ScenarioResult.BLOCKED_UNVERIFIED,
            blocked_reason=BlockedReason.START_FAILED,
        ),
    )
    # #2416: a measured reading and a not-measured one, each through the JSONB column and back.
    readings = {
        22: QualityReading(
            QualityStatus.MEASURED,
            pages=(
                PageMeasure(
                    "/",
                    {"performance": 0.93, "accessibility": 0.96, "best_practices": 0.78},
                    {"critical": 0, "serious": 0, "moderate": 2, "minor": 0},
                ),
                PageMeasure("/runs", error="lighthouse: NO_FCP"),
            ),
            evaluator="squadops-evaluator:test",
        ),
        21: QualityReading.not_measured(NotMeasured.START_FAILED),
    }
    lints = {
        22: LintReading(
            QualityStatus.MEASURED,
            reading={"version": 1, "total": 2, "by_rule": {"ruff:F401": 2}, "unavailable": {}},
            evaluator="squadops-evaluator:test",
        ),
        21: LintReading.not_measured(NotMeasured.NOT_A_SCAFFOLD_STACK),
    }
    # §10j, §10n (#2562): a seeded reading, its page keyed by route and record and loaded at its
    # own instance's address, with its account; and a record from before it, with none.
    seeded = {
        22: QualityReading(
            QualityStatus.MEASURED,
            pages=(
                PageMeasure(
                    "/runs/{id}#at_capacity",
                    {"performance": 0.84, "accessibility": 0.96, "best_practices": 0.78},
                    {"critical": 0, "serious": 1, "moderate": 2, "minor": 0},
                    url="/runs/r-93",
                ),
            ),
            evaluator="squadops-evaluator:test",
            seed={"version": "seed:0123456789ab:plan-v1", "unfilled": [], "notes": []},
        ),
        21: None,
    }
    records = [
        evaluation_record(
            suite,
            outcomes,
            project_id="group_run",
            campaign_id=None,
            cycle_id="cyc_pg0000000001",
            evaluated_tree_identity="a" * 64,
            previous_accepted_tree_identity=None,
            evaluated_at=T0.replace(hour=h),
            quality=readings[h],
            lint=lints[h],
            quality_seeded=seeded[h],
        )
        for h in (22, 21)
    ]
    for record in records:
        await scenarios.save_evaluation(record)

    assert await scenarios.evaluations_for_cycle("cyc_pg0000000001") == records[::-1]
    assert await scenarios.get_evaluation(records[0].evaluation_id) == records[0]

    # §10j, §10n ruling 1 (#2562): a re-measure is its own row, a series written once, and only
    # of an evaluation that exists.
    from squadops.scenarios.evaluation import QualityRemeasure

    remeasure = QualityRemeasure(
        remeasure_id="rmq_pg00000001",
        evaluation_id=records[0].evaluation_id,
        project_id="group_run",
        campaign_id=None,
        cycle_id="cyc_pg0000000001",
        evaluated_tree_identity="a" * 64,
        previous_accepted_tree_identity=None,
        provenance="2.4 window, seeded",
        round=1,
        measured_at=T0,
        quality=readings[22],
        lint=lints[22],
        quality_seeded=seeded[22],
    )
    await scenarios.save_remeasure(remeasure)
    assert await scenarios.remeasures_for_cycle("cyc_pg0000000001") == [remeasure]
    assert await scenarios.evaluations_for_cycle("cyc_pg0000000001") == records[::-1]
    with pytest.raises(asyncpg.UniqueViolationError):
        await scenarios.save_remeasure(replace(remeasure, remeasure_id="rmq_pg00000002"))
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await scenarios.save_remeasure(
            replace(remeasure, remeasure_id="rmq_pg00000003", evaluation_id="evl_nothing000")
        )

    # SIP-0113 §10p ruling 8 (#2564): a page scenario's evidence, once per scenario, its bytes and
    # details whole, and only of an evaluation that exists.
    from squadops.scenarios.evidence import ScenarioEvidence

    item = ScenarioEvidence(
        first.scenario_id, 3, b"\x89PNG\x00bytes", "button",
        ({"name": "Join", "visible": True, "disabled": False},), ("console: 404",), (),
        ("screenshot: over the evaluation's cap",),
    )  # fmt: skip
    await scenarios.save_evidence(records[0].evaluation_id, [item])
    await scenarios.save_evidence(records[0].evaluation_id, [replace(item, step=4)])
    assert await scenarios.evidence_for(records[0].evaluation_id) == [item]
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await scenarios.save_evidence("evl_nothing000", [item])
    # The cut's purge: strictly before, and the count of scenarios removed.
    assert await scenarios.purge_evidence(records[0].evaluated_at) == 0
    assert await scenarios.purge_evidence(datetime(2100, 1, 1, tzinfo=UTC)) == 1
    assert await scenarios.evidence_for(records[0].evaluation_id) == []
    with pytest.raises(asyncpg.CheckViolationError):
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE scenario_evaluations SET evaluated_tree_identity = $1",
                "15c7a12b8ed45f63ae47e90e3e854f6b3a2775f1",
            )


async def test_a_calibration_records_reading_names_it_in_place_of_a_cycle_and_the_table_holds_one(
    store,
):
    """SIP-0113 §10l, migration 1980. Bugs caught: the record's id lost in the round trip, so the
    reading reads back as a cycle's with no cycle; the reading found by a cycle query, or a cycle's
    by the record's; or a row naming neither unit, or both, accepted by the table."""
    from squadops.scenarios.evaluation import (
        Applicability,
        ScenarioOutcome,
        ScenarioResult,
        evaluation_record,
    )

    scenarios, pool = store
    suite = parse_suite(SUITE)
    await draft_suite(scenarios, suite, actor="supervisor", at=T0)
    outcomes = tuple(
        ScenarioOutcome(
            s.scenario_id, s.version, s.goal, Applicability.APPLICABLE, ScenarioResult.PASSED
        )
        for s in suite.scenarios
    )

    def reading(**unit):
        return evaluation_record(
            suite, outcomes, project_id="prj-tally", campaign_id="cmp_pg0000000010",
            evaluated_tree_identity="d" * 64, previous_accepted_tree_identity=None,
            evaluated_at=T0, quality=QualityReading(QualityStatus.NOT_APPLICABLE),
            lint=LintReading.not_measured(NotMeasured.NOT_A_SCAFFOLD_STACK), **unit,
        )  # fmt: skip

    baseline = reading(cycle_id=None, calibration_record_id="calrec_pg00000001")
    cycle = reading(cycle_id="cyc_pg0000000010")
    for record in (baseline, cycle):
        await scenarios.save_evaluation(record)

    assert await scenarios.evaluations_for_calibration_record("calrec_pg00000001") == [baseline]
    assert await scenarios.get_evaluation(baseline.evaluation_id) == baseline
    assert await scenarios.evaluations_for_cycle("cyc_pg0000000010") == [cycle]
    async with pool.acquire() as conn:
        for cycle_id, record_id in ((None, None), ("cyc_pg0000000011", "calrec_pg00000002")):
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO scenario_evaluations (evaluation_id, project_id, cycle_id, "
                    "calibration_record_id, evaluated_tree_identity, suite_digest, outcomes, "
                    "evaluated_at) VALUES ($1, 'prj-tally', $2, $3, $4, $5, '[]', $6)",
                    f"evl_pg_{record_id}_{cycle_id}",
                    cycle_id,
                    record_id,
                    "d" * 64,
                    suite.digest,
                    T0,
                )
