"""Authored-manifest mode: whether the squad writes the manifest, and where (#791, M1).

Bug classes guarded:

- **the authoring stage firing in bind mode** — the seeded contract binds an exact
  manifest hash, so a re-derived manifest is unwinnable on any naming drift (#496). The
  cycle would look healthy and fail at the hash check after spending a framing workload;
- the stage firing on a stack with no expander, producing a manifest describing a
  skeleton nothing can build;
- the stage running *after* qa, which would have qa author its test strategy blind to the
  interface it is about to be held to — the whole reason §5a places it where it is;
- the seeded framing sequence changing shape, which would move the control the 1.4/1.5
  evidence was measured on;
- the step naming a role no registered handler serves, which aborts dispatch with
  "No handler for capability" *after* the run has started.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.bootstrap.handlers import get_all_handlers
from squadops.cycles.manifest_authoring import (
    AUTHOR_MANIFEST_CAPABILITY,
    AUTHOR_MANIFEST_ROLE,
    authors_interface_manifest,
)
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_plan import build_planning_steps, generate_task_plan

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_SCAFFOLDABLE = "fullstack_fastapi_react"


@pytest.fixture
def full_profile() -> SquadProfile:
    return SquadProfile(
        profile_id="full",
        name="Full Squad",
        description="All agents",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="nat", role="strat", model="m", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="m", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="m", enabled=True),
            AgentProfileEntry(agent_id="data-agent", role="data", model="m", enabled=True),
            AgentProfileEntry(agent_id="max", role="lead", model="m", enabled=True),
        ),
        created_at=NOW,
    )


def _cycle(**config) -> Cycle:
    return Cycle(
        cycle_id="cyc_001",
        project_id="group_run",
        created_at=NOW,
        created_by="system",
        prd_ref="prd_ref_123",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults=dict(config),
        execution_overrides={},
    )


def _run() -> Run:
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="config_hash_abc",
        workload_type="framing",
    )


# --------------------------------------------------------------------------- #
# The mode predicate
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("config", "expected", "why"),
    [
        ({"build_profile": _SCAFFOLDABLE}, True, "scaffoldable stack, nothing pinned"),
        (
            {"build_profile": _SCAFFOLDABLE, "contract_ref": "art_deadbeef"},
            False,
            "bind mode: the contract binds a manifest hash the squad cannot reproduce",
        ),
        ({"build_profile": "django_htmx"}, False, "no expander for this stack"),
        ({"build_profile": ""}, False, "no stack declared at all"),
        ({}, False, "config says nothing about a build"),
        (None, False, "no config"),
    ],
)
def test_authored_mode_is_derived_from_config_that_already_exists(config, expected, why):
    """Derived, never flagged — a third state (a cycle claiming authored mode over a
    seeded contract) is the one that produces an unwinnable run, and it is unreachable
    when the answer is computed from ``contract_ref`` and the stack."""
    assert authors_interface_manifest(config) is expected, why


def test_a_pinned_contract_wins_over_a_scaffoldable_stack():
    """Order matters: both conditions are true in bind mode on a scaffoldable stack, and
    reading the stack first would author a manifest against a pinned hash."""
    assert authors_interface_manifest({"build_profile": _SCAFFOLDABLE}) is True
    assert (
        authors_interface_manifest({"build_profile": _SCAFFOLDABLE, "contract_ref": "art_x"})
        is False
    )


# --------------------------------------------------------------------------- #
# Sequence placement
# --------------------------------------------------------------------------- #


def test_the_authoring_stage_sits_between_the_technical_design_and_qas_strategy():
    """§5a's placement, as an ordering assertion. After ``development.design_plan`` so the
    author holds the design it is expressing; before ``qa.define_test_strategy`` so qa
    writes its strategy against a fixed interface rather than a guess."""
    steps = [t for t, _ in build_planning_steps(None, authors_manifest=True)]

    assert steps.index("development.design_plan") < steps.index(AUTHOR_MANIFEST_CAPABILITY)
    assert steps.index(AUTHOR_MANIFEST_CAPABILITY) < steps.index("qa.define_test_strategy")


def test_seeded_mode_keeps_the_framing_sequence_it_had():
    """The control configuration must not move. Seeded framing is the referent every
    replay and regression comparison uses; a step appearing there would change what the
    1.4/1.5 numbers describe."""
    seeded = build_planning_steps(None, authors_manifest=False)

    assert AUTHOR_MANIFEST_CAPABILITY not in [t for t, _ in seeded]
    assert seeded == [
        ("data.research_context", "data"),
        ("strategy.frame_objective", "strat"),
        ("development.design_plan", "dev"),
        ("qa.define_test_strategy", "qa"),
        ("governance.prepare_plan_authoring_brief", "lead"),
        ("governance.merge_plan", "lead"),
        ("governance.review_plan", "lead"),
    ]


def test_the_stage_composes_with_the_proposer_fan_out():
    """Two independently configured insertions into one sequence. Authoring is a framing
    concern and contributors are a plan-authoring concern, so both must be able to be on
    at once without either dropping the other."""
    steps = [t for t, _ in build_planning_steps(["development", "qa"], authors_manifest=True)]

    assert steps.index(AUTHOR_MANIFEST_CAPABILITY) < steps.index(
        "governance.prepare_plan_authoring_brief"
    )
    assert "development.propose_plan_tasks" in steps
    assert "qa.propose_plan_tasks" in steps


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #


def test_a_framing_run_on_a_scaffoldable_stack_dispatches_the_author(full_profile):
    """The wiring from cycle config through to a real envelope — the seam that decides
    whether anything authors a manifest at all."""
    envelopes = generate_task_plan(_cycle(build_profile=_SCAFFOLDABLE), _run(), full_profile)

    authoring = [e for e in envelopes if e.task_type == AUTHOR_MANIFEST_CAPABILITY]
    assert len(authoring) == 1
    assert authoring[0].metadata["role"] == AUTHOR_MANIFEST_ROLE
    assert authoring[0].agent_id == "neo"


def test_a_bind_mode_framing_run_dispatches_no_author(full_profile):
    """#496 at the dispatch seam: the manifest already exists and its hash is pinned."""
    cycle = _cycle(build_profile=_SCAFFOLDABLE, contract_ref="art_deadbeef")

    envelopes = generate_task_plan(cycle, _run(), full_profile)

    assert AUTHOR_MANIFEST_CAPABILITY not in [e.task_type for e in envelopes]


def test_the_authoring_capability_has_a_handler_registered_for_its_step_role():
    """A step whose (capability, role) pair no handler serves aborts dispatch mid-run with
    "No handler for capability" — after the cycle has already spent its framing tail."""
    registered = {(handler_cls._capability_id, roles) for handler_cls, roles in get_all_handlers()}
    matches = [roles for cap, roles in registered if cap == AUTHOR_MANIFEST_CAPABILITY]

    assert matches, f"{AUTHOR_MANIFEST_CAPABILITY} has no registered handler"
    assert AUTHOR_MANIFEST_ROLE in matches[0], (
        f"the framing step dispatches {AUTHOR_MANIFEST_CAPABILITY} to "
        f"{AUTHOR_MANIFEST_ROLE!r}, but the handler is registered for {matches[0]}"
    )
