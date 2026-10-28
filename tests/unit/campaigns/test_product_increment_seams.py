"""A repository-backed increment through the increment seams (SIP-0109 §24bv point 5).

Its ``campaign_proposal`` block names its basis, ``campaign_branch``, and carries no manifest. Every
seam that asked "is this an increment?" by the manifest read such a cycle as none. Each test enters
at the seam's live caller: the launcher's continuation (``CampaignProgress._bound_seeds``), plan
generation (``generate_task_plan``, which ``RunProvisioning.prepare`` calls), the framing gate
(``_reject_invalid_plan_before_workload_gate``) and the proposal's evidence step
(``with_proposal_evidence``). The change requests are invented changes to the shared fixture's
Tally.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.noop.ports import NoOpFailurePatternRecall, NoOpProposalEvidence
from squadops.campaigns.change_request import (
    PlacedCriterionFile,
    stored_change_request,
    validate_proposal,
)
from squadops.campaigns.increment_tree import (
    IncrementBasis,
    increment_basis,
    increment_criterion_files,
)
from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from tests.unit.campaigns.test_product_change_request import _context, _request

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
_REQUEST = validate_proposal(_request(), _context()).change_request
STORED = stored_change_request(_REQUEST)
_BLOCK = {
    "proposal_id": "prop_tally0001",
    "version": 1,
    "basis": "campaign_branch",
    "baseline_tree": "f" * 64,
    "objective": {"statement": "s", "allowed_scope": ["tally/**"], "measurement": "m"},
    "prior_criteria": [],
    "frozen_criteria": [],
    "max_revisions": 2,
}


@pytest.mark.parametrize(
    ("block", "basis"),
    [
        (None, None),
        ({"proposal_id": "p"}, None),
        ({"proposal_id": "p", "baseline_manifest": "api: {}\n"}, IncrementBasis.MANIFEST),
        (_BLOCK, IncrementBasis.CAMPAIGN_BRANCH),
    ],
    ids=["no block", "a block with no tree", "a sample application's", "a campaign branch's"],
)
def test_the_basis_is_read_from_the_block_never_from_a_manifests_presence(block, basis):
    """Rule 3's marker. Bugs caught: a campaign branch's increment read as no increment because it
    carries no manifest; a block written before §24bv point 5 read as anything but a manifest's."""
    config = {"campaign_proposal": block} if block is not None else {}

    assert increment_basis(config) is basis


@pytest.mark.parametrize(
    "block",
    [{**_BLOCK, "basis": "workspace"}, {"proposal_id": "p", "basis": "manifest"}],
    ids=["an unknown basis", "a manifest basis with no manifest"],
)
def test_a_block_the_reader_cant_place_is_refused_never_read_as_no_increment(block):
    """Bug caught: an unreadable basis defaulted to no increment, so its framing designs the
    product again with no change request."""
    with pytest.raises(ValueError):
        increment_basis({"campaign_proposal": block})


class _Vault:
    """The proposal run's artifacts: its change request, promoted at the approval or not."""

    def __init__(self, promoted: bool) -> None:
        self.ref = ArtifactRef(
            "art_cr", "prj-tally", "change_request", "change_request.yaml", "h", 1, "text/yaml",
            NOW, cycle_id="cyc_inc", run_id="run_prop",
            promotion_status="promoted" if promoted else "working",
        )  # fmt: skip

    async def list_artifacts(self, *, run_id=None, promotion_status=None, **_):
        refs = [self.ref] if run_id in (None, self.ref.run_id) else []
        return [r for r in refs if promotion_status in (None, r.promotion_status)]

    async def retrieve(self, artifact_id):
        return self.ref, STORED.encode()


def _cycle(**overrides) -> Cycle:
    return Cycle(
        cycle_id="cyc_inc",
        project_id="prj-tally",
        created_at=NOW,
        created_by="campaign-launcher",
        prd_ref=None,
        squad_profile_id="full-38",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"implementation_plan": True},
        execution_overrides={"campaign_proposal": dict(_BLOCK), **overrides},
        campaign_id="cmp_tally00001",
        kind="increment",
    )


@pytest.mark.parametrize(("promoted", "seeds"), [(True, (["art_cr"], None)), (False, None)])
async def test_a_branch_increments_continuation_carries_its_approved_change_request(
    promoted, seeds
):
    """§10a, entered at ``CampaignProgress._bound_seeds``, which a repair's and a retry's launch
    reads. Bugs caught: the seed read only where a manifest was promoted, so a repository-backed
    increment's repair or retry carries no change request and its framing has nothing to frame;
    a change request read before its approval promoted it."""
    from squadops.campaigns.progress import CampaignProgress

    cycles = MemoryCycleRegistry()
    cycle = _cycle()
    await cycles.create_cycle(cycle)
    for number, (run_id, workload) in enumerate(
        (("run_prop", "proposal"), ("run_impl", "implementation")), start=1
    ):
        await cycles.create_run(
            Run(
                run_id, cycle.cycle_id, number, "completed", "system", "cfg", workload_type=workload
            )
        )
    progress = CampaignProgress(
        campaigns=AsyncMock(), cycles=cycles, vault=_Vault(promoted), assess=AsyncMock(),
        launch=AsyncMock(), evaluate_outcome=None, outcome_section=None,
        intervention_section=None, campaign_branch=None,
    )  # fmt: skip

    assert await progress._bound_seeds(cycle) == seeds


def test_a_branch_requests_criterion_files_are_the_placed_ones_with_no_stack():
    """Bug caught: ``scaffold.criterion_test_path`` asked for a product's file, which raises with
    no stack, so the framing gate skips the criterion-file rule and the evaluation finds no file; or a
    request whose placement was dropped read as placing nothing (§24cj: it is refused)."""
    [placed] = increment_criterion_files(STORED, "")
    unplaced = dataclasses.replace(_REQUEST, criterion_files=(), footprint=("tally/report.py",))
    data = yaml.safe_load(stored_change_request(unplaced))

    assert (placed.criterion_id, placed.path) == ("R1", "checks/check_criterion_R1.py")
    assert _REQUEST.criterion_files == (PlacedCriterionFile("R1", placed.path),)
    with pytest.raises(
        ValueError, match="placement is refused: its criteria are R1, and it places none"
    ):
        increment_criterion_files(yaml.safe_dump(data), "")


def _profile() -> SquadProfile:
    return SquadProfile(
        profile_id="full", name="full", description="", version=1, created_at=NOW,
        agents=tuple(
            AgentProfileEntry(agent_id=a, role=r, model="m", enabled=True, serves_roles=(r,))
            for a, r in (("nat", "strat"), ("neo", "dev"), ("eve", "qa"), ("data", "data"),
                         ("max", "lead"))
        ),
    )  # fmt: skip


def test_a_branch_increments_plan_authors_are_shown_its_footprint_and_criterion_files():
    """Teach, then enforce (#686), entered at ``generate_task_plan``. A product has no manifest,
    so no contract. Bugs caught: the indexes injected only in bind mode, so the plan author is
    never shown the footprint and criterion files the framing gate then holds it to; or the
    framing given no change request, so it frames the product anew."""
    from squadops.cycles.task_plan import generate_task_plan

    run = Run("run_f", "cyc_inc", 2, "running", "system", "cfg", workload_type="framing")

    plan = generate_task_plan(_cycle(), run, _profile(), change_request=STORED)

    [merge] = [e for e in plan if e.task_type == "governance.merge_plan"]
    assert merge.inputs["increment_footprint_index"] == (
        "- `tally/report.py`\n- `checks/check_criterion_R1.py`"
    )
    assert merge.inputs["increment_criterion_files_index"] == (
        "- R1 (package `tally.report`): `checks/check_criterion_R1.py`"
    )
    assert "report-totals" in merge.inputs["increment_change_request"]


def _plan(*artifacts: str) -> str:
    return yaml.safe_dump(
        {
            "version": 1, "project_id": "prj-tally", "cycle_id": "cyc_inc", "prd_hash": "abc",
            "summary": {"total_dev_tasks": 1, "total_qa_tasks": 1, "total_tasks": 2},
            "tasks": [
                {
                    "task_index": i, "task_type": task_type, "role": role, "focus": f"write {a}",
                    "description": "d", "expected_artifacts": [a], "acceptance_criteria": [],
                }
                for i, (a, task_type, role) in enumerate(artifacts)
            ],
        }
    )  # fmt: skip


class _GateVault(_Vault):
    def __init__(self, plan: str, document: str = STORED) -> None:
        super().__init__(promoted=True)
        self.plan = ArtifactRef(
            "art_plan", "prj-tally", "control_implementation_plan", "implementation_plan.yaml",
            "h", 1, "text/yaml", NOW, cycle_id="cyc_inc", run_id="run_f",
        )  # fmt: skip
        self.plan_text = plan
        self.document = document

    async def retrieve(self, artifact_id):
        if artifact_id == "art_plan":
            return self.plan, self.plan_text.encode()
        return self.ref, self.document.encode()


def _executor(vault):
    from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor

    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(), artifact_vault=vault,
        queue=AsyncMock(), squad_profile=AsyncMock(), task_timeout=5.0, project_registry=None,
        campaign_registry=None, campaign_progress=None, box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(), proposal_evidence=NoOpProposalEvidence(),
    )  # fmt: skip
    executor._cycle_event_bus = MagicMock()
    return executor


def _tampered() -> str:
    """The stored request with its criterion's file moved after the ruling (the review's P2)."""
    data = yaml.safe_load(STORED)
    data["criterion_files"] = [{"criterion_id": "R1", "path": "tests/check_criterion_R1.py"}]
    data["footprint"] = ["tally/report.py", "tests/check_criterion_R1.py"]
    return yaml.safe_dump(data, sort_keys=False)


async def test_a_tampered_placement_fails_closed_at_each_reader_after_the_ruling():
    """The review's P2, at the live readers: the framing's provisioning
    (``approved_change_request``, which ``RunProvisioning.prepare`` calls) and the framing gate.
    Bugs caught: the moved file read as the one ruled on; or, at the gate, the unreadable request
    read as no rule to apply (its sample-application rules skip on an unreadable input, #473), so a
    product's plan passes held to nothing."""
    from squadops.campaigns.increment_tree import approved_change_request

    plan = _plan(
        ("tally/report.py", "development.develop", "dev"),
        ("tests/check_criterion_R1.py", "qa.test", "qa"),
    )
    vault = _GateVault(plan, _tampered())
    run = Run(
        "run_f", "cyc_inc", 2, "completed", "system", "cfg",
        workload_type="framing", artifact_refs=("art_plan",),
    )  # fmt: skip
    cycle = _cycle(plan_artifact_refs=["art_cr"])

    with pytest.raises(ValueError, match="does not match its hash"):
        await approved_change_request(vault, cycle)
    errors = await _executor(vault)._reject_invalid_plan_before_workload_gate(
        run, cycle, "progress_plan_review"
    )

    [held] = [e for e in errors if "can't be held to its footprint and criterion files" in e]
    assert held.endswith("the stored change request's content does not match its hash")


@pytest.mark.parametrize(
    ("artifacts", "refused"),
    [
        (
            (("tally/report.py", "development.develop", "dev"),
             ("checks/check_criterion_R1.py", "qa.test", "qa")),
            [],
        ),
        (
            (("tally/report.py", "development.develop", "dev"),
             ("tally/ledger.py", "development.develop", "dev"),
             ("checks/check_criterion_R1.py", "qa.test", "qa")),
            ["approved change does not touch"],
        ),
        ((("tally/report.py", "development.develop", "dev"),), ["R1"]),
    ],
    ids=["inside the footprint", "a product file outside it", "the criterion's file unplanned"],
)  # fmt: skip
async def test_the_framing_gate_holds_a_branch_increments_plan_to_its_request(artifacts, refused):
    """The plan validator enforces the authored footprint as today (§24bv point 5), entered at
    ``_reject_invalid_plan_before_workload_gate``. Bugs caught: the footprint rule skipped because
    the cycle carries no manifest; the criterion-file rule skipped because no stack places it."""
    executor = _executor(_GateVault(_plan(*artifacts)))
    run = Run(
        "run_f", "cyc_inc", 2, "completed", "system", "cfg",
        workload_type="framing", artifact_refs=("art_plan",),
    )  # fmt: skip

    errors = await executor._reject_invalid_plan_before_workload_gate(
        run, _cycle(plan_artifact_refs=["art_cr"]), "progress_plan_review"
    )

    relevant = [e for e in errors if "approved change" in e or "R1" in e]
    assert len(relevant) == len(refused), errors
    assert all(any(r in e for e in relevant) for r in refused)


async def test_a_branch_increments_proposal_is_shown_no_outcome_evidence_and_not_refused():
    """``with_proposal_evidence``, which ``RunProvisioning.prepare`` calls for every proposal. Bug
    caught: a repository-backed proposal, whose block names no accepted cycle, refused as having
    no tree to show evidence of, so every such proposal run fails before its first task."""
    from squadops.execution.proposal_evidence import with_proposal_evidence

    port = AsyncMock()
    envelope = MagicMock(task_type="strategy.propose_increment", inputs={"a": 1})

    composed = await with_proposal_evidence(port, [envelope], cycle=_cycle())

    assert composed == [envelope]
    port.for_proposal.assert_not_called()


# --- SIP-0109 §24cp (#2779): the anchor of a page the change adds, shown to its authors --------


def _anchored() -> str:
    """Tally's request with R1 on ``/totals``, a page its profile doesn't judge, naming the
    anchor its view renders, as the rails accepted and stored it."""
    from tests.unit.campaigns.test_product_change_request import _WITH_PAGES, _on_a_page

    verdict = validate_proposal(
        _request(criteria=[_on_a_page("/totals", "totals-view")]), _context(product=_WITH_PAGES)
    )
    assert verdict.accepted, verdict.refusals
    return stored_change_request(verdict.change_request)


_VIEW_LINE = "- page `/totals`: anchor `totals-view` (criteria R1)"


def _renderer():
    from adapters.prompts.factory import DEFAULT_TEMPLATES_PATH, create_prompt_asset_source
    from squadops.prompts.renderer import RequestTemplateRenderer

    return RequestTemplateRenderer(
        asset_source=create_prompt_asset_source(
            provider="filesystem", templates_path=DEFAULT_TEMPLATES_PATH
        )
    )


async def test_a_branch_increments_plan_authors_are_shown_the_anchor_of_each_page_it_adds():
    """Entered at ``generate_task_plan`` (framing), then the plan authors' real render of the
    increment surfaces (``render_surfaces``, which the proposers and the sole-author merger call).
    Bugs caught: the anchor stored and never shown, so the plan never gives the view's task the
    anchor acceptance reads the page for; or shown on a request that names none."""
    from squadops.capabilities.handlers._plan_authoring import INCREMENT_SURFACES, render_surfaces
    from squadops.cycles.task_plan import generate_task_plan

    run = Run("run_f", "cyc_inc", 2, "running", "system", "cfg", workload_type="framing")

    anchored = generate_task_plan(_cycle(), run, _profile(), change_request=_anchored())
    plain = generate_task_plan(_cycle(), run, _profile(), change_request=STORED)

    [merge] = [e for e in anchored if e.task_type == "governance.merge_plan"]
    assert merge.inputs["increment_views_index"] == _VIEW_LINE
    assert all("increment_views_index" not in e.inputs for e in plain)
    rendered = await render_surfaces(_renderer(), merge.inputs, INCREMENT_SURFACES)
    assert "## The pages this change adds, and the anchor each one's view renders" in rendered
    assert '`<section data-testid="export-view">`' in rendered
    assert rendered.endswith(_VIEW_LINE)


async def test_a_branch_increments_view_and_suite_authors_are_shown_the_anchor(monkeypatch):
    """Entered at ``generate_task_plan`` (implementation), then each author's prompt as its
    handler builds it: the developer's focused prompt, and the qa author's whole ``handle()``.
    Bugs caught: the developer, who writes the view, never told the anchor, so the page renders
    without it and the increment is rejected; the suite's author never told it, so the criterion's
    test looks for the view by another id; either told it on an increment that adds no page."""
    from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
    from squadops.cycles.task_plan import generate_task_plan
    from tests.unit.campaigns.test_increment_test_scope import _qa_prompt
    from tests.unit.cycles.test_increment_evaluation_wiring import _PLAN

    run = Run("run_i", "cyc_inc", 3, "running", "system", "cfg", workload_type="implementation")
    anchored = generate_task_plan(_cycle(), run, _profile(), plan=_PLAN, change_request=_anchored())
    plain = generate_task_plan(_cycle(), run, _profile(), plan=_PLAN, change_request=STORED)
    [dev] = [e for e in anchored if e.task_type == "development.develop"]
    [qa] = [e for e in anchored if e.task_type == "qa.test"]

    view = {"route": "/totals", "anchor": "totals-view", "criteria": ["R1"]}
    assert dev.inputs["increment_views"] == [view]
    assert qa.inputs["increment_test_scope"]["views"] == [view]
    assert "increment_views" not in qa.inputs  # the suite's author has it in its scope
    for e in plain:
        assert "increment_views" not in e.inputs
        assert "views" not in (e.inputs.get("increment_test_scope") or {})
    handler = DevelopmentDevelopHandler()
    handler._resolved_config = {}  # as handle() sets it before the prompt is built
    dev_prompt = await handler._build_focused_prompt(
        {**dev.inputs, "prd": "Tally", "artifact_contents": {}}, _renderer()
    )
    qa_prompt = await _qa_prompt(qa, monkeypatch)
    for prompt in (dev_prompt, qa_prompt):
        assert "## The pages this change adds, and the anchor each one's view renders" in prompt
        assert _VIEW_LINE in prompt


async def _dev_repair_prompt(change_request: str) -> tuple[dict, str]:
    """A failed ``development.develop`` of the implementation ``generate_task_plan`` makes for
    ``change_request``, through the correction loop (``run_correction_protocol``, a patch
    decision), then the repair it dispatches through ``DevelopmentCorrectionRepairHandler``'s whole
    ``handle()`` with the real assets: the repair's inputs and its prompt's user turn."""
    from squadops.capabilities.handlers.impl.repair_handlers import (
        DevelopmentCorrectionRepairHandler,
    )
    from squadops.cycles.task_plan import generate_task_plan
    from squadops.tasks.models import TaskResult
    from tests.unit.cycles.test_correction_runner import TestCorrectionRunnerStandalone
    from tests.unit.cycles.test_increment_evaluation_wiring import _PLAN

    run = Run("run_i", "cyc_inc", 3, "running", "system", "cfg", workload_type="implementation")
    [dev] = [
        e
        for e in generate_task_plan(
            _cycle(), run, _profile(), plan=_PLAN, change_request=change_request
        )
        if e.task_type == "development.develop"
    ]
    captured: list = []

    def responder(envelope):
        if envelope.task_type == "governance.correction_decision":
            return TaskResult(
                task_id=envelope.task_id,
                status="SUCCEEDED",
                outputs={
                    "correction_path": "patch",
                    "decision_rationale": "the view is patchable",
                    "affected_task_types": ["development.develop"],
                },
            )
        if envelope.task_type == "development.correction_repair":
            captured.append(envelope)
        return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

    runner, *_ = TestCorrectionRunnerStandalone()._make_runner(responder)
    cycle = dataclasses.replace(
        _cycle(), applied_defaults={"correction_steps": ["analyze", "decide", "repair"]}
    )
    await runner.run_correction_protocol(
        run_id="run_i", cycle=cycle, envelope=dev,
        result=TaskResult(task_id=dev.task_id, status="FAILED", error="the view failed"),
        correction_attempts=0, prior_outputs={}, all_artifact_refs=[], stored_artifacts=[],
        completed_task_ids=[], plan_delta_refs=[], correction_budget=3,
    )  # fmt: skip
    [repair] = captured
    ctx = MagicMock()
    ctx.role_id = "dev"
    ctx.task_id = repair.task_id
    ctx.correlation_context = None
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        return_value=MagicMock(
            content="no fences", prompt_tokens=1, completion_tokens=1, reasoning_tokens=None
        )
    )
    ctx.ports.llm.default_model = "m"
    ctx.ports.llm_observability = None
    ctx.ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ctx.ports.request_renderer = _renderer()
    await DevelopmentCorrectionRepairHandler().handle(
        ctx, {**repair.inputs, "prd": "Tally", "failed_task_type": "development.develop"}
    )
    return repair.inputs, ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0][
        -1
    ].content


async def test_a_dev_repair_of_an_added_pages_view_keeps_its_anchor():
    """The outside review of #2780 (P2 2): a developer correcting a failed view of a page the
    change adds is shown the anchor acceptance reads the page for, as its first author was.
    Entered at the correction loop on an anchored ``development.develop``. Bugs caught:
    ``increment_views`` dropped at the repair handoff (``REPAIR_PRESENCE_KEYS``), so the repair
    rewrites the view without the anchor and the increment is rejected; or carried and never
    rendered (#1289's shape)."""
    inputs, prompt = await _dev_repair_prompt(_anchored())

    assert inputs["increment_views"] == [
        {"route": "/totals", "anchor": "totals-view", "criteria": ["R1"]}
    ]
    assert "## The pages this change adds, and the anchor each one's view renders" in prompt
    assert _VIEW_LINE in prompt
    assert "{{increment_views_section}}" not in prompt


async def test_a_dev_repair_on_an_increment_that_adds_no_page_is_shown_none():
    """The edge. Bug caught: the views section rendered empty, or from nothing, on every repair."""
    inputs, prompt = await _dev_repair_prompt(STORED)

    assert "increment_views" not in inputs
    assert "The pages this change adds" not in prompt
