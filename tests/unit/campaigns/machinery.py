"""The machinery composition: a scripted squad, the runtime's executor and a fixture worker, every
hop between them the production one (#3050, slice 2; SIP-0117 R5.6, R5.9; SIP-0109 §8).

What runs is what a live increment runs, in one process:

- **The runtime's side:** ``create_flow_executor``'s ``DispatchedFlowExecutor`` over the memory
  cycle registry, a filesystem vault, the managed clone of the product, the sandbox service
  running the product's checks as local processes, ``RegistryRemoteExecution`` and the worker
  registry. Its ``TaskDispatcher`` and ``ReplyRouter`` are the real ones, over ``Broker``.
- **The squad:** one ``AgentRunner`` per agent, its ports built by its own ``_create_ports``, so
  its model is ``with_scripted_model`` answering from the cycle's script. Each delivery enters at
  ``_process_comms_message``, where the agent's comms consumer hands it on.
- **The worker:** ``Worker.serve()`` over HTTP into the runtime's real worker and
  remote-operation routes, running the fixture provider's ``fixture/declared_scenario``. qa's
  operation reaches it from the agent's ``RuntimeApiRemoteExecution`` over the same routes, and
  the routes read the executor's own reply router for the send that is current.

Only the I/O under the ports is replaced: RabbitMQ (``Broker``), Redis (the script's positions
and each agent's delivery record, in process), LangFuse, and the network (ASGI transports into
one app). The model engine under the scripted model fails any call that reaches it.

**The product** is the shared contract's Tally with a door: ``.fixture/world.json``, the world the
fixture's reader observes, committed on top with the door shut (``SHUT``). Its recorded
development configuration, derived profile and inherited baseline are the Project registry's
answers, the baseline re-pinned to the door's commit. **The fixture skillsets and development
profile** are the test's (SIP-0116 §14): no deployed registry holds them.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import json
import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import yaml

from adapters.cycles.factory import create_flow_executor
from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.llm.script_positions import InProcessScriptPositions
from adapters.noop.ports import NoOpFailurePatternRecall, NoOpProposalEvidence
from adapters.remote_execution.fixture_operation_runner import WORLD_PATH
from adapters.remote_execution.registry_remote_execution import RegistryRemoteExecution
from adapters.tools.git_source import GitSourceRepository
from squadops.campaigns.increment_tree import INCREMENT_EVALUATION_ARTIFACT_TYPE
from squadops.capabilities import skillsets
from squadops.capabilities.handlers.cycle import run_remote_operation
from squadops.comms.queue_message import QueueMessage
from squadops.contracts.cycle_request_profiles import load_profile
from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    Project,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.skillset_content import keep_skillset_content
from squadops.execution import dispatched_flow_executor, product_acceptance
from squadops.execution.reply_router import ReplyRouter
from squadops.llm.script import script_version
from squadops.ports.comms.queue import AckPolicy, QueuePort, SubscriptionHandle
from squadops.ports.comms.task_attempts import TaskAttemptsPort
from squadops.projects.baseline import parse_baseline
from squadops.projects.derived_profile import parse_profile
from squadops.projects.development_configuration import parse_configuration
from squadops.projects.models import ProjectSource
from squadops.projects.registration import LocatorPolicy
from squadops.projects.source_context import parse_source_context
from squadops.remote_execution.workers import QueuedOperation
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import WorkspaceStore
from tests.fixtures.shared_contract.repository import build_repository, recorded
from tests.unit.campaigns.test_product_runner_acceptance_wiring import _scenario_catalog
from tests.unit.cycles.skillset_fixture import built, requiring_config
from tests.unit.cycles.test_source_backed_run import _LocalBackend
from tests.unit.remote_execution.registry_contract import T0
from tests.unit.remote_execution.remote_path import Path as RemotePath
from tests.unit.remote_execution.scenario_fixture import SHUT

#: The model every agent of a machinery squad names (#2495).
SCRIPTED = "scripted"
PROJECT = "prj-tally"
#: The squad, each agent's id and role as ``instances.yaml`` names them, and the fixture
#: skillset each supplies (SIP-0116).
AGENTS = (
    ("max", "lead", ()),
    ("neo", "dev", ("fixture-dev",)),
    ("nat", "strat", ()),
    ("eve", "qa", ("fixture-qa",)),
    ("data", "data", ()),
    ("bob", "builder", ()),
)


class Broker(QueuePort):
    """RabbitMQ's part, in process. A task published to ``{agent}_comms`` is handed to that
    agent's comms consumer as a delivery, beside the publisher as a consumer runs; a reply
    published to ``{agent}_replies`` reaches the reply router's subscription. Every message is
    kept, in order, for the test to read."""

    def __init__(self) -> None:
        self.agents: dict[str, Any] = {}
        self.published: list[tuple[str, dict]] = []
        self._subscriptions: dict[str, Any] = {}
        self._running: set[asyncio.Task] = set()

    async def publish(self, queue_name: str, payload: str, delay_seconds: int | None = None):
        if delay_seconds:
            raise NotImplementedError("the broker delivers at once")
        self.published.append((queue_name, json.loads(payload)))
        message = QueueMessage(
            message_id=uuid.uuid4().hex,
            queue_name=queue_name,
            payload=payload,
            receipt_handle="",
            attributes={},
        )
        if queue_name.endswith("_comms"):
            agent = self.agents[queue_name.removesuffix("_comms")]
            task = asyncio.create_task(agent._process_comms_message(message))
            self._running.add(task)
            task.add_done_callback(self._running.discard)
        elif queue_name in self._subscriptions:
            result = self._subscriptions[queue_name](message)
            if asyncio.iscoroutine(result):
                await result
        else:
            raise AssertionError(f"nothing consumes {queue_name}")

    async def subscribe(self, queue_name, *, on_message, ack_policy: AckPolicy):
        self._subscriptions[queue_name] = on_message
        return SubscriptionHandle(asyncio.create_task(asyncio.Event().wait()), queue_name)

    async def consume(self, queue_name: str, max_messages: int = 1):
        return []

    async def ensure_queue(self, queue_name: str) -> None:
        return None

    async def ack(self, message) -> None:
        return None

    async def retry(self, message, delay_seconds: int) -> None:
        raise NotImplementedError("a delivery is never handed back here")

    async def health(self) -> dict[str, Any]:
        return {"healthy": True}

    def capabilities(self) -> dict[str, bool]:
        return {"delay": False}

    async def drained(self) -> None:
        """Wait for every delivery still running, so nothing outlives the test."""
        while self._running:
            await asyncio.gather(*list(self._running), return_exceptions=True)


class Attempts(TaskAttemptsPort):
    """An agent's delivery record (#1977), in process where a deploy keeps it in Redis."""

    def __init__(self) -> None:
        self.begun: dict[str, int] = {}
        self.done: set[str] = set()

    async def completed(self, key: str) -> bool:
        return key in self.done

    async def begin_attempt(self, key: str) -> int:
        self.begun[key] = self.begun.get(key, 0) + 1
        return self.begun[key]

    async def mark_completed(self, key: str) -> None:
        self.done.add(key)


def _agent_config() -> SimpleNamespace:
    """The fields an agent's ``_create_ports`` reads, as a deploy's config carries them. The
    engine under the scripted model is unreachable."""
    return SimpleNamespace(
        llm=SimpleNamespace(
            provider="ollama", url="http://unreachable.invalid:1", timeout=5, api_key=None,
            model=None,
        ),
        prompts=SimpleNamespace(asset_source_provider="filesystem"),
        telemetry=SimpleNamespace(backend="null", otlp_endpoint=None),
        langfuse=SimpleNamespace(enabled=False),
        tools=SimpleNamespace(filesystem=SimpleNamespace(provider="local")),
        remote_execution=SimpleNamespace(provider="runtime_api", wait_seconds=300, max_attempts=2),
        runtime_api_url="http://runtime-api",
        auth=SimpleNamespace(agent_client=None, oidc=None),
        comms=SimpleNamespace(
            delivery=SimpleNamespace(max_attempts=3, dead_letter_queue="squadops.dead_letter")
        ),
    )  # fmt: skip


class _Profiles:
    """The squad profile port: one profile, every agent on the scripted model."""

    def __init__(self, profile: SquadProfile) -> None:
        self.profile = profile

    async def resolve_snapshot(self, profile_id):
        return self.profile, "sha256:machinery"

    async def get_profile(self, profile_id):
        return self.profile

    async def get_active_profile(self):
        return self.profile


def squad_profile() -> SquadProfile:
    return SquadProfile(
        profile_id="machinery", name="machinery", description="", version=1, created_at=_now(),
        agents=tuple(
            AgentProfileEntry(
                agent_id=a, role=r, model=SCRIPTED, enabled=True, serves_roles=(r,), skillsets=s
            )
            for a, r, s in AGENTS
        ),
    )  # fmt: skip


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def door_product(root: Path) -> tuple[Path, str]:
    """Tally with the door's world committed on top, shut: the product and its head."""
    repo = build_repository(root / "tally").path
    world = repo / WORLD_PATH
    world.parent.mkdir(parents=True)
    world.write_text(json.dumps(SHUT, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t.invalid", "commit", "-q", "-m", "door")
    return repo, _git(repo, "rev-parse", "HEAD")


def _projects(repo: Path, head: str) -> AsyncMock:
    """The Project registry as the recorded contracts answer it, at the door product."""
    registry = AsyncMock()
    registry.get_project.return_value = Project(
        project_id=PROJECT, name="Tally", description="", created_at=_now(),
        source=ProjectSource(str(repo), "refs/heads/main", "review_request"),
    )  # fmt: skip
    registry.get_development_configuration.return_value = parse_configuration(
        recorded("development_configuration", "valid")
    )
    # The checks' baseline, re-pinned to the door's commit: a candidate is compared only with the
    # baseline of the tree it changed (FR-20).
    registry.get_inherited_baseline.return_value = dataclasses.replace(
        parse_baseline(recorded("inherited_baseline", "valid")), commit=head
    )
    registry.get_derived_profile.return_value = parse_profile(recorded("derived_profile", "valid"))
    registry.get_initialization.return_value = None
    return registry


def _now() -> datetime:
    return datetime.now(UTC)


def answer(task_type: str, occurrence: int, content: str, call: int = 1) -> dict:
    """One scripted answer, at the key the squad's model looks it up by (#2495)."""
    return {"task_type": task_type, "occurrence": occurrence, "call": call, "content": content}


def emitted(path: str, content: str, language: str = "json") -> str:
    """A whole file, as an author's answer carries it."""
    return f"```{language}:{path}\n{content}\n```\n"


def edited(path: str, search: str, replace: str) -> str:
    """An anchored edit, as a repair's answer carries it."""
    return f"```edit:{path}\n<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE\n```\n"


@dataclasses.dataclass
class Machinery:
    """The composed world a test drives."""

    path: RemotePath
    broker: Broker
    executor: Any
    registry: MemoryCycleRegistry
    vault: FilesystemArtifactVault
    scripts: Path
    context: Any
    record: Any
    kept: Any

    async def increment(
        self,
        cycle_id: str,
        run_id: str,
        *,
        change_request: str,
        plan: dict,
        answers: list[dict],
        allowed_scope: tuple[str, ...],
    ) -> Cycle:
        """An increment's cycle as its launch makes it, framed: its approved change request and
        its implementation plan on its plan refs, its skillset record and kept copy, and the
        script its squad answers from. Its implementation run is queued."""
        raw = yaml.safe_dump(
            {"script": cycle_id, "description": "a machinery increment", "answers": answers},
            sort_keys=False,
            width=1000,
        ).encode()
        (self.scripts / f"{cycle_id}.yaml").write_bytes(raw)
        refs = [
            await self._store(cycle_id, "change_request", "change_request.yaml", change_request),
            await self._store(
                cycle_id, "control_implementation_plan", "implementation_plan.yaml",
                json.dumps(plan),
            ),
        ]  # fmt: skip
        await keep_skillset_content(
            self.vault, project_id=PROJECT, cycle_id=cycle_id, document=self.kept
        )
        block = {
            "proposal_id": f"prop_{cycle_id}", "version": 1, "basis": "campaign_branch",
            "baseline_tree": "f" * 64,
            "objective": {"statement": "s", "allowed_scope": list(allowed_scope),
                          "measurement": "m"},
            "prior_criteria": [], "frozen_criteria": [], "accepted_pages": [],
            "max_revisions": 2,
        }  # fmt: skip
        cycle = Cycle(
            cycle_id=cycle_id, project_id=PROJECT, created_at=_now(),
            created_by="campaign-launcher", prd_ref="The door opens from its panel.",
            squad_profile_id="machinery", squad_profile_snapshot_ref="sha256:machinery",
            task_flow_policy=TaskFlowPolicy(mode="sequential"), build_strategy="fresh",
            applied_defaults=dict(load_profile("campaign-increment-source").defaults),
            execution_overrides={
                "campaign_proposal": block, "plan_artifact_refs": refs,
                "llm_script": f"{cycle_id}@{script_version(raw)}",
            },
            campaign_id="cmp_machinery1", kind="increment",
            request_profile="campaign-increment-source", source_context=self.context,
            skillset_record=self.record,
        )  # fmt: skip
        await self.registry.create_cycle(cycle)
        await self.registry.create_run(
            Run(run_id, cycle_id, 1, "queued", "system", "cfg", workload_type="implementation")
        )
        return cycle

    async def _store(self, cycle_id, artifact_type, filename, content: str) -> str:
        ref = ArtifactRef(
            artifact_id=f"art_{uuid.uuid4().hex[:12]}", project_id=PROJECT, cycle_id=cycle_id,
            run_id=f"{cycle_id}_framing", artifact_type=artifact_type, filename=filename,
            content_hash="h", size_bytes=len(content), media_type="text/yaml",
            created_at=_now(),
        )  # fmt: skip
        await self.vault.store(ref, content.encode())
        return ref.artifact_id

    @contextlib.asynccontextmanager
    async def worker(self):
        """The fixture worker, registered and claiming, while the block runs."""
        async with self.path.serving(self.path.worker()) as serving:
            yield serving

    def dispatched(self) -> list[str]:
        """Every task the runtime sent the squad, by type, in the order sent."""
        return [m["payload"]["task_type"] for q, m in self.broker.published if q.endswith("_comms")]

    def replies(self) -> list[tuple[str, str]]:
        """Every reply's status and error, in the order the squad sent them."""
        return [
            (m["payload"]["status"], m["payload"].get("error") or "")
            for q, m in self.broker.published
            if q.endswith("_replies")
        ]

    def operations(self) -> list[QueuedOperation]:
        """Every operation the worker registry holds, in the order they were queued. Read from
        the memory store's rows: the registry's port names no listing of them all."""
        rows = self.path.registry._store._rows.operations.values()
        return sorted(rows, key=lambda o: o.created_at)

    async def evaluation(self, cycle_id: str) -> dict:
        [ref] = await self.vault.list_artifacts(
            cycle_id=cycle_id, artifact_type=INCREMENT_EVALUATION_ARTIFACT_TYPE
        )
        _, raw = await self.vault.retrieve(ref.artifact_id)
        return json.loads(raw)


async def _squad(monkeypatch, broker: Broker, path: RemotePath) -> None:
    """Each agent of ``AGENTS``, composed by its own ``_create_ports``. Its remote-execution port
    is the agent's ``RuntimeApiRemoteExecution``, over the path's line into the runtime."""
    from squadops.agents import entrypoint

    roles = {a: r for a, r, _ in AGENTS}
    monkeypatch.setattr(
        entrypoint,
        "load_instance_config",
        lambda aid: {"id": aid, "role": roles[aid], "model": SCRIPTED},
    )
    monkeypatch.setattr("adapters.comms.factory.create_queue_adapter", lambda *a, **k: broker)
    monkeypatch.setattr("adapters.comms.factory.create_task_attempts", lambda *a, **k: Attempts())
    positions = InProcessScriptPositions()
    monkeypatch.setattr("adapters.llm.factory.create_script_positions", lambda comms: positions)
    monkeypatch.setattr(
        "adapters.remote_execution.factory.create_remote_execution",
        lambda *a, origin, **k: path.requester(origin=origin),
    )
    for agent_id, role, _ in AGENTS:
        agent = entrypoint.AgentRunner(role=role, agent_id=agent_id)
        agent._config = _agent_config()
        agent.system = await agent._create_system()
        engine = agent.system.ports.llm._engine

        async def _refuse(*_args, _agent=agent_id, **kwargs):
            raise AssertionError(f"{_agent}: a scripted squad's call reached the model engine")

        engine.chat_stream_with_usage = _refuse
        engine.chat = _refuse
        broker.agents[agent_id] = agent


async def compose(tmp_path: Path, monkeypatch) -> Machinery:
    catalog = _scenario_catalog()
    for module in (skillsets, product_acceptance, run_remote_operation, dispatched_flow_executor):
        monkeypatch.setattr(module, "packaged_skillsets", lambda: catalog)
    record, kept = built(requiring_config(monkeypatch), catalog)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    monkeypatch.setattr("squadops.llm.script.PACKAGED_SCRIPTS_DIR", scripts)

    sources = tmp_path / "sources"
    repo, head = door_product(sources)
    context = dataclasses.replace(
        parse_source_context(recorded("project_source_context", "valid")),
        repo_uri=str(repo),
        pinned_commit=head,
    )
    path = RemotePath()
    broker = Broker()
    registry = MemoryCycleRegistry()
    vault = FilesystemArtifactVault(tmp_path / "vault")
    store = WorkspaceStore(tmp_path / "sandbox")
    executor = create_flow_executor(
        "dispatched",
        cycle_registry=registry,
        artifact_vault=vault,
        queue=broker,
        squad_profile=_Profiles(squad_profile()),
        project_registry=_projects(repo, head),
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(),
        proposal_evidence=NoOpProposalEvidence(),
        task_timeout=600.0,
        binding_fill=None,
        reply_router=ReplyRouter(broker),
        source_repository=GitSourceRepository(
            tmp_path / "cache",
            LocatorPolicy.of([], [str(sources)]),
            timeout_seconds=60,
            committer_name="SquadOps",
            committer_email="squadops@squadops.invalid",
        ),
        sandbox=SandboxService(
            store=store,
            journal=OperationEvidenceJournal(tmp_path / "sandbox"),
            backend=_LocalBackend(store),
        ),
        route_renderer=None,
        goal_set_registry=None,
        remote_execution=RegistryRemoteExecution(
            path.registry,
            origin={"service": "runtime-api"},
            wait=timedelta(seconds=300),
            max_attempts=2,
            clock=lambda: (path.clock.now - T0).total_seconds(),
            sleep=path.sleep,
        ),
        worker_registry=path.registry,
    )
    # The requester's routes read the executor's own router for the send that is current (R5.6).
    path.world.app.state.reply_router = executor._reply_router
    await _squad(monkeypatch, broker, path)
    return Machinery(
        path=path, broker=broker, executor=executor, registry=registry, vault=vault,
        scripts=scripts, context=context, record=record, kept=kept,
    )  # fmt: skip
