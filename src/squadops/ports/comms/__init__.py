"""
Communication port interfaces.
"""

from squadops.ports.comms.messaging import MessagingPort
from squadops.ports.comms.noop import NoOpQueuePort
from squadops.ports.comms.queue import QueuePort

__all__ = ["QueuePort", "NoOpQueuePort", "MessagingPort"]
