"""The worker's composition root (SIP-0117 R5.5)."""

from __future__ import annotations

import os
import platform
import typing

import pytest
from pydantic import ValidationError

from squadops.config.schema import PROVIDER_SETTINGS, WorkerConfig
from squadops.remote_execution.worker_main import (
    build_worker,
    client_secret,
    worker_config_from_env,
)

SECTION = {
    "SQUADOPS__WORKER__WORKER_ID": "macbook",
    "SQUADOPS__WORKER__RUNTIME_API_URL": "http://spark.test:8001",
    "SQUADOPS__WORKER__TOKEN_ENDPOINT": "http://spark.test:8180/realms/r/protocol/openid-connect/token",
    "SQUADOPS__WORKER__CLIENT_ID": "squadops-worker",
    "SQUADOPS__WORKER__CLIENT_SECRET": "a-literal-secret",
    "SQUADOPS__WORKER__PROVIDER": "fixture",
}


@pytest.fixture
def env(monkeypatch):
    """The worker's section set, and nothing else of the worker's or the secrets section's
    from the process running the tests."""
    for key in list(os.environ):
        if key.startswith(("SQUADOPS__WORKER__", "SQUADOPS__SECRETS__")):
            monkeypatch.delenv(key)
    for key, value in SECTION.items():
        monkeypatch.setenv(key, value)
    return monkeypatch


def _secret_manager():
    from squadops.bootstrap.secrets import secret_manager_from_env

    return secret_manager_from_env()


def test_the_section_is_read_from_its_variables(env):
    """Bug caught: a field read under another name, so a worker starts against a default."""
    config = worker_config_from_env()

    assert config.model_dump() == {
        "worker_id": "macbook",
        "runtime_api_url": "http://spark.test:8001",
        "token_endpoint": SECTION["SQUADOPS__WORKER__TOKEN_ENDPOINT"],
        "client_id": "squadops-worker",
        "client_secret": "a-literal-secret",
        "provider": "fixture",
    } | {name: None for name in PROVIDER_SETTINGS["roblox-studio"]}


@pytest.mark.parametrize("key", sorted(SECTION))
def test_every_field_is_required_and_a_blank_one_is_refused(env, key):
    """Bug caught: a worker that starts with no address, identity or provider and serves a
    default, or one given an empty value by an unset variable."""
    field = key.removeprefix("SQUADOPS__WORKER__").lower()
    env.setenv(key, "")
    with pytest.raises(ValidationError, match=field):
        worker_config_from_env()
    env.delenv(key)
    with pytest.raises(ValidationError, match=field):
        worker_config_from_env()


def test_a_misspelled_variable_and_a_provider_outside_the_vocabulary_are_refused(env):
    env.setenv("SQUADOPS__WORKER__PROVIDER", "roblox-studoi")
    with pytest.raises(ValidationError, match="provider"):
        worker_config_from_env()
    env.setenv("SQUADOPS__WORKER__PROVIDER", "fixture")
    env.setenv("SQUADOPS__WORKER__RUNTIME_URL", "http://spark.test:8001")
    with pytest.raises(
        ValueError, match="unknown SQUADOPS__WORKER__ settings: \\['runtime_url'\\]"
    ):
        worker_config_from_env()


def test_a_secret_reference_is_resolved_and_one_with_no_provider_is_refused(env):
    """Bug caught: ``secret://…`` sent to the identity provider as the password, which reads
    there as a wrong secret and nowhere as a configuration fault."""
    env.setenv("SQUADOPS__WORKER__CLIENT_SECRET", "secret://worker_secret")
    config = worker_config_from_env()

    with pytest.raises(ValueError, match="no secrets provider is configured"):
        client_secret(config, _secret_manager())

    env.setenv("SQUADOPS__SECRETS__PROVIDER", "env")
    env.setenv("SQUADOPS__SECRETS__ENV_PREFIX", "WORKER_TEST_")
    env.setenv("WORKER_TEST_WORKER_SECRET", "the-real-secret")
    assert client_secret(config, _secret_manager()) == "the-real-secret"


async def test_the_root_builds_a_worker_that_registers_as_configured(env, monkeypatch):
    """The wiring, entered at ``build_worker``. Bug caught: the worker built with another id,
    or with a runner other than the provider's, so it registers as something it isn't. The
    runtime here is the factory's adapter with its calls recorded."""
    import adapters.remote_execution.factory as factory
    from squadops.remote_execution.workers import WorkerRefused

    registered = []
    bound = []

    class Recording:
        async def register(self, registration):
            registered.append(registration)
            raise WorkerRefused("the test ends the worker at its first call")

        async def close(self):
            bound.append("closed")

    def create_worker_api(base_url, token):
        bound.append(base_url)
        return Recording()

    monkeypatch.setattr(factory, "create_worker_api", create_worker_api)
    worker, close = build_worker(worker_config_from_env(), _secret_manager())

    with pytest.raises(WorkerRefused):
        await worker.serve()
    await close()

    (registration,) = registered
    assert registration.worker_id == "macbook"
    assert [(o.provider, o.operation) for o in registration.operations] == [
        ("fixture", "declared_scenario")
    ]
    assert registration.tool_versions == {"fixture": "2", "reader": "fixture/1"}
    assert registration.platform == f"{platform.system().lower()}-{platform.machine().lower()}"
    assert bound == ["http://spark.test:8001", "closed"]


def _studio_section(tmp_path) -> dict[str, str]:
    for name in ("StudioMCP", "ta-copy.rbxl", "ta-copy.pristine.rbxl"):
        (tmp_path / name).write_bytes(b"x")
    return {
        "SQUADOPS__WORKER__PROVIDER": "roblox-studio",
        "SQUADOPS__WORKER__ROBLOX_STUDIO_MCP": str(tmp_path / "StudioMCP"),
        "SQUADOPS__WORKER__ROBLOX_STUDIO_PLACE_FILE": str(tmp_path / "ta-copy.rbxl"),
        "SQUADOPS__WORKER__ROBLOX_STUDIO_BASELINE_FILE": str(tmp_path / "ta-copy.pristine.rbxl"),
        "SQUADOPS__WORKER__ROBLOX_STUDIO_BASELINE_SHA256": "49157df1" * 8,
        "SQUADOPS__WORKER__ROBLOX_STUDIO_BASELINE_DIGEST": "354636ad" * 8,
        "SQUADOPS__WORKER__ROBLOX_STUDIO_PROVED_VERSION": "0.747.0",
        "SQUADOPS__WORKER__ROBLOX_STUDIO_PROVED_TOOLS": "38:" + "1ba499d8" * 8,
    }


def test_a_studio_worker_is_built_with_the_runner_its_package_creates(env, tmp_path):
    """The wiring, entered at ``build_worker``: the provider found in its package, not named in
    the factory (R4.6). Bug caught: a setting dropped between the config and the runner, so the
    worker resets from, or pins, something other than what it was configured with."""
    for key, value in _studio_section(tmp_path).items():
        env.setenv(key, value)

    worker, _ = build_worker(worker_config_from_env(), _secret_manager())

    runner = worker._runner
    assert [(o.provider, o.operation) for o in runner.serves()] == [
        ("roblox-studio", "play_scenario")
    ]
    assert (runner._files.place, runner._files.baseline_digest) == (
        tmp_path / "ta-copy.rbxl",
        "354636ad" * 8,
    )
    assert (runner._proved.studio_version, runner._proved.studio_tools) == (
        "0.747.0",
        "38:" + "1ba499d8" * 8,
    )


@pytest.mark.parametrize("dropped", sorted(PROVIDER_SETTINGS["roblox-studio"]))
def test_a_studio_worker_needs_every_one_of_its_settings(env, tmp_path, dropped):
    """Bug caught: a Studio worker started without its baseline pin or proved-on version, so a
    drifted place or an updated Studio goes unnoticed."""
    for key, value in _studio_section(tmp_path).items():
        env.setenv(key, value)
    env.delenv(f"SQUADOPS__WORKER__{dropped.upper()}")

    with pytest.raises(
        ValidationError, match=f"roblox-studio needs SQUADOPS__WORKER__{dropped.upper()}"
    ):
        worker_config_from_env()


def test_a_setting_the_provider_doesnt_read_is_refused(env, tmp_path):
    """Bug caught: a fixture worker given Studio's place file, which it ignores, so the person
    configuring it believes Studio is served."""
    env.setenv("SQUADOPS__WORKER__ROBLOX_STUDIO_PLACE_FILE", str(tmp_path / "ta-copy.rbxl"))

    with pytest.raises(
        ValidationError, match="fixture doesn't read SQUADOPS__WORKER__ROBLOX_STUDIO_PLACE_FILE"
    ):
        worker_config_from_env()


def test_a_studio_file_that_isnt_there_stops_the_worker_before_it_registers(env, tmp_path):
    """Bug caught: a worker on a mistyped path registering as serving, and failing every claim."""
    for key, value in _studio_section(tmp_path).items():
        env.setenv(key, value)
    (tmp_path / "ta-copy.pristine.rbxl").unlink()

    with pytest.raises(ValueError, match="files aren't there: roblox_studio_baseline_file"):
        build_worker(worker_config_from_env(), _secret_manager())


def test_each_provider_has_its_settings_listed_and_its_package_reads_the_same_ones():
    """Bug caught: a provider added to the vocabulary with no settings entry, failing at start
    with a KeyError; or the schema and the adapter disagreeing about a setting's name."""
    from adapters.remote_execution.game_dev_roblox_studio import worker

    provider = typing.get_args(WorkerConfig.model_fields["provider"].annotation)
    assert set(PROVIDER_SETTINGS) == set(provider)
    assert worker.SETTINGS == PROVIDER_SETTINGS["roblox-studio"]
