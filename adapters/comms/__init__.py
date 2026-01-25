"""
Communication adapters for queue transport.
"""

from adapters.comms.rabbitmq import QueueError, RabbitMQAdapter

__all__ = ["RabbitMQAdapter", "QueueError"]
