"""
Unit test configuration and fixtures for SquadOps.

This file contains fixtures specific to unit tests that mock external dependencies.
Integration tests use real services via tests/integration/conftest.py.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.tasks.models import TaskResult

# =============================================================================
# SIP-0094 reply-router test double (shared by all executor tests)
# =============================================================================


class FakeReplyRouter:
    """Shared test double for the SIP-0094 ReplyRouter
    (``adapters/cycles/reply_router.py``).

    Post-cutover the executor awaits this router instead of polling the queue.
    It simulates the agent round-trip: :meth:`bind` wires a mock QueuePort so
    that publishing a ``comms.task`` to ``{agent_id}_comms`` calls
    :meth:`_autorespond`, which resolves the registered future with the
    configured reply.

    Configure the agent's reply per test:
    - ``responder`` — callable(envelope_dict) -> TaskResult, the default reply
      for every task (defaults to SUCCEEDED, empty outputs). Use a stateful
      closure to reproduce a scripted per-dispatch reply sequence.
    - ``results`` — ``{task_id: TaskResult}`` exact replies (resolve at
      register time, so they work even if publish is intercepted).
    - ``suppress`` — task_ids that never reply (drives a dispatch timeout).

    Mirrors the real router's register/cancel/ensure_subscribed/stop surface so
    the executor's ordering and pending-future-leak invariants are exercised.
    """

    def __init__(self) -> None:
        self._futures: dict[str, asyncio.Future] = {}
        self.subscribed: list[str] = []
        self.registered: list[str] = []
        self.cancelled: list[str] = []
        self.results: dict[str, TaskResult] = {}
        self.suppress: set[str] = set()
        self.stopped = False
        self.responder = lambda env: TaskResult(
            task_id=env["task_id"], status="SUCCEEDED", outputs={}
        )

    async def ensure_subscribed(self, agent_id: str) -> None:
        self.subscribed.append(agent_id)

    def register(self, task_id: str):
        self.registered.append(task_id)
        fut = asyncio.get_running_loop().create_future()
        self._futures[task_id] = fut
        # A pre-seeded result resolves immediately, so tests that bypass the
        # autoresponding publish (e.g. those overriding publish to capture the
        # envelope) still receive their reply.
        if task_id not in self.suppress and task_id in self.results:
            fut.set_result(self.results[task_id])
        return fut

    def cancel(self, task_id: str) -> None:
        self.cancelled.append(task_id)
        self._futures.pop(task_id, None)

    def _autorespond(self, envelope: dict) -> None:
        """Called by the bound mock_queue.publish to simulate the agent reply."""
        task_id = envelope["task_id"]
        if task_id in self.suppress:
            return  # no reply -> executor times out
        result = self.results.get(task_id)
        if result is None:
            result = self.responder(envelope)
        fut = self._futures.get(task_id)
        if fut is not None and not fut.done():
            fut.set_result(result)

    async def stop(self) -> None:
        self.stopped = True

    def bind(self, mock_queue):
        """Wire ``mock_queue.publish`` so dispatching a ``comms.task``
        auto-delivers the agent's reply through this router. Returns the queue.
        """
        mock_queue.reply_router = self
        router = self

        async def _publish(queue_name, payload, delay_seconds=None):
            data = json.loads(payload)
            if queue_name.endswith("_comms") and data.get("action") == "comms.task":
                router._autorespond(data["payload"])
            return None

        mock_queue.publish.side_effect = _publish
        return mock_queue


@pytest.fixture
def reply_router():
    """SIP-0094 reply-router test double; bind it to a mock queue with
    ``reply_router.bind(mock_queue)``."""
    return FakeReplyRouter()


# =============================================================================
# Mock Infrastructure Fixtures
# =============================================================================


@pytest.fixture
def mock_redis():
    """Mock Redis connection for testing"""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = True
    return mock


@pytest.fixture
def mock_ollama():
    """Mock Ollama LLM for testing"""
    mock = AsyncMock()
    mock.generate.return_value = {
        "response": "Mock LLM response",
        "model": "test-model",
        "created_at": "2025-01-01T00:00:00Z",
    }
    return mock


# =============================================================================
# Mock Ports Fixtures (New Architecture)
# =============================================================================


@pytest.fixture
def mock_ports():
    """Create mock ports bundle for BaseAgent testing."""
    return {
        "llm": MagicMock(),
        "memory": MagicMock(),
        "prompt_service": MagicMock(),
        "queue": MagicMock(),
        "metrics": MagicMock(),
        "events": MagicMock(),
        "filesystem": MagicMock(),
        "llm_observability": MagicMock(),
    }
