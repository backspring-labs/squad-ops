#!/usr/bin/env python3
"""
AgentRequest contract for SIP-046
Defines the structured input for agent capability requests
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentRequest:
    """Contract: AgentRequest for capability invocation"""

    action: str
    payload: dict[str, Any]
    metadata: dict[str, Any]

    def __post_init__(self):
        """Validate required metadata fields"""
        if "pid" not in self.metadata:
            raise ValueError("metadata.pid is required")
        # SIP-0048: cycle_id is required (ecid backward compatibility removed)
        if "cycle_id" not in self.metadata:
            raise ValueError("metadata.cycle_id is required")

    def generate_idempotency_key(self, agent_id: str) -> str:
        """Generate idempotency key from agent_id, action, payload, and metadata.pid"""
        key_data = {
            "agent_id": agent_id,
            "action": self.action,
            "payload": self.payload,
            "pid": self.metadata.get("pid"),
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict"""
        return {"action": self.action, "payload": self.payload, "metadata": self.metadata}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentRequest":
        """Create AgentRequest from dict"""
        return cls(
            action=data["action"],
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
        )

    def validate_action_format(self) -> bool:
        """Validate action matches capability format (e.g., build.artifact)"""
        parts = self.action.split(".")
        return len(parts) == 2 and all(part.replace("_", "").isalnum() for part in parts)
