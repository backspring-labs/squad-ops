"""The deploy record the deploy step writes (#1720).

Bug classes guarded: a record that names a deploy it does not describe (a service dropped, a
revision or digest guessed), and a deploy that cannot record itself passing as recorded. Entered
at ``record_deploy``, the function the one-off command composes and calls, with the facts the
host hands over and the ports the runtime image builds.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from adapters.cycles.memory_deploy_registry import MemoryDeployRegistry
from squadops.api.runtime import record_deploy as recorder
from squadops.cycles.deploy_record import DeployFactsError, DeployRecord, ModelWeights, ServiceImage
from squadops.llm.models import ModelInfo

NOW = datetime(2026, 9, 29, 23, 0, tzinfo=UTC)

FACTS = {
    "recorded_by": "rebuild_and_deploy.sh all",
    "source_revision": "7acc2bc1",
    "services": [
        {"service": "runtime-api", "image_id": "sha256:api", "revision": "7acc2bc1"},
        {"service": "neo", "image_id": "sha256:neo", "revision": "7acc2bc1-dirty"},
        {"service": "postgres", "image_id": "sha256:pg", "revision": None},
        {"service": "han", "image_id": "sha256:han", "revision": "unknown"},
    ],
}


def _profiles(*models_by_profile: list[tuple[str, bool]]):
    port = AsyncMock()
    port.list_profiles.return_value = [
        SimpleNamespace(agents=[SimpleNamespace(model=m, enabled=on) for m, on in agents])
        for agents in models_by_profile
    ]
    return port


def _llm(available: list[ModelInfo] | Exception):
    port = AsyncMock()
    if isinstance(available, Exception):
        port.list_available_models.side_effect = available
    else:
        port.list_available_models.return_value = available
    return port


async def test_the_record_holds_each_service_and_each_named_models_weights():
    registry = MemoryDeployRegistry()
    profiles = _profiles(
        [("qwen3.8:27b", True), ("qwen2.5:3b-instruct", False)],
        [("qwen3.6:27b", True), ("llama3.1:8b", True)],
    )
    llm = _llm(
        [
            ModelInfo("qwen3.8:27b", digest="22130167c4c2"),
            ModelInfo("qwen3.6:27b", digest=None),  # a provider that reports no digest
            ModelInfo(
                "qwen2.5:3b-instruct", digest="357c53fb659c"
            ),  # named only by a disabled agent
        ]
    )

    record = await recorder.record_deploy(
        FACTS, registry=registry, profiles=profiles, llm=llm, now=NOW
    )

    assert await registry.latest() == record
    assert record.recorded_by == "rebuild_and_deploy.sh all"
    assert record.source_revision == "7acc2bc1"
    assert record.services == (
        ServiceImage("han", "sha256:han", None),  # the build argument's own `unknown`
        ServiceImage("neo", "sha256:neo", "7acc2bc1-dirty"),
        ServiceImage("postgres", "sha256:pg", None),
        ServiceImage("runtime-api", "sha256:api", "7acc2bc1"),
    )
    assert record.models == (
        ModelWeights("llama3.1:8b", None),  # named, but the provider does not serve it
        ModelWeights("qwen3.6:27b", None),
        ModelWeights("qwen3.8:27b", "22130167c4c2"),
    )


async def test_a_provider_that_cannot_be_listed_records_every_digest_unknown(capsys):
    registry = MemoryDeployRegistry()

    record = await recorder.record_deploy(
        FACTS,
        registry=registry,
        profiles=_profiles([("qwen3.8:27b", True)]),
        llm=_llm(ConnectionError("ollama unreachable")),
        now=NOW,
    )

    assert record.models == (ModelWeights("qwen3.8:27b", None),)
    assert len(record.services) == 4
    assert "model digests unavailable (ollama unreachable)" in capsys.readouterr().err


@pytest.mark.parametrize(
    "facts, refusal",
    [
        ({**FACTS, "services": []}, "no services"),
        ({**FACTS, "services": [{"service": "neo", "revision": "x"}]}, "lacks its name or image"),
        ({**FACTS, "recorded_by": " "}, "what is recording them"),
    ],
    ids=["no-services", "service-without-image", "no-writer"],
)
async def test_facts_that_cannot_describe_a_deploy_are_refused_unwritten(facts, refusal):
    registry = MemoryDeployRegistry()

    with pytest.raises(DeployFactsError, match=refusal):
        await recorder.record_deploy(
            facts, registry=registry, profiles=_profiles([]), llm=_llm([]), now=NOW
        )

    assert await registry.latest() is None


@pytest.mark.parametrize(
    "stdin, expected_exit",
    [("not json", 2), (json.dumps({**FACTS, "services": []}), 2)],
    ids=["unreadable", "no-services"],
)
def test_the_command_exits_non_zero_so_the_deploy_reports_the_record_failed(
    monkeypatch, capsys, stdin, expected_exit
):
    """The deploy script reads the exit code; a refusal that exited 0 would pass as recorded."""
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))

    async def _never(facts):
        recorder.services_from_facts(facts)
        raise AssertionError("composed past a refusal")

    monkeypatch.setattr(recorder, "_compose_and_record", _never)

    assert recorder.main() == expected_exit
    assert "record_deploy: refused" in capsys.readouterr().err


async def test_the_one_off_loads_the_deploys_config_as_the_runtime_does(monkeypatch):
    """Wiring, entered at ``_compose_and_record``, the command's own composition. Bug caught: the
    config loaded without the secret provider every root passes, so on a real deploy — whose
    configuration carries ``secret://`` references — the record failed before it began (the
    1.9 deploy's first record, ``ConfigValidationError``)."""
    from squadops.bootstrap.secrets import secret_provider_for

    seen = {}

    def load_config(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(
            db=SimpleNamespace(url="postgresql://unused"),
            cycles=SimpleNamespace(registry_provider="memory", squad_profile_provider="config"),
            llm=SimpleNamespace(
                provider="ollama", url="http://ollama:11434", timeout=5, api_key=None, model=None
            ),
        )

    pool = AsyncMock()
    monkeypatch.setattr("squadops.config.load_config", load_config)
    monkeypatch.setattr("adapters.persistence.pool.create_pool", AsyncMock(return_value=pool))
    monkeypatch.setattr(
        "adapters.cycles.factory.create_squad_profile_port", lambda *a, **k: _profiles([])
    )
    monkeypatch.setattr("adapters.llm.factory.create_llm_provider", lambda **k: _llm([]))

    record = await recorder._compose_and_record(FACTS)

    assert seen.get("secret_provider_factory") is secret_provider_for
    assert len(record.services) == 4
    pool.close.assert_awaited_once()


# --- the check (#2193): whether the latest record describes what runs, writing nothing ---

_RUNNING = {
    "recorded_by": "record_deploy.sh --check",
    "services": [
        {"service": "runtime-api", "image_id": "sha256:api", "revision": "7acc2bc1"},
        {"service": "sandbox-service", "image_id": "sha256:435ca602e23c99", "revision": None},
    ],
}


@pytest.mark.parametrize(
    "recorded, running, why",
    [
        (
            [("runtime-api", "sha256:api"), ("sandbox-service", "sha256:435ca602e23c99")],
            _RUNNING["services"],
            [],
        ),
        (  # rebuild 11: the sandbox rebuilt three seconds after the record
            [("runtime-api", "sha256:api"), ("sandbox-service", "sha256:2ee90a99609e55")],
            _RUNNING["services"],
            ["sandbox-service runs 435ca602e23c; dep_a records 2ee90a99609e"],
        ),
        (
            [("runtime-api", "sha256:api")],
            _RUNNING["services"],
            ["sandbox-service runs 435ca602e23c, which dep_a does not record"],
        ),
        (
            [("runtime-api", "sha256:api"), ("sandbox-service", "sha256:435ca602e23c99")],
            _RUNNING["services"][:1],
            ["sandbox-service is recorded (435ca602e23c) but does not run"],
        ),
    ],
    ids=["describes", "rebuilt-after", "started-since", "stopped-since"],
)
async def test_the_check_names_each_service_the_latest_record_misdescribes(recorded, running, why):
    registry = MemoryDeployRegistry()
    await registry.record(
        DeployRecord(
            "dep_a",
            NOW,
            "rebuild_and_deploy.sh all",
            "fd492323",
            tuple(ServiceImage(s, i, None) for s, i in recorded),
            (),
        )
    )

    record, stale = await recorder.check_deploy({"services": running}, registry=registry)

    assert record.deploy_id == "dep_a"
    assert stale == why
    assert [r.deploy_id for r in registry._records.values()] == ["dep_a"]  # nothing written


async def test_with_no_record_the_check_fails_rather_than_passing_empty():
    record, stale = await recorder.check_deploy(_RUNNING, registry=MemoryDeployRegistry())

    assert record is None
    assert stale == ["no deploy is recorded"]


@pytest.mark.parametrize(
    "stdin, answer, expected_exit, said",
    [
        (json.dumps(_RUNNING), [], 0, "dep_a describes what runs: 2 services"),
        (
            json.dumps(_RUNNING),
            ["sandbox-service runs 435ca602e23c; dep_a records 2ee90a99609e"],
            1,
            "dep_a does not describe what runs: sandbox-service runs 435ca602e23c",
        ),
        ("not json", None, 2, ""),
    ],
    ids=["describes", "stale", "unreadable"],
)
def test_the_check_command_exits_non_zero_when_the_record_is_stale(
    monkeypatch, capsys, stdin, answer, expected_exit, said
):
    """``verify_loaded`` and ``record_deploy.sh --check`` read the exit code: a stale record that
    exited 0 would pass as describing the deploy."""
    from squadops.api.runtime import deploy_check

    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    record = SimpleNamespace(deploy_id="dep_a", services=(1, 2))

    async def _answer(facts):
        recorder.services_from_facts(facts)
        return record, answer

    monkeypatch.setattr(deploy_check, "compose_and_check", _answer)

    assert deploy_check.main() == expected_exit
    assert said in capsys.readouterr().out


async def test_the_check_loads_the_deploys_config_and_reads_the_registry_it_selects(monkeypatch):
    """Wiring, entered at ``compose_and_check``, the check's own composition: the same config load
    and registry selection the record uses, its pool closed. On a memory registry nothing is
    recorded, so the check fails as it must on a deploy that never recorded itself."""
    from squadops.bootstrap.secrets import secret_provider_for

    seen = {}

    def load_config(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(
            db=SimpleNamespace(url="postgresql://unused"),
            cycles=SimpleNamespace(registry_provider="memory"),
        )

    pool = AsyncMock()
    monkeypatch.setattr("squadops.config.load_config", load_config)
    monkeypatch.setattr("adapters.persistence.pool.create_pool", AsyncMock(return_value=pool))

    record, stale = await recorder.compose_and_check(_RUNNING)

    assert seen.get("secret_provider_factory") is secret_provider_for
    assert (record, stale) == (None, ["no deploy is recorded"])
    pool.close.assert_awaited_once()
