"""Chat API routes for console messaging (SIP-0085)."""

from squadops.api.routes.chat.routes import agents_router
from squadops.api.routes.chat.routes import router as chat_router

__all__ = ["agents_router", "chat_router"]
