"""
Cycle execution API routes (SIP-0064, SIP-0074).
"""

from squadops.api.routes.cycles.artifacts import router as artifacts_router
from squadops.api.routes.cycles.cycle_request_profiles import (
    router as cycle_request_profiles_router,
)
from squadops.api.routes.cycles.cycles import router as cycles_router
from squadops.api.routes.cycles.models import router as models_router
from squadops.api.routes.cycles.profiles import router as profiles_router
from squadops.api.routes.cycles.projects import router as projects_router
from squadops.api.routes.cycles.runs import router as runs_router

__all__ = [
    "projects_router",
    "cycles_router",
    "runs_router",
    "profiles_router",
    "artifacts_router",
    "cycle_request_profiles_router",
    "models_router",
]
