"""Remote execution port (SIP-0117 R3.3, R4.4).

One operation: run a provider's operation for a request and return its result. Everything
about how the operation reaches the provider (a worker that connects outward, its claim,
lease and fence) is an adapter's, behind this port. The handler of ``qa.run_remote_operation``
is its only caller.

An implementation returns a ``RemoteOperationResult`` for every request it accepts. When the
operation can't run it says so, as ``not_executed`` with the reason; it doesn't raise for
that, and it never returns a pass for an operation that didn't run.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.remote_execution.models import RemoteOperationRequest, RemoteOperationResult


class RemoteExecutionPort(ABC):
    @abstractmethod
    async def run_operation(self, request: RemoteOperationRequest) -> RemoteOperationResult:
        """Run ``request``'s operation and return what the provider reported."""
