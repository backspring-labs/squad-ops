"""Sandbox service composition root (SIP-0102 — 102.1 slice d)."""

import os

import pytest
from fastapi.testclient import TestClient

from squadops.sandbox.main import build_app, sandbox_config_from_env, secret_manager_from_env


@pytest.fixture
def clean_env(monkeypatch):
    """No SQUADOPS__SANDBOX__ or SQUADOPS__SECRETS__ setting from the process running the tests."""
    for key in list(os.environ):
        if key.startswith(("SQUADOPS__SANDBOX__", "SQUADOPS__SECRETS__")):
            monkeypatch.delenv(key)
    return monkeypatch


def test_env_section_is_parsed_and_coerced(monkeypatch):
    """Bug caught: the env convention (SQUADOPS__SANDBOX__*, double
    underscores) not reaching the service, or string env values not coerced
    to their schema types."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "docker")
    monkeypatch.setenv("SQUADOPS__SANDBOX__APP_PORT", "9001")
    monkeypatch.setenv("SQUADOPS__SANDBOX__IMAGE", "sandbox:pinned")
    config = sandbox_config_from_env()
    assert config.provider == "docker"
    assert config.app_port == 9001
    assert config.image == "sandbox:pinned"


def test_typoed_env_setting_fails_loudly(monkeypatch):
    """Bug caught: pydantic silently ignoring an unknown constructor kwarg —
    a typo'd env var (IMGAE) would deploy as an unconfigured default."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__IMGAE", "sandbox:pinned")
    with pytest.raises(ValueError, match="unknown SQUADOPS__SANDBOX__"):
        sandbox_config_from_env()


def test_a_secret_token_is_resolved_before_it_reaches_the_app(clean_env, tmp_path):
    """#1982, entered at the sandbox's composition root. Bug caught: a ``secret://`` service
    token, the form ``.env.example`` documents for secrets, crashing the sandbox at startup, or
    reaching the app unresolved so every caller's real token is refused."""
    clean_env.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")
    clean_env.setenv("SQUADOPS__SANDBOX__WORKSPACE_ROOT", str(tmp_path))
    clean_env.setenv("SQUADOPS__SANDBOX__SERVICE_TOKEN", "secret://sandbox_token")
    clean_env.setenv("SQUADOPS__SECRETS__PROVIDER", "env")
    clean_env.setenv("SQUADOPS__SECRETS__ENV_PREFIX", "SANDBOX_TEST_")
    clean_env.setenv("SANDBOX_TEST_SANDBOX_TOKEN", "the-real-token")

    client = TestClient(build_app())

    def status(bearer: str) -> int:
        return client.post(
            "/api/v1/workspaces/cyc_x/seed", json={}, headers={"Authorization": bearer}
        ).status_code

    assert status("Bearer secret://sandbox_token") == 401
    assert status("Bearer the-real-token") != 401


def test_no_secrets_section_selects_no_manager(clean_env):
    """The sandbox's literal-token deploy (compose today) configures no secrets provider."""
    assert secret_manager_from_env() is None


def test_a_typoed_secrets_setting_fails_loudly(clean_env):
    clean_env.setenv("SQUADOPS__SECRETS__PROVIDRE", "env")
    with pytest.raises(ValueError, match="unknown SQUADOPS__SECRETS__"):
        secret_manager_from_env()
