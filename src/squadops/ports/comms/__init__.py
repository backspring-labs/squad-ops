"""
Communication port interfaces.
"""

from squadops.ports.comms.queue import QueuePort
from squadops.ports.comms.noop import NoOpQueuePort

__all__ = ["QueuePort", "NoOpQueuePort"]
