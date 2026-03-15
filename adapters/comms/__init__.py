"""
Communication adapters for queue and messaging transport.

A2A modules (a2a_server, a2a_client, chat_executor) are imported lazily
at their call sites — they depend on a2a-sdk and uvicorn which are only
installed for agents with a2a_messaging_enabled.
"""

from adapters.comms.rabbitmq import QueueError, RabbitMQAdapter

__all__ = [
    "QueueError",
    "RabbitMQAdapter",
]
