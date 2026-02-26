"""
Tests for SIP-0064 lifecycle state machine, status derivation, and hash computation.
"""

from datetime import UTC, datetime

import pytest

from squadops.cycles.lifecycle import (
    TERMINAL_STATES,
    compute_config_hash,
    compute_profile_snapshot_hash,
    derive_cycle_status,
    validate_run_transition,
)
from squadops.cycles.models import (
    CycleStatus,
    IllegalStateTransitionError,
    Run,
    RunStatus,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _make_run(
    run_number: int = 1,
    status: str = "queued",
    run_id: str | None = None,
) -> Run:
    return Run(
        run_id=run_id or f"run_{run_number:03d}",
        cycle_id="cyc_001",
        run_number=run_number,
        status=status,
        initiated_by="api",
        resolved_config_hash="hash",
    )


# =============================================================================
# validate_run_transition tests
# =============================================================================


class TestValidateRunTransition:
    """Legal/illegal transition tests per SIP-0064 §6.2."""

    # Legal transitions
    def test_queued_to_running(self):
        validate_run_transition(RunStatus.QUEUED, RunStatus.RUNNING)

    def test_running_to_completed(self):
        validate_run_transition(RunStatus.RUNNING, RunStatus.COMPLETED)

    def test_running_to_failed(self):
        validate_run_transition(RunStatus.RUNNING, RunStatus.FAILED)

    def test_running_to_paused(self):
        validate_run_transition(RunStatus.RUNNING, RunStatus.PAUSED)

    def test_paused_to_running(self):
        validate_run_transition(RunStatus.PAUSED, RunStatus.RUNNING)

    def test_queued_to_cancelled(self):
        validate_run_transition(RunStatus.QUEUED, RunStatus.CANCELLED)

    def test_running_to_cancelled(self):
        validate_run_transition(RunStatus.RUNNING, RunStatus.CANCELLED)

    def test_paused_to_cancelled(self):
        validate_run_transition(RunStatus.PAUSED, RunStatus.CANCELLED)

    # Illegal transitions — terminal states have no outgoing
    def test_completed_to_running_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.COMPLETED, RunStatus.RUNNING)

    def test_completed_to_failed_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.COMPLETED, RunStatus.FAILED)

    def test_completed_to_cancelled_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.COMPLETED, RunStatus.CANCELLED)

    def test_failed_to_running_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.FAILED, RunStatus.RUNNING)

    def test_failed_to_completed_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.FAILED, RunStatus.COMPLETED)

    def test_failed_to_cancelled_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.FAILED, RunStatus.CANCELLED)

    def test_cancelled_to_running_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.CANCELLED, RunStatus.RUNNING)

    def test_cancelled_to_queued_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.CANCELLED, RunStatus.QUEUED)

    # Illegal — skip states
    def test_queued_to_completed_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.QUEUED, RunStatus.COMPLETED)

    def test_queued_to_failed_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.QUEUED, RunStatus.FAILED)

    def test_queued_to_paused_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.QUEUED, RunStatus.PAUSED)

    def test_paused_to_completed_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.PAUSED, RunStatus.COMPLETED)

    def test_paused_to_failed_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.PAUSED, RunStatus.FAILED)

    # Self-transitions are illegal
    def test_queued_to_queued_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.QUEUED, RunStatus.QUEUED)

    def test_running_to_running_illegal(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.RUNNING, RunStatus.RUNNING)

    # Terminal states constant
    def test_terminal_states(self):
        assert TERMINAL_STATES == frozenset(
            {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
        )

    def test_all_terminal_states_reject_all_targets(self):
        for terminal in TERMINAL_STATES:
            for target in RunStatus:
                with pytest.raises(IllegalStateTransitionError):
                    validate_run_transition(terminal, target)


# =============================================================================
# derive_cycle_status tests
# =============================================================================


class TestDeriveCycleStatus:
    def test_no_runs(self):
        assert derive_cycle_status([], cycle_cancelled=False) == CycleStatus.CREATED

    def test_queued_run(self):
        runs = [_make_run(status="queued")]
        assert derive_cycle_status(runs, cycle_cancelled=False) == CycleStatus.ACTIVE

    def test_running_run(self):
        runs = [_make_run(status="running")]
        assert derive_cycle_status(runs, cycle_cancelled=False) == CycleStatus.ACTIVE

    def test_paused_run(self):
        runs = [_make_run(status="paused")]
        assert derive_cycle_status(runs, cycle_cancelled=False) == CycleStatus.ACTIVE

    def test_completed_run(self):
        runs = [_make_run(status="completed")]
        assert derive_cycle_status(runs, cycle_cancelled=False) == CycleStatus.COMPLETED

    def test_failed_run(self):
        runs = [_make_run(status="failed")]
        assert derive_cycle_status(runs, cycle_cancelled=False) == CycleStatus.FAILED

    def test_cycle_cancelled(self):
        runs = [_make_run(status="running")]
        assert derive_cycle_status(runs, cycle_cancelled=True) == CycleStatus.CANCELLED

    def test_cycle_cancelled_no_runs(self):
        assert derive_cycle_status([], cycle_cancelled=True) == CycleStatus.CANCELLED

    def test_all_runs_cancelled_cycle_not_cancelled(self):
        runs = [
            _make_run(run_number=1, status="cancelled"),
            _make_run(run_number=2, status="cancelled"),
        ]
        assert derive_cycle_status(runs, cycle_cancelled=False) == CycleStatus.CREATED

    def test_cancelled_run_does_not_mask_prior_completed(self):
        runs = [
            _make_run(run_number=1, status="completed"),
            _make_run(run_number=2, status="cancelled"),
        ]
        assert derive_cycle_status(runs, cycle_cancelled=False) == CycleStatus.COMPLETED

    def test_cancelled_run_does_not_mask_prior_failed(self):
        runs = [
            _make_run(run_number=1, status="failed"),
            _make_run(run_number=2, status="cancelled"),
        ]
        assert derive_cycle_status(runs, cycle_cancelled=False) == CycleStatus.FAILED

    def test_latest_non_cancelled_by_run_number(self):
        runs = [
            _make_run(run_number=1, status="completed"),
            _make_run(run_number=2, status="running"),
            _make_run(run_number=3, status="cancelled"),
        ]
        assert derive_cycle_status(runs, cycle_cancelled=False) == CycleStatus.ACTIVE

    def test_single_cancelled_run_cycle_cancelled(self):
        runs = [_make_run(status="cancelled")]
        assert derive_cycle_status(runs, cycle_cancelled=True) == CycleStatus.CANCELLED


# =============================================================================
# compute_config_hash tests
# =============================================================================


class TestComputeConfigHash:
    def test_deterministic(self):
        h1 = compute_config_hash({"a": 1}, {"b": 2})
        h2 = compute_config_hash({"a": 1}, {"b": 2})
        assert h1 == h2

    def test_changes_with_defaults(self):
        h1 = compute_config_hash({"a": 1}, {"b": 2})
        h2 = compute_config_hash({"a": 999}, {"b": 2})
        assert h1 != h2

    def test_changes_with_overrides(self):
        h1 = compute_config_hash({"a": 1}, {"b": 2})
        h2 = compute_config_hash({"a": 1}, {"b": 999})
        assert h1 != h2

    def test_override_takes_precedence(self):
        h1 = compute_config_hash({"key": "default"}, {"key": "override"})
        h2 = compute_config_hash({}, {"key": "override"})
        assert h1 == h2

    def test_empty_inputs(self):
        h = compute_config_hash({}, {})
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_order_independent_keys(self):
        h1 = compute_config_hash({"a": 1, "b": 2}, {})
        h2 = compute_config_hash({"b": 2, "a": 1}, {})
        assert h1 == h2


# =============================================================================
# compute_profile_snapshot_hash tests
# =============================================================================


class TestComputeProfileSnapshotHash:
    def test_deterministic(self, sample_profile):
        h1 = compute_profile_snapshot_hash(sample_profile)
        h2 = compute_profile_snapshot_hash(sample_profile)
        assert h1 == h2

    def test_changes_with_agent_model(self, sample_profile):
        import dataclasses

        h1 = compute_profile_snapshot_hash(sample_profile)
        # Change first agent's model
        new_agents = list(sample_profile.agents)
        new_agents[0] = dataclasses.replace(new_agents[0], model="gpt-5")
        modified = dataclasses.replace(sample_profile, agents=tuple(new_agents))
        h2 = compute_profile_snapshot_hash(modified)
        assert h1 != h2

    def test_changes_with_agent_enabled(self, sample_profile):
        import dataclasses

        h1 = compute_profile_snapshot_hash(sample_profile)
        new_agents = list(sample_profile.agents)
        new_agents[0] = dataclasses.replace(new_agents[0], enabled=False)
        modified = dataclasses.replace(sample_profile, agents=tuple(new_agents))
        h2 = compute_profile_snapshot_hash(modified)
        assert h1 != h2

    def test_changes_with_version(self, sample_profile):
        import dataclasses

        h1 = compute_profile_snapshot_hash(sample_profile)
        modified = dataclasses.replace(sample_profile, version=2)
        h2 = compute_profile_snapshot_hash(modified)
        assert h1 != h2

    def test_hex_length(self, sample_profile):
        h = compute_profile_snapshot_hash(sample_profile)
        assert len(h) == 64  # SHA-256 hex
