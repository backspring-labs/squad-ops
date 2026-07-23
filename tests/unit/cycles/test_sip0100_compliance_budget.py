"""SIP-0100 Task 3.4a — bounded contract-compliance circuit-breaker."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
from adapters.cycles.execution_errors import _ExecutionError
from squadops.cycles.scaffold_integrity_evidence import ScaffoldIntegrityEvidence
from squadops.cycles.task_outcome import ContractComplianceViolation


def _ev(code: str) -> ScaffoldIntegrityEvidence:
    return ScaffoldIntegrityEvidence(
        producer_task_id="t1",
        producer_task_type="qa.test",
        stage="artifact_storage",
        kind="attempted_emission",
        violation_code=code,
        attempted_path="backend/routes.py",
        normalized_path="backend/routes.py",
        bound_run_id="r",
        bound_attempt_id="a",
        manifest_hash="m",
        expected_sha256=None,
        attempted_sha256="x",
        disposition="dropped",
        siblings_retained=0,
    )


def _cycle(bound: int = 3) -> SimpleNamespace:
    return SimpleNamespace(applied_defaults={"contract_compliance_attempts": bound})


def _env() -> SimpleNamespace:
    return SimpleNamespace(task_id="t1", task_type="qa.test")


def _call(evidence: list, counter: dict, cycle: SimpleNamespace | None = None) -> None:
    DispatchedFlowExecutor._enforce_compliance_budget(
        object(), evidence, cycle or _cycle(), _env(), counter
    )


_UNAUTH = ContractComplianceViolation.UNAUTHORIZED_SLOT_EMISSION
_FROZEN = ContractComplianceViolation.FROZEN_PATH_EMISSION


def test_unauthorized_under_bound_increments_without_raising():
    counter = {"n": 0}
    _call([_ev(_UNAUTH)], counter, _cycle(bound=3))
    assert counter["n"] == 1  # counted, but 1 <= 3 so no termination


def test_over_bound_raises_contract_compliance():
    counter = {"n": 3}
    with pytest.raises(_ExecutionError) as exc:
        _call([_ev(_UNAUTH)], counter, _cycle(bound=3))
    assert counter["n"] == 4
    # The termination is classified CONTRACT_COMPLIANCE and names the budget.
    assert "contract_compliance" in str(exc.value)
    assert "(3)" in str(exc.value)


def test_frozen_restores_are_not_counted():
    """Frozen re-emission is the tolerated 2.4 baseline; counting it would false-terminate normal
    runs. Three frozen restores must not move the compliance counter or trip a bound of 1."""
    counter = {"n": 0}
    _call([_ev(_FROZEN), _ev(_FROZEN), _ev(_FROZEN)], counter, _cycle(bound=1))
    assert counter["n"] == 0  # frozen never counts


def test_multiple_unauthorized_in_one_response_count_per_file():
    counter = {"n": 0}
    _call([_ev(_UNAUTH), _ev(_UNAUTH)], counter, _cycle(bound=3))
    assert counter["n"] == 2  # two cross-slot writes = two increments


def test_no_unauthorized_leaves_counter_untouched():
    counter = {"n": 2}
    _call([], counter, _cycle(bound=3))
    _call([_ev(_FROZEN)], counter, _cycle(bound=3))
    assert counter["n"] == 2  # neither empty evidence nor a frozen restore changes it


def test_bound_is_configurable_zero_terminates_on_first():
    """A profile can set contract_compliance_attempts=0 to forbid any cross-slot write outright."""
    counter = {"n": 0}
    with pytest.raises(_ExecutionError):
        _call([_ev(_UNAUTH)], counter, _cycle(bound=0))


def test_default_bound_applies_when_unset():
    """Absent the key, the default (3) is used — a fourth cross-slot write terminates."""
    counter = {"n": 3}
    cycle = SimpleNamespace(applied_defaults={})  # no contract_compliance_attempts
    with pytest.raises(_ExecutionError):
        _call([_ev(_UNAUTH)], counter, cycle)
