"""The context-assembly port (SIP-0110 Appendix A §3.6; #2176, inert in 2.3).

The consuming seams ask it what a task, or a chat turn, is given before it authors, and it discloses the answer.
In 2.3 its one section is the lessons recall supplies, so a task's prompt is the one it had before the port
existed; 2.4 adds the binding sections (#2179) and chat's (#2180) behind the same two calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.memory.context import ContextBundle, ContextRequest


class ContextAssemblyPort(ABC):
    @abstractmethod
    async def assemble(self, request: ContextRequest) -> ContextBundle:
        """Each section's records and disposition. Never raises: a failure is a section's disposition."""

    @abstractmethod
    async def disclose(self, bundle: ContextBundle) -> None:
        """Record what the consumer was given: one exposure per invocation or turn. Never raises."""
