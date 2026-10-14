"""SIP-042's per-agent store, dormant (SIP-0110 §A.4.3, #2174).

The legacy LanceDB store holds no record in any of the eight agent stores, and no agent can write
one: its embedder was built at an address nobody set, for a model nobody installed, and the
failure was swallowed (#2171). The accepted design retires the store rather than restoring that
path, so until its retirement (#2184) the agents hold this port in its place. Nothing calls it.
A call that does is refused loudly: logged at WARNING with the refusal, then raised.
"""

from __future__ import annotations

import logging

from squadops.memory.exceptions import MemoryDormantError
from squadops.memory.models import MemoryEntry, MemoryQuery, MemoryResult
from squadops.ports.memory.store import MemoryPort

logger = logging.getLogger(__name__)


class DormantMemoryPort(MemoryPort):
    """Refuses every operation: the legacy agent store is dormant."""

    async def store(self, entry: MemoryEntry) -> str:
        raise _refused("store")

    async def search(self, query: MemoryQuery) -> list[MemoryResult]:
        raise _refused("search")

    async def get(self, memory_id: str) -> MemoryEntry | None:
        raise _refused("get")

    async def delete(self, memory_id: str) -> bool:
        raise _refused("delete")


def _refused(operation: str) -> MemoryDormantError:
    error = MemoryDormantError(
        f"legacy agent memory is dormant (SIP-0110 §A.4.3, #2174): {operation} refused"
    )
    logger.warning("%s", error)
    return error
