"""The repeat report (SIP-0110 §0.4, D14): what recurs across independent units, with a retry
merged into the cycle it retries and a proposal's versions counted as one proposal."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from squadops.memory.observations import (
    UNCLASSIFIED,
    Classification,
    Observation,
    ObservationSource,
)
from squadops.memory.repeats import repeated_signatures, root_of

pytestmark = [pytest.mark.domain_memory]

T0 = datetime(2026, 10, 8, tzinfo=UTC)


def _round(cycle_id: str, shape: str | None = "unresolved_import", n: int = 0) -> Observation:
    return Observation(
        source=ObservationSource.CORRECTION_ROUND,
        source_id=f"correction_round:{cycle_id}:{n}",
        project_id="group_run",
        observed_at=T0,
        classification=Classification("attribution", ("verification_artifact_failure",)),
        cycle_id=cycle_id,
        run_id=f"run_{cycle_id}",
        evidence={"failure_shapes": [{"check": "tests_pass", "runner": "vitest", "shape": shape}]},
    )


def _ruling(proposal: str, version: int, cls: str = "criteria_not_checkable") -> Observation:
    return Observation(
        source=ObservationSource.PROPOSAL_RULING,
        source_id=f"proposal_ruling:cmp_1:{proposal}:{version}",
        project_id="group_run",
        observed_at=T0,
        classification=Classification("proposal_classification", (cls,)),
        campaign_id="cmp_1",
        run_id=f"run_{proposal}_{version}",
        evidence={"proposal_id": proposal, "version": version},
    )


def test_a_shape_in_two_independent_cycles_is_a_repeated_signature():
    """Bug caught: a repeat missed, so the auditor is never pointed at a recurring mistake."""
    [row] = repeated_signatures(
        [_round("cyc_a"), _round("cyc_b"), _round("cyc_c", "element_not_found")], {}
    )

    assert (row.signature, row.independent_cycles, row.cycles) == (
        "vitest:unresolved_import",
        2,
        ("cyc_a", "cyc_b"),
    )


def test_a_retry_and_the_cycle_it_retries_count_once():
    """Bug caught: a retry, which is handed its predecessor's failure (#1692), counted as an
    independent recurrence of the same mistake."""
    assert repeated_signatures([_round("cyc_a"), _round("cyc_retry")], {"cyc_retry": "cyc_a"}) == []
    assert root_of("cyc_r2", {"cyc_r2": "cyc_r1", "cyc_r1": "cyc_a"}) == "cyc_a"
    assert root_of("cyc_x", {"cyc_x": "cyc_y", "cyc_y": "cyc_x"}) in {"cyc_x", "cyc_y"}  # no loop


def test_a_proposals_versions_are_one_proposal():
    """Bug caught: counted campaign 1's v1 and v2 read as two campaigns' recurrence. They are a
    revision, the within-unit rung (§0.11)."""
    assert repeated_signatures([_ruling("prop_1", 1), _ruling("prop_1", 2)], {}) == []
    [row] = repeated_signatures([_ruling("prop_1", 1), _ruling("prop_2", 1)], {})
    assert row.signature == "proposal_classification:criteria_not_checkable"


def test_unshaped_and_unclassified_observations_are_never_counted():
    """Bug caught: a signature invented from nothing, so two unrelated failures read as one."""
    unclassified = dataclasses.replace(
        _ruling("prop_9", 1), classification=Classification(UNCLASSIFIED, rationale="none")
    )
    observations = [_round("cyc_a", None), _round("cyc_b", None), unclassified, unclassified]

    assert repeated_signatures(observations, {}) == []
