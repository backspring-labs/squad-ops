"""Cross-Cycle Memory's routes: the lessons (SIP-0110 §0.6, slice 3d), the typed records
(Appendix A, #2177) and a unit's snapshot with its re-binding (Appendix A §3.7, #2179)."""

from squadops.api.routes.memory.lessons import router as memory_router
from squadops.api.routes.memory.records import router as memory_records_router
from squadops.api.routes.memory.snapshots import router as memory_snapshots_router

__all__ = ["memory_records_router", "memory_router", "memory_snapshots_router"]
