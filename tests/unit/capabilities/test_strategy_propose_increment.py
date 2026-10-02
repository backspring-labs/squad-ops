"""``strategy.propose_increment`` (SIP-0109 §9.1; #1706), entered at ``handle()``.

The real prompt assets render through the real renderer and assembler; the model is stubbed with
the emissions under test. The baseline is the 1.9 roll cyc_7a4b7a6fbf0e's authored manifest, served
from a vault by its artifact id the way the campaign's cycle names it.
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


class _Vault:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def retrieve(self, artifact_id: str):
        if self.fail:
            raise OSError("vault unavailable")
        assert artifact_id == "art_f127a0c2f5e7"
        return None, _BASELINE.encode("utf-8")


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


def _inputs(*, scope=("backend/**", "frontend/**"), vault=None, block=True) -> dict:
    config: dict = {"build_profile": "fullstack_fastapi_react", "proposal_max_attempts": 2}
    if block:
        config["campaign_proposal"] = {
            "proposal_id": "prop_1",
            "version": 1,
            "baseline_tree": "tree:7a4b7a6f",
            "baseline_manifest_artifact_id": "art_f127a0c2f5e7",
            "objective": {
                "statement": "evolve group_run toward its PRD's expansion scope",
                "allowed_scope": list(scope),
                "measurement": "two accepted increments",
            },
            "prior_criteria": [],
        }
    return {"resolved_config": config, "artifact_vault": vault or _Vault(), "prd": ""}


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
        (_inputs(vault=_Vault(fail=True)), "is unreadable"),
    ],
    ids=["no-campaign-context", "unreadable-baseline"],
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
