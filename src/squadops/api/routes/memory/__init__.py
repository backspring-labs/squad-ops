"""Cross-Cycle Memory's routes: the lessons (SIP-0110 §0.6, slice 3d) and the typed records
(Appendix A, #2177)."""

from squadops.api.routes.memory.lessons import router as memory_router
from squadops.api.routes.memory.records import router as memory_records_router

__all__ = ["memory_records_router", "memory_router"]
