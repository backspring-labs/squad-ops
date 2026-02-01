"""Handler Registry for capability handlers.

Manages registration and lookup of capability handlers
by capability ID and role.

Part of SIP-0.8.8 Phase 6.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadops.capabilities.handlers.base import CapabilityHandler

logger = logging.getLogger(__name__)


class HandlerNotFoundError(Exception):
    """Raised when a handler is not found."""

    def __init__(self, capability_id: str):
        self.capability_id = capability_id
        super().__init__(f"No handler registered for capability: {capability_id}")


class DuplicateHandlerError(Exception):
    """Raised when attempting to register a duplicate handler."""

    def __init__(self, capability_id: str):
        self.capability_id = capability_id
        super().__init__(f"Handler already registered for capability: {capability_id}")


@dataclass
class HandlerRegistration:
    """Registration entry for a handler.

    Attributes:
        handler: The capability handler instance
        roles: Roles that can use this handler
        priority: Handler priority (higher = preferred)
    """

    handler: CapabilityHandler
    roles: tuple[str, ...] = ()
    priority: int = 0


class HandlerRegistry:
    """Registry for capability handlers.

    Manages handler registration and lookup by capability ID.
    Supports role-based filtering and priority ordering.

    Example:
        registry = HandlerRegistry()
        registry.register(TaskAnalysisHandler(), roles=("lead",))
        handler = registry.get("governance.task_analysis")
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._handlers: dict[str, HandlerRegistration] = {}
        self._by_role: dict[str, list[str]] = {}

    def register(
        self,
        handler: CapabilityHandler,
        roles: tuple[str, ...] | list[str] = (),
        priority: int = 0,
        allow_override: bool = False,
    ) -> None:
        """Register a capability handler.

        Args:
            handler: Handler to register
            roles: Roles that can use this handler
            priority: Handler priority
            allow_override: Allow overriding existing registration

        Raises:
            DuplicateHandlerError: If handler already registered and not allow_override
        """
        capability_id = handler.capability_id

        if capability_id in self._handlers and not allow_override:
            raise DuplicateHandlerError(capability_id)

        roles_tuple = tuple(roles) if isinstance(roles, list) else roles

        self._handlers[capability_id] = HandlerRegistration(
            handler=handler,
            roles=roles_tuple,
            priority=priority,
        )

        # Index by role
        for role in roles_tuple:
            if role not in self._by_role:
                self._by_role[role] = []
            if capability_id not in self._by_role[role]:
                self._by_role[role].append(capability_id)

        logger.debug(
            "handler_registered",
            extra={
                "capability_id": capability_id,
                "handler_name": handler.name,
                "roles": roles_tuple,
            },
        )

    def unregister(self, capability_id: str) -> bool:
        """Unregister a handler.

        Args:
            capability_id: Capability ID to unregister

        Returns:
            True if handler was removed, False if not found
        """
        if capability_id not in self._handlers:
            return False

        registration = self._handlers.pop(capability_id)

        # Remove from role index
        for role in registration.roles:
            if role in self._by_role:
                self._by_role[role] = [
                    cid for cid in self._by_role[role] if cid != capability_id
                ]

        return True

    def get(self, capability_id: str) -> CapabilityHandler:
        """Get handler by capability ID.

        Args:
            capability_id: Capability ID to look up

        Returns:
            Registered handler

        Raises:
            HandlerNotFoundError: If no handler registered
        """
        if capability_id not in self._handlers:
            raise HandlerNotFoundError(capability_id)

        return self._handlers[capability_id].handler

    def get_for_role(self, role: str) -> list[CapabilityHandler]:
        """Get all handlers available to a role.

        Args:
            role: Role ID

        Returns:
            List of handlers available to the role
        """
        capability_ids = self._by_role.get(role, [])
        return [self._handlers[cid].handler for cid in capability_ids]

    def has(self, capability_id: str) -> bool:
        """Check if handler is registered.

        Args:
            capability_id: Capability ID to check

        Returns:
            True if handler is registered
        """
        return capability_id in self._handlers

    def list_capabilities(self) -> list[str]:
        """List all registered capability IDs.

        Returns:
            List of capability IDs
        """
        return list(self._handlers.keys())

    def list_by_role(self, role: str) -> list[str]:
        """List capability IDs available to a role.

        Args:
            role: Role ID

        Returns:
            List of capability IDs
        """
        return list(self._by_role.get(role, []))

    def clear(self) -> None:
        """Clear all registrations."""
        self._handlers.clear()
        self._by_role.clear()
