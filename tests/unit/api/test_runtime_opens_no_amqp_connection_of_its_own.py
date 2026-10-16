"""The runtime API publishes only through the queue port (#2322).

Until 2.3.1 the runtime's startup opened an AMQP connection and a channel of its own and kept
them on ``app.state``. Nothing read either. Every publish goes through the queue port, which
opens its own connection and, since #1977 §5.2, raises on a returned publish. A second channel
configured otherwise is a path that would not.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aio_pika
import pytest

from squadops.api.runtime import main as runtime_main

pytestmark = [pytest.mark.domain_api]

_SUBSYSTEMS = (
    "_init_auth_subsystem",
    "_init_migrations",
    "_init_log_forwarding",
    "_init_cycle_subsystem",
    "_init_monitoring",
    "_init_duty_scheduler",
    "_resume_campaigns",
    "_sweep_campaigns",
    "_reconcile_memory",
)


async def test_startup_opens_no_amqp_connection_outside_the_queue_port(monkeypatch):
    """Bug caught: the composition root opens its own AMQP connection again, beside the
    queue port's, as it did until #2322.

    Driven through ``_startup`` with every subsystem stubbed, so the only AMQP connection it
    could open is one of its own. Both of aio_pika's connect functions are watched, and the
    state it leaves holds no AMQP slot.
    """
    opened = []
    for name in ("connect", "connect_robust"):
        record = AsyncMock(side_effect=lambda *a, n=name, **k: opened.append(n))
        monkeypatch.setattr(aio_pika, name, record)
    monkeypatch.setattr(runtime_main, "create_pool", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(runtime_main, "_init_memory", MagicMock())
    for name in _SUBSYSTEMS:
        monkeypatch.setattr(runtime_main, name, AsyncMock())
    app = SimpleNamespace(state=SimpleNamespace(config=MagicMock()))

    await runtime_main._startup(app)

    assert opened == []
    assert [slot for slot in vars(app.state) if "rabbitmq" in slot] == []
