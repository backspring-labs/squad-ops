"""The proposal's outcome evidence as the reader takes it from a campaign's records (SIP-0113 §4.5;
§10t step 3, rulings 2, 3 and 6).

What bugs would these catch? A step's or a check's value, or a blocked outcome's reason, reaching
the proposer; a goal that quotes a step's value shown, not held back; another campaign's or another
suite's reading shown as this tree's; the seeded reading or a page's URL in the quality moves; a
retired PRD section still shown as accepted; and an unreadable pin passing as nothing to show.

The suite is invented, in a domain no held-out suite covers.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.campaigns.change_request import (
    ChangeKind,
    ChangeRequest,
    PrdOp,
    PrdSection,
    content_hash,
    stored_change_request,
)
from squadops.campaigns.models import ControlOperation, ControlOutcome, CycleKind
from squadops.outcomes.proposal_evidence import (
    AcceptedSection,
    GoalEvidence,
    GoalResult,
    ProposalEvidence,
)
from squadops.outcomes.proposal_reader import StoredProposalEvidence
from squadops.scenarios.evaluation import (
    Applicability,
    BlockedReason,
    EvaluationRecord,
    ScenarioOutcome,
    ScenarioResult,
)
from squadops.scenarios.models import CampaignSuitePin, parse_suite
from squadops.scenarios.quality import LintReading, PageMeasure, QualityReading, QualityStatus
from squadops.scenarios.suites import approve_suite, draft_suite

pytestmark = [pytest.mark.domain_contracts]

T0 = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
CID = "cmp_reader000001"
STEP_VALUE = "Northwind Traders"
REASON = BlockedReason.SURFACE_ABSENT.value


def _scenario(scenario_id: str, goal: str, payee: str = "Contoso Ltd") -> dict:
    return {
        "scenario_id": scenario_id,
        "goal": goal,
        "surfaces": [{"kind": "http_endpoint", "method": "POST", "path": "/entries"}],
        "steps": [
            {"action": "http", "method": "POST", "path": "/entries", "json": {"payee": payee}}
        ],
        "checks": [{"check": "status", "step": 1, "equals": 201}],
    }


SUITE = parse_suite(
    {
        "name": "ledger",
        "scenarios": [
            _scenario("export", "A reader exports the ledger as a spreadsheet"),
            _scenario("search", "A reader finds an entry by its payee"),
            _scenario("totals", "The ledger's totals show beside each month"),
            _scenario("archive", "An archived ledger opens read-only"),
            # Its goal quotes its own step's value: held back, never shown (§10t ruling 3).
            _scenario("first", f"An entry for {STEP_VALUE} is listed first", payee=STEP_VALUE),
        ],
    }
)
RESULTS = {
    "export": (Applicability.APPLICABLE, ScenarioResult.FAILED, None),
    "search": (Applicability.APPLICABLE, ScenarioResult.PASSED, None),
    "totals": (
        Applicability.APPLICABLE,
        ScenarioResult.BLOCKED_UNVERIFIED,
        BlockedReason.SURFACE_ABSENT,
    ),
    "archive": (Applicability.NOT_APPLICABLE, None, None),
    "first": (Applicability.APPLICABLE, ScenarioResult.FAILED, None),
}


def _quality(perf: tuple[float, float], *, seeded: bool = False) -> QualityReading:
    pages = tuple(
        PageMeasure(
            path, {"performance": p, "accessibility": 0.9, "best_practices": 0.8}, {"serious": 1}
        )
        for path, p in zip(("/", "/entries"), perf, strict=True)
    )
    return QualityReading(QualityStatus.MEASURED, pages=pages, evaluator="t")


def _lint(total: int) -> LintReading:
    reading = {"tools": {}, "total": total, "by_rule": {}, "unavailable": {}}
    return LintReading(QualityStatus.MEASURED, reading=reading, evaluator="t")


def _record(
    cycle_id,
    tree,
    built_on,
    *,
    results=RESULTS,
    at=T0,
    campaign_id=CID,
    suite=SUITE,
    perf=(0.8, 0.6),
    lint=10,
    seeded=None,
) -> EvaluationRecord:
    outcomes = tuple(
        ScenarioOutcome(
            s.scenario_id,
            s.version,
            s.goal,
            *results[s.scenario_id][:2],
            blocked_reason=results[s.scenario_id][2],
            first_failing_step=1 if results[s.scenario_id][1] is ScenarioResult.FAILED else None,
        )
        for s in suite.scenarios
    )
    return EvaluationRecord(
        evaluation_id=f"evl_{cycle_id}_{at.minute}",
        project_id="ledger",
        campaign_id=campaign_id,
        cycle_id=cycle_id,
        evaluated_tree_identity=tree,
        previous_accepted_tree_identity=built_on,
        suite_digest=suite.digest,
        outcomes=outcomes,
        evaluated_at=at,
        quality=_quality(perf),
        lint=_lint(lint),
        quality_seeded=seeded,
    )


@dataclass
class _Entry:
    seq: int
    cycle_id: str
    operation: str = ControlOperation.PROMOTE
    outcome: str = ControlOutcome.APPLIED

    @property
    def binding(self) -> dict:
        return {"cycle_id": self.cycle_id}


@dataclass
class _Intent:
    cycle_id: str
    cycle_kind: CycleKind


@dataclass
class _Campaigns:
    """The campaign registry's two reads the evidence takes: its control log and its launches."""

    entries: list = field(default_factory=list)
    intents: list = field(default_factory=list)

    def promote(self, cycle_id: str, kind: CycleKind, *, outcome=ControlOutcome.APPLIED) -> None:
        self.entries.append(_Entry(len(self.entries) + 1, cycle_id, outcome=outcome))
        self.intents.append(_Intent(cycle_id, kind))

    async def control_log(self, campaign_id):
        return list(self.entries)

    async def launch_intents(self, campaign_id):
        return list(self.intents)


@dataclass
class _Cycles:
    async def get_cycle(self, cycle_id):
        return cycle_id

    async def list_runs(self, cycle_id):
        return [dataclasses.make_dataclass("Run", ["run_number"])(1)]


async def _store(*records: EvaluationRecord, pin: bool = True) -> MemoryScenarioStore:
    store = MemoryScenarioStore()
    await draft_suite(store, SUITE, actor="supervisor", at=T0)
    await approve_suite(store, SUITE.digest, actor="owner", at=T0)
    if pin:
        await store.save_pin(CampaignSuitePin(CID, SUITE.digest, pinned_by="owner", pinned_at=T0))
    for record in records:
        await store.save_evaluation(record)
    return store


def _reader(store, campaigns, requests=None, monkeypatch=None) -> StoredProposalEvidence:
    if monkeypatch is not None:

        async def built(vault, registry, cycle, run):
            return (requests or {}).get(cycle)

        monkeypatch.setattr("squadops.outcomes.proposal_reader.built_change_request", built)
    return StoredProposalEvidence(
        scenarios=store, campaigns=campaigns, cycles=_Cycles(), vault=None
    )


def _calibrated() -> _Campaigns:
    campaigns = _Campaigns()
    campaigns.promote("cyc_cal", CycleKind.CALIBRATION)
    campaigns.promote("cyc_inc1", CycleKind.INCREMENT)
    return campaigns


async def test_each_goal_is_shown_with_its_result_and_nothing_of_its_steps_or_reasons(monkeypatch):
    """Bugs caught: a blocked outcome's reason shown (it names a held-out surface), a
    ``not_applicable`` goal shown, a goal quoting its step's value shown, or the latest reading
    of the accepted tree passed over for an earlier one."""
    earlier = {**RESULTS, "search": (Applicability.APPLICABLE, ScenarioResult.FAILED, None)}
    store = await _store(
        _record("cyc_cal", "a" * 64, None),
        _record("cyc_inc1", "b" * 64, "a" * 64, results=earlier),
        _record("cyc_inc1", "b" * 64, "a" * 64, at=T0 + timedelta(minutes=5)),
    )

    evidence = await _reader(store, _calibrated(), monkeypatch=monkeypatch).for_proposal(
        campaign_id=CID, accepted_cycle_id="cyc_inc1"
    )

    assert evidence.goals == (
        GoalEvidence("export", "A reader exports the ledger as a spreadsheet", GoalResult.FAILED),
        GoalEvidence("search", "A reader finds an entry by its payee", GoalResult.PASSED),
        GoalEvidence(
            "totals", "The ledger's totals show beside each month", GoalResult.NOT_VERIFIED
        ),
    )
    assert evidence.held_back == 1
    shown = json.dumps(evidence.to_inputs())
    assert STEP_VALUE not in shown and REASON not in shown and "Contoso" not in shown


async def test_another_campaigns_or_another_suites_reading_is_not_this_trees(monkeypatch):
    """Bug caught: a reading of the same cycle by another campaign, or of another suite, shown as
    the pinned suite's result on this tree."""
    other = parse_suite({"name": "other", "scenarios": [_scenario("export", "Something else")]})
    all_passed = {k: (Applicability.APPLICABLE, ScenarioResult.PASSED, None) for k in RESULTS}
    store = await _store(
        _record("cyc_inc1", "b" * 64, "a" * 64),
        _record(
            "cyc_inc1",
            "b" * 64,
            "a" * 64,
            results=all_passed,
            campaign_id="cmp_other0000001",
            at=T0 + timedelta(minutes=9),
        ),
    )
    await draft_suite(store, other, actor="supervisor", at=T0)
    await store.save_evaluation(
        _record(
            "cyc_inc1",
            "b" * 64,
            "a" * 64,
            suite=other,
            at=T0 + timedelta(minutes=8),
            results={"export": (Applicability.APPLICABLE, ScenarioResult.PASSED, None)},
        )
    )

    evidence = await _reader(store, _calibrated(), monkeypatch=monkeypatch).for_proposal(
        campaign_id=CID, accepted_cycle_id="cyc_inc1"
    )

    assert [(g.goal_id, g.result) for g in evidence.goals][:2] == [
        ("export", GoalResult.FAILED),
        ("search", GoalResult.PASSED),
    ]


async def test_quality_moves_against_the_calibration_averaged_over_pages_without_the_seeded(
    monkeypatch,
):
    """Bugs caught: a page's URL shown, a measure read against the previous tree instead of the
    calibration, or the seeded reading shown (§10o's S2)."""
    seeded = _quality((0.5, 0.5))
    store = await _store(
        _record("cyc_cal", "a" * 64, None, perf=(0.8, 0.6), lint=10, seeded=seeded),
        _record("cyc_inc1", "b" * 64, "a" * 64, perf=(0.9, 0.7), lint=7, seeded=seeded),
    )

    evidence = await _reader(store, _calibrated(), monkeypatch=monkeypatch).for_proposal(
        campaign_id=CID, accepted_cycle_id="cyc_inc1"
    )

    moves = {q.measure: (q.before, q.after) for q in evidence.quality}
    assert moves["lighthouse:performance"] == (0.7, 0.8)
    assert moves["lint:total"] == (10, 7)
    assert not [m for m in moves if m.startswith("seeded:")]
    assert "/entries" not in json.dumps(evidence.to_inputs())


def _finer(nodes: int, app: float) -> QualityReading:
    """Both pages read by -7, with §10y's finer reading: invented counts and ids."""
    pages = tuple(
        dataclasses.replace(
            page,
            axe_nodes={"critical": 0, "serious": nodes, "moderate": 0, "minor": 0},
            failing={
                "accessibility": ("label",) if nodes else (),
                "best_practices": (),
                "environment": ("is-on-https", "redirects-http"),
                "axe": ("label",) if nodes else (),
            },
            errored={"accessibility": (), "best_practices": (), "environment": ()},
            best_practices_app=app,
        )
        for page in _quality((0.8, 0.6)).pages
    )
    return QualityReading(QualityStatus.MEASURED, pages=pages, evaluator="t")


async def test_the_proposal_is_shown_only_the_measures_it_was_shown_before_the_finer_reading(
    monkeypatch,
):
    """§10y: the finer reading is reporting-only, and whether the proposal sees it is the owner's
    ruling. Bug caught: its node counts or ``best_practices_app`` averaged into the proposal's
    quality moves the day -7 deploys, because every unseeded delta is passed through."""
    store = await _store(
        dataclasses.replace(_record("cyc_cal", "a" * 64, None), quality=_finer(0, 1.0)),
        dataclasses.replace(_record("cyc_inc1", "b" * 64, "a" * 64), quality=_finer(4, 0.95)),
    )

    evidence = await _reader(store, _calibrated(), monkeypatch=monkeypatch).for_proposal(
        campaign_id=CID, accepted_cycle_id="cyc_inc1"
    )

    assert [q.measure for q in evidence.quality] == [
        "lighthouse:performance",
        "lighthouse:accessibility",
        "lighthouse:best_practices",
        "axe:serious",  # the fixture's only axe impact
        "lint:total",
    ]
    shown = json.dumps(evidence.to_inputs())
    assert "axe_nodes" not in shown and "best_practices_app" not in shown and "label" not in shown


def _request(cycle: str, *sections: tuple[str, PrdOp, str]) -> str:
    request = ChangeRequest(
        proposal_id=f"prop_{cycle}",
        version=1,
        baseline_tree="t",
        kind=ChangeKind.FEATURE,
        prd_delta=tuple(PrdSection(i, op, text) for i, op, text in sections),
        manifest_delta=(),
        criteria=(),
        must_not_break=(),
    )
    return stored_change_request(dataclasses.replace(request, content_hash=content_hash(request)))


async def test_the_accepted_prd_is_what_the_promoted_increments_left_in_their_order(monkeypatch):
    """Bugs caught: a retired section still shown as accepted, a section shown as first written
    after an increment modified it, a refused promotion's request read as accepted, or the
    calibration read as an increment."""
    campaigns = _calibrated()
    campaigns.promote("cyc_inc2", CycleKind.RETRY)
    campaigns.promote("cyc_refused", CycleKind.INCREMENT, outcome=ControlOutcome.REFUSED)
    campaigns.promote("cyc_inc3", CycleKind.REPAIR)
    requests = {
        "cyc_cal": _request("cal", ("never", PrdOp.ADD, "a calibration adds nothing")),
        "cyc_inc1": _request(
            "1", ("export", PrdOp.ADD, "Export as CSV."), ("audit", PrdOp.ADD, "Log.")
        ),
        "cyc_inc2": _request("2", ("export", PrdOp.MODIFY, "Export as CSV or XLSX.")),
        "cyc_refused": _request("r", ("refused", PrdOp.ADD, "never accepted")),
        "cyc_inc3": _request("3", ("audit", PrdOp.RETIRE, ""), ("totals", PrdOp.ADD, "Monthly.")),
    }
    store = await _store(pin=False)

    evidence = await _reader(store, campaigns, requests, monkeypatch).for_proposal(
        campaign_id=CID, accepted_cycle_id="cyc_inc3"
    )

    assert evidence.accepted_prd == (
        AcceptedSection("export", "Export as CSV or XLSX."),
        AcceptedSection("totals", "Monthly."),
    )
    assert evidence.goals == () and evidence.quality == ()


@pytest.mark.parametrize(
    ("records", "accepted", "expected"),
    [
        # No evaluation of the accepted tree: nothing known of its goals, which is not a failure.
        ((), "cyc_inc1", ProposalEvidence()),
        # The first proposal is on the calibration's own tree: no move against itself.
        ((_record("cyc_cal", "a" * 64, None),), "cyc_cal", None),
    ],
)
async def test_nothing_to_show_is_shown_as_nothing(monkeypatch, records, accepted, expected):
    """Bugs caught: an unevaluated tree failing the proposal run, and the calibration compared
    with itself as a move."""
    store = await _store(*records)

    evidence = await _reader(store, _calibrated(), monkeypatch=monkeypatch).for_proposal(
        campaign_id=CID, accepted_cycle_id=accepted
    )

    if expected is not None:
        assert evidence == expected
    else:
        assert evidence.quality == () and len(evidence.goals) == 3


async def test_a_pin_whose_suite_the_store_does_not_return_raises(monkeypatch):
    """§10t ruling 6. Bug caught: an unreadable suite read as no suite, so the proposal is shown
    nothing while its campaign pins one. The stores refuse a reading of a suite they don't hold,
    so this is a read that answered nothing."""
    store = await _store(_record("cyc_inc1", "b" * 64, "a" * 64))

    async def answered_nothing(digest):
        return None

    monkeypatch.setattr(store, "get_suite", answered_nothing)

    with pytest.raises(LookupError, match="doesn't hold"):
        await _reader(store, _calibrated(), monkeypatch=monkeypatch).for_proposal(
            campaign_id=CID, accepted_cycle_id="cyc_inc1"
        )
