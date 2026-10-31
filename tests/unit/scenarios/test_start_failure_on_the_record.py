"""Why an evaluation's start failed, kept on its record, its package and the runtime's log (SIP-0113
§10ae; #2793).

The wiring tests enter where the live campaign enters: ``CampaignProgress.calibration_recorded``,
which reads a repository-backed Campaign's baseline (``evaluate_calibration_record``), and
``CampaignProgress.cycle_ended``, which evaluates each increment (``evaluate_cycle``), both through
the evaluator the runtime builds. The world is the shared fixture's Tally, which declares an
``http_base`` and no ``ui_base``: a product that serves no pages, so its quality reading is *not
applicable* and can't say why the start failed. The rest enter at ``evaluate_cycle`` with a
blueprint delivery that serves pages.

What bugs would these catch?
- the runner's detail and the app's last lines dropped between the runner and the record, so every
  scenario reads ``start_failed`` with no cause (#2793, read live on the 2.5 demonstration's first
  Campaign);
- a product that serves no pages losing the cause, since its quality reading can't carry it;
- the cause in the record but not in the package or its digest, which is where an operator reads a
  record through the API and the CLI;
- an evaluation secret's value stored or logged because the runner that returned it scrubbed
  nothing, or a value that spans two of the app's lines missed by a line-by-line scrub;
- a log or a record that grows with whatever the app printed;
- a start that succeeded, or one never attempted, recorded or logged as a failed start.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from adapters.scenarios.postgres_scenario_store import (
    _EVALUATION_COLUMNS,
    PostgresScenarioStore,
    _row_to_evaluation,
)
from squadops.scenarios import evaluate
from squadops.scenarios.evaluation import (
    Applicability,
    BlockedReason,
    ScenarioResult,
    StartFailure,
)
from squadops.scenarios.models import parse_suite
from squadops.scenarios.quality import NotMeasured, QualityReading, QualityStatus
from squadops.scenarios.runner import (
    DIAGNOSTIC_LINE_CHARS,
    DIAGNOSTIC_LINES,
    RunnerUnavailable,
    StartUndeclared,
    TreeEvaluation,
)
from squadops.scenarios.steps import ScenarioRun
from squadops.scenarios.suites import approve_suite, draft_suite
from tests.unit.api.test_campaign_calibration_record import PROJECT
from tests.unit.campaigns.test_campaign_branch import CID
from tests.unit.scenarios.test_campaign_baseline_reading import (
    _first_increment_heard,
    _heard,
    _package,
)
from tests.unit.scenarios.test_quality_evaluation import _MANIFEST, _SUITE, _Cycle, _Vault

T0 = datetime(2026, 10, 29, 14, 0, tzinfo=UTC)
#: Invented: a readiness that never answered 2xx, and the app's own last lines.
CAUSE = "not ready at /healthz within 30s"
APP_LINES = ("tally: serving on 0.0.0.0:18407", "tally: refused a request for an unknown host")
EVALUATE_LOGGER = "squadops.scenarios.evaluate"
#: Invented evaluation secrets, as an owner's approval would release them (#2421).
ADMIN_VALUE = "invented-tally-admin-value"
SPANNING = "-----BEGIN INVENTED KEY-----\nAAAAinventedBBBB\n-----END INVENTED KEY-----"


class _StartFails:
    """A runner that scrubs nothing: a start fails with ``detail`` and the app's ``lines``. With
    ``fails`` set, only the trees it names fail, and every other tree starts with its scenarios
    passed."""

    def __init__(self, world=None, *, detail=CAUSE, lines=APP_LINES, fails=None) -> None:
        self.world, self.detail, self.lines, self.fails = world, detail, lines, fails
        self.calls: list[dict] = []

    async def evaluate_tree(self, **kw):
        self.calls.append(kw)
        identity = kw["tree_identity"]
        if self.fails is not None and identity not in self.fails:
            runs = tuple(
                ScenarioRun(s["scenario_id"], "passed", steps_taken=1) for s in kw["scenarios"]
            )
            return TreeEvaluation(identity, started=True, runs=runs)
        return TreeEvaluation(
            identity, started=False, start_detail=self.detail, startup_diagnostics=self.lines
        )


def _start_logs(caplog) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == EVALUATE_LOGGER and r.getMessage().startswith("evaluation_start_failed")
    ]


async def test_a_baseline_readings_failed_start_reaches_its_record_its_package_and_the_log(
    tmp_path, caplog
):
    """The 2.5 demonstration's case (#2793): a repository-backed Campaign's baseline reading, on a
    product that serves no pages. Bugs caught: the cause dropped before the record, so the reading
    says only ``start_failed``; the record holding it and the package or digest not, so no CLI or
    API reader sees it; no log line naming the reading."""
    caplog.set_level(logging.WARNING, logger=EVALUATE_LOGGER)

    world, store, runner, record = await _heard(tmp_path, runner=lambda w: _StartFails(w))
    doc, digest = await _package(world)

    [reading] = await store.evaluations_for_calibration_record(record.record_id)
    assert reading.start_failure == StartFailure(CAUSE, APP_LINES)
    # Tally serves no pages: its quality reading can't say why, so the record does.
    assert reading.quality == QualityReading(QualityStatus.NOT_APPLICABLE)
    applicable = [o for o in reading.outcomes if o.applicability is Applicability.APPLICABLE]
    assert {(o.result, o.blocked_reason) for o in applicable} == {
        (ScenarioResult.BLOCKED_UNVERIFIED, BlockedReason.START_FAILED)
    }
    assert doc["outcomes"]["baseline"]["start_failure"] == {
        "detail": CAUSE,
        "diagnostics": list(APP_LINES),
    }
    assert f"  - the start failed: {CAUSE} (the app's last 2 lines are in the package)" in digest
    assert _start_logs(caplog) == [
        f"evaluation_start_failed: evaluation {reading.evaluation_id} of Project {PROJECT} "
        f"(calibration record {record.record_id}, campaign {CID}): {CAUSE}; the app's last 2 "
        "lines are on the record"
    ]


async def test_an_increments_failed_start_is_its_own_and_a_start_that_succeeded_carries_none(
    tmp_path, caplog
):
    """An increment evaluated at its cycle's end (``evaluate_cycle``) whose start fails, on a
    baseline whose start succeeded. Bugs caught: the cycle's path dropping what the baseline's
    keeps; a start that succeeded given a failure, or a ``start_failure`` key in its package
    section, which would change the package of every campaign whose starts all succeed."""
    caplog.set_level(logging.WARNING, logger=EVALUATE_LOGGER)
    world, store, runner, record = await _heard(
        tmp_path, runner=lambda w: _StartFails(w, fails=set())
    )
    runner.fails = None  # the baseline started; from here on every start fails
    await _first_increment_heard(world)

    doc, digest = await _package(world)

    [baseline] = await store.evaluations_for_calibration_record(record.record_id)
    [increment] = await store.evaluations_for_cycle("cyc_inc000000001")
    assert (baseline.start_failure, increment.start_failure) == (
        None,
        StartFailure(CAUSE, APP_LINES),
    )
    [section] = doc["outcomes"]["cycles"]
    assert "start_failure" not in doc["outcomes"]["baseline"]
    assert section["start_failure"] == {"detail": CAUSE, "diagnostics": list(APP_LINES)}
    assert digest.count("  - the start failed:") == 1
    assert _start_logs(caplog) == [
        f"evaluation_start_failed: evaluation {increment.evaluation_id} of Project {PROJECT} "
        f"(cycle cyc_inc000000001, campaign {CID}): {CAUSE}; the app's last 2 lines are on the "
        "record"
    ]


@pytest.fixture
async def blueprint(monkeypatch):
    """A blueprint delivery that serves pages, evaluated at ``evaluate_cycle``: its quality and
    seeded readings are *not measured* when its start fails."""

    async def tree_refs(vault, cycle):
        return {"backend/main.py": "tree"}

    monkeypatch.setattr(evaluate, "evaluated_tree_refs", tree_refs)
    store, suite = MemoryScenarioStore(), parse_suite(_SUITE)
    await draft_suite(store, suite, actor="supervisor", at=T0)
    await approve_suite(store, suite.digest, actor="owner", at=T0)

    async def run(runner, **kw):
        return await evaluate.evaluate_cycle(
            store=store,
            runner=runner,
            vault=_Vault(_MANIFEST),
            cycle=_Cycle(),
            suite_digest=suite.digest,
            campaign_id="cmp_start0000001",
            previous_accepted_tree_identity=None,
            evaluated_at=T0,
            **kw,
        )

    return run, store


@pytest.mark.parametrize(
    ("environment", "detail", "lines", "kept_detail", "kept_lines"),
    [
        (
            {"TALLY_ADMIN_TOKEN": ADMIN_VALUE},
            f"the start could not run: token {ADMIN_VALUE} refused",
            (f"TALLY_ADMIN_TOKEN={ADMIN_VALUE}", "Traceback: boom"),
            "the start could not run: token [redacted] refused",
            ("TALLY_ADMIN_TOKEN=[redacted]", "Traceback: boom"),
        ),
        (
            {"TALLY_SIGNING_KEY": SPANNING},
            CAUSE,
            ("loading the signing key", *SPANNING.split("\n"), "Traceback: boom"),
            CAUSE,
            ("loading the signing key", "[redacted]", "Traceback: boom"),
        ),
        (
            # The token straddles the cut: cut first, its head would be kept.
            {"TALLY_ADMIN_TOKEN": ADMIN_VALUE},
            "e" * 495 + ADMIN_VALUE,
            ("e" * 495 + ADMIN_VALUE,),
            "e" * 495 + "[reda… (5 more characters)",
            ("e" * 495 + "[reda… (5 more characters)",),
        ),
    ],
    ids=["a-token-in-the-detail-and-a-line", "a-key-across-three-lines", "a-token-at-the-cut"],
)
async def test_a_secret_the_start_was_given_is_never_stored_or_logged(
    blueprint, caplog, environment, detail, lines, kept_detail, kept_lines
):
    """Q40: never in a log, a record or an agent's input. The sandbox's runner scrubs what it
    returns; this runner scrubs nothing, as any other runner might. Bugs caught: the value stored
    in the record, its quality or seeded reading, or the log line; a value that spans the app's
    lines missed by scrubbing each line alone."""
    caplog.set_level(logging.WARNING, logger=EVALUATE_LOGGER)
    run, store = blueprint
    runner = _StartFails(detail=detail, lines=lines)

    record = await run(runner, environment=environment)

    [secret] = environment.values()
    assert runner.calls[0]["environment"] == environment  # the start was given it
    assert record.start_failure == StartFailure(kept_detail, kept_lines)
    assert (record.quality.reason, record.quality.detail) == (
        NotMeasured.START_FAILED,
        kept_detail,
    )
    assert (record.quality_seeded.reason, record.quality_seeded.detail) == (
        NotMeasured.START_FAILED,
        kept_detail,
    )
    stored = await store.get_evaluation(record.evaluation_id)
    for text in (
        json.dumps(stored.start_failure.as_dict()),
        json.dumps(stored.quality.as_dict()),
        json.dumps(stored.quality_seeded.as_dict()),
        caplog.text,
    ):
        # A value that spans lines is read line by line: JSON escapes its newlines.
        assert all(part not in text for part in secret.split("\n"))
    assert len(_start_logs(caplog)) == 1


async def test_a_secret_that_contains_another_is_replaced_whole(blueprint):
    """The scrubber's longest-first rule, now the runner's and the record's one scrubber. Bug
    caught: the shorter value replaced first inside the longer one, so the longer one no longer
    matches and the rest of it is kept (``[redacted]-tally-admin-value``)."""
    run, _store = blueprint
    environment = {"TALLY_USER": "invented", "TALLY_ADMIN_TOKEN": ADMIN_VALUE}

    record = await run(
        _StartFails(lines=(f"TALLY_ADMIN_TOKEN={ADMIN_VALUE}",)), environment=environment
    )

    assert record.start_failure.diagnostics == ("TALLY_ADMIN_TOKEN=[redacted]",)


async def test_what_the_app_printed_is_kept_bounded(blueprint, caplog):
    """Bugs caught: a record, a package and a log line that grow with whatever the app printed (a
    bundler's one line can be megabytes); the first lines kept rather than the last, which hold
    the failure; a long line cut without saying so."""
    caplog.set_level(logging.WARNING, logger=EVALUATE_LOGGER)
    run, _store = blueprint
    long_cause = "the start could not run: " + "e" * 900
    printed = tuple(f"line {n}" for n in range(1, 56)) + ("x" * 2000,)

    record = await run(_StartFails(detail=long_cause, lines=printed))

    kept = record.start_failure
    assert len(kept.diagnostics) == DIAGNOSTIC_LINES == 40
    assert kept.diagnostics[:2] == ("line 17", "line 18")
    assert kept.diagnostics[-2:] == (
        "line 55",
        "x" * DIAGNOSTIC_LINE_CHARS + "… (1500 more characters)",
    )
    assert kept.detail == long_cause[:DIAGNOSTIC_LINE_CHARS] + "… (425 more characters)"
    assert record.quality.detail == kept.detail
    [logged] = _start_logs(caplog)
    assert kept.detail in logged and "x" * 100 not in logged
    assert len(logged) < DIAGNOSTIC_LINE_CHARS + 300


class _Started:
    async def evaluate_tree(self, **kw):
        runs = tuple(
            ScenarioRun(s["scenario_id"], "passed", steps_taken=1) for s in kw["scenarios"]
        )
        return TreeEvaluation(kw["tree_identity"], started=True, runs=runs)


class _Unreachable:
    async def evaluate_tree(self, **kw):
        raise RunnerUnavailable("503 from the sandbox service")


@pytest.mark.parametrize(
    ("runner", "kw", "quality_reason"),
    [
        (_Started(), {}, None),
        (None, {}, NotMeasured.NO_RUNNER),
        (_Unreachable(), {}, NotMeasured.NO_RUNNER),
        (
            _Started(),
            {"unstartable": StartUndeclared("the Project declares no start")},
            NotMeasured.NO_START_DECLARATION,
        ),
    ],
    ids=["the-start-succeeded", "no-runner", "the-runner-unreachable", "never-attempted"],
)
async def test_a_start_that_didnt_fail_keeps_no_start_failure_and_logs_none(
    blueprint, caplog, runner, kw, quality_reason
):
    """Bugs caught: a start that succeeded given a failure; ``no_runner`` or a declaration that
    couldn't run (a start never attempted) read as a failed start, its reading given a detail it
    never had, or logged as one."""
    caplog.set_level(logging.WARNING, logger=EVALUATE_LOGGER)
    run, _store = blueprint

    record = await run(runner, **kw)

    assert record.start_failure is None
    assert _start_logs(caplog) == []
    if quality_reason is not None:
        assert (record.quality.reason, record.quality.detail) == (quality_reason, None)


async def test_a_start_whose_runner_named_no_cause_says_so(blueprint, caplog):
    """Bug caught: a failed start with no detail and no lines (a runner that named none) kept as
    no failure at all, or logged as ``None``."""
    caplog.set_level(logging.WARNING, logger=EVALUATE_LOGGER)
    run, _store = blueprint

    record = await run(_StartFails(detail=None, lines=()))

    assert record.start_failure == StartFailure(None, ())
    assert record.quality.detail is None
    [logged] = _start_logs(caplog)
    assert logged.endswith(
        "(cycle cyc_quality00001, campaign cmp_start0000001): the runner named no cause; the app "
        "printed nothing"
    )


class _Connection:
    def __init__(self, written: list) -> None:
        self.written = written

    async def execute(self, sql: str, *args) -> None:
        self.written.append((sql, args))


class _Pool:
    def __init__(self) -> None:
        self.written: list = []

    def acquire(self):
        pool = self

        class _Acquired:
            async def __aenter__(self):
                return _Connection(pool.written)

            async def __aexit__(self, *exc):
                return False

        return _Acquired()


@pytest.mark.parametrize(
    "start_failure", [StartFailure(CAUSE, APP_LINES), None], ids=["failed", "succeeded"]
)
async def test_the_postgres_store_writes_and_reads_the_start_failure_by_its_column(
    blueprint, start_failure
):
    """Migration 1990's column, through the adapter's own write and read (the integration test
    holds it against Postgres). Bugs caught: the column named with its value not passed, or passed
    in another's place; the stored document read back as a mapping, not a ``StartFailure``; a
    start that succeeded read back with one."""
    run, _store = blueprint
    runner = _StartFails() if start_failure is not None else _Started()
    record = await run(runner)
    pool = _Pool()

    await PostgresScenarioStore(pool).save_evaluation(record)

    [(sql, args)] = pool.written
    columns = [c.strip() for c in _EVALUATION_COLUMNS.split(",")]
    assert sql.count("$") == len(columns) == len(args)
    row = dict(zip(columns, args, strict=True))
    assert row["start_failure"] == (start_failure.as_dict() if start_failure else None)
    assert _row_to_evaluation(row) == record
