"""The orchestrator's per-task wait is its own setting (#1147), and required (1.8.2 item 15).

``SQUADOPS__LLM__TIMEOUT`` bounded both one HTTP call to the model and the orchestrator's
wait for a whole task; raising it for a long qa emission raised the hung-agent detector
with it. #1147 read the two from different keys but let an unset task wait follow the request
timeout, which is how deploy B″ ran: a hang detector at 1,800 s that nobody declared. It is
now required where it is read, and never follows ``llm.timeout``.
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


def test_unset_is_refused_where_it_is_read_and_never_follows_the_request_timeout():
    """Bug this catches: the #1147 fallback, where raising the model-call timeout for a long
    emission silently raised the hung-agent detector with it."""
    with pytest.raises(ValueError, match="SQUADOPS__DISPATCH__TASK_TIMEOUT"):
        _config().task_timeout_seconds()


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


def test_an_empty_passthrough_is_unset_and_so_refused_where_it_is_read(monkeypatch, caplog):
    """A blank value is not a value: the loader reads it as unset without the old "Invalid
    value … using as string" warning, the schema refuses a blank given directly, and the one
    reader refuses unset. Compose refuses to start the runtime API before any of this
    (``${SQUADOPS__DISPATCH__TASK_TIMEOUT:?…}``)."""
    monkeypatch.setenv("SQUADOPS__DISPATCH__TASK_TIMEOUT", "")
    with caplog.at_level("WARNING"):
        overrides = _parse_env_overrides()
    assert overrides["dispatch"]["task_timeout"] is None
    assert "Invalid value" not in caplog.text
    with pytest.raises(ValueError):
        DispatchConfig(task_timeout="")


@pytest.mark.parametrize("bad", [0, -5])
def test_a_non_positive_wait_is_refused(bad):
    with pytest.raises(ValueError):
        DispatchConfig(task_timeout=bad)
