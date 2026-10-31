"""Lighthouse and axe in an evaluation's record (SIP-0113 §4.2; #2416), entered at the evaluation
service, ``evaluate_cycle``, with the runner's side faked: which pages it is asked to measure,
and what the record says when it couldn't measure them."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.scenarios import evaluate
from squadops.scenarios.evaluate import declared_surfaces
from squadops.scenarios.models import SurfaceKind, parse_suite
from squadops.scenarios.quality import (
    LintReading,
    NotMeasured,
    PageMeasure,
    QualityReading,
    QualityStatus,
)
from squadops.scenarios.runner import (
    DeclaredStart,
    RunnerUnavailable,
    StartUndeclared,
    TreeEvaluation,
)
from squadops.scenarios.steps import ScenarioRun
from squadops.scenarios.suites import approve_suite, draft_suite

T0 = datetime(2026, 10, 19, 3, 0, tzinfo=UTC)
#: Its routes are ``/``, ``/create`` and ``/runs/:id``; delivered manifests name the entity ``Run``.
_MANIFEST = (
    (Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml")
    .read_bytes()
    .replace(b"RunEvent", b"Run")
)
_MEASURED = QualityReading(
    QualityStatus.MEASURED, pages=(PageMeasure("/", error="answered 500"),), evaluator="e:1"
)
_SUITE = {
    "name": "quality",
    "scenarios": [
        {
            "scenario_id": "runs-list",
            "goal": "The runs are listed.",
            "surfaces": [{"kind": "http_endpoint", "method": "GET", "path": "/runs"}],
            "steps": [{"action": "http", "method": "GET", "path": "/runs"}],
            "checks": [{"check": "status", "step": 1, "equals": 200}],
        }
    ],
}


@dataclass
class _Ref:
    artifact_id: str
    filename: str


class _Vault:
    def __init__(self, manifest: bytes | None):
        self._manifest, self.listed = manifest, 0

    async def list_artifacts(self, *, cycle_id):
        self.listed += 1
        return [_Ref("manifest", "interface_manifest.yaml")] if self._manifest else []

    async def retrieve(self, artifact_id):
        return None, self._manifest if artifact_id == "manifest" else b"app = 1\n"


class _Cycle:
    cycle_id, project_id = "cyc_quality00001", "group_run"

    def resolved_config(self):
        return {"build_profile": "fullstack_fastapi_react"}


_LINTED = LintReading(QualityStatus.MEASURED, reading={"total": 3}, evaluator="e:1")
#: §10j, §10n: what a runner answers for a seeded instance it was asked for.
_SEEDED = QualityReading(
    QualityStatus.MEASURED, evaluator="e:1", seed={"version": "seed:x:plan-v1"}
)


class _Runner:
    def __init__(
        self, *, started=True, quality=_MEASURED, raises=None, lint=_LINTED, seeded=_SEEDED
    ):
        self.calls: list[dict] = []
        self._started, self._quality, self._raises, self._lint = started, quality, raises, lint
        self._seeded = seeded

    async def evaluate_tree(self, **kw):
        self.calls.append(kw)
        if self._raises:
            raise self._raises
        runs = tuple(
            ScenarioRun(s["scenario_id"], "passed", steps_taken=1) for s in kw["scenarios"]
        )
        return TreeEvaluation(
            kw["tree_identity"],
            started=self._started,
            runs=runs if self._started else (),
            quality=self._quality if self._started else None,
            lint=self._lint,
            quality_seeded=self._seeded if self._started and "seed" in kw else None,
        )


@pytest.fixture
async def world(monkeypatch):
    async def tree_refs(vault, cycle):
        return {"backend/main.py": "tree"}

    monkeypatch.setattr(evaluate, "evaluated_tree_refs", tree_refs)
    store, suite = MemoryScenarioStore(), parse_suite(_SUITE)
    await draft_suite(store, suite, actor="supervisor", at=T0)
    await approve_suite(store, suite.digest, actor="owner", at=T0)

    async def run(runner, vault=None, **kw):
        return await evaluate.evaluate_cycle(
            store=store,
            runner=runner,
            vault=vault or _Vault(_MANIFEST),
            cycle=_Cycle(),
            suite_digest=suite.digest,
            campaign_id=None,
            previous_accepted_tree_identity=None,
            evaluated_at=T0,
            **kw,
        )

    return run


async def test_a_blueprint_deliverys_own_routes_are_measured_and_its_reading_recorded(world):
    """Bug caught: the pages taken from a sample app, or a parameterised route loaded literally,
    or the runner's reading dropped between the runner and the record."""
    runner = _Runner()

    record = await world(runner)

    [call] = runner.calls
    assert call["pages"] == ("/", "/create")
    assert record.quality == _MEASURED


@pytest.mark.parametrize(
    ("runner", "kw", "reason"),
    [
        (None, {}, NotMeasured.NO_RUNNER),
        (_Runner(raises=RunnerUnavailable("unreachable")), {}, NotMeasured.NO_RUNNER),
        (_Runner(started=False), {}, NotMeasured.START_FAILED),
        (_Runner(quality=None), {}, NotMeasured.EVALUATOR_FAILED),
        (_Runner(), {"unstartable": StartUndeclared("none")}, NotMeasured.NO_START_DECLARATION),
    ],
    ids=["no-runner", "unreachable", "start-failed", "a-runner-with-no-reading", "undeclared"],
)
async def test_pages_that_couldnt_be_measured_are_recorded_not_measured_with_why(
    world, runner, kw, reason
):
    """§4.2: never read as a baseline held. Bug caught: a gap recorded as no reading at all, so
    nothing counts what wasn't measured; or as measured with no pages, a clean page by omission."""
    record = await world(runner, **kw)

    assert (record.quality.status, record.quality.reason) == (QualityStatus.NOT_MEASURED, reason)


async def test_a_delivery_with_no_manifest_has_no_declared_page(world):
    """Bug caught: a blueprint with no manifest measured at a guessed ``/``, a sample app's page."""
    runner = _Runner()

    record = await world(runner, vault=_Vault(None))

    assert runner.calls[0]["pages"] == ()
    assert record.quality.reason is NotMeasured.NO_DECLARED_PAGE


@pytest.mark.parametrize(
    ("entry_points", "pages", "status"),
    [
        ([{"kind": "http_base"}], (), QualityStatus.NOT_APPLICABLE),
        ([{"kind": "http_base"}, {"kind": "ui_base"}], ("/app",), QualityStatus.MEASURED),
    ],
    ids=["an-api-only-product", "one-with-a-ui"],
)
async def test_a_declared_project_is_measured_at_its_ui_base_and_never_by_a_manifest(
    world, entry_points, pages, status
):
    """SIP-0112 §8.3 item 2, and §4.2: on a Project with no pages, Lighthouse and axe are not
    applicable. Bug caught: an API-only product's reading counted as a page that failed, or a
    sample manifest beside its tree supplying its pages."""
    declared = DeclaredStart(
        start=("./serve",),
        port=8080,
        ready_kind="tcp",
        ready_path="",
        ready_timeout_seconds=30,
        api_port=8080,
        ui_port=8081 if len(entry_points) > 1 else None,
        ui_path="/app" if len(entry_points) > 1 else "",
    )
    runner, vault = _Runner(), _Vault(_MANIFEST)

    record = await world(
        runner, vault=vault, declared=declared, served=declared_surfaces(entry_points)
    )

    assert runner.calls[0]["pages"] == pages
    assert record.quality.status is status
    assert vault.listed == 0


@pytest.mark.parametrize(
    ("runner", "declared", "lint"),
    [
        (_Runner(), False, _LINTED),
        (_Runner(started=False), False, _LINTED),
        (None, False, LintReading.not_measured(NotMeasured.NO_RUNNER)),
        (
            _Runner(raises=RunnerUnavailable("down")),
            False,
            LintReading.not_measured(NotMeasured.NO_RUNNER),
        ),
        (_Runner(), True, LintReading.not_measured(NotMeasured.NOT_A_SCAFFOLD_STACK)),
    ],
    ids=[
        "linted",
        "linted-though-it-didnt-start",
        "no-runner",
        "unreachable",
        "a-declared-project",
    ],
)
async def test_the_records_lint_is_the_runners_or_says_why_not(world, runner, declared, lint):
    """§4.2. Bug caught: the runner's lint dropped on the way to the record; a delivery that
    wouldn't start recorded with no lint, though its tree was read; or a declared Project's lint
    recorded as measured by rules it never chose."""
    kw = {}
    if declared:
        kw = {
            "declared": DeclaredStart(
                start=("./serve",),
                port=8080,
                ready_kind="tcp",
                ready_path="",
                ready_timeout_seconds=30,
                api_port=8080,
            ),
            "served": declared_surfaces([{"kind": "http_base"}]),
        }

    record = await world(runner, **kw)

    assert record.lint == lint


async def test_a_blueprint_is_linted_when_nothing_else_would_start_it(world):
    """Bug caught: a delivery none of whose scenarios apply and which declares no page left
    unlinted, so its increment has no lint reading to compare."""
    manifest = _MANIFEST.replace(b'path: "/"', b'path: "/:a"').replace(
        b'path: "/create"', b'path: "/c/:b"'
    )
    # Its list endpoint moved, so the suite's one scenario is surface_absent.
    manifest = manifest.replace(b"{ method: GET,  path: /runs,", b"{ method: GET,  path: /all,")
    runner = _Runner()

    record = await world(runner, vault=_Vault(manifest))

    [call] = runner.calls
    assert (call["scenarios"], call["pages"]) == ([], ())
    assert record.lint == _LINTED


# §10j, §10n (#2562): the seeded reading, planned from the Project's declared seed.


async def test_a_blueprint_that_serves_pages_is_seeded_from_its_projects_declared_seed(world):
    """Entered at ``evaluate_cycle``. Bug caught: the seed never planned, so no runner is asked for
    a seeded instance; planned on something other than the delivery's own manifest; or the
    runner's seeded reading dropped between the runner and the record."""
    runner = _Runner()

    record = await world(runner)

    [call] = runner.calls
    plan = call["seed"]
    assert [r.label for r in plan.records] == ["partial", "at_capacity", "unjoined"]
    assert [p.key for p in plan.pages if p.record] == [
        "/runs/{id}#partial",
        "/runs/{id}#at_capacity",
    ]
    assert record.quality_seeded == _SEEDED
    assert record.quality == _MEASURED


@pytest.mark.parametrize(
    ("change", "kw", "runner", "status", "reason"),
    [
        ("no-seed", {}, _Runner(), QualityStatus.NOT_MEASURED, NotMeasured.NO_SEED),
        ("no-create", {}, _Runner(), QualityStatus.NOT_MEASURED, NotMeasured.SEED_REFUSED),
        ("declared", {}, _Runner(), QualityStatus.NOT_APPLICABLE, None),
        (None, {}, _Runner(started=False), QualityStatus.NOT_MEASURED, NotMeasured.START_FAILED),
        (None, {}, _Runner(seeded=None), QualityStatus.NOT_MEASURED, NotMeasured.EVALUATOR_FAILED),
    ],
    ids=["no-seed-declared", "a-seed-the-interface-cant-take", "a-declared-project",
         "the-tree-didnt-start", "a-runner-with-no-seeded-reading"],
)  # fmt: skip
async def test_a_seeded_reading_that_couldnt_be_taken_says_why_never_none(
    world, monkeypatch, change, kw, runner, status, reason
):
    """§10j's reasons. Bug caught: a record with no seeded reading at all, read later as one
    written before the measure existed; or a seed the interface can't take sent anyway."""
    vault = _Vault(_MANIFEST)
    if change == "no-seed":
        monkeypatch.setattr(evaluate, "quality_seed", lambda project_id: None)
    elif change == "no-create":
        vault = _Vault(
            _MANIFEST.replace(b"method: POST, path: /runs,", b"method: POST, path: /races,")
        )
    elif change == "declared":
        kw = {
            "declared": DeclaredStart(("python3", "app.py"), 18407, "http", "/healthz", 30.0),
            "served": frozenset({SurfaceKind.PAGE}),
        }

    record = await world(runner, vault=vault, **kw)

    assert (record.quality_seeded.status, record.quality_seeded.reason) == (status, reason)
    # A reading planning decided sends no seed; one the runner decides was sent one.
    assert all(("seed" in call) == (change is None) for call in runner.calls)


@pytest.mark.parametrize(
    ("linted", "blocked", "evaluated", "profile_unread", "expected"),
    [
        (
            True,
            evaluate.BlockedReason.START_FAILED,
            TreeEvaluation("a" * 64, started=False, start_detail="setup step 1 exited 2"),
            None,
            (NotMeasured.EVALUATOR_FAILED, "the runner returned no lint for the tree"),
        ),
        (True, evaluate.BlockedReason.NO_RUNNER, None, None, (NotMeasured.NO_RUNNER, None)),
        (False, None, None, None, (NotMeasured.NOT_A_SCAFFOLD_STACK, None)),
        (
            False,
            None,
            None,
            "the derived profile at 962858eb0e32, revision 1: the registry is down",
            (
                NotMeasured.PROFILE_UNREADABLE,
                "the derived profile at 962858eb0e32, revision 1: the registry is down",
            ),
        ),
    ],
    ids=["started-and-returned-no-lint", "no-runner", "not-a-scaffold", "profile-unreadable"],
)
def test_a_lint_that_wasnt_taken_says_why(linted, blocked, evaluated, profile_unread, expected):
    """§10l and the second review of #2788 (P3-2, P3-6). Bugs caught: a runner that ran the tree
    and returned no lint read as the start's failure (it was asked, and answered nothing: the
    evaluator's); a profile that couldn't be read claimed as ``not_a_scaffold_stack``, a thing
    nobody knows."""
    lint = evaluate.lint_of(linted, blocked, evaluated, profile_unread)

    assert (lint.status, lint.reason, lint.detail) == (QualityStatus.NOT_MEASURED, *expected)
