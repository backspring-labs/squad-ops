"""The brownfield reference scenario (SIP-0109 §11a; #1804): its seeds, its pins, and that a
reference cycle outside any campaign is framed and built as an increment."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from squadops.campaigns.change_request import apply_manifest_delta, load_stored_change_request
from squadops.campaigns.reference import (
    REFERENCE_PROPOSAL_ID,
    ReferenceDrift,
    check_pins,
    reference_increment,
    reference_proposal_block,
)

ROOT = Path(__file__).resolve().parents[3]
SCENARIO = yaml.safe_load(
    (ROOT / "examples" / "03_group_run" / "reference_scenario.yaml").read_text()
)
BASELINE = (ROOT / SCENARIO["baseline"]["manifest"]).read_text()
AUTHORED = yaml.safe_load((ROOT / SCENARIO["change_request"]).read_text())
TREE = SCENARIO["pins"]["baseline_tree"]


def _seeds(authored=AUTHORED):
    return reference_increment(
        authored,
        baseline_manifest=BASELINE,
        baseline_tree=TREE,
        stack=SCENARIO["stack"],
        allowed_scope=tuple(SCENARIO["allowed_scope"]),
    )


def test_the_seeds_are_what_an_approved_increment_gate_stores_and_match_their_pins():
    """Bugs caught: the reference request built through a path the campaign's gate does not use
    (so the scenario measures something no increment does), or its seeds drifting silently
    between runs — the yardstick moving under the measurement."""
    seeds = _seeds()

    request = load_stored_change_request(seeds.change_request)  # the stored hash holds
    assert (request.proposal_id, request.version, request.baseline_tree) == (
        REFERENCE_PROPOSAL_ID,
        1,
        TREE,
    )
    assert seeds.candidate_manifest == apply_manifest_delta(BASELINE, request.manifest_delta)
    assert b"criteria" in seeds.contract
    check_pins(
        {**seeds.pins, **{k: SCENARIO["pins"][k] for k in SCENARIO["pins"] if k not in seeds.pins}},
        SCENARIO["pins"],
    )


def test_a_request_the_rails_refuse_is_refused_naming_every_refusal():
    authored = {**AUTHORED, "footprint": ["backend/**"]}  # authored a derived field
    with pytest.raises(ValueError, match="authored_derived_field"):
        _seeds(authored)


@pytest.mark.parametrize(
    ("actual", "message"),
    [
        ({"baseline_tree": "other"}, "baseline_tree other != pinned"),
        ({"baseline_tree": "pinned", "extra": "x"}, "unpinned: extra"),
    ],
    ids=["drifted", "unpinned"],
)
def test_an_input_off_its_pin_is_refused(actual, message):
    """Bug caught: a different baseline or request launched as the reference — a different
    measurement reported as the yardstick."""
    with pytest.raises(ReferenceDrift, match=message):
        check_pins(actual, {"baseline_tree": "pinned"})


def test_a_reference_cycle_outside_any_campaign_is_framed_as_an_increment():
    """Wiring, entered at ``generate_task_plan`` for the cycle the launcher creates: no campaign,
    no cycle kind, the block and the seeds. Bug caught: the reference cycle framed as a new
    application — the scenario measuring greenfield framing."""
    from unittest.mock import MagicMock

    from squadops.cycles.models import (
        AgentProfileEntry,
        Cycle,
        Run,
        SquadProfile,
        TaskFlowPolicy,
    )
    from squadops.cycles.task_plan import generate_task_plan

    now = datetime(2026, 10, 2, tzinfo=UTC)
    seeds = _seeds()
    cycle = Cycle(
        cycle_id="cyc_ref",
        project_id="group_run",
        created_at=now,
        created_by="operator",
        prd_ref="the PRD",
        squad_profile_id="full",
        squad_profile_snapshot_ref="x",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"build_profile": "fullstack_fastapi_react", "implementation_plan": True},
        execution_overrides={
            "campaign_proposal": reference_proposal_block(
                baseline_tree=TREE,
                accepted_cycle_id=SCENARIO["baseline"]["cycle_id"],
                baseline_manifest=BASELINE,
                objective=SCENARIO["objective"],
            ),
            "plan_artifact_refs": ["art_candidate", "art_cr"],
            "contract_ref": "art_contract",
        },
    )
    profile = SquadProfile(
        profile_id="full",
        name="full",
        description="",
        version=1,
        created_at=now,
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
    contract = MagicMock()
    contract.criteria_index_lines.return_value = ["- K1"]
    contract.behavioral.probes = ()

    plan = generate_task_plan(
        cycle,
        Run("run_f", "cyc_ref", 1, "running", "system", "cfg", workload_type="framing"),
        profile,
        contract=contract,
        change_request=seeds.change_request,
    )

    assert [e.task_type for e in plan][0] == "development.design_plan"
    assert plan[0].inputs["increment_change_request"] == seeds.change_request
