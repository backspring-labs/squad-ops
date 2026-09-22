"""The identity layer reads what the process IS, not what the step does (SIP-0108 §10i).

Every handler carries a ``_role`` — the step's role, which owns its artifacts and routes its
repairs. The system prompt's identity layer is a different question: what this process is.
On a squad container the two coincide; on a generalist process serving every role they do
not, and a handler that briefed itself by its step role would tell Han "you are the QA
Agent" on every qa task. These tests pin the wiring at the three places it is read and the
invariant that makes the change byte-identical for the squad.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.bootstrap.handlers import HANDLER_CONFIGS
from squadops.capabilities.handlers.cycle.builder import BuilderAssembleHandler
from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
from squadops.capabilities.handlers.cycle.governance import GovernanceReviewHandler
from squadops.capabilities.handlers.cycle.roles import StrategyAnalyzeHandler
from squadops.llm.models import ChatMessage
from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.orchestration.handler_registry import HandlerRegistry
from squadops.tasks.models import TaskEnvelope


def test_every_handlers_step_role_is_the_one_role_it_is_registered_for():
    """The invariant behind "byte-identical for the squad": a squad container's process role
    equals the registered role of every handler it runs, so reading the process role at the
    identity layer changes no squad prompt. Bug this catches: a handler registered for two
    roles, or under a role other than its own — the case where the two readings diverge on
    a squad container and the window's substrate is no longer held equal."""
    for handler_class, roles in HANDLER_CONFIGS:
        step_role = getattr(handler_class, "_role", None)
        if step_role is None:
            continue
        assert roles == (step_role,), (
            f"{handler_class.__name__}: _role={step_role!r} but registered for {roles!r}"
        )


def _ctx(role_id: str) -> MagicMock:
    ctx = MagicMock()
    ctx.role_id = role_id
    ctx.ports.llm.chat = AsyncMock(return_value=ChatMessage(role="assistant", content="out"))
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        return_value=ChatMessage(role="assistant", content="out")
    )
    ctx.ports.llm.default_model = "m"
    assembled = MagicMock()
    assembled.content = "System prompt"
    assembled.assembly_hash = "sha256:x"
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
    del ctx.ports.request_renderer
    return ctx


@pytest.mark.parametrize(
    ("handler", "inputs"),
    [
        (StrategyAnalyzeHandler(), {"prd": "Build a game"}),
        (GovernanceReviewHandler(), {"prd": "Build a widget"}),
        (
            DevelopmentDevelopHandler(),
            {"prd": "Build a game", "artifact_contents": {"implementation_plan.md": "p"}},
        ),
        (
            BuilderAssembleHandler(),
            {
                "prd": "Build a game",
                "artifact_contents": {"backend/app.py": "print(1)\n"},
                "resolved_config": {"build_profile": "python_cli_builder"},
            },
        ),
    ],
    ids=["cycle-base", "governance", "develop", "builder"],
)
async def test_every_call_site_briefs_the_process_not_the_step(handler, inputs):
    """Wiring, entered at ``handle`` for each of the four places the system prompt is assembled. Bug this
    catches: one call site still passing ``self._role`` — Han briefed as a specialist on that
    task type only, invisible on the squad where the two roles coincide."""
    ctx = _ctx("generalist")
    await handler.handle(ctx, inputs)
    ctx.ports.prompt_service.get_system_prompt.assert_called_with("generalist")
    assert handler._role != "generalist", "the test proves nothing if the roles coincide"


async def test_the_executor_hands_handlers_the_process_role():
    """Wiring from the executor to the context. Bug this catches: the executor building the
    context from a default (it was "lead" for every container until 1.8.1) — the three call
    sites above would then brief everything as the lead."""
    seen: dict[str, str] = {}

    class Probe:
        name = "probe"
        task_type = "probe.task"

        def validate_inputs(self, inputs):
            return []

        async def handle(self, context, inputs):
            seen["role_id"] = context.role_id
            from squadops.capabilities.handlers.base import HandlerResult

            return HandlerResult(success=True, outputs={})

    registry = HandlerRegistry()
    registry.register(Probe(), roles=("qa",))
    executor = HandlerExecutor("x", registry, MagicMock(), role="generalist")
    envelope = TaskEnvelope(
        task_id="t1",
        agent_id="han",
        cycle_id="cyc_1",
        pulse_id="p",
        project_id="proj",
        task_type="probe.task",
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
        inputs={},
    )
    await executor.execute(envelope)
    assert seen["role_id"] == "generalist"


def test_the_role_is_required_at_every_seam():
    """Require, don't default (the owner's ruling of 2026-09-14). Bug this catches: a default
    creeping back at any of the three constructors, which is how "lead" briefed every
    container for as long as nobody read the field."""
    from squadops.bootstrap.system import SystemConfig
    from squadops.orchestration.orchestrator import AgentOrchestrator

    with pytest.raises(TypeError):
        HandlerExecutor("x", HandlerRegistry(), MagicMock())  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        AgentOrchestrator(handler_registry=HandlerRegistry(), ports=MagicMock())  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        SystemConfig()  # type: ignore[call-arg]
