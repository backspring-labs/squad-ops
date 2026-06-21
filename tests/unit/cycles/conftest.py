"""
Shared fixtures for SIP-0064 cycle domain tests.
"""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    Gate,
    GateDecision,
    Project,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.tasks.models import TaskResult

_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


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


@pytest.fixture
def now():
    return _NOW


@pytest.fixture
def sample_project(now):
    return Project(
        project_id="hello_squad",
        name="Hello Squad",
        description="Simple single-agent greeting",
        created_at=now,
        tags=("example", "selftest"),
    )


@pytest.fixture
def sample_gate():
    return Gate(
        name="qa_review",
        description="QA review gate after code generation",
        after_task_types=("code_generate",),
    )


@pytest.fixture
def sample_flow_policy(sample_gate):
    return TaskFlowPolicy(mode="sequential", gates=(sample_gate,))


@pytest.fixture
def sample_cycle(now, sample_flow_policy):
    return Cycle(
        cycle_id="cyc_001",
        project_id="hello_squad",
        created_at=now,
        created_by="system",
        prd_ref="art_prd_v1",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc123",
        task_flow_policy=sample_flow_policy,
        build_strategy="fresh",
        applied_defaults={"timeout": 300},
        execution_overrides={"parallel": False},
        expected_artifact_types=("code", "test_report"),
        experiment_context={"infra_profile": "gpu-a100-4x"},
        notes="Test cycle",
    )


@pytest.fixture
def sample_run():
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="sha256:def456",
    )


@pytest.fixture
def sample_gate_decision(now):
    return GateDecision(
        gate_name="qa_review",
        decision="approved",
        decided_by="operator-1",
        decided_at=now,
        notes="Looks good",
    )


@pytest.fixture
def sample_artifact_ref(now):
    return ArtifactRef(
        artifact_id="art_001",
        project_id="hello_squad",
        artifact_type="prd",
        filename="prd-v1.md",
        content_hash="sha256:abc",
        size_bytes=1024,
        media_type="text/markdown",
        created_at=now,
    )


@pytest.fixture
def sample_agent_entry():
    return AgentProfileEntry(
        agent_id="max",
        role="lead",
        model="gpt-4",
        enabled=True,
    )


@pytest.fixture
def sample_profile(now, sample_agent_entry):
    return SquadProfile(
        profile_id="full-squad",
        name="Full Squad",
        description="All agents with default models",
        version=1,
        agents=(
            sample_agent_entry,
            AgentProfileEntry(agent_id="neo", role="dev", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="nat", role="strategy", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="data", role="analytics", model="gpt-4", enabled=True),
        ),
        created_at=now,
    )
