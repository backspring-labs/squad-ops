"""An increment's producers may write only the fill slots its change touches (SIP-0109 §7.3;
#1705 step c2).

The plan gate refuses a task outside the footprint (#1843). This is the net under it, at the
ownership seam every emission and every repair passes: a dev or builder write to an accepted
slot the change does not touch is another producer's surface, dropped with evidence, and the
accepted file stays.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from squadops.campaigns.change_request import (
    ProposalContext,
    apply_manifest_delta,
    validate_proposal,
)
from squadops.capabilities.scaffold import InterfaceManifest

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"
BASELINE = (_FIXTURES / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml").read_text()
CANDIDATE = InterfaceManifest.from_yaml(
    apply_manifest_delta(
        BASELINE,
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
        ).change_request.manifest_delta,
    )
)
INCREMENT = {"campaign_proposal": {"proposal_id": "prop_cap", "baseline_manifest": BASELINE}}
TOUCHED = "frontend/src/views/RunDetailView.jsx"  # in the reference change's footprint
ACCEPTED = "frontend/src/views/RunListView.jsx"  # a fill slot the change does not touch


def _enforce(config: dict, task_type: str) -> tuple[list[str], list]:
    """Entered where a bound run builds its record and stores an emission (the executor's own
    seam pair), as a repair's emission reaches it too (``correction_runner``)."""
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    record = DispatchedFlowExecutor._build_bound_record_for_run(
        object(), CANDIDATE, "run_i", config
    )
    envelope = MagicMock(task_type=task_type, task_id="task-1")
    artifacts = [
        {
            "name": path,
            "content": "export default function View() { return null }\n",
            "type": "source",
        }
        for path in (TOUCHED, ACCEPTED)
    ]
    kept, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(), artifacts, record, envelope
    )
    return [a["name"] for a in kept], evidence


@pytest.mark.parametrize("task_type", ["development.develop", "builder.assemble"])
def test_an_increments_producer_writes_only_the_slots_its_change_touches(task_type):
    """Bug caught: an increment's dev or builder rewriting an accepted view the approved
    change never touched — accepted work replaced, unruled, past the plan gate."""
    kept, evidence = _enforce(INCREMENT, task_type)

    assert kept == [TOUCHED]
    [dropped] = evidence
    assert (dropped.attempted_path, dropped.violation_code) == (
        ACCEPTED,
        "unauthorized_slot_emission",
    )


def test_an_ordinary_cycles_producer_keeps_every_fill_slot():
    kept, evidence = _enforce({}, "development.develop")

    assert (kept, evidence) == ([TOUCHED, ACCEPTED], [])


def test_the_footprint_survives_the_records_round_trip():
    """Bug caught: a stored and reloaded record silently widening the grant to every slot."""
    from squadops.campaigns.increment_tree import increment_footprint
    from squadops.cycles.bound_scaffold_record import BoundScaffoldRecord, build_bound_record

    record = build_bound_record(
        CANDIDATE,
        run_id="r",
        attempt_id="r",
        created_at="",
        increment_footprint=increment_footprint(INCREMENT, CANDIDATE),
    )

    reloaded = BoundScaffoldRecord.from_dict(record.to_dict())

    assert TOUCHED in reloaded.increment_footprint
    assert ACCEPTED not in reloaded.increment_footprint
    assert (
        BoundScaffoldRecord.from_dict(
            {k: v for k, v in record.to_dict().items() if k != "increment_footprint"}
        ).increment_footprint
        == ()
    )  # a record bound before the field: no narrowing
