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
