"""
Transport-neutral queue message wrapper.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class QueueMessage:
    """
    Transport-neutral message wrapper for queue operations.

    The payload MUST be ACI TaskEnvelope JSON only.
    Adapters must not mutate TaskEnvelope identity or lineage fields.
    """

    message_id: str
    """Provider-specific message identifier"""

    queue_name: str
    """Name of the queue this message came from"""

    payload: str
    """Message payload (ACI TaskEnvelope JSON)"""

    receipt_handle: str
    """Provider-specific acknowledgment token (used for ack/retry operations)"""

    attributes: dict[str, Any]
    """Provider-specific metadata (e.g., delivery count, timestamp, etc.)"""
