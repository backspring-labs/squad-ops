"""Factories for the communication adapters — the composition roots' only way in (#301).

Each takes the typed ``CommsConfig`` and reads its selector; the vendor's own settings stay
under the vendor's key (``comms.rabbitmq.url``). Selectors are ``Literal`` and required in
the schema (R2), so an unknown value cannot reach a factory through ``load_config`` — the
``ValueError`` below is for a caller that builds ``CommsConfig`` by hand, and it names the
selector so the failure reads as misconfiguration, never as a missing adapter.

The profile-dictionary ``get_queue_adapter(profile, secret_manager)`` this file used to hold
predated the typed config: the loader resolves ``secret://`` before any factory runs, so its
``SecretManager`` parameter was dead, and its only caller was its own test. Ported, not kept
beside (no dual paths).
"""

from __future__ import annotations

import logging
from typing import Any

from adapters.comms.a2a_client import A2AClientAdapter
from adapters.comms.rabbitmq import RabbitMQAdapter
from squadops.config.schema import CommsConfig
from squadops.ports.comms.messaging import MessagingPort
from squadops.ports.comms.queue import QueuePort

logger = logging.getLogger(__name__)


def create_queue_adapter(comms: CommsConfig, *, prefetch_count: int | None = None) -> QueuePort:
    """The queue transport ``comms.queue.provider`` selects.

    ``prefetch_count`` is a tunable the agent root passes (1: the broker hands an agent one
    unacked message at a time, #323); the runtime root leaves it at the adapter's default.
    """
    provider = comms.queue.provider
    if provider == "rabbitmq":
        kwargs: dict[str, Any] = {"url": comms.rabbitmq.url}
        if prefetch_count is not None:
            kwargs["prefetch_count"] = prefetch_count
        return RabbitMQAdapter(**kwargs)
    raise ValueError(f"comms.queue.provider={provider!r}: no queue adapter for that selector")


def create_a2a_client(comms: CommsConfig) -> A2AClientAdapter:
    """The A2A client ``comms.a2a.provider`` selects, with its timeouts from config.

    Returns the adapter type: there is no client port in ``squadops.ports`` today — the
    runtime root hands it to ``deps.set_chat_ports`` typed ``object``. That gap is named in
    the #301 PR; a port is not invented here.
    """
    provider = comms.a2a.provider
    if provider == "http":
        return A2AClientAdapter(
            timeout_seconds=comms.a2a.timeout_seconds,
            agent_card_timeout_seconds=comms.a2a.agent_card_timeout_seconds,
        )
    raise ValueError(f"comms.a2a.provider={provider!r}: no A2A client for that selector")


def create_a2a_server(
    comms: CommsConfig,
    *,
    agent_card: Any,
    executor: Any,
    port: int,
    host: str = "0.0.0.0",
    log_level: str = "info",
) -> MessagingPort:
    """The A2A server ``comms.a2a.provider`` selects. Whether the agent binds one at all is
    the agent-level ``a2a_messaging_enabled`` switch; the selector decides what it binds."""
    # Imported HERE, not at module scope. `A2AServerAdapter` pulls the `a2a` SDK, which
    # only the AGENT lock ships — and this module's other two factories are what the
    # runtime-api needs. At module scope the import made `adapters.comms.factory`
    # unimportable in the runtime-api image, `_init_cycle_subsystem` swallowed the
    # ModuleNotFoundError into a log line, and every `cycles create` answered 500 with
    # "ProjectRegistryPort not configured" on a container reporting healthy (deploy B,
    # 2026-09-11). The client above is safe: it is httpx, not the SDK.
    from adapters.comms.a2a_server import A2AServerAdapter

    provider = comms.a2a.provider
    if provider == "http":
        return A2AServerAdapter(
            agent_card=agent_card, executor=executor, host=host, port=port, log_level=log_level
        )
    raise ValueError(f"comms.a2a.provider={provider!r}: no A2A server for that selector")
