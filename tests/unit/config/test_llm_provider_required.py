"""``llm.provider`` is required configuration (#1157, SIP-0106 Ruling 3).

A selector at a composition seam is never defaulted: with the old ``default_factory``
an ``AppConfig`` built with no LLM section at all quietly ran Ollama, and
``SQUADOPS__LLM__PROVIDER`` did not exist as a key.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from squadops.config.loader import _parse_env_overrides
from squadops.config.schema import (
    AppConfig,
    AuthConfig,
    CommsConfig,
    DBConfig,
    LLMConfig,
    RabbitMQConfig,
    RedisConfig,
)

pytestmark = [pytest.mark.domain_contracts]


def _rest() -> dict:
    return {
        "db": DBConfig(url="postgresql://u@localhost:5432/db"),
        "comms": CommsConfig(
            rabbitmq=RabbitMQConfig(url="amqp://u@localhost:5672/"),
            redis=RedisConfig(url="redis://localhost:6379/0"),
        ),
        "auth": AuthConfig(enabled=False),
    }


def test_llm_config_without_a_provider_fails_to_validate():
    with pytest.raises(ValidationError) as exc:
        LLMConfig()  # type: ignore[call-arg]
    assert "provider" in str(exc.value)


def test_app_config_without_an_llm_section_fails_rather_than_defaulting():
    with pytest.raises(ValidationError) as exc:
        AppConfig(**_rest())
    assert "llm" in str(exc.value)


def test_the_provider_is_carried_through_and_other_llm_fields_keep_defaults():
    cfg = AppConfig(**_rest(), llm=LLMConfig(provider="vllm"))
    assert cfg.llm.provider == "vllm"
    assert cfg.llm.timeout == 180  # only the selector is required


def test_env_var_reaches_the_llm_provider_field(monkeypatch):
    """``SQUADOPS__LLM__PROVIDER`` nests as ``llm.provider`` — the key a deploy
    surface writes is the key the schema reads. (The old ``SQUADOPS__LLM__USE__LOCAL``
    in ``.env.example`` nested as ``llm.use.local`` and reached nothing.)"""
    monkeypatch.setenv("SQUADOPS__LLM__PROVIDER", "vllm")
    overrides = _parse_env_overrides()
    assert overrides["llm"]["provider"] == "vllm"
