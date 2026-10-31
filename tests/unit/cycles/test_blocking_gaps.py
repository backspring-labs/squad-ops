"""A blocking gap of the derived profile refuses the work it meets (SIP-0112 H.4; H.6, H.8).

A gap that stops ``work`` names paths where no check of the product can run. A source-backed
Cycle whose work meets one is refused before dispatch: at create for an unconfined gap or an
operator's plan (``test_contract1_source_context.py``), and at both plan-gate seams for a plan
framing authored, entered here as the live run reaches them. Shelfnote's shape is the example: a
runner over ``frontend/`` that lost its toolchain, and one over ``backend/`` that still runs.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from adapters.noop.ports import NoOpFailurePatternRecall, NoOpProposalEvidence
from squadops.cycles.models import (
    ArtifactRef,
    Cycle,
    DerivedProfileNotFoundError,
    Run,
    TaskFlowPolicy,
)
from squadops.projects.derived_profile import Gap, parse_profile
from squadops.projects.source_context import parse_source_context
from tests.fixtures.shared_contract.repository import recorded

NOW = datetime(2026, 10, 24, tzinfo=UTC)
_NPM = Gap(
    "missing_toolchain", "blocking", "npm", ("frontend/**",),
    "npm isn't in the sandbox's image, so frontend_tests can't run", "npm in the sandbox's image",
)  # fmt: skip
_NO_CHECK = Gap(
    "no_check_ran", "blocking", None, ("**",), "no check ran at the baseline: none is declared",
    "a check the sandbox can run, declared in the Development Configuration",
)  # fmt: skip
_RUFF = Gap(
    "missing_toolchain", "disclosed", "ruff", ("**",), "ruff isn't in the sandbox's image",
    "ruff in the sandbox's image",
)  # fmt: skip
_TESTS_UNCLASSED = Gap(
    "test_files_unclassed", "blocking", None, ("frontend/e2e/**",), "1 file belongs to no runner",
    "a check that runs it",
)  # fmt: skip
_CONTEXT = parse_source_context(recorded("project_source_context", "valid"))


def _profile(*gaps: Gap):
    return dataclasses.replace(parse_profile(recorded("derived_profile", "valid")), gaps=gaps)


@pytest.mark.parametrize(
    ("gaps", "paths", "met"),
    [
        ((_NPM,), ("frontend/src/App.jsx",), ["missing_toolchain"]),
        ((_NPM,), ("backend/main.py",), []),
        ((_NPM,), None, []),
        ((_NO_CHECK,), None, ["no_check_ran"]),
        ((_NO_CHECK,), ("backend/main.py",), ["no_check_ran"]),
        ((_RUFF, _TESTS_UNCLASSED), ("frontend/e2e/home.spec.ts",), []),
    ],
    ids=[
        "a confined gap the paths meet",
        "a confined gap the paths miss",
        "a confined gap and paths not yet known",
        "an unconfined gap meets work whose paths aren't known",
        "an unconfined gap meets any paths",
        "disclosed gaps and a campaigns-only gap stop no Cycle's work",
    ],
)
def test_a_blocking_gap_stops_the_work_its_paths_meet(gaps, paths, met):
    """H.6's rule, single-sourced on the record. Bugs caught: a confined gap refusing work
    elsewhere in the tree; an unconfined one let through because no paths are known yet; a
    disclosed gap, or one that stops only Campaigns, refusing a standalone Cycle."""
    assert [g.id for g in _profile(*gaps).blocking_work(paths)] == met


def _plan(*artifacts: str) -> str:
    return yaml.safe_dump(
        {
            "version": 1,
            "project_id": "prj-tally",
            "cycle_id": "cyc_gap",
            "prd_hash": "abc",
            "summary": {"total_dev_tasks": len(artifacts), "total_qa_tasks": 0},
            "tasks": [
                {
                    "task_index": i,
                    "task_type": "development.develop",
                    "role": "dev",
                    "focus": f"change {a}",
                    "description": "change it",
                    "expected_artifacts": [a],
                    "acceptance_criteria": [],
                }
                for i, a in enumerate(artifacts)
            ],
        }
    )


class _Vault:
    def __init__(self, plan: str) -> None:
        self.ref = ArtifactRef(
            "art_plan", "prj-tally", "control_implementation_plan", "implementation_plan.yaml",
            "h", 1, "text/yaml", NOW, cycle_id="cyc_gap", run_id="run_f",
        )  # fmt: skip
        self.plan = plan.encode()

    async def retrieve(self, artifact_id):
        return self.ref, self.plan


class _Registry:
    def __init__(self, profile) -> None:
        self.profile, self.asked = profile, []

    async def get_derived_profile(self, project_id, *, at=None):
        self.asked.append((project_id, at))
        if self.profile is None:
            raise DerivedProfileNotFoundError("none")
        return self.profile


def _executor(plan: str, registry: _Registry):
    from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor

    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=_Vault(plan),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        project_registry=registry,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(),
        proposal_evidence=NoOpProposalEvidence(),
    )
    executor._cycle_event_bus = MagicMock()
    return executor


def _cycle(source_backed: bool = True) -> Cycle:
    return Cycle(
        cycle_id="cyc_gap",
        project_id="prj-tally",
        created_at=NOW,
        created_by="owner",
        prd_ref=None,
        squad_profile_id="full",
        squad_profile_snapshot_ref="x",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"implementation_plan": True},
        source_context=_CONTEXT if source_backed else None,
    )


async def _promotion_errors(plan: str, registry: _Registry, source_backed: bool = True):
    run = Run(
        "run_f", "cyc_gap", 1, "completed", "system", "cfg",
        workload_type="framing", artifact_refs=("art_plan",),
    )  # fmt: skip
    errors = await _executor(plan, registry)._reject_invalid_plan_before_workload_gate(
        run, _cycle(source_backed), "progress_plan_review"
    )
    return [e for e in errors if e.startswith("blocking_gap")]


async def test_the_promotion_seam_rejects_a_plan_writing_where_a_gap_stops_the_work():
    """Entered at the inter-workload gate, so the framing re-rolls told where (#522, #669).
    Bugs caught: a plan building frontend/ when no check can run there promoted to a full
    implementation run; the profile read at another source than the cycle pinned."""
    registry = _Registry(_profile(_NPM))

    [error] = await _promotion_errors(_plan("backend/main.py", "frontend/src/App.jsx"), registry)

    assert "frontend/src/App.jsx lie where missing_toolchain (npm) stops the work" in error
    assert "backend/main.py" not in error
    assert "npm in the sandbox's image" in error  # what would close it, for the re-roll
    assert registry.asked == [
        (
            "prj-tally",
            (_CONTEXT.development_baseline_commit, _CONTEXT.development_configuration_revision),
        )
    ]


@pytest.mark.parametrize(
    ("profile", "source_backed", "asked"),
    [
        (_profile(_NPM), True, 1),
        (None, True, 1),
        (_profile(_NO_CHECK), False, 0),
    ],
    ids=["a plan clear of the gap", "a pin with no profile", "a sample application"],
)
async def test_a_plan_clear_of_every_gap_or_with_no_profile_to_read_passes(
    profile, source_backed, asked
):
    registry = _Registry(profile)

    errors = await _promotion_errors(_plan("backend/main.py"), registry, source_backed)

    assert errors == []
    assert len(registry.asked) == asked


async def test_the_dispatch_seam_fails_the_run_naming_the_gap_and_its_validator():
    """Entered at the in-run plan gate (the #718/#719 rule: both seams). Bug caught: a plan
    reaching implementation through the in-run gate, which never read the gaps, while the
    promotion seam refuses the same plan."""
    from squadops.execution.execution_errors import _ExecutionError

    dev = MagicMock(role="dev", serves_roles=("dev",), enabled=True)
    squad = MagicMock(profile_id="full", agents=[dev])
    executor = _executor(_plan("frontend/src/App.jsx"), _Registry(_profile(_NPM)))

    with pytest.raises(_ExecutionError) as raised:
        await executor._reject_unsatisfiable_plan_at_gate(
            [("art_plan", executor._artifact_vault.ref)], squad, ["progress_plan_review"], _cycle()
        )

    assert "missing_toolchain (npm)" in str(raised.value)
    assert raised.value.terminal.refused_validators == ("validate_blocking_gaps",)


@pytest.fixture
def noop_sandbox(monkeypatch):
    """The create path's preflight reads the sandbox's provider, as the route's would."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


def _creation_ports(profile, vault=None):
    from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
    from adapters.cycles.memory_deploy_registry import MemoryDeployRegistry
    from squadops.api.routes.cycles.cycles import CreationPorts
    from squadops.projects.baseline import parse_baseline
    from tests.unit.shared_contract.test_contract1_source_context import _profile as _squad
    from tests.unit.shared_contract.test_contract1_source_context import _project

    registry = AsyncMock()
    registry.get_project.return_value = _project()
    registry.get_inherited_baseline.return_value = parse_baseline(
        recorded("inherited_baseline", "valid")
    )
    registry.source_syncs.return_value = []
    if profile is None:
        registry.get_derived_profile.side_effect = DerivedProfileNotFoundError("none")
    else:
        registry.get_derived_profile.return_value = profile
    squads = AsyncMock()
    squads.resolve_snapshot.return_value = (_squad(), "sha256:abc")
    return CreationPorts(
        project_registry=registry,
        squad_profile=squads,
        cycle_registry=MemoryCycleRegistry(),
        deploy_registry=MemoryDeployRegistry(),
        artifact_vault=vault,
    )


@pytest.mark.parametrize(
    ("gaps", "planned", "refused"),
    [
        ((_NO_CHECK,), None, "no_check_ran stops all work"),
        ((_NPM,), None, None),
        ((_NPM,), ("frontend/src/App.jsx",), "frontend/src/App.jsx lie where missing_toolchain"),
        ((_NPM,), ("backend/main.py",), None),
    ],
    ids=[
        "an unconfined gap",
        "a confined gap and no plan yet",
        "an operator's plan meeting a confined gap",
        "an operator's plan clear of it",
    ],
)
async def test_a_cycle_whose_known_work_meets_a_blocking_gap_is_refused_at_create(
    noop_sandbox, gaps, planned, refused
):
    """Entered at ``prepare_cycle``, which the create route and the Campaign launcher share.
    Bugs caught: a Cycle created over a product where no check can run, to fail hours later
    unverifiable; an operator's plan into a blocked area accepted because no framing gate
    reads it; a confined gap refusing work it doesn't meet."""
    from squadops.api.cycle_schemas import CycleCreateRequest
    from squadops.api.routes.cycles.cycles import prepare_cycle
    from squadops.cycles.models import ProjectStateConflictError

    vault = _Vault(_plan(*planned)) if planned else None
    overrides = {"plan_artifact_refs": ["art_plan"]} if planned else {}
    ports = _creation_ports(_profile(*gaps), vault)
    body = CycleCreateRequest(squad_profile_id="full", execution_overrides=overrides)

    if refused:
        with pytest.raises(ProjectStateConflictError, match=refused):
            await prepare_cycle(ports, "prj-tally", body)
        return
    prepared = await prepare_cycle(ports, "prj-tally", body)
    assert prepared.cycle.source_context == _CONTEXT
    pinned = (_CONTEXT.development_baseline_commit, _CONTEXT.development_configuration_revision)
    ports.project_registry.get_derived_profile.assert_awaited_once_with("prj-tally", at=pinned)


async def test_a_pin_with_no_profile_runs_as_before_with_the_absence_warned(noop_sandbox):
    """H.6: a baseline captured before profiles leaves its Cycles as they were in 2.4. Bug
    caught: every Project configured before 2.5 refused until someone recaptures it, or
    accepted with nothing said about the check it skipped."""
    from squadops.api.cycle_schemas import CycleCreateRequest
    from squadops.api.routes.cycles.cycles import prepare_cycle

    prepared = await prepare_cycle(
        _creation_ports(None), "prj-tally", CycleCreateRequest(squad_profile_id="full")
    )

    assert "derived_profile_absent" in [w.code for w in prepared.warnings]


def _envelope(task_type: str):
    from squadops.tasks.models import TaskEnvelope

    return TaskEnvelope(
        task_id=f"t-{task_type}", agent_id="a", cycle_id="cyc_gap", pulse_id="p",
        project_id="prj-tally", task_type=task_type, correlation_id="c", causation_id="c",
        trace_id="t", span_id="s", inputs={"prd": "x"},
    )  # fmt: skip


@pytest.mark.parametrize(
    ("gaps", "source_backed", "shown"),
    [
        ((_NPM,), True, True),
        ((_NO_CHECK, _RUFF), True, False),
        ((_NPM,), False, False),
        (None, True, False),
    ],
    ids=[
        "a confined gap",
        "only an unconfined gap (refused at create) and a disclosed one",
        "a sample application",
        "a pin with no profile",
    ],
)
async def test_the_plan_authors_are_shown_the_blocked_paths_before_a_gate_refuses(
    gaps, source_backed, shown
):
    """Teach, then enforce (#686), entered at the plan step ``RunProvisioning.prepare`` applies.
    Bugs caught: an author refused at the gate for paths it was never shown; a task that writes
    no plan given them; a sample application, or a pin with no profile, given a key it never had."""
    from squadops.execution.blocked_paths import BLOCKED_PATHS_INPUT, with_blocked_paths

    registry = _Registry(_profile(*gaps) if gaps else None)
    executor = _executor(_plan("backend/main.py"), registry)
    envelopes = [
        _envelope("governance.merge_plan"),
        _envelope("qa.propose_plan_tasks"),
        _envelope("development.develop"),
    ]

    composed = await with_blocked_paths(
        executor._derived_profile_for, envelopes, cycle=_cycle(source_backed)
    )

    has = [BLOCKED_PATHS_INPUT in e.inputs for e in composed]
    assert has == ([True, True, False] if shown else [False, False, False])
    if shown:
        assert composed[0].inputs[BLOCKED_PATHS_INPUT] == (
            "- `frontend/**`: missing_toolchain (npm). npm isn't in the sandbox's image, so "
            "frontend_tests can't run. It closes with: npm in the sandbox's image."
        )


@pytest.mark.parametrize("author", ["merger", "proposer"])
async def test_both_plan_author_paths_render_the_blocked_paths_through_the_managed_asset(author):
    """#448, #846: the prose is the asset's, and both authoring paths render it: the merger
    authoring alone, and the dev and qa proposers. Bug caught: the index reaching one path, the
    way the contract surfaces once reached only the proposers."""
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.capabilities.handlers._plan_authoring import contract_surface_sections
    from squadops.capabilities.handlers.planning.propose import DevelopmentProposePlanTasksHandler
    from squadops.execution.blocked_paths import BLOCKED_PATHS_INPUT, blocked_paths_index
    from squadops.prompts.renderer import RequestTemplateRenderer

    renderer = RequestTemplateRenderer(create_prompt_asset_source("filesystem"))
    inputs = {BLOCKED_PATHS_INPUT: blocked_paths_index(_profile(_NPM))}

    if author == "merger":
        text = await contract_surface_sections(renderer, inputs)
    else:
        text = await DevelopmentProposePlanTasksHandler()._increment_sections(renderer, inputs)

    assert "Where this product's checks can't run: plan no task there" in text
    assert "- `frontend/**`: missing_toolchain (npm)" in text


async def test_a_framing_runs_plan_authors_carry_the_blocked_paths_from_run_provisioning():
    """Wiring (anti-pattern 6a), entered at ``RunProvisioning.prepare``, the step ``execute_run``
    takes before dispatch, with the real plan generation for the ``validate`` profile's framing.
    On the Mac's live check (``cyc_0661f9d38394``) the merger authored the plan alone, and the
    plan gate refused it for ``frontend/``. Bug caught: the step applied nowhere on the live
    path, so an author is refused for paths the run never showed it."""
    from squadops.contracts.cycle_request_profiles import load_profile
    from squadops.execution.blocked_paths import BLOCKED_PATHS_INPUT
    from squadops.execution.run_provisioning import RunInProgress
    from tests.unit.cycles.test_increment_evaluation_wiring import PROFILE

    cycle = dataclasses.replace(
        _cycle(), applied_defaults={**dict(load_profile("validate").defaults)}
    )
    run = Run("run_f", "cyc_gap", 1, "queued", "system", "cfg", workload_type="framing")
    executor = _executor(_plan("backend/main.py"), _Registry(_profile(_NPM)))
    executor._prepare_cycle_for_run = AsyncMock(return_value=(cycle, None))
    executor._cycle_registry.get_run.return_value = run
    executor._cycle_registry.get_latest_checkpoint.return_value = None
    executor._squad_profile.resolve_snapshot.return_value = (PROFILE, "sha")
    executor._load_plan_for_run = AsyncMock(return_value=None)
    executor._load_contract_for_run = AsyncMock(return_value=None)
    state = RunInProgress()

    await executor._run_provisioning.prepare(
        state, cycle.cycle_id, run.run_id, "full", forwarding_overrides=None
    )

    carried = {e.task_type for e in state.plan if BLOCKED_PATHS_INPUT in e.inputs}
    assert "governance.merge_plan" in {e.task_type for e in state.plan}
    assert carried == {e.task_type for e in state.plan if e.task_type in (
        "governance.merge_plan", "development.propose_plan_tasks", "qa.propose_plan_tasks"
    )}  # fmt: skip
