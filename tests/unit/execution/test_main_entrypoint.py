"""Execution service composition root (SIP-0102 — 102.1 slice d)."""

import pytest

from squadops.execution.main import execution_config_from_env


def test_env_section_is_parsed_and_coerced(monkeypatch):
    """Bug caught: the env convention (SQUADOPS__EXECUTION__*, double
    underscores) not reaching the service, or string env values not coerced
    to their schema types."""
    monkeypatch.setenv("SQUADOPS__EXECUTION__PROVIDER", "docker")
    monkeypatch.setenv("SQUADOPS__EXECUTION__APP_PORT", "9001")
    monkeypatch.setenv("SQUADOPS__EXECUTION__IMAGE", "sandbox:pinned")
    config = execution_config_from_env()
    assert config.provider == "docker"
    assert config.app_port == 9001
    assert config.image == "sandbox:pinned"


def test_typoed_env_setting_fails_loudly(monkeypatch):
    """Bug caught: pydantic silently ignoring an unknown constructor kwarg —
    a typo'd env var (IMGAE) would deploy as an unconfigured default."""
    monkeypatch.setenv("SQUADOPS__EXECUTION__IMGAE", "sandbox:pinned")
    with pytest.raises(ValueError, match="unknown SQUADOPS__EXECUTION__"):
        execution_config_from_env()
