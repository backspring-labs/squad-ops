"""An answered question reaches the author as a revision (#811).

The gate could ask and could not be answered: `RETURNED_FOR_REVISION` stopped the sequence
and revision needed a manual retry run. A system that asks a question and cannot act on the
reply is the rubber stamp M4 replaced, wearing a better costume.

Bug classes guarded:

- the reviewer's notes never reaching the author, leaving a revision run that re-authors
  blind — the fay-6 new-dice failure with an audit trail;
- **the prior manifest not reaching the author**, which is the same failure one level
  subtler: given only a note, the author re-derives the whole design, so decisions the
  reviewer accepted come back different and they must read it all again (§5c.6's
  "revise, don't re-roll");
- a manifest author being shown the *plan* re-roll appendix — a rejected plan they did not
  write, describing rules that do not apply to them;
- the revision context escaping the declared input contract, which would make it
  contamination rather than capability;
- a first-roll authoring run rendering a revision appendix it has no reason to see;
- **the revision re-earning a framing prefix its note did not invalidate** — 58 minutes to
  change one document, when research and the objective frame are upstream of the design and
  unaffected by a note about it;
- the technical design NOT answering the note, which would leave `technical_design.md`
  describing an interface the revised manifest no longer has;
- a revision failing closed when its boundary is unresolvable. Replay fails closed because it
  would otherwise claim a saved prefix it never earned; a revision claims nothing, so the
  full re-run is simply the slower correct answer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.planning import DevelopmentAuthorManifestHandler
from squadops.cycles.manifest_authoring import AUTHORING_INPUT_CONTRACT
from squadops.cycles.task_plan import inject_contract_inputs  # noqa: F401  (import guard)

pytestmark = [pytest.mark.domain_capabilities]

_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "authored_v4"
    / "interface_manifest_roll2.yaml"
).read_text(encoding="utf-8")


def _renderer() -> Any:
    renderer = AsyncMock()

    async def _render(template_id: str, variables: dict[str, Any]):
        rendered = MagicMock()
        rendered.content = f"[{template_id}] {variables}"
        rendered.template_id = template_id
        rendered.template_version = "1"
        rendered.render_hash = "cafe"
        return rendered

    renderer.render.side_effect = _render
    return renderer


async def _section(inputs: dict[str, Any]) -> tuple[str, Any]:
    handler = DevelopmentAuthorManifestHandler()
    renderer = _renderer()
    section = await handler._revision_context_section(renderer, inputs)
    return section, renderer


async def test_the_reviewers_notes_reach_the_author():
    section, renderer = await _section(
        {"rejection_reasons": ["drop the pagination assumption and ask instead"]}
    )

    assert "drop the pagination assumption" in section
    template_ids = [c.args[0] for c in renderer.render.call_args_list]
    assert template_ids == ["request.manifest_revision_request_appendix"]


async def test_the_design_being_revised_is_shown_to_the_author():
    """The difference between a revision and a re-roll. Without the prior manifest the
    author re-derives everything, so decisions the reviewer accepted come back changed."""
    section, renderer = await _section(
        {"rejection_reasons": ["resolve the expansion question"], "prior_manifest_yaml": _MANIFEST}
    )

    variables = renderer.render.call_args_list[0].args[1]
    assert "prior_manifest" in variables
    assert "kind: interface_manifest" in variables["prior_manifest"]
    assert "expansion-gating" in variables["prior_manifest"], (
        "the author must see the unresolved decision the reviewer is answering"
    )


async def test_notes_without_a_prior_manifest_still_revise():
    """A seeded cycle, or a manifest that failed to load, still gets the reviewer's words —
    degraded, not silent."""
    section, renderer = await _section({"rejection_reasons": ["narrow the scope"]})

    assert "prior_manifest" not in renderer.render.call_args_list[0].args[1]
    assert "narrow the scope" in section


async def test_a_first_roll_renders_no_revision_appendix():
    """Nothing was returned, so there is nothing to revise — a first-roll prompt must be
    byte-identical to one from before this existed."""
    section, renderer = await _section({})

    assert section == ""
    renderer.render.assert_not_awaited()


async def test_the_manifest_author_never_sees_the_plan_reroll_appendix():
    """The inherited planning-base version renders `request.plan_reroll_rejection_appendix`,
    which shows a rejected *plan* — a document this author did not write, under rules that do
    not apply to it."""
    _, renderer = await _section({"rejection_reasons": ["revise"]})

    assert "request.plan_reroll_rejection_appendix" not in [
        c.args[0] for c in renderer.render.call_args_list
    ]


def test_the_revision_context_is_inside_the_declared_input_contract():
    """§5c.1: an undeclared input is contamination by definition. The prior manifest is
    in-cycle — this cycle's own prior output — so it belongs in the contract, declared."""
    assert "prior_manifest_yaml" in AUTHORING_INPUT_CONTRACT
    assert "rejection_reasons" in AUTHORING_INPUT_CONTRACT


def test_the_injector_threads_the_prior_manifest_onto_the_envelope():
    """The executor puts it on the forwarding rail; the composer has to carry it to the
    authoring task or the appendix renders without it."""
    from squadops.capabilities.context_assembly import get_context_contract
    from squadops.cycles.task_plan import _inject_rejection_context

    assert get_context_contract("development.author_manifest").plan_rejection_context

    inputs: dict[str, Any] = {}
    _inject_rejection_context(
        inputs,
        {"rejection_reasons": ["revise"], "prior_manifest_yaml": _MANIFEST},
        "development.author_manifest",
    )

    assert inputs["rejection_reasons"] == ["revise"]
    assert inputs["prior_manifest_yaml"] == _MANIFEST


def test_a_task_type_outside_the_registry_gets_no_revision_context():
    """Who receives rejection context is the registry's declaration (#663 S3), not the
    injector's opinion — the merger is deliberately excluded."""
    from squadops.cycles.task_plan import _inject_rejection_context

    inputs: dict[str, Any] = {}
    _inject_rejection_context(
        inputs,
        {"rejection_reasons": ["revise"], "prior_manifest_yaml": _MANIFEST},
        "governance.merge_plan",
    )

    assert inputs == {}


# --------------------------------------------------------------------------- #
# The replay half: restore the prefix a revision does not invalidate
# --------------------------------------------------------------------------- #


def _checkpoint(index: int, task_ids: tuple[str, ...]) -> Any:
    from datetime import UTC, datetime

    from squadops.cycles.checkpoint import RunCheckpoint

    return RunCheckpoint(
        run_id="run_source0001",
        checkpoint_index=index,
        completed_task_ids=task_ids,
        prior_outputs={"data": {"summary": "research"}},
        artifact_refs=(),
        plan_delta_refs=(),
        created_at=datetime(2026, 8, 9, tzinfo=UTC),
    )


def _executor_with_checkpoints(checkpoints: list[Any]) -> Any:
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    executor = DispatchedFlowExecutor(artifact_vault=AsyncMock())
    executor._cycle_registry = AsyncMock()
    executor._cycle_registry.list_checkpoints.return_value = checkpoints
    return executor


def _cycle(**overrides: Any) -> Any:
    cycle = MagicMock()
    cycle.execution_overrides = dict(overrides)
    return cycle


async def test_the_revision_restores_the_prefix_before_the_design():
    """Research and the objective frame are upstream of the design, so a note about the
    design cannot invalidate them. Re-earning them costs ~20 of the 58 minutes for nothing."""
    executor = _executor_with_checkpoints(
        [
            _checkpoint(0, ("task-run_source00-000-data.research_context",)),
            _checkpoint(
                1,
                (
                    "task-run_source00-000-data.research_context",
                    "task-run_source00-001-strategy.frame_objective",
                ),
            ),
        ]
    )

    restored = await executor._resolve_revision_checkpoint(
        _cycle(framing_revision_source="run_source0001"), "run_target0002"
    )

    assert restored is not None
    assert len(restored.completed_task_ids) == 2
    assert all(t.startswith("task-run_target00-") for t in restored.completed_task_ids), (
        "ids must be rebound into the target run's namespace or suppression matches nothing"
    )


async def test_a_checkpoint_that_already_did_the_design_is_not_restorable():
    """The design must re-run — it is the first thing a revision invalidates. Restoring past
    it would skip the stage that answers the note."""
    executor = _executor_with_checkpoints(
        [
            _checkpoint(0, ("task-run_source00-000-data.research_context",)),
            _checkpoint(
                2,
                (
                    "task-run_source00-000-data.research_context",
                    "task-run_source00-002-development.design_plan",
                ),
            ),
        ]
    )

    restored = await executor._resolve_revision_checkpoint(
        _cycle(framing_revision_source="run_source0001"), "run_target0002"
    )

    assert restored is not None
    assert restored.checkpoint_index == 0, "the latest boundary BEFORE the design, not after"


@pytest.mark.parametrize(
    ("checkpoints", "why"),
    [
        ([], "no checkpoints survived pruning"),
        (
            [_checkpoint(0, ("opaque-uuid4-id-from-before-deterministic-framing-ids",))],
            "a source run predating deterministic framing ids cannot be translated",
        ),
    ],
)
async def test_an_unresolvable_boundary_degrades_instead_of_failing(checkpoints, why):
    """Replay fails closed because a replay that ran the full plan would claim a prefix it
    never earned. A revision claims nothing — the full re-run is the slower correct answer,
    and it is exactly what this did before the optimisation existed."""
    executor = _executor_with_checkpoints(checkpoints)

    restored = await executor._resolve_revision_checkpoint(
        _cycle(framing_revision_source="run_source0001"), "run_target0002"
    )

    assert restored is None, why


async def test_a_normal_run_resolves_no_revision_checkpoint():
    """Every framing run passes through this seam; only a revision names a source."""
    executor = _executor_with_checkpoints([_checkpoint(0, ("task-run_source00-000-x",))])

    assert await executor._resolve_revision_checkpoint(_cycle(), "run_target0002") is None


async def test_framing_task_ids_are_deterministic_so_a_checkpoint_can_translate():
    """The enabling change. `translate_checkpoint_for_replay` rebinds a run prefix and RAISES
    on anything else, so framing's old `uuid4().hex` ids could never be replayed onto a new
    run — which is what made a revision cost a full re-execution."""
    from datetime import UTC, datetime

    from squadops.cycles.models import (
        AgentProfileEntry,
        Cycle,
        Run,
        SquadProfile,
        TaskFlowPolicy,
    )
    from squadops.cycles.task_plan import generate_task_plan

    now = datetime(2026, 8, 9, tzinfo=UTC)
    profile = SquadProfile(
        profile_id="full",
        name="f",
        description="d",
        version=1,
        agents=tuple(
            AgentProfileEntry(agent_id=a, role=r, model="m", enabled=True)
            for a, r in (
                ("nat", "strat"),
                ("neo", "dev"),
                ("eve", "qa"),
                ("d", "data"),
                ("max", "lead"),
            )
        ),
        created_at=now,
    )
    cycle = Cycle(
        cycle_id="cyc_1",
        project_id="p",
        created_at=now,
        created_by="s",
        prd_ref="prd",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:a",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={},
        execution_overrides={},
    )
    run = Run(
        run_id="run_abcdef123456",
        cycle_id="cyc_1",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="h",
        workload_type="framing",
    )

    envelopes = generate_task_plan(cycle, run, profile)

    assert envelopes, "framing must produce a plan"
    for env in envelopes:
        assert env.task_id.startswith("task-run_abcdef12-"), env.task_id
        assert env.task_id.endswith(env.task_type), env.task_id
    assert len({e.task_id for e in envelopes}) == len(envelopes), "ids stay unique within a run"
