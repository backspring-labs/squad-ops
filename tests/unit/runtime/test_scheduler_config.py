"""Unit tests for SIP-0089 §2.4 scheduler config (`runtime.scheduler`).

The activation gate reads `config.runtime.scheduler.{enabled,poll_interval_seconds}`,
so two bug classes matter here:
- the new `runtime` section must actually be wired into `AppConfig` (a default
  that silently dropped it would make every deployment un-activatable, or worse,
  read a stale default), and
- `poll_interval_seconds` must reject non-positive values — a 0s interval turns
  the poll loop into an unthrottled hot spin.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from squadops.config.schema import (
    AppConfig,
    AuthConfig,
    CommsConfig,
    DBConfig,
    RabbitMQConfig,
    RedisConfig,
    SchedulerConfig,
)

pytestmark = [pytest.mark.domain_runtime]


def _app_config(runtime: dict | None = None) -> AppConfig:
    """Build a minimal valid AppConfig, optionally overriding the runtime section."""
    kwargs: dict = {
        "db": DBConfig(url="postgresql://u@localhost:5432/db"),
        "comms": CommsConfig(
            rabbitmq=RabbitMQConfig(url="amqp://u@localhost:5672/"),
            redis=RedisConfig(url="redis://localhost:6379/0"),
        ),
        "auth": AuthConfig(enabled=False),
    }
    if runtime is not None:
        kwargs["runtime"] = runtime
    return AppConfig(**kwargs)


def test_runtime_scheduler_defaults_to_disabled_when_section_omitted():
    """Bug class: if the `runtime` field were not wired into AppConfig (or its
    default_factory dropped), activation would read the wrong default. Omitting
    the section entirely must still yield the opt-in-safe default: disabled,
    30s poll. A regression to enabled-by-default would auto-activate the single
    central mode-writer in every deployment."""
    cfg = _app_config()
    assert cfg.runtime.scheduler.enabled is False
    assert cfg.runtime.scheduler.poll_interval_seconds == 30


def test_runtime_scheduler_override_nests_into_app_config():
    """Bug class: a mis-wired nested field would ignore the override and keep the
    default. An explicit override must reach `runtime.scheduler`."""
    cfg = _app_config(runtime={"scheduler": {"enabled": True, "poll_interval_seconds": 5}})
    assert cfg.runtime.scheduler.enabled is True
    assert cfg.runtime.scheduler.poll_interval_seconds == 5


@pytest.mark.parametrize("bad_interval", [0, -1])
def test_poll_interval_rejects_non_positive(bad_interval):
    """Bug class: a 0s (or negative) interval would make the scheduler poll loop
    spin without throttling. The `ge=1` constraint must reject it at load time,
    not at runtime."""
    with pytest.raises(ValidationError):
        SchedulerConfig(poll_interval_seconds=bad_interval)
