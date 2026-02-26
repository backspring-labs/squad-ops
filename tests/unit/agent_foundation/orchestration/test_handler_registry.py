"""Unit tests for HandlerRegistry.

Tests capability handler registration and lookup.
Part of SIP-0.8.8 Phase 6.
"""

import pytest

from squadops.capabilities.handlers.base import CapabilityHandler, HandlerEvidence, HandlerResult
from squadops.orchestration.handler_registry import (
    DuplicateHandlerError,
    HandlerNotFoundError,
    HandlerRegistry,
)


class MockHandler(CapabilityHandler):
    """Mock handler for testing."""

    def __init__(self, name: str, capability_id: str):
        self._name = name
        self._capability_id = capability_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def capability_id(self) -> str:
        return self._capability_id

    async def handle(self, context, inputs):
        evidence = HandlerEvidence.create(
            handler_name=self.name,
            capability_id=self.capability_id,
            duration_ms=0,
        )
        return HandlerResult(success=True, outputs={}, _evidence=evidence)


class TestHandlerRegistry:
    """Tests for HandlerRegistry."""

    def test_register_handler(self):
        """Should register a handler."""
        registry = HandlerRegistry()
        handler = MockHandler("test", "test.capability")

        registry.register(handler)

        assert registry.has("test.capability")

    def test_register_duplicate_raises(self):
        """Should raise on duplicate registration."""
        registry = HandlerRegistry()
        handler = MockHandler("test", "test.capability")

        registry.register(handler)

        with pytest.raises(DuplicateHandlerError):
            registry.register(handler)

    def test_register_with_override(self):
        """Should allow override when specified."""
        registry = HandlerRegistry()
        handler1 = MockHandler("test1", "test.capability")
        handler2 = MockHandler("test2", "test.capability")

        registry.register(handler1)
        registry.register(handler2, allow_override=True)

        assert registry.get("test.capability").name == "test2"

    def test_register_with_roles(self):
        """Should index handler by roles."""
        registry = HandlerRegistry()
        handler = MockHandler("test", "test.capability")

        registry.register(handler, roles=("lead", "dev"))

        assert "test.capability" in registry.list_by_role("lead")
        assert "test.capability" in registry.list_by_role("dev")
        assert "test.capability" not in registry.list_by_role("qa")

    def test_get_handler(self):
        """Should get registered handler."""
        registry = HandlerRegistry()
        handler = MockHandler("test", "test.capability")
        registry.register(handler)

        retrieved = registry.get("test.capability")

        assert retrieved is handler

    def test_get_not_found_raises(self):
        """Should raise on not found."""
        registry = HandlerRegistry()

        with pytest.raises(HandlerNotFoundError) as exc:
            registry.get("nonexistent")

        assert "nonexistent" in str(exc.value)

    def test_unregister_handler(self):
        """Should unregister handler."""
        registry = HandlerRegistry()
        handler = MockHandler("test", "test.capability")
        registry.register(handler, roles=("lead",))

        result = registry.unregister("test.capability")

        assert result is True
        assert not registry.has("test.capability")
        assert "test.capability" not in registry.list_by_role("lead")

    def test_unregister_not_found(self):
        """Should return False for missing handler."""
        registry = HandlerRegistry()

        result = registry.unregister("nonexistent")

        assert result is False

    def test_has_handler(self):
        """Should check handler existence."""
        registry = HandlerRegistry()
        handler = MockHandler("test", "test.capability")
        registry.register(handler)

        assert registry.has("test.capability") is True
        assert registry.has("nonexistent") is False

    def test_list_capabilities(self):
        """Should list all capability IDs."""
        registry = HandlerRegistry()
        registry.register(MockHandler("h1", "cap.one"))
        registry.register(MockHandler("h2", "cap.two"))
        registry.register(MockHandler("h3", "cap.three"))

        caps = registry.list_capabilities()

        assert len(caps) == 3
        assert "cap.one" in caps
        assert "cap.two" in caps
        assert "cap.three" in caps

    def test_list_by_role(self):
        """Should list capabilities by role."""
        registry = HandlerRegistry()
        registry.register(MockHandler("h1", "cap.one"), roles=("lead",))
        registry.register(MockHandler("h2", "cap.two"), roles=("lead", "dev"))
        registry.register(MockHandler("h3", "cap.three"), roles=("qa",))

        lead_caps = registry.list_by_role("lead")
        dev_caps = registry.list_by_role("dev")
        qa_caps = registry.list_by_role("qa")

        assert set(lead_caps) == {"cap.one", "cap.two"}
        assert set(dev_caps) == {"cap.two"}
        assert set(qa_caps) == {"cap.three"}

    def test_get_for_role(self):
        """Should get handlers for role."""
        registry = HandlerRegistry()
        h1 = MockHandler("h1", "cap.one")
        h2 = MockHandler("h2", "cap.two")
        registry.register(h1, roles=("lead",))
        registry.register(h2, roles=("lead",))

        handlers = registry.get_for_role("lead")

        assert len(handlers) == 2
        assert h1 in handlers
        assert h2 in handlers

    def test_clear(self):
        """Should clear all registrations."""
        registry = HandlerRegistry()
        registry.register(MockHandler("h1", "cap.one"), roles=("lead",))
        registry.register(MockHandler("h2", "cap.two"))

        registry.clear()

        assert registry.list_capabilities() == []
        assert registry.list_by_role("lead") == []
