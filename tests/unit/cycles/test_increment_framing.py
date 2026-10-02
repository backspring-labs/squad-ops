"""An increment's framing frames its approved change request (SIP-0109 §7.3; #1705 step d).

Research and objective framing are skipped, because the change request is the framed objective;
every framing stage after them is shown it verbatim.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from squadops.campaigns.change_request import (
    ProposalContext,
    stored_change_request,
    validate_proposal,
)
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    CycleError,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_plan import build_planning_steps, generate_task_plan

NOW = datetime(2026, 10, 2, 14, 0, tzinfo=UTC)
_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"
BASELINE = (_FIXTURES / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml").read_text()
STORED_REQUEST = stored_change_request(
    validate_proposal(
        yaml.safe_load((_FIXTURES / "reference-capacity-change-request.yaml").read_text()),
        ProposalContext(
            "prop_cap",
            1,
            "sha-accepted",
            BASELINE,
            "fullstack_fastapi_react",
            ("backend/**", "frontend/**"),
            (),
        ),
    ).change_request
)
PROFILE = SquadProfile(
    profile_id="full",
    name="full",
    description="",
    version=1,
    created_at=NOW,
    agents=tuple(
        AgentProfileEntry(agent_id=a, role=r, model="m", enabled=True, serves_roles=(r,))
        for a, r in (
            ("nat", "strat"),
            ("neo", "dev"),
            ("eve", "qa"),
            ("data", "data"),
            ("max", "lead"),
        )
    ),
)
FRAMING = Run("run_f", "cyc_inc", 2, "running", "system", "cfg", workload_type="framing")


def _cycle(increment: bool) -> Cycle:
    overrides: dict = {"contract_ref": "art_contract"}
    if increment:
        overrides["campaign_proposal"] = {"proposal_id": "prop_cap", "baseline_manifest": BASELINE}
    return Cycle(
        cycle_id="cyc_inc",
        project_id="group_run",
        created_at=NOW,
        created_by="launcher",
        prd_ref="the group_run PRD",
        squad_profile_id="full",
        squad_profile_snapshot_ref="x",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"build_profile": "fullstack_fastapi_react"},
        execution_overrides=overrides,
        campaign_id="cmp_1" if increment else None,
        kind="increment" if increment else None,
    )


async def _prompt(handler, inputs: dict) -> str:
    """The user prompt a framing stage sends, through its real ``handle()`` and the shipped
    prompt assets."""
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.prompts.renderer import RequestTemplateRenderer

    sent: list[str] = []

    async def _llm_call(context, messages, chat_kwargs, **_):
        sent.append(messages[-1].content)
        return MagicMock(), "the document"

    handler._llm_call = _llm_call
    context = MagicMock()
    context.ports.request_renderer = RequestTemplateRenderer(
        create_prompt_asset_source("filesystem")
    )
    context.ports.prompt_service.assemble.return_value = MagicMock(content="sys", assembly_hash="h")
    await handler.handle(context, inputs)
    return sent[0]


async def test_an_increments_framing_skips_the_frame_and_shows_every_stage_the_change():
    """Wiring, entered at ``generate_task_plan`` (what the framing run's provisioning calls) and
    carried to the prompt the technical design sends. Bugs caught: an increment researched and
    framed as a new application from its PRD, or the change request reaching a stage's inputs
    and not its prompt (#1845's shape)."""
    from squadops.capabilities.handlers.planning.framing import DevelopmentDesignPlanHandler

    plan = generate_task_plan(_cycle(True), FRAMING, PROFILE, change_request=STORED_REQUEST)

    types = [e.task_type for e in plan]
    assert types[0] == "development.design_plan"
    assert not {"data.research_context", "strategy.frame_objective"} & set(types)
    assert all(e.inputs["increment_change_request"] == STORED_REQUEST for e in plan)

    [design] = [e for e in plan if e.task_type == "development.design_plan"]
    prompt = await _prompt(DevelopmentDesignPlanHandler(), dict(design.inputs, prd="the PRD"))

    assert "THIS CYCLE IS AN INCREMENT" in prompt
    assert f"```\n{STORED_REQUEST}```" in prompt  # verbatim, fenced


async def test_the_brief_frames_the_proposers_from_the_change_request():
    """Bug caught: the proposers' shared frame pinned from the PRD alone, so the plan authors
    plan the accepted application rather than the change."""
    from squadops.capabilities.handlers.planning.brief import (
        GovernancePreparePlanAuthoringBriefHandler,
    )

    plan = generate_task_plan(_cycle(True), FRAMING, PROFILE, change_request=STORED_REQUEST)
    [brief] = [e for e in plan if e.task_type == "governance.prepare_plan_authoring_brief"]

    prompt = await _prompt(
        GovernancePreparePlanAuthoringBriefHandler(), dict(brief.inputs, prd="the PRD")
    )

    assert "THIS CYCLE IS AN INCREMENT" in prompt
    assert "capacity_exceeded" in prompt  # the approved delta, shown


async def test_a_new_applications_framing_is_unchanged():
    plan = generate_task_plan(_cycle(False), FRAMING, PROFILE)

    assert [e.task_type for e in plan][:2] == ["data.research_context", "strategy.frame_objective"]
    assert not any("increment_change_request" in e.inputs for e in plan)


@pytest.mark.parametrize(
    ("increment", "change_request", "refusal"),
    [
        (True, None, "frames an increment with no approved change request"),
        (False, STORED_REQUEST, "only an increment's framing frames"),
    ],
    ids=["an-increment-without-its-change", "a-change-for-a-cycle-that-proposed-none"],
)
def test_a_change_request_frames_an_increment_and_nothing_else(increment, change_request, refusal):
    with pytest.raises(CycleError, match=refusal):
        generate_task_plan(_cycle(increment), FRAMING, PROFILE, change_request=change_request)


def test_an_increment_authors_no_manifest():
    """Bug caught: an increment's framing authoring an interface from its PRD, replacing the
    accepted interface and the approved delta with a fresh one."""
    with pytest.raises(CycleError, match="authors no manifest"):
        build_planning_steps(None, authors_manifest=True, increment=True)
