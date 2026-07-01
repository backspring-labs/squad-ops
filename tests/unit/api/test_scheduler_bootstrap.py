"""Unit tests for SIP-0089 §2.4 activation gate — `create_duty_scheduler`.

This factory is the whole point of "activating" the scheduler: it decides, from
config + pool, whether a live `DutyScheduler` exists at all. The bug classes it
guards:
- accidental activation: a disabled config (the opt-in default) must yield no
  scheduler, even when a pool is present;
- a missing precondition: enabled but pool-less must not return a scheduler that
  would then NPE against absent assignment/state tables;
- lifecycle: the factory must hand back an INERT scheduler (not yet polling) so
  the composition root owns `start()`/`stop()` — per the plan, "must not start
  implicitly".
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from squadops.api.runtime.scheduler_bootstrap import (
    create_duty_scheduler,
    create_runtime_coordinator,
)
from squadops.config.schema import (
    AppConfig,
    AuthConfig,
    CommsConfig,
    DBConfig,
    RabbitMQConfig,
    RedisConfig,
)
from squadops.runtime.coordinator import RuntimeCoordinator
from squadops.runtime.scheduler import DutyScheduler

pytestmark = [pytest.mark.domain_runtime]


def _config(*, enabled: bool, poll: int = 30) -> AppConfig:
    return AppConfig(
        db=DBConfig(url="postgresql://u@localhost:5432/db"),
        comms=CommsConfig(
            rabbitmq=RabbitMQConfig(url="amqp://u@localhost:5672/"),
            redis=RedisConfig(url="redis://localhost:6379/0"),
        ),
        auth=AuthConfig(enabled=False),
        runtime={"scheduler": {"enabled": enabled, "poll_interval_seconds": poll}},
    )


def test_disabled_config_returns_no_scheduler_even_with_pool():
    """Bug class: the opt-in default must not be overridable by mere presence of
    a pool. Disabled means no scheduler, full stop."""
    assert create_duty_scheduler(_config(enabled=False), MagicMock()) is None


def test_enabled_without_pool_returns_none():
    """Bug class: assignments + runtime state both live in Postgres. Returning a
    scheduler with no pool would defer the failure to the first tick (an NPE
    against a None pool). Refuse to build it instead."""
    assert create_duty_scheduler(_config(enabled=True), None) is None


def test_enabled_with_pool_builds_inert_scheduler_with_configured_interval():
    """Bug class: activation must produce a real DutyScheduler carrying the
    configured poll interval, and it must be INERT — the factory hands ownership
    of start()/stop() to the composition root (no implicit background ticking)."""
    scheduler = create_duty_scheduler(_config(enabled=True, poll=7), MagicMock())

    assert isinstance(scheduler, DutyScheduler)
    assert scheduler._poll_interval_seconds == 7
    assert scheduler._task is None  # not started by the factory


def test_enabled_scheduler_coordinator_has_focus_lease_and_activity_wired():
    """Bug class (§3.4/§4.5 activation): the coordinator must be built WITH both a
    FocusLeasePort and a RuntimeActivityPort, else duty transitions silently skip
    lease arbitration / the activity seam even though Phase 3/4 shipped. Guards
    against the wiring regressing to a bare `RuntimeCoordinator(state, ...)`."""
    scheduler = create_duty_scheduler(_config(enabled=True), MagicMock())

    assert scheduler is not None
    assert scheduler._coordinator._focus_lease is not None
    assert scheduler._coordinator._activity is not None


def test_create_runtime_coordinator_without_pool_returns_none():
    """Bug class: the focus-lease + runtime-state tables live in Postgres, so a
    pool-less coordinator can't function. Recruitment must fall back to the §2.5
    guard (executor wires coordinator=None), not get a half-built coordinator."""
    assert create_runtime_coordinator(None) is None


def test_create_runtime_coordinator_wires_focus_lease_activity_and_transaction():
    """The shared coordinator (used by the executor for recruitment) must carry
    the §3.4/§4.5 wiring — focus lease, activity, AND the RuntimeTransaction UoW
    (#244/D25). A bare coordinator would skip lease arbitration on recruitment, and
    a missing transaction would silently fall back to best-effort compensation
    instead of an atomic rollback."""
    from adapters.persistence.runtime import PostgresRuntimeTransaction

    coordinator = create_runtime_coordinator(MagicMock())

    assert isinstance(coordinator, RuntimeCoordinator)
    assert coordinator._focus_lease is not None
    assert coordinator._activity is not None
    assert isinstance(coordinator._transaction, PostgresRuntimeTransaction)


def test_injected_coordinator_is_shared_not_rebuilt():
    """D16 single-writer: when the composition root injects its coordinator, the
    scheduler must drive THAT instance, not build a second mode-writer. A rebuild
    here would silently create two writers of AgentRuntimeState.mode."""
    shared = create_runtime_coordinator(MagicMock())

    scheduler = create_duty_scheduler(_config(enabled=True), MagicMock(), coordinator=shared)

    assert scheduler is not None
    assert scheduler._coordinator is shared
