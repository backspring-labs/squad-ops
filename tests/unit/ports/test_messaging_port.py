"""Tests for MessagingPort interface (SIP-0085 Phase 1)."""

from typing import Any

import pytest

from squadops.ports.comms.messaging import MessagingPort


class TestMessagingPort:
    """Contract tests for MessagingPort ABC."""

    def test_cannot_instantiate_directly(self):
        """MessagingPort is abstract — instantiation raises TypeError."""
        with pytest.raises(TypeError):
            MessagingPort()  # type: ignore

    def test_concrete_subclass_can_instantiate(self):
        """A concrete subclass implementing all methods is instantiable."""

        class _ConcreteMessaging(MessagingPort):
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def health(self) -> dict[str, Any]:
                return {"healthy": True}

        port = _ConcreteMessaging()
        assert port is not None

    def test_partial_implementation_raises(self):
        """Subclass missing any abstract method cannot be instantiated."""

        class _MissingStop(MessagingPort):
            async def start(self) -> None:
                pass

            async def health(self) -> dict[str, Any]:
                return {"healthy": True}

        with pytest.raises(TypeError):
            _MissingStop()  # type: ignore

    def test_exported_from_comms_package(self):
        """MessagingPort is importable from ports.comms package."""
        from squadops.ports.comms import MessagingPort as Exported

        assert Exported is MessagingPort
