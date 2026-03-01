"""Tests for CycleEventBusPort and EventSubscriber protocol."""

import pytest

from squadops.events.models import CycleEvent
from squadops.events.subscriber import EventSubscriber
from squadops.ports.events.cycle_event_bus import CycleEventBusPort


@pytest.mark.domain_events
class TestCycleEventBusPort:
    def test_is_abstract(self):
        """CycleEventBusPort cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CycleEventBusPort()  # type: ignore[abstract]

    def test_has_emit_method(self):
        assert hasattr(CycleEventBusPort, "emit")

    def test_has_subscribe_method(self):
        assert hasattr(CycleEventBusPort, "subscribe")


@pytest.mark.domain_events
class TestEventSubscriber:
    def test_is_runtime_checkable_protocol(self):
        """EventSubscriber is a runtime-checkable Protocol."""

        class MySubscriber:
            def on_event(self, event: CycleEvent) -> None:
                pass

        sub = MySubscriber()
        assert isinstance(sub, EventSubscriber)

    def test_non_conforming_class_is_not_subscriber(self):
        """A class without on_event does not satisfy the Protocol."""

        class NotASubscriber:
            pass

        obj = NotASubscriber()
        assert not isinstance(obj, EventSubscriber)

    def test_callable_is_not_subscriber(self):
        """A bare callable does not satisfy the Protocol."""

        def handler(event: CycleEvent) -> None:
            pass

        assert not isinstance(handler, EventSubscriber)
