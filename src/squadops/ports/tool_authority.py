"""The authority that governs a provider's operations (SIP-0116 §8, SIP-0117 R4.2, R4.6).

A skillset requests a tool; it grants nothing. Whether the request is within the authority that
already governs the operation is the provider's to say: its deny list, its argument and target
validation, its compatibility checks (for Studio, the product's eligibility rules). A provider
registers its authority at the composition root, keyed by its name, and cycle creation asks it
of every tool the cycle's work requires. A provider that registers none governs nothing, so its
tools are refused: carrying a skillset never authorizes an operation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from squadops.capabilities.skillsets import ToolRequest


@dataclass(frozen=True)
class BrokenRule:
    """A rule of the provider's authority a tool request breaks, and why."""

    rule: str
    why: str


class ToolAuthorityPort(Protocol):
    """One provider's authority over the operations it runs."""

    def broken_rules(
        self, tool: ToolRequest, *, project_id: str | None, config: Mapping[str, Any]
    ) -> list[BrokenRule]:
        """Each rule ``tool`` breaks for a cycle of ``config`` on ``project_id``, or ``[]``."""
        ...
