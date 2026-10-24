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
from squadops.campaigns.box import EngineReading, Model, box_quietness
from squadops.campaigns.box_reading import declared_models
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
        FACTS, registry=registry, profiles=profiles, llm=llm, instances=[], now=NOW
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
        ModelWeights("llama3.1:8b", None, served=False),  # named, but the provider doesn't serve it
        ModelWeights("qwen3.6:27b", None, served=True),  # served, with no digest reported
        ModelWeights("qwen3.8:27b", "22130167c4c2", served=True),
    )


async def test_a_tensorfold_deploy_records_its_served_weights_and_what_it_does_not_serve():
    """#2561. Entry: ``record_deploy`` with the runtime's own TensorFold adapter, the provider
    since the engine switch, over its wire. Bug caught: every model recorded ``digest: null``,
    TensorFold's served one included, since ``/v1/models`` lists ids only, and nothing in the
    record told an unserved model's null from a served one's."""
    from adapters.llm.tensorfold import TensorFoldAdapter
    from tests.unit.llm.conformance import TENSORFOLD_KEY, TENSORFOLD_SERVED, tensorfold_ok, wire

    llm = TensorFoldAdapter(
        base_url="http://tensorfold:8080",
        default_model=TENSORFOLD_SERVED,
        timeout_seconds=5.0,
        api_key=TENSORFOLD_KEY,
    )
    with wire(tensorfold_ok):
        record = await recorder.record_deploy(
            FACTS,
            registry=MemoryDeployRegistry(),
            profiles=_profiles([(TENSORFOLD_SERVED, True), ("qwen2.5:3b-instruct", True)]),
            llm=llm,
            instances=[],
            now=NOW,
        )

    assert record.models == (
        ModelWeights("qwen2.5:3b-instruct", None, served=False),
        ModelWeights(
            TENSORFOLD_SERVED,
            "hf:nvidia/Qwen3.8-27B-NVFP4@482ca0f3832238542f8f5295dde86b5f22711d80",
            served=True,
        ),
    )


async def test_a_provider_that_cannot_be_listed_records_every_digest_unknown(capsys):
    registry = MemoryDeployRegistry()

    record = await recorder.record_deploy(
        FACTS,
        registry=registry,
        profiles=_profiles([("qwen3.8:27b", True)]),
        llm=_llm(ConnectionError("ollama unreachable")),
        instances=[],
        now=NOW,
    )

    # Unreadable, so whether it is served is unknown too, never guessed as unserved.
    assert record.models == (ModelWeights("qwen3.8:27b", None, served=None),)
    assert len(record.services) == 4
    assert "model digests unavailable (ollama unreachable)" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("instance", "quiet"),
    [
        ({"id": "joi", "model": "llama3.1:8b", "enabled": True}, True),
        ({"id": "joi", "model": "llama3.1:8b", "enabled": False}, False),
        ({"id": "curator-agent", "model": "llama3.1:8b", "enabled": True}, False),
    ],
    ids=["the-deploys-chat-agent", "disabled", "an-agent-the-deploy-does-not-run"],
)
async def test_the_model_of_an_agent_the_deploy_runs_leaves_the_box_quiet(instance, quiet):
    """#2676, entered at ``record_deploy`` and read by the quiet-box check. Joi is no squad
    profile's member and answers chat on its instance's model. A record that left it out read a
    chat turn's resident model as foreign, and refused every launch until the engine unloaded it."""
    facts = {
        **FACTS,
        "services": [*FACTS["services"], {"service": "joi", "image_id": "sha256:joi"}],
    }
    record = await recorder.record_deploy(
        facts,
        registry=MemoryDeployRegistry(),
        profiles=_profiles([("qwen3.8:27b", True)]),
        llm=_llm([ModelInfo("llama3.1:8b", digest="46e0c10c039e")]),
        instances=[instance],
        now=NOW,
    )
    resident = EngineReading("ollama", (Model("llama3.1:8b", "46e0c10c039e"),), in_flight=0)

    assert box_quietness(declared_models(record), [resident]).quiet is quiet


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
            facts, registry=registry, profiles=_profiles([]), llm=_llm([]), instances=[], now=NOW
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


def _one_off(monkeypatch, instances_file):
    """The command's composition over stand-in ports, its config loader recording its arguments."""
    seen = {}

    def load_config(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(
            database=lambda: SimpleNamespace(url="postgresql://unused"),
            cycles=SimpleNamespace(registry_provider="memory", squad_profile_provider="config"),
            llm=SimpleNamespace(
                provider="ollama", url="http://ollama:11434", timeout=5, api_key=None, model=None
            ),
            agent=SimpleNamespace(instances_file=instances_file),
        )

    pool = AsyncMock()
    monkeypatch.setattr("squadops.api.runtime.record_deploy.load_config", load_config)
    monkeypatch.setattr("adapters.persistence.pool.create_pool", AsyncMock(return_value=pool))
    monkeypatch.setattr(
        "adapters.cycles.factory.create_squad_profile_port", lambda *a, **k: _profiles([])
    )
    monkeypatch.setattr("adapters.llm.factory.create_llm_provider", lambda **k: _llm([]))
    return seen, pool


async def test_the_one_off_loads_the_deploys_config_as_the_runtime_does(monkeypatch, tmp_path):
    """Wiring, entered at ``_compose_and_record``, the command's own composition. Bugs caught: the
    config loaded without the secret provider every root passes, so on a real deploy — whose
    configuration carries ``secret://`` references — the record failed before it began (the
    1.9 deploy's first record, ``ConfigValidationError``); and the configured agent instances
    file left unread, so an agent's own model went undeclared (#2676)."""
    from squadops.bootstrap.secrets import secret_provider_for

    instances_file = tmp_path / "instances.yaml"
    instances_file.write_text(
        "instances:\n  - {id: neo, model: qwen2.5:7b, enabled: true}\n"
        "  - {id: joi, model: llama3.1:8b, enabled: true}\n"
    )
    seen, pool = _one_off(monkeypatch, instances_file)

    record = await recorder._compose_and_record(FACTS)

    assert seen.get("secret_provider_factory") is secret_provider_for
    assert len(record.services) == 4
    # FACTS runs neo, not joi; the provider lists nothing, so the model is recorded unserved.
    assert record.models == (ModelWeights("qwen2.5:7b", None, served=False),)
    pool.close.assert_awaited_once()


async def test_a_deploy_without_its_agent_instances_file_is_refused_unrecorded(
    monkeypatch, tmp_path
):
    """Bug caught: a missing file read as no agents, so the record declared none of their models
    and the box refused launches beside them, with nothing saying why (#2676)."""
    _seen, pool = _one_off(monkeypatch, tmp_path / "absent.yaml")

    with pytest.raises(DeployFactsError, match="agent instances file .* is missing"):
        await recorder._compose_and_record(FACTS)

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
            database=lambda: SimpleNamespace(url="postgresql://unused"),
            cycles=SimpleNamespace(registry_provider="memory"),
        )

    pool = AsyncMock()
    monkeypatch.setattr("squadops.api.runtime.record_deploy.load_config", load_config)
    monkeypatch.setattr("adapters.persistence.pool.create_pool", AsyncMock(return_value=pool))

    record, stale = await recorder.compose_and_check(_RUNNING)

    assert seen.get("secret_provider_factory") is secret_provider_for
    assert (record, stale) == (None, ["no deploy is recorded"])
    pool.close.assert_awaited_once()
