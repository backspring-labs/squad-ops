"""Campaign API routes (SIP-0109 §13, #1799)."""

from squadops.api.routes.campaigns.campaigns import router as campaigns_router

__all__ = ["campaigns_router"]
