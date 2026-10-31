"""#2796, wired: the plan gate of a repository-backed product's increment, read by the tier through
``WorkloadGate._plan_review_tier``, the call a live cycle's plan gate makes.

Bug caught: the tier escalating every product plan gate on ``no_open_question`` because a product has
no interface manifest (the 2.6 spike's three, ``cmp_76242b27df5b``), so an unattended product
Campaign needed a person at each plan gate.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from squadops.campaigns.models import PlanGate
from squadops.campaigns.plan_review_tier import TierCondition
from squadops.execution import workload_gate
from squadops.execution.workload_gate import WorkloadGate

pytestmark = [pytest.mark.domain_orchestration]

_PLAN = """version: 1
project_id: prj_x
cycle_id: cyc_inc
prd_hash: h
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: search
    description: add the q filter
    expected_artifacts: [backend/routes.py]
    acceptance_criteria: []
    depends_on: []
"""


async def _async(value):
    return value


def _gate(*, change_request) -> WorkloadGate:
    campaign = SimpleNamespace(
        policy=SimpleNamespace(plan_gate=PlanGate.TIER),
        objective=SimpleNamespace(allowed_scope=("backend/**", "tests/**")),
        project_id="prj_x",
    )
    executor = SimpleNamespace(
        _campaign_registry=SimpleNamespace(get_campaign=lambda _cid: _async(campaign)),
        _cycle_registry=SimpleNamespace(list_runs=lambda *_a, **_k: _async([])),
        _run_manifest_content=lambda *_a: _async(None),
        _load_run_plan_yaml=lambda *_a: _async(_PLAN),
        _artifact_vault=object(),
    )
    gate = WorkloadGate(executor=lambda: executor)
    gate._change_request = change_request
    return gate


@pytest.mark.parametrize(
    ("change_request", "held"),
    [("change_request.yaml", True), (None, False)],
    ids=["ruled-change-request", "none-on-record"],
)
async def test_a_product_increments_plan_gate_reads_its_ruled_change_request(
    monkeypatch, change_request, held
):
    """The scope and the framing are the tier's unit tests' (``test_plan_review_tier.py``); this one
    enters where the live gate does and reads what reaches the question check."""

    async def approved(_vault, _cycle):
        return change_request

    monkeypatch.setattr(workload_gate, "approved_change_request", approved)
    monkeypatch.setattr(
        workload_gate,
        "load_stored_change_request",
        lambda _document: SimpleNamespace(criterion_files=[]),
    )
    monkeypatch.setattr(
        workload_gate,
        "increment_basis",
        lambda _config: SimpleNamespace(has_manifest=False),
    )
    cycle = SimpleNamespace(
        cycle_id="cyc_inc",
        campaign_id="cmp_x",
        kind="increment",
        resolved_config=lambda: {},
    )

    reading = await _gate(change_request=change_request)._plan_review_tier(
        cycle, SimpleNamespace(run_id="run_f"), cycle, "run_f"
    )

    [questions] = [
        c for c in reading.verdict.checks if c.condition is TierCondition.NO_OPEN_QUESTION
    ]
    assert questions.held is held
    assert ("approved change request" in questions.reading) is held
