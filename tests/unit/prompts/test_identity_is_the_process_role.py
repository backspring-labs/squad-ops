"""The identity layer reads what the process IS, not what the step does (SIP-0108 §10m).

Every handler carries a ``_role`` — the step's role, which owns its artifacts and routes its
repairs. The system prompt's identity layer is a different question: what this process is.
On a squad container the two coincide; on a generalist process serving every role they do
not, and a handler that briefed itself by its step role would tell Han "you are the QA
Agent" on every qa task. These tests pin the wiring at every place an identity-carrying
prompt is assembled and the invariant that makes the change byte-identical for the squad.
The architecture guard (``test_identity_layer_reads_the_process_role``) covers the same
surface syntactically; these prove each path is actually taken.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.bootstrap.handlers import HANDLER_CONFIGS
from squadops.capabilities.handlers._plan_authoring_service import produce_plan
from squadops.capabilities.handlers.cycle.builder import BuilderAssembleHandler
from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
from squadops.capabilities.handlers.cycle.governance import GovernanceReviewHandler
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.cycle.roles import StrategyAnalyzeHandler
from squadops.capabilities.handlers.planning.brief import (
    GovernancePreparePlanAuthoringBriefHandler,
)
from squadops.capabilities.handlers.planning.framing import StrategyFrameObjectiveHandler
from squadops.capabilities.handlers.planning.manifest import DevelopmentAuthorManifestHandler
from squadops.capabilities.handlers.planning.propose import DevelopmentProposePlanTasksHandler
from squadops.llm.models import ChatMessage
from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.orchestration.handler_registry import HandlerRegistry
from squadops.prompts.asset_models import RenderedRequest
from squadops.tasks.models import TaskEnvelope

_QA_REPLY = "```python:tests/test_main.py\ndef test_x():\n    assert True\n```\n"


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


def _ctx(role_id: str, *, reply: str = "out") -> MagicMock:
    ctx = MagicMock()
    ctx.role_id = role_id
    ctx.ports.llm.chat = AsyncMock(return_value=ChatMessage(role="assistant", content=reply))
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        return_value=ChatMessage(role="assistant", content=reply)
    )
    ctx.ports.llm.default_model = "m"
    ctx.ports.llm_observability = None
    ctx.correlation_context = None
    assembled = MagicMock()
    assembled.content = "System prompt"
    assembled.assembly_hash = "sha256:x"
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
    ctx.ports.prompt_service.assemble = MagicMock(return_value=assembled)
    # The planning handlers refuse to run without a renderer (the template is the prompt);
    # every handler takes the rendered path here, which is the live path.
    rendered = RenderedRequest(
        content="rendered",
        template_id="t",
        template_version="1",
        render_hash=RenderedRequest.compute_hash("rendered"),
    )
    ctx.ports.request_renderer.render = AsyncMock(return_value=rendered)
    return ctx


def _role_briefed(ctx: MagicMock) -> str:
    """The role the identity-carrying assembly asked for, whichever seam the handler used."""
    svc = ctx.ports.prompt_service
    for m in (svc.get_system_prompt, svc.assemble):
        if m.call_args is not None:
            args, kwargs = m.call_args
            return kwargs.get("role", args[0] if args else None)
    raise AssertionError("no identity-carrying assembly was made")


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
        (StrategyFrameObjectiveHandler(), {"prd": "Plan a game"}),
        (GovernancePreparePlanAuthoringBriefHandler(), {"prd": "Plan a game"}),
        (DevelopmentAuthorManifestHandler(), {"prd": "Plan a game"}),
        (DevelopmentProposePlanTasksHandler(), {"prd": "Plan a game"}),
        (
            QATestHandler(),
            {"prd": "Build a CLI", "artifact_contents": {"src/main.py": "def main(): ..."}},
        ),
    ],
    ids=[
        "cycle-base",
        "governance",
        "develop",
        "builder",
        "planning-base",
        "planning-brief",
        "planning-manifest",
        "planning-propose",
        "qa-test",
    ],
)
async def test_every_call_site_briefs_the_process_not_the_step(handler, inputs):
    """Wiring, entered at ``handle`` for each place a system prompt is assembled — the four
    ``get_system_prompt`` sites and the ``assemble`` sites the review found (§10m). Bug this
    catches: one call site still passing ``self._role`` — Han briefed as a specialist on that
    task type only, invisible on the squad where the two roles coincide."""
    ctx = _ctx("generalist", reply=_QA_REPLY)
    await handler.handle(ctx, inputs)
    assert _role_briefed(ctx) == "generalist"
    assert handler._role != "generalist", "the test proves nothing if the roles coincide"


async def test_the_plan_authoring_service_briefs_the_process():
    """``produce_plan`` (the merge handler's authoring loop) took ``role`` as a knob and passed
    it to the identity layer; the knob is gone and the context is read. Bug this catches: a
    caller reintroducing a role argument that shadows the process's."""
    ctx = _ctx("generalist")

    async def call(messages, **kwargs):
        return None, "no yaml here"

    await produce_plan(
        ctx,
        {"prd": "Plan a game"},
        planning_content="framing",
        resolved_config={"manifest_max_attempts": 1},
        handler_name="merge",
        chat_kwargs={},
        call=call,
        record=lambda *a, **k: None,
    )
    assert _role_briefed(ctx) == "generalist"


async def test_the_executor_hands_handlers_the_process_role():
    """Wiring from the executor to the context. Bug this catches: the executor building the
    context from a default (it was "lead" for every container until 1.8.1) — every call site
    above would then brief everything as the lead."""
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
