"""The scenario store in Postgres (SIP-0113 §4.1; #2413), over the runtime's one pool (#577).

Migration 1900 creates its tables. A suite's content is stored as its document, and its digest
is recomputed on every read: JSONB orders keys its own way, so the digest is the content's
canonical hash, never the stored text's. A row whose content no longer hashes to its key is
refused rather than served.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import asyncpg

from squadops.ports.scenarios import ScenarioStorePort
from squadops.scenarios.evaluation import EvaluationRecord, QualityRemeasure, ScenarioOutcome
from squadops.scenarios.evidence import ScenarioEvidence
from squadops.scenarios.models import (
    CampaignSuitePin,
    SuiteRecord,
    SuiteState,
    parse_suite,
)
from squadops.scenarios.quality import LintReading, QualityReading

_SUITE_COLUMNS = "digest, content, state, drafted_by, drafted_at, approved_by, approved_at"
_EVALUATION_COLUMNS = (
    "evaluation_id, project_id, campaign_id, cycle_id, evaluated_tree_identity, "
    "previous_accepted_tree_identity, suite_digest, outcomes, evaluated_at, quality, lint, "
    "quality_seeded"
)

_REMEASURE_COLUMNS = (
    "remeasure_id, evaluation_id, project_id, campaign_id, cycle_id, evaluated_tree_identity, "
    "previous_accepted_tree_identity, provenance, round, measured_at, quality, lint, quality_seeded"
)


class PostgresScenarioStore(ScenarioStorePort):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save_suite(self, record: SuiteRecord) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO scenario_suites ({_SUITE_COLUMNS}) VALUES ($1,$2,$3,$4,$5,$6,$7) "
                "ON CONFLICT (digest) DO UPDATE SET state = EXCLUDED.state, "
                "approved_by = EXCLUDED.approved_by, approved_at = EXCLUDED.approved_at",
                record.digest,
                record.suite.content(),
                record.state.value,
                record.drafted_by,
                record.drafted_at,
                record.approved_by,
                record.approved_at,
            )

    async def get_suite(self, digest: str) -> SuiteRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_SUITE_COLUMNS} FROM scenario_suites WHERE digest = $1", digest
            )
        return _row_to_record(row) if row else None

    async def list_suites(self) -> list[SuiteRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_SUITE_COLUMNS} FROM scenario_suites ORDER BY drafted_at DESC"
            )
        return [_row_to_record(r) for r in rows]

    async def save_pin(self, pin: CampaignSuitePin) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO campaign_scenario_suites (campaign_id, suite_digest, pinned_by, "
                "pinned_at) VALUES ($1,$2,$3,$4)",
                pin.campaign_id,
                pin.suite_digest,
                pin.pinned_by,
                pin.pinned_at,
            )

    async def get_pin(self, campaign_id: str) -> CampaignSuitePin | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT campaign_id, suite_digest, pinned_by, pinned_at "
                "FROM campaign_scenario_suites WHERE campaign_id = $1",
                campaign_id,
            )
        return CampaignSuitePin(**dict(row)) if row else None

    async def save_evaluation(self, record: EvaluationRecord) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO scenario_evaluations ({_EVALUATION_COLUMNS}) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)",
                record.evaluation_id,
                record.project_id,
                record.campaign_id,
                record.cycle_id,
                record.evaluated_tree_identity,
                record.previous_accepted_tree_identity,
                record.suite_digest,
                [o.as_dict() for o in record.outcomes],
                record.evaluated_at,
                record.quality.as_dict() if record.quality is not None else None,
                record.lint.as_dict() if record.lint is not None else None,
                record.quality_seeded.as_dict() if record.quality_seeded is not None else None,
            )

    async def get_evaluation(self, evaluation_id: str) -> EvaluationRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_EVALUATION_COLUMNS} FROM scenario_evaluations WHERE evaluation_id = $1",
                evaluation_id,
            )
        return _row_to_evaluation(row) if row else None

    async def evaluations_for_cycle(self, cycle_id: str) -> list[EvaluationRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_EVALUATION_COLUMNS} FROM scenario_evaluations WHERE cycle_id = $1 "
                "ORDER BY evaluated_at",
                cycle_id,
            )
        return [_row_to_evaluation(r) for r in rows]

    async def save_remeasure(self, remeasure: QualityRemeasure) -> None:
        def reading(r):
            return r.as_dict() if r is not None else None

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO quality_remeasures ({_REMEASURE_COLUMNS}) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)",
                remeasure.remeasure_id,
                remeasure.evaluation_id,
                remeasure.project_id,
                remeasure.campaign_id,
                remeasure.cycle_id,
                remeasure.evaluated_tree_identity,
                remeasure.previous_accepted_tree_identity,
                remeasure.provenance,
                remeasure.round,
                remeasure.measured_at,
                reading(remeasure.quality),
                reading(remeasure.lint),
                reading(remeasure.quality_seeded),
            )

    async def remeasures_for_cycle(self, cycle_id: str) -> list[QualityRemeasure]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_REMEASURE_COLUMNS} FROM quality_remeasures WHERE cycle_id = $1 "
                "ORDER BY provenance, round",
                cycle_id,
            )
        return [_row_to_remeasure(row) for row in rows]

    async def save_evidence(self, evaluation_id: str, evidence: Sequence[ScenarioEvidence]) -> None:
        # §10p ruling 8: once per scenario, so a retry of the same evaluation keeps the first.
        async with self._pool.acquire() as conn:
            for item in evidence:
                await conn.execute(
                    "INSERT INTO scenario_evidence (evaluation_id, scenario_id, step, screenshot, "
                    "details, sha256, size) VALUES ($1,$2,$3,$4,$5,$6,$7) "
                    "ON CONFLICT (evaluation_id, scenario_id) DO NOTHING",
                    evaluation_id,
                    item.scenario_id,
                    item.step,
                    item.screenshot,
                    item.details(),
                    item.sha256,
                    item.size,
                )

    async def evidence_for(self, evaluation_id: str) -> list[ScenarioEvidence]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT scenario_id, step, screenshot, details FROM scenario_evidence "
                "WHERE evaluation_id = $1 ORDER BY scenario_id",
                evaluation_id,
            )
        return [_row_to_evidence(row) for row in rows]

    async def purge_evidence(self, before: datetime) -> int:
        async with self._pool.acquire() as conn:
            status = await conn.execute(
                "DELETE FROM scenario_evidence e USING scenario_evaluations v "
                "WHERE e.evaluation_id = v.evaluation_id AND v.evaluated_at < $1",
                before,
            )
        return int(status.split()[-1])


def _row_to_record(row: asyncpg.Record) -> SuiteRecord:
    suite = parse_suite(row["content"])
    if suite.digest != row["digest"]:
        raise ValueError(
            f"scenario suite {row['digest']} no longer hashes to its key ({suite.digest}): "
            "its stored content changed"
        )
    return SuiteRecord(
        suite=suite,
        state=SuiteState(row["state"]),
        drafted_by=row["drafted_by"],
        drafted_at=row["drafted_at"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
    )


def _row_to_evaluation(row: asyncpg.Record) -> EvaluationRecord:
    values = dict(row)
    values["outcomes"] = tuple(ScenarioOutcome.from_dict(o) for o in row["outcomes"])
    values["quality"] = QualityReading.from_dict(row["quality"]) if row["quality"] else None
    values["lint"] = LintReading.from_dict(row["lint"]) if row["lint"] else None
    seeded = row["quality_seeded"]
    values["quality_seeded"] = QualityReading.from_dict(seeded) if seeded else None
    return EvaluationRecord(**values)


def _row_to_remeasure(row: asyncpg.Record) -> QualityRemeasure:
    values = dict(row)
    values["quality"] = QualityReading.from_dict(row["quality"]) if row["quality"] else None
    values["lint"] = LintReading.from_dict(row["lint"]) if row["lint"] else None
    seeded = row["quality_seeded"]
    values["quality_seeded"] = QualityReading.from_dict(seeded) if seeded else None
    return QualityRemeasure(**values)


def _row_to_evidence(row: asyncpg.Record) -> ScenarioEvidence:
    details = row["details"]
    return ScenarioEvidence(
        scenario_id=row["scenario_id"],
        step=row["step"],
        screenshot=bytes(row["screenshot"]) if row["screenshot"] is not None else None,
        role=details.get("role"),
        nodes=tuple(details.get("nodes") or ()),
        errors=tuple(details.get("errors") or ()),
        failed_requests=tuple(details.get("failed_requests") or ()),
        withheld=tuple(details.get("withheld") or ()),
    )
