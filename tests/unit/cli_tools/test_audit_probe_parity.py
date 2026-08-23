"""The oracle and the in-cycle runner judge a contract the same way (#1079).

`audit_delivered_app` decides whether a delivered app actually works, independently
of the run's own verdict. It used to re-implement the probe expectation block inline
and carried two of the three kinds — no `json_has` branch — so of the two judges of
one contract, the one whose verdict carried the most weight was the more permissive.

Nothing had caught it because `json_has` has no producer yet (the other half of
#1079). These tests exist so it cannot regress in the window between a producer
landing and someone noticing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from squadops.capabilities.handlers.probe_runner import evaluate_expectations

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "audit_delivered_app.py"
_spec = importlib.util.spec_from_file_location("audit_delivered_app_parity", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["audit_delivered_app_parity"] = _mod
_spec.loader.exec_module(_mod)


def test_the_oracle_uses_the_runners_judgment_not_its_own():
    """One function, not two implementations that agree today.

    Asserting the identity rather than comparing behaviours is the point: matching
    outputs on sampled inputs is what the previous arrangement had, right up until
    a third expectation kind was added to one side.
    """
    assert _mod.evaluate_expectations is evaluate_expectations


class TestExpectationJudgment:
    def test_a_fully_matching_response_passes(self):
        expect = {"status": 200, "json_has": ["id", "participants"]}
        assert evaluate_expectations(expect, 200, {"id": 1, "participants": []}) is None

    def test_missing_key_is_named(self):
        failure = evaluate_expectations({"json_has": ["id", "participants"]}, 200, {"id": 1})
        assert failure == "response missing key(s): ['participants']"

    def test_list_response_requires_the_key_in_every_element(self):
        expect = {"json_has": ["id"]}
        assert evaluate_expectations(expect, 200, [{"id": 1}, {"id": 2}]) is None
        assert evaluate_expectations(expect, 200, [{"id": 1}, {"x": 2}]) == (
            "response missing key(s): ['id']"
        )

    def test_empty_collection_satisfies_json_has(self):
        """An empty list has no element that lacks the key.

        Same boundary #1029's floor settled: absence of data is not evidence of a
        shape defect, and a probe that fails on an empty collection would fail every
        list endpoint before anything is created.
        """
        assert evaluate_expectations({"json_has": ["id"]}, 200, []) is None

    def test_non_json_body_fails_when_a_shape_is_expected(self):
        assert evaluate_expectations({"json_has": ["id"]}, 200, None) == "response body is not JSON"

    def test_status_is_judged_before_shape(self):
        """A 500 should report the status, not a list of keys its error body lacks."""
        failure = evaluate_expectations({"status": 201, "json_has": ["id"]}, 500, {"error": {}})
        assert failure == "status 500 != expected 201"

    @pytest.mark.parametrize(
        "payload,expected",
        [
            ({"error": {"code": "run_not_found"}}, None),
            ({"error": {"code": "other"}}, "error_code 'other' != expected 'run_not_found'"),
            ({}, "error_code None != expected 'run_not_found'"),
        ],
        ids=["match", "mismatch", "absent"],
    )
    def test_error_code_reads_the_pinned_envelope(self, payload, expected):
        assert evaluate_expectations({"error_code": "run_not_found"}, 404, payload) == expected

    def test_an_empty_expect_block_passes_anything(self):
        assert evaluate_expectations({}, 500, None) is None
