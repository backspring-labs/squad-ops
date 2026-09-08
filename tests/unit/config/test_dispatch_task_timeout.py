"""The orchestrator's per-task wait is its own setting (#1147).

``SQUADOPS__LLM__TIMEOUT`` bounded both one HTTP call to the model and the orchestrator's
wait for a whole task; raising it for a long qa emission raised the hung-agent detector
with it. The two are now read from different keys, and the task wait follows the request
timeout only while unset.
"""

from __future__ import annotations

import pytest

from squadops.config.loader import _parse_env_overrides
from squadops.config.schema import AppConfig, DispatchConfig, LLMConfig
from tests.unit.config.test_llm_provider_required import _rest

pytestmark = [pytest.mark.unit]


def _config(**dispatch) -> AppConfig:
    return AppConfig(
        **_rest(),
        llm=LLMConfig(provider="ollama", timeout=1800),
        dispatch=DispatchConfig(**dispatch),
    )


def test_unset_follows_the_request_timeout_so_a_deploy_keeps_behaving():
    assert _config().task_timeout_seconds() == 1800.0


def test_set_it_is_read_apart_from_the_request_timeout():
    cfg = _config(task_timeout=600)
    assert cfg.task_timeout_seconds() == 600.0
    assert cfg.llm.timeout == 1800, "the request timeout is untouched"


def test_the_two_settings_arrive_on_different_env_keys(monkeypatch):
    """The bug this catches: a single key feeding both quantities."""
    monkeypatch.setenv("SQUADOPS__LLM__TIMEOUT", "1800")
    monkeypatch.setenv("SQUADOPS__DISPATCH__TASK_TIMEOUT", "900")
    overrides = _parse_env_overrides()
    assert overrides["llm"]["timeout"] == 1800
    assert overrides["dispatch"]["task_timeout"] == 900


def test_an_empty_passthrough_is_unset_not_an_error_and_not_a_warning(monkeypatch, caplog):
    """docker-compose hands an unset variable through as "" — that must read as unset,
    silently: the old path warned "Invalid value … using as string" at every start."""
    monkeypatch.setenv("SQUADOPS__DISPATCH__TASK_TIMEOUT", "")
    with caplog.at_level("WARNING"):
        overrides = _parse_env_overrides()
    assert overrides["dispatch"]["task_timeout"] is None
    assert "Invalid value" not in caplog.text
    assert DispatchConfig(task_timeout="").task_timeout is None


@pytest.mark.parametrize("bad", [0, -5])
def test_a_non_positive_wait_is_refused(bad):
    with pytest.raises(ValueError):
        DispatchConfig(task_timeout=bad)
