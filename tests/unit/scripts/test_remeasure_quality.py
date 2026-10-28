"""Prediction 4's re-measure script (#2416) reads the deploy's own config.

The script runs in the runtime image, piped to ``python -``, so nothing but a live run executed its
``main()``: at the 2.4 window's close it failed on all four calibration trees before measuring
anything, because it asked the window deploy's ``AppConfig`` for a ``database()`` that arrived only
with #2457. It reads the database there now, the one accessor that requires it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "remeasure_quality.py"

#: The minimum that makes ``load_config()`` validate offline (as ``test_loader_secrets_seam.py``).
_ENV = {
    "SQUADOPS__AUTH__ENABLED": "false",
    "SQUADOPS__AUTH__KEYCLOAK__ADMIN__PASSWORD": "literal",
    "SQUADOPS__DB__URL": "postgresql://test:test@localhost:5432/test",
    "SQUADOPS__COMMS__RABBITMQ__URL": "amqp://test:test@localhost:5672/",
    "SQUADOPS__COMMS__REDIS__URL": "redis://localhost:6379/0",
    "SQUADOPS__LLM__PROVIDER": "ollama",
    "SQUADOPS__LLM__URL": "http://ollama:11434",
    "SQUADOPS__COMMS__QUEUE__PROVIDER": "rabbitmq",
    "SQUADOPS__COMMS__A2A__PROVIDER": "http",
    "SQUADOPS__TOOLS__FILESYSTEM__PROVIDER": "local",
    "SQUADOPS__CYCLES__REGISTRY_PROVIDER": "memory",
    "SQUADOPS__CYCLES__SQUAD_PROFILE_PROVIDER": "config",
    "SQUADOPS__CYCLES__PROJECT_REGISTRY_PROVIDER": "config",
    "SQUADOPS__PROMPTS__ASSET_SOURCE_PROVIDER": "filesystem",
    "SQUADOPS__TELEMETRY__BACKEND": "null",
    "SQUADOPS__SANDBOX__PROVIDER": "noop",
}


def _load():
    spec = importlib.util.spec_from_file_location("remeasure_quality", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["remeasure_quality"] = module
    spec.loader.exec_module(module)
    return module


class _Stop(Exception):
    pass


@pytest.fixture
def opened(monkeypatch):
    """The pool the script opens, read where it opens it; the run stops there."""
    for key, value in _ENV.items():
        monkeypatch.setenv(key, value)
    seen: dict = {}

    async def create_pool(url, **kwargs):
        seen.update(url=url, **kwargs)
        raise _Stop

    monkeypatch.setattr("adapters.persistence.pool.create_pool", create_pool)
    return seen


async def test_the_script_opens_the_deploys_database_read_only(opened):
    """Bug caught: the script asking the config for an attribute it doesn't have, so every
    re-measure fails before it starts (the 2.4 close), or opening a pool that can write."""
    with pytest.raises(_Stop):
        await _load().main("cyc_000000000000", 3)

    assert opened["url"] == _ENV["SQUADOPS__DB__URL"]
    assert opened["server_settings"] == {"default_transaction_read_only": "on"}


def test_no_cycle_named_is_a_usage_error_and_nothing_opens(opened, monkeypatch):
    """Edge: no cycle named is a usage error, and nothing is opened."""
    monkeypatch.setattr(sys, "argv", [str(_SCRIPT)])
    with pytest.raises(SystemExit, match="usage"):
        exec(compile(_SCRIPT.read_text(), str(_SCRIPT), "exec"), {"__name__": "__main__"})
    assert opened == {}


# §10j, §10n ruling 1 (#2562): `--record` writes each re-measure as its own row.


async def _evaluated_store(tree: str):
    """A store holding one approved suite and one cycle's two evaluations, the later one of
    ``tree``."""
    from datetime import UTC, datetime

    from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
    from squadops.scenarios.evaluation import EvaluationRecord
    from squadops.scenarios.models import SuiteRecord, SuiteState, parse_suite

    store = MemoryScenarioStore()
    suite = parse_suite(
        {
            "name": "a re-measure fixture",
            "scenarios": [
                {
                    "scenario_id": "fixture-health",
                    "goal": "The fixture answers.",
                    "surfaces": [{"kind": "http_endpoint", "method": "GET", "path": "/health"}],
                    "steps": [{"action": "http", "method": "GET", "path": "/health"}],
                    "checks": [{"check": "status", "step": 1, "equals": 200}],
                }
            ],
        }
    )
    t0 = datetime(2026, 10, 20, tzinfo=UTC)
    await store.save_suite(SuiteRecord(suite, SuiteState.APPROVED, "s", t0, "o", t0))

    def evaluation(evaluation_id: str, identity: str, hour: int) -> EvaluationRecord:
        return EvaluationRecord(
            evaluation_id=evaluation_id, project_id="group_run", campaign_id="cmp_c1",
            cycle_id="cyc_c1inc1", evaluated_tree_identity=identity,
            previous_accepted_tree_identity="a" * 64, suite_digest=suite.digest, outcomes=(),
            evaluated_at=t0.replace(hour=hour),
        )  # fmt: skip

    await store.save_evaluation(evaluation("evl_older", "c" * 64, 1))
    await store.save_evaluation(evaluation("evl_latest", tree, 2))
    return store


class _Cycle:
    cycle_id = "cyc_c1inc1"


async def test_record_writes_each_re_measure_against_the_cycles_latest_evaluation():
    """Bug caught: re-measures written as evaluation records (which a package would read as the
    cycle's latest); against an older evaluation; or one row for three rounds."""
    from datetime import UTC, datetime

    from squadops.scenarios.quality import NotMeasured, QualityReading

    store = await _evaluated_store("b" * 64)
    seeded = QualityReading.not_measured(NotMeasured.SEED_FAILED, "POST /runs answered 500")
    readings = [(None, None, seeded)] * 3

    written = await _load().record_remeasures(
        store, _Cycle(), "b" * 64, "2.4 window, seeded", readings, datetime.now(UTC)
    )

    stored = await store.remeasures_for_cycle("cyc_c1inc1")
    assert [(r.evaluation_id, r.round, r.provenance) for r in stored] == [
        ("evl_latest", n, "2.4 window, seeded") for n in (1, 2, 3)
    ]
    assert stored == written and stored[0].quality_seeded == seeded
    assert [r.evaluation_id for r in await store.evaluations_for_cycle("cyc_c1inc1")] == [
        "evl_older", "evl_latest"
    ]  # fmt: skip


@pytest.mark.parametrize(
    ("identity", "why"),
    [("d" * 64, "re-measured"), (None, "no evaluation to re-measure")],
    ids=["another-tree", "no-evaluation"],
)
async def test_record_refuses_a_re_measure_of_a_tree_the_cycle_didnt_evaluate(identity, why):
    """Bug caught: a re-measure filed against an evaluation of a different tree, so its deltas
    compare two trees as one."""
    from datetime import UTC, datetime

    from adapters.scenarios.memory_scenario_store import MemoryScenarioStore

    store = await _evaluated_store("b" * 64) if identity else MemoryScenarioStore()

    with pytest.raises(ValueError, match=why):
        await _load().record_remeasures(
            store, _Cycle(), identity or "b" * 64, "p", [(None, None, None)], datetime.now(UTC)
        )
    assert await store.remeasures_for_cycle("cyc_c1inc1") == []


# §10y (#2637): the positive control, `--fault`, and S1's failing-id spreads. Invented tree.

_TREE = {
    "frontend/src/Detail.jsx": b"<main><h1>Orchard</h1><p>Rows</p></main>",
    "backend/main.py": b"app = 1\n",
}
_FAULT = {
    "diagnostic": "two unlabelled images on the detail page",
    "edits": [
        {
            "path": "frontend/src/Detail.jsx",
            "old": "<p>Rows</p>",
            "new": '<p>Rows</p><img src="a.png"><img src="b.png">',
        }
    ],
}


class _Runner:
    """The scenario runner's call, answering a -7 reading by the tree it was sent: two
    ``image-alt`` nodes more where the tree carries the fault's images."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def evaluate_tree(self, **call):
        from squadops.scenarios.quality import PageMeasure, QualityReading, QualityStatus
        from squadops.scenarios.runner import TreeEvaluation

        faulted = b"<img" in call["tree"]["frontend/src/Detail.jsx"]
        self.sent.append(call["tree_identity"])
        page = PageMeasure(
            "/runs/{id}#full",
            {"performance": 0.97, "accessibility": 0.9 if faulted else 1, "best_practices": 0.78},
            {"critical": 1 if faulted else 0, "serious": 0, "moderate": 1, "minor": 0},
            axe_nodes={"critical": 2 if faulted else 0, "serious": 0, "moderate": 1, "minor": 0},
            failing={
                "accessibility": ("image-alt",) if faulted else (),
                "best_practices": (),
                "environment": ("is-on-https", "redirects-http"),
                "axe": ("image-alt", "region") if faulted else ("region",),
            },
            errored={"accessibility": (), "best_practices": (), "environment": ()},
            best_practices_app=1,
        )
        seeded = QualityReading(
            QualityStatus.MEASURED, pages=(page,), evaluator="e-7", seed={"version": "s:v1"}
        )
        return TreeEvaluation(call["tree_identity"], True, quality_seeded=seeded)


async def test_the_fault_is_measured_through_the_runners_call_beside_the_tree_it_was_made_from():
    """§10y's positive control, entered where ``main`` calls it. Bug caught: the edits applied
    after the runner was called, so the faulted rounds measure the unchanged tree; round n read
    against another round; the faulted tree filed under its source's identity; or the rise read
    from the rule count, which one rule's two images move by one."""
    from squadops.campaigns.evaluator_trees import FileTree

    runner = _Runner()
    made_from = FileTree.of(_TREE).identity
    faulted = FileTree.of(_load().faulted_tree(_TREE, _FAULT["edits"])).identity

    doc, readings, started = await _load().readings_of(
        runner, _TREE, stack="s", pages=(), planned=None, plan=object(), times=2, fault=_FAULT
    )

    assert runner.sent == [made_from, faulted, made_from, faulted]
    assert (doc["tree_identity"], doc["diagnostic"]) == (
        faulted,
        {
            "what": _FAULT["diagnostic"],
            "made_from": made_from,
            "edited": ["frontend/src/Detail.jsx"],
        },
    )
    assert started and len(readings) == len(doc["fault_deltas"]) == 2
    for round_ in doc["fault_deltas"]:
        moved = {(d[0], d[1]): d[4] for d in round_["deltas"] if d[4]}
        assert moved == {
            ("seeded:lighthouse:accessibility", "/runs/{id}#full"): -0.1,
            ("seeded:axe:critical", "/runs/{id}#full"): 1,
            ("seeded:axe_nodes:critical", "/runs/{id}#full"): 2,
        }
        assert [f for f in round_["failing"] if f[2] or f[3]] == [
            ["seeded:failing:accessibility", "/runs/{id}#full", ["image-alt"], []],
            ["seeded:failing:axe", "/runs/{id}#full", ["image-alt"], []],
        ]
    assert {f["measure"]: f["stable"] for f in doc["seeded_failing_spreads"]} == {
        "failing:accessibility": True,
        "failing:axe": True,
        "failing:best_practices": True,
        "failing:environment": True,
    }


@pytest.mark.parametrize(
    ("edit", "why"),
    [
        ({"path": "frontend/src/Missing.jsx", "old": "x"}, "isn't in the tree"),
        ({"path": "backend/main.py", "old": "nowhere"}, "occurs 0 times"),
        ({"path": "frontend/src/Detail.jsx", "old": "<"}, "occurs 6 times"),
    ],
    ids=["no-such-file", "text-absent", "text-not-unique"],
)
async def test_a_fault_that_doesnt_apply_is_refused_before_the_runner_is_called(edit, why):
    """Bug caught: an edit that matched nothing measured as a fault, so the control reads no rise
    and passes for the measure's blindness; or one that matched twice, so its count is wrong."""
    runner = _Runner()

    with pytest.raises(ValueError, match=why):
        await _load().readings_of(
            runner,
            _TREE,
            stack="s",
            pages=(),
            planned=None,
            plan=None,
            times=2,
            fault={"diagnostic": "d", "edits": [edit]},
        )
    assert runner.sent == []


async def test_a_fault_is_never_recorded_and_nothing_opens(opened):
    """§10y: a diagnostic, never a reading. Bug caught: a faulted reading filed as a re-measure
    of the cycle's evaluation, where it joins the series S1 reads."""
    with pytest.raises(ValueError, match="never a reading"):
        await _load().main("cyc_000000000000", 3, "2.5, finer", _FAULT)

    assert opened == {}
