"""``strategy.propose_increment`` (SIP-0109 §9.1; #1706), entered at ``handle()``.

The real prompt assets render through the real renderer and assembler; the model is stubbed with
the emissions under test. The baseline is the 1.9 roll cyc_7a4b7a6fbf0e's authored manifest, carried
in the cycle's persisted campaign_proposal block — the way the live run receives it: the agent's
container has no artifact vault (cyc_a06843b58e4f refused for exactly that).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from adapters.prompts.factory import create_prompt_asset_source, create_prompt_repository
from squadops.capabilities.handlers.planning.proposal import StrategyProposeIncrementHandler
from squadops.cycles.models import CycleError, WorkloadType
from squadops.cycles.task_plan import _resolve_workload_steps
from squadops.llm.models import ChatMessage
from squadops.prompts.assembler import PromptAssembler
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.tasks.task_types import TaskType

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"
_BASELINE = (_FIXTURES / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml").read_text()
_REFERENCE = (_FIXTURES / "reference-capacity-change-request.yaml").read_text()


def _fenced(doc: str) -> str:
    return f"Here is my proposal.\n\n```yaml:change_request.yaml\n{doc}\n```\n"


def _out_of_scope() -> str:
    """The reference request, which reaches the frontend — refused when only backend is allowed."""
    return _REFERENCE


def _ctx(*replies: str) -> MagicMock:
    ctx = MagicMock()
    ctx.role_id = "strat"
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        side_effect=[ChatMessage(role="assistant", content=r) for r in replies]
    )
    ctx.ports.llm.default_model = "m"
    ctx.ports.llm_observability = None
    ctx.correlation_context = None
    ctx.ports.request_renderer = RequestTemplateRenderer(create_prompt_asset_source("filesystem"))
    ctx.ports.prompt_service = PromptAssembler(create_prompt_repository("filesystem"))
    return ctx


def _inputs(*, scope=("backend/**", "frontend/**"), manifest=_BASELINE, block=True) -> dict:
    config: dict = {"build_profile": "fullstack_fastapi_react", "proposal_max_attempts": 2}
    if block:
        config["campaign_proposal"] = {
            "proposal_id": "prop_1",
            "version": 1,
            "baseline_tree": "tree:7a4b7a6f",
            "baseline_manifest_artifact_id": "art_f127a0c2f5e7",
            "baseline_manifest": manifest,
            "objective": {
                "statement": "evolve group_run toward its PRD's expansion scope",
                "allowed_scope": list(scope),
                "measurement": "two accepted increments",
            },
            "prior_criteria": [],
        }
    return {
        "resolved_config": config,
        "prd": "## Expansion Tier 1\n1. Capacity limit per run",
    }


def _prompts(ctx) -> list[str]:
    """Every message the model was sent, call by call."""
    return [
        "\n".join(m.content for m in call.args[0])
        for call in ctx.ports.llm.chat_stream_with_usage.call_args_list
    ]


async def test_an_accepted_proposal_is_the_typed_change_request_with_its_footprint_and_hash():
    """Wiring: the handler's real render reaches the model with the accepted manifest verbatim
    (the model sees what it changes), and the artifact is the rails' typed request, not the raw
    emission. Bug caught: an artifact without the derived footprint and hash the ruling binds."""
    ctx = _ctx(_fenced(_REFERENCE))

    result = await StrategyProposeIncrementHandler().handle(ctx, _inputs())

    assert result.success, result.error
    [artifact] = result.outputs["artifacts"]
    document = yaml.safe_load(artifact["content"])
    assert artifact["name"] == "change_request.yaml" and artifact["type"] == "change_request"
    assert document["footprint"][:4] == [
        "backend/errors.py",
        "backend/models.py",
        "backend/routes.py",
        "frontend/src/views/RunDetailView.jsx",
    ]
    assert document["content_hash"] == result.outputs["change_request"]["content_hash"]
    [prompt] = _prompts(ctx)
    assert "run-detail-leave-submit" in prompt  # the baseline manifest, shown verbatim
    assert "- `frontend/**`" in prompt  # the allowed scope
    assert "1. Capacity limit per run" in prompt  # the requirements the objective points into


async def test_a_revision_run_is_shown_the_note_and_the_version_it_revises_and_emits_the_next():
    """SIP-0109 §9.2, as the gate hands a revision over (the block the gate writes: the next
    version, the note, the returned change request). Bugs caught: the revision re-rolled from
    scratch without the version it revises (#811's revise-don't-re-roll), the note dropped, or
    the new version stamped with the old number — its ruling would bind to the returned one."""
    inputs = _inputs()
    block = inputs["resolved_config"]["campaign_proposal"]
    block.update(
        version=2,
        supervisor_note="Keep the capacity field out of the create view; backend only.",
        prior_change_request="kind: feature\ncriteria:\n  - id: T1\n    statement: a prior marker\n",
    )
    ctx = _ctx(_fenced(_REFERENCE))

    result = await StrategyProposeIncrementHandler().handle(ctx, inputs)

    assert result.success, result.error
    [prompt] = _prompts(ctx)
    assert "returned version 1 of your proposal" in prompt
    assert "> Keep the capacity field out of the create view; backend only." in prompt
    assert "statement: a prior marker" in prompt
    assert result.outputs["change_request"]["version"] == 2


async def test_a_proposal_after_an_abandoned_increment_is_shown_why_it_was_abandoned():
    """SIP-0109 §7, row 13 (#1692), through the real render: the launch carries the abandoned
    increment's brief and the proposal shows it. Bugs caught: the brief carried and never
    rendered (a template slot no handler fills, #1289's shape), or shown to a first proposal
    that replaces nothing."""
    abandoned = {
        "cycle_id": "cyc_inc",
        "verdict": "rejected",
        "failed_checks": ["tests_pass"],
        "why_failed": [
            {"check_id": "tests_pass", "reason": "POST /runs returned 422", "contested": False}
        ],
    }
    inputs = _inputs()
    inputs["resolved_config"]["campaign_proposal"]["abandoned_increment"] = abandoned
    shown, first = _ctx(_fenced(_REFERENCE)), _ctx(_fenced(_REFERENCE))

    await StrategyProposeIncrementHandler().handle(shown, inputs)
    await StrategyProposeIncrementHandler().handle(first, _inputs())

    [prompt] = _prompts(shown)
    assert "### The last increment was abandoned" in prompt
    assert "- failed checks: `tests_pass`" in prompt
    assert "POST /runs returned 422" in prompt
    assert "abandoned" not in _prompts(first)[0]


async def test_the_proposal_is_shown_what_each_frozen_criterion_asserts():
    """#1938, through the real render. Bug caught: frozen criteria rendered as bare ids. Shakeout
    6's strategy role, told only "`T3`", re-proposed the date sort T3 had frozen one increment
    earlier. A record frozen before statements were kept still renders, by its id."""
    inputs = _inputs()
    block = inputs["resolved_config"]["campaign_proposal"]
    block["prior_criteria"] = ["S1", "S2"]
    block["frozen_criteria"] = [
        {
            "criterion_id": "S1",
            "statement": "GET /runs returns runs sorted by datetime, ascending",
            "surface": "GET /runs",
            "test_path": "backend/tests/criteria/test_S1.py",
        },
        {"criterion_id": "S2", "test_path": "backend/tests/criteria/test_S2.py"},
    ]
    ctx = _ctx(_fenced(_REFERENCE))

    await StrategyProposeIncrementHandler().handle(ctx, inputs)

    [prompt] = _prompts(ctx)
    assert "- `S1`: GET /runs returns runs sorted by datetime, ascending (on `GET /runs`)" in prompt
    assert "- `S2`\n" in prompt
    assert "each is something the application already does" in prompt


async def test_the_proposal_is_told_a_new_criterion_must_fail_before_the_change():
    """#1946, through the real render. Bug caught: the rule a new criterion is judged by (§8.2,
    the evaluation's discrimination; the supervisor's §3a) never reaching the proposer. Two of the
    2.0 shakeouts' first proposals carried a criterion the accepted app already met, the default
    case of the feature, and were returned for it."""
    ctx = _ctx(_fenced(_REFERENCE))

    await StrategyProposeIncrementHandler().handle(ctx, _inputs())

    [prompt] = _prompts(ctx)
    assert "Each criterion you add names something the application does not do yet." in prompt
    assert "the test must fail there, then pass" in prompt


async def test_a_refusal_comes_back_with_every_reason_and_the_revision_is_judged_afresh():
    """Bug caught: the model revising blind — told only that it failed — or the second attempt
    judged against the first attempt's verdict."""
    ctx = _ctx(_fenced(_out_of_scope()), _fenced(_out_of_scope()))
    inputs = _inputs()
    inputs["resolved_config"]["campaign_proposal"]["objective"]["allowed_scope"] = ["backend/**"]

    result = await StrategyProposeIncrementHandler().handle(ctx, inputs)

    first, second = _prompts(ctx)
    assert "[out_of_scope]" not in first
    assert "[out_of_scope]" in second and "RunDetailView.jsx" in second
    assert not result.success
    assert "refused after its revision budget" in result.error and "out_of_scope" in result.error


async def test_a_backend_only_revision_of_a_refused_proposal_is_accepted():
    backend_only = yaml.safe_load(_REFERENCE)
    backend_only["manifest_delta"] = [
        op for op in backend_only["manifest_delta"] if op["target"] != "client_route"
    ]
    backend_only["criteria"] = [c for c in backend_only["criteria"] if c["id"] != "C3"]
    ctx = _ctx(_fenced(_out_of_scope()), _fenced(yaml.safe_dump(backend_only, sort_keys=False)))
    inputs = _inputs()
    inputs["resolved_config"]["campaign_proposal"]["objective"]["allowed_scope"] = [
        "backend/**",
        "frontend/src/__tests__/**",
        "frontend/src/tests/**",
    ]

    result = await StrategyProposeIncrementHandler().handle(ctx, inputs)

    assert result.success, result.error
    assert ctx.ports.llm.chat_stream_with_usage.await_count == 2


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        (_inputs(block=False), "no campaign_proposal"),
        (_inputs(manifest=""), "carries no baseline_manifest"),
    ],
    ids=["no-campaign-context", "no-baseline-manifest"],
)
async def test_a_proposal_without_its_context_fails_before_asking_the_model(inputs, message):
    ctx = _ctx()
    result = await StrategyProposeIncrementHandler().handle(ctx, inputs)
    assert not result.success and message in result.error
    ctx.ports.llm.chat_stream_with_usage.assert_not_awaited()


def test_the_proposal_workload_is_one_strategy_step_and_needs_the_strategy_role():
    profile = MagicMock(profile_id="full")
    steps, builder = _resolve_workload_steps(WorkloadType.PROPOSAL, profile, {"strat", "dev"})
    assert (steps, builder) == ([(TaskType.STRATEGY_PROPOSE_INCREMENT, "strat")], False)
    with pytest.raises(CycleError, match="missing required proposal roles: strat"):
        _resolve_workload_steps(WorkloadType.PROPOSAL, profile, {"dev", "qa"})


async def test_an_envelope_from_the_runtime_reaches_the_handler_with_no_vault_and_is_accepted():
    """Wiring, entered where the agent enters: a task envelope through the real HandlerExecutor
    and HandlerRegistry, its inputs shaped as the runtime sends them — the cycle's resolved
    config and the PRD, and no artifact vault. Bug caught: the handler needing an input the
    runtime never sends (cyc_a06843b58e4f, the first live proposal run, refused for the vault)."""
    from squadops.orchestration.handler_executor import HandlerExecutor
    from squadops.orchestration.handler_registry import HandlerRegistry
    from squadops.tasks.models import TaskEnvelope

    ctx = _ctx(_fenced(_REFERENCE))
    registry = HandlerRegistry()
    registry.register(StrategyProposeIncrementHandler(), roles=("strat",))
    executor = HandlerExecutor("nat", registry, ctx.ports, role="strat")
    inputs = _inputs()
    assert "artifact_vault" not in inputs
    envelope = TaskEnvelope(
        task_id="t1",
        agent_id="nat",
        cycle_id="cyc_1",
        pulse_id="p",
        project_id="group_run",
        task_type=TaskType.STRATEGY_PROPOSE_INCREMENT,
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
        inputs=inputs,
    )

    result = await executor.execute(envelope)

    assert str(result.status).lower().endswith("succeeded"), (result.status, result.error)
    assert result.outputs["change_request"]["proposal_id"] == "prop_1"
