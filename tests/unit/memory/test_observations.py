"""Observations (SIP-0110 §0.3–§0.5; slice 3a, #2096): each a projection of one committed record,
classified in its source's vocabulary or explicitly unclassified, and none from a cycle that says
nothing about authoring."""

from __future__ import annotations

import dataclasses
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from squadops.campaigns.models import (
    CampaignState,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
)
from squadops.cycles.cycle_assessment import RejectionRecord
from squadops.cycles.llm_usage import RunUsageAccumulator
from squadops.cycles.models import Gate, GateDecision, Run, TaskFlowPolicy
from squadops.cycles.run_loop_summary import RoundFailure, RunLoopSummary
from squadops.memory.observations import (
    UNCLASSIFIED,
    VOCABULARY_ATTRIBUTION,
    VOCABULARY_PLAN_VALIDATOR,
    VOCABULARY_PROPOSAL,
    Observation,
    ObservationSource,
    observe_cycle,
    observe_proposal_rulings,
)
from squadops.memory.reconcile import reconcile_cycle
from tests.unit.cycles.test_benchmark_registry import _cycle

pytestmark = [pytest.mark.domain_memory]

T0 = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def _run(run_id: str, *, decisions=(), finished=True) -> Run:
    return Run(
        run_id=run_id,
        cycle_id="cyc_1",
        run_number=1,
        status="completed",
        initiated_by="api",
        resolved_config_hash="h",
        started_at=T0,
        finished_at=T0 + timedelta(hours=1) if finished else None,
        workload_type="implementation",
        gate_decisions=tuple(decisions),
    )


def _rejected(at: datetime = T0, gate: str = "progress_plan_review") -> GateDecision:
    return GateDecision(gate_name=gate, decision="rejected", decided_by="system", decided_at=at)


def _summary(run_id: str, *failures: RoundFailure) -> RunLoopSummary:
    return RunLoopSummary(
        run_id=run_id, usage=RunUsageAccumulator().summary(), round_failures=failures
    )


#: The 2.1 cut's round (SIP-0110 §5b): the suite's own mock misused, its detail as recorded.
_MOCK_MISUSE = RoundFailure(
    task_id="task-run_44bce918-m006-qa.test",
    round_index=0,
    category="executed_and_failed",
    locus="own_artifact",
    failed_checks=("tests_pass",),
    failed_detail=(
        (
            "tests_pass",
            "frontend/src/__tests__/runViews.test.jsx:39 renders run titles and participant "
            "counts: TypeError: __vi_import_5__.apiFetch.mockResolvedValue is not a function",
        ),
    ),
)


def test_a_rejected_plan_is_classified_by_the_validators_its_record_names():
    """Bug caught: a rejection read as unclassified when its record names the validator (so no
    lesson can ever be keyed to it), or an approval observed as if it were a rejection."""
    approved = GateDecision("progress_plan_review", "approved", "system", T0)
    run = _run("run_a", decisions=[approved, _rejected()])
    record = RejectionRecord("art_1", "run_a", "progress_plan_review", {"validate_build_config": 1})

    [plan] = observe_cycle(_cycle(), [run], {}, [record])

    assert plan.source is ObservationSource.PLAN_REVIEW
    assert (plan.classification.vocabulary, plan.classification.values) == (
        VOCABULARY_PLAN_VALIDATOR,
        ("validate_build_config",),
    )
    assert plan.observed_at == T0 and plan.evidence["rejection_records"] == ["art_1"]


def test_a_rejection_with_no_record_is_unclassified_with_its_reason_and_another_gate_is_ignored():
    """Bug caught: a person's rejection forced into a class it was never given, or a different
    gate's rejection read as a plan review."""
    run = _run("run_a", decisions=[_rejected(), _rejected(T0, gate="progress_increment_ruling")])

    [plan] = observe_cycle(_cycle(), [run], {}, [])

    assert plan.classification.vocabulary == UNCLASSIFIED
    assert "no rejection_record" in plan.classification.rationale


def test_a_failed_round_carries_its_attribution_and_its_own_account_of_why():
    """Bug caught: the round's detail dropped (the only place the defect's shape lives, so no
    repeat could ever be seen), or the attribution re-derived differently from the registry's."""
    run = _run("run_a")

    [round_] = observe_cycle(_cycle(), [run], {"run_a": _summary("run_a", _MOCK_MISUSE)}, [])

    assert round_.source is ObservationSource.CORRECTION_ROUND
    assert round_.classification.vocabulary == VOCABULARY_ATTRIBUTION
    assert round_.classification.values == ("verification_artifact_failure",)
    assert round_.evidence["failed_detail"] == [list(_MOCK_MISUSE.failed_detail[0])]
    assert round_.observed_at == run.finished_at  # the record's commit, never earlier
    assert round_.evidence["failure_shapes"] == [
        {"check": "tests_pass", "runner": "vitest", "shape": "not_a_function"}
    ]


@pytest.mark.parametrize(
    ("category", "locus", "expected"),
    [
        pytest.param("sandbox_preexec_failure", "subject", None, id="environment-excluded"),
        pytest.param("evidence_unavailable", "unknown", UNCLASSIFIED, id="unattributed"),
        pytest.param("executed_and_failed", "subject", VOCABULARY_ATTRIBUTION, id="producer"),
    ],
)
def test_a_rounds_attribution_decides_whether_and_how_it_is_observed(category, locus, expected):
    """Bug caught: an environment failure taught as an authoring lesson, or an unattributed one
    given a class the evidence never established."""
    failure = dataclasses.replace(_MOCK_MISUSE, category=category, locus=locus)

    observed = observe_cycle(_cycle(), [_run("run_a")], {"run_a": _summary("run_a", failure)}, [])

    assert [o.classification.vocabulary for o in observed] == ([expected] if expected else [])


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"fault_injection": ["dev_join_response_omits_declared_fields"]}, id="fault"),
        pytest.param(
            {"execution_mode": "replay", "replay": {"source_run_id": "run_x", "boundary_index": 2}},
            id="replay",
        ),
        pytest.param({"execution_mode": "replay"}, id="half-declared-replay"),
    ],
)
def test_a_diagnostic_or_a_replay_produces_no_observation(overrides):
    """Bug caught: a manufactured red (#1251) or another run's re-execution entering the corpus
    as if a squad had made the mistake."""
    cycle = dataclasses.replace(_cycle(), execution_overrides=overrides)
    run = _run("run_a", decisions=[_rejected()])

    assert observe_cycle(cycle, [run], {"run_a": _summary("run_a", _MOCK_MISUSE)}, []) == []


def _entry(seq: int, operation, binding: dict, *, target="run_p1", outcome=ControlOutcome.APPLIED):
    return ControlLogEntry(
        entry_id=f"e{seq}",
        campaign_id="cmp_c4b81554bd59",
        seq=seq,
        operation=operation,
        actor="squadops-admin",
        actor_role="supervisor",
        reason="r",
        target=target,
        idempotency_key=f"k{seq}",
        request_hash="h",
        binding=binding,
        outcome=outcome,
        refusal=None,
        prior_state=CampaignState.AWAITING_RULING,
        next_state=CampaignState.AT_PROPOSAL,
        committed_at=T0 + timedelta(minutes=seq),
    )


def _counted_campaign_1() -> list[ControlLogEntry]:
    """Counted campaign 1's increment 2 as the control log holds it: v1 returned and classified,
    v2 returned and classified, v3 approved (SIP-0110 §5b, §5e)."""
    bind = {"proposal_id": "prop_5fb2d8136c36"}
    return [
        _entry(
            14, ControlOperation.RULE, {**bind, "version": 1, "decision": "returned_for_revision"}
        ),
        _entry(
            15,
            ControlOperation.CLASSIFY,
            {**bind, "version": 1, "classification": "criteria_not_checkable"},
        ),
        _entry(
            17,
            ControlOperation.RULE,
            {**bind, "version": 2, "decision": "returned_for_revision"},
            target="run_p2",
        ),
        _entry(
            18,
            ControlOperation.CLASSIFY,
            {**bind, "version": 2, "classification": "criteria_not_checkable"},
        ),
        _entry(
            20,
            ControlOperation.RULE,
            {**bind, "version": 3, "decision": "approved"},
            target="run_p3",
        ),
    ]


def test_each_returned_proposal_is_observed_with_its_versions_classification():
    """Bug caught: an approval observed as a return, or a version credited with another version's
    class (the classify row comes after the ruling, keyed by proposal and version)."""
    observed = observe_proposal_rulings("cmp_c4b81554bd59", "group_run", _counted_campaign_1())

    assert [
        (o.evidence["version"], o.classification.vocabulary, o.classification.values)
        for o in observed
    ] == [
        (1, VOCABULARY_PROPOSAL, ("criteria_not_checkable",)),
        (2, VOCABULARY_PROPOSAL, ("criteria_not_checkable",)),
    ]
    assert observed[0].observed_at == T0 + timedelta(minutes=14)


def test_a_return_never_classified_or_refused_or_from_a_diagnostic_is_handled_explicitly():
    """Bugs caught: a return without a class silently dropped (it belongs in the backlog as
    unclassified, §0.4), a refused ruling observed, or a diagnostic campaign's return counted."""
    bind = {"proposal_id": "prop_1", "version": 1, "decision": "returned_for_revision"}
    log = [
        _entry(1, ControlOperation.RULE, bind),
        _entry(
            2,
            ControlOperation.RULE,
            {**bind, "version": 2},
            target="run_p2",
            outcome=ControlOutcome.REFUSED,
        ),
        _entry(3, ControlOperation.RULE, {**bind, "version": 3}, target="run_diag"),
    ]

    [observed] = observe_proposal_rulings(
        "cmp_1", "group_run", log, ineligible_runs=frozenset({"run_diag"})
    )

    assert observed.classification.vocabulary == UNCLASSIFIED
    assert observed.evidence["version"] == 1


@pytest.mark.parametrize(
    ("at_ruling", "later", "expected"),
    [
        # SIP-0109 §24bi: the class the ruling carried.
        (
            {"classification": "scope_too_large"},
            [],
            (VOCABULARY_PROPOSAL, ("scope_too_large",), ""),
        ),
        # A novel defect, returned as unclassified with why: the rationale is kept.
        (
            {"classification": "unclassified", "classification_rationale": "a route it forbids"},
            [],
            (UNCLASSIFIED, (), "a route it forbids"),
        ),
        # A later reading of the version (the classify route) joins the ruling's class.
        (
            {"classification": "scope_too_large"},
            ["ambiguous_manifest_delta"],
            (VOCABULARY_PROPOSAL, ("ambiguous_manifest_delta", "scope_too_large"), ""),
        ),
        # A later reading classes an unclassified return.
        (
            {"classification": "unclassified", "classification_rationale": "novel"},
            ["criteria_not_checkable"],
            (VOCABULARY_PROPOSAL, ("criteria_not_checkable",), ""),
        ),
        # A ruling from before the rail, never classified.
        ({}, [], (UNCLASSIFIED, (), "no classification of this version was recorded")),
    ],
)
def test_a_returns_class_is_read_from_its_ruling_row_and_any_later_reading(
    at_ruling, later, expected
):
    """SIP-0110 §0.4 with SIP-0109 §24bi. Bugs caught: the class the ruling carried ignored, so
    every return after the rail reads as unclassified; or an unclassified return's rationale lost,
    leaving the backlog unable to say why it has no class."""
    bind = {"proposal_id": "prop_1", "version": 1}
    log = [_entry(1, ControlOperation.RULE, {**bind, "decision": "rejected", **at_ruling})] + [
        _entry(2 + n, ControlOperation.CLASSIFY, {**bind, "classification": c})
        for n, c in enumerate(later)
    ]

    [observed] = observe_proposal_rulings("cmp_1", "group_run", log)

    c = observed.classification
    assert (c.vocabulary, c.values, c.rationale or "") == expected


def test_an_observation_survives_the_store_unchanged():
    """Bug caught: a field lost between the projection and the Postgres row's JSON."""
    [observed] = observe_cycle(
        _cycle(), [_run("run_a")], {"run_a": _summary("run_a", _MOCK_MISUSE)}, []
    )

    assert Observation.from_dict(json.loads(json.dumps(observed.to_dict()))) == observed


def test_the_migrations_source_check_is_the_enums_values():
    """Bug caught: a source added to the enum that the table refuses at insert."""
    sql = (
        Path(__file__).resolve().parents[3]
        / "infra"
        / "migrations"
        / "1710_memory_observations.sql"
    ).read_text()
    check = re.search(r"CHECK \(source IN \(([^)]*)\)\)", sql)

    assert check is not None
    assert sorted(re.findall(r"'([^']+)'", check.group(1))) == sorted(
        s.value for s in ObservationSource
    )


class _Vault:
    """The two calls the reconciler makes, over one stored rejection record."""

    def __init__(self, run_id: str) -> None:
        from types import SimpleNamespace

        self._ref = SimpleNamespace(artifact_id="art_rej", run_id=run_id)
        self._content = json.dumps(
            {"gate": "progress_plan_review", "classes": {"validate_builder_floor": 1}}
        ).encode()

    async def list_artifacts(self, **kwargs):
        return [self._ref] if kwargs.get("artifact_type") == "rejection_record" else []

    async def retrieve(self, artifact_id):
        return self._ref, self._content


async def test_reconciling_a_cycle_stores_its_observations_once():
    """Wiring, entered at ``reconcile_cycle``: the registry's runs, their gate decisions and loop
    summaries, and the vault's rejection record, through to the store. Bugs caught: a source the
    reconciler never reads, or a second reconciliation (after a crash, say) counting twice."""
    registry = MemoryCycleRegistry()
    gated = TaskFlowPolicy(
        mode="sequential",
        gates=(Gate(name="progress_plan_review", description="plan review", after_task_types=()),),
    )
    await registry.create_cycle(dataclasses.replace(_cycle("cyc_1"), task_flow_policy=gated))
    run = await registry.create_run(_run("run_a"))
    await registry.record_gate_decision(run.run_id, _rejected())
    await registry.record_run_loop_summary(run.run_id, _summary(run.run_id, _MOCK_MISUSE))
    store = InMemoryCrossCycleMemoryStore()

    first = await reconcile_cycle("cyc_1", registry=registry, vault=_Vault(run.run_id), store=store)
    again = await reconcile_cycle("cyc_1", registry=registry, vault=_Vault(run.run_id), store=store)

    stored = await store.list_observations("group_run")
    assert (first, again) == (len(stored), 0)
    assert {o.source for o in stored} == {
        ObservationSource.PLAN_REVIEW,
        ObservationSource.CORRECTION_ROUND,
    }
    plan = next(o for o in stored if o.source is ObservationSource.PLAN_REVIEW)
    assert plan.classification.values == ("validate_builder_floor",)
