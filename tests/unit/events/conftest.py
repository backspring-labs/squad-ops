"""Shared fixtures for cycle event system tests."""

from __future__ import annotations

import pytest

from adapters.events.in_process_cycle_event_bus import InProcessCycleEventBus
from squadops.events.models import CycleEvent


class CollectingSubscriber:
    """Test subscriber that collects all received events."""

    def __init__(self) -> None:
        self.events: list[CycleEvent] = []

    def on_event(self, event: CycleEvent) -> None:
        self.events.append(event)


@pytest.fixture
def event_bus() -> InProcessCycleEventBus:
    return InProcessCycleEventBus(
        source_service="test-service",
        source_version="0.0.1",
    )


@pytest.fixture
def collector() -> CollectingSubscriber:
    return CollectingSubscriber()
