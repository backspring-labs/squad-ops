"""
Tests for SIP-0064 lifecycle state machine, status derivation, and hash computation.
"""

import dataclasses
from datetime import UTC, datetime

import pytest

from squadops.cycles.lifecycle import (
    GATE_REJECTED_STATES,
    TERMINAL_STATES,
    WorkloadStranding,
    classify_workload_stranding,
    compute_config_hash,
    compute_profile_snapshot_hash,
    derive_cycle_status,
    resolve_cycle_status,
    validate_run_transition,
)
from squadops.cycles.models import (
    CycleStatus,
    GateDecision,
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

    def test_completed_to_cancelled_legal_as_supersede(self):
        """#522 / pf-43: REVERSES the prior assertion that this was illegal.

        Inter-workload gates are decided on COMPLETED runs by design (SIP-0083 D15), so a
        framing run whose plan is auto-rejected is already terminal when its re-roll needs
        to supersede it. With no edge, the re-roll's cancel raised and killed the re-roll
        — which is why #522 passed its harness and never fired live. The edge is named
        ``supersede``; operator-facing cancel refuses terminal runs at the API boundary.
        """
        validate_run_transition(RunStatus.COMPLETED, RunStatus.CANCELLED)

    def test_failed_to_running_legal(self):
        """SIP-0079: resume_from_failed allows FAILED → RUNNING."""
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

    def test_cancelled_rejects_all_targets(self):
        """CANCELLED has no outgoing transitions."""
        for target in RunStatus:
            with pytest.raises(IllegalStateTransitionError):
                validate_run_transition(RunStatus.CANCELLED, target)

    def test_completed_rejects_all_targets_except_supersede(self):
        """COMPLETED gained exactly one outgoing edge (#522), and no more."""
        for target in RunStatus:
            if target == RunStatus.CANCELLED:
                validate_run_transition(RunStatus.COMPLETED, RunStatus.CANCELLED)  # legal
            else:
                with pytest.raises(IllegalStateTransitionError):
                    validate_run_transition(RunStatus.COMPLETED, target)

    def test_failed_rejects_all_except_running(self):
        """FAILED only allows resume_from_failed → RUNNING (SIP-0079)."""
        for target in RunStatus:
            if target == RunStatus.RUNNING:
                validate_run_transition(RunStatus.FAILED, RunStatus.RUNNING)  # legal
            else:
                with pytest.raises(IllegalStateTransitionError):
                    validate_run_transition(RunStatus.FAILED, target)


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


# =============================================================================
# GATE_REJECTED_STATES tests (SIP-0083 D15)
# =============================================================================


async def _seeded_registry_with_run(status: str):
    """A memory registry holding one cycle and one run in ``status`` (#1150).

    The registry's ``record_gate_decision`` is the single enforcement point (T11), so the
    behavioural tests enter there rather than reading the constant.
    """
    import uuid

    from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
    from squadops.cycles.models import Cycle, FlowMode, Gate, TaskFlowPolicy

    now = datetime.now(UTC)
    cycle = Cycle(
        cycle_id=str(uuid.uuid4()),
        project_id="test-project",
        created_at=now,
        created_by="test",
        prd_ref="prd/test.md",
        squad_profile_id="full",
        squad_profile_snapshot_ref="snap-001",
        task_flow_policy=TaskFlowPolicy(
            mode=FlowMode.SEQUENTIAL,
            gates=(
                Gate(
                    name="progress_plan_review",
                    description="gate",
                    after_task_types=("governance.review",),
                ),
            ),
        ),
        build_strategy="fresh",
        applied_defaults={},
        execution_overrides={},
    )
    registry = MemoryCycleRegistry()
    await registry.create_cycle(cycle)
    run = await registry.create_run(
        dataclasses.replace(_make_run(status=status), cycle_id=cycle.cycle_id)
    )
    return registry, cycle, run


class TestGateRejectedStates:
    """#1150: the set is derived from ``TERMINAL_STATES``, so these test the rule, not the
    literal.

    The tests that stood here asserted `FAILED in GATE_REJECTED_STATES` and
    `CANCELLED in GATE_REJECTED_STATES` — a restatement of the constant's own definition,
    which passes whether or not the derivation exists and, more to the point, would have
    said nothing if a fourth terminal state were added. Both directions below are
    parametrised over ``TERMINAL_STATES`` itself, so a new terminal state arrives as a new
    case rather than as a silent gap.
    """

    @pytest.mark.parametrize("state", sorted(TERMINAL_STATES, key=lambda s: s.value))
    def test_every_terminal_state_except_completed_rejects_a_gate_decision(self, state):
        """COMPLETED is the one exception, and it is a design fact rather than an oversight:
        inter-workload gates are decided ON completed runs (SIP-0083 D15), which is also why
        the ``supersede`` edge COMPLETED → CANCELLED exists for the re-roll."""
        assert (state in GATE_REJECTED_STATES) is (state is not RunStatus.COMPLETED)

    def test_no_non_terminal_state_rejects_a_gate_decision(self):
        """The other direction: a gate on a running or queued run is a normal decision."""
        assert not (GATE_REJECTED_STATES - TERMINAL_STATES)

    async def test_the_registry_refuses_a_gate_decision_on_a_failed_run(self):
        """Entered at the enforcement point the live path uses, not at the constant.

        ``record_gate_decision`` is the single enforcement point (T11); a derivation that
        produced the right set but was read by nobody would pass every test above.
        """
        from squadops.cycles.models import RunTerminalError

        registry, cycle, run = await _seeded_registry_with_run(status="failed")
        with pytest.raises(RunTerminalError, match="gate-rejected"):
            await registry.record_gate_decision(
                run.run_id,
                GateDecision(
                    gate_name="progress_plan_review",
                    decision="approved",
                    decided_by="test",
                    decided_at=datetime.now(UTC),
                ),
            )

    async def test_the_registry_accepts_a_gate_decision_on_a_completed_run(self):
        """The exception, exercised rather than asserted — this is the behaviour the
        excluded COMPLETED exists for."""
        registry, cycle, run = await _seeded_registry_with_run(status="completed")
        updated = await registry.record_gate_decision(
            run.run_id,
            GateDecision(
                gate_name="progress_plan_review",
                decision="approved",
                decided_by="test",
                decided_at=datetime.now(UTC),
            ),
        )
        assert [d.gate_name for d in updated.gate_decisions] == ["progress_plan_review"]


# =============================================================================
# resolve_cycle_status tests (SIP-0083 D5)
# =============================================================================


class TestResolveCycleStatus:
    def test_no_workload_statuses_delegates_to_derive(self):
        """Without workload_statuses, resolve equals derive — backward compat."""
        runs = [_make_run(status="completed")]
        assert resolve_cycle_status(runs, False) == CycleStatus.COMPLETED
        assert resolve_cycle_status(runs, False) == derive_cycle_status(runs, False)

    def test_empty_workload_statuses_delegates_to_derive(self):
        """Empty list is equivalent to None — backward compat."""
        runs = [_make_run(status="completed")]
        assert resolve_cycle_status(runs, False, workload_statuses=[]) == CycleStatus.COMPLETED

    def test_gate_awaiting_returns_paused(self):
        """Cycle at inter-workload gate must show PAUSED, not COMPLETED."""
        runs = [_make_run(status="completed")]
        statuses = ["gate_awaiting", "pending", "pending"]
        assert resolve_cycle_status(runs, False, statuses) == CycleStatus.PAUSED

    def test_rejected_returns_failed(self):
        """Rejected gate means the pipeline failed to complete."""
        runs = [_make_run(status="completed")]
        statuses = ["rejected", "pending", "pending"]
        assert resolve_cycle_status(runs, False, statuses) == CycleStatus.FAILED

    def test_gate_awaiting_takes_precedence_over_rejected(self):
        """P6-RC5: gate_awaiting wins — the gate is still actionable."""
        runs = [_make_run(status="completed")]
        statuses = ["rejected", "gate_awaiting", "pending"]
        assert resolve_cycle_status(runs, False, statuses) == CycleStatus.PAUSED

    def test_completed_without_pending_stays_completed(self):
        """All workloads completed, no pending entries → COMPLETED."""
        runs = [
            _make_run(run_number=1, status="completed"),
            _make_run(run_number=2, status="completed"),
            _make_run(run_number=3, status="completed"),
        ]
        statuses = ["completed", "completed", "completed"]
        assert resolve_cycle_status(runs, False, statuses) == CycleStatus.COMPLETED

    def test_pending_workloads_prevent_completed(self):
        """P6-RC5 rule 3: completed run + pending workloads → ACTIVE."""
        runs = [_make_run(status="completed")]
        statuses = ["completed", "pending", "pending"]
        assert resolve_cycle_status(runs, False, statuses) == CycleStatus.ACTIVE

    def test_running_workload_stays_active(self):
        """Mid-workload execution shows ACTIVE via derive_cycle_status."""
        runs = [_make_run(status="running")]
        statuses = ["running", "pending", "pending"]
        assert resolve_cycle_status(runs, False, statuses) == CycleStatus.ACTIVE

    def test_cycle_cancelled_overrides_workload_statuses(self):
        """cycle_cancelled=True wins regardless of workload statuses."""
        runs = [_make_run(status="completed")]
        statuses = ["gate_awaiting", "pending", "pending"]
        assert resolve_cycle_status(runs, True, statuses) == CycleStatus.CANCELLED

    def test_pending_guard_skipped_when_derive_not_completed(self):
        """Rule 3 only fires when derive returns COMPLETED — running stays ACTIVE."""
        runs = [_make_run(status="running")]
        statuses = ["running", "pending", "pending"]
        assert resolve_cycle_status(runs, False, statuses) == CycleStatus.ACTIVE


# =============================================================================
# classify_workload_stranding tests (#481)
# =============================================================================

_SEQ_GATED = [
    {"type": "framing", "gate": "plan-review"},
    {"type": "implementation", "gate": None},
    {"type": "wrapup"},
]
_SEQ_UNGATED = [{"type": "framing"}, {"type": "implementation"}]


def _decided(gate_name: str, decision: str) -> GateDecision:
    return GateDecision(
        gate_name=gate_name,
        decision=decision,
        decided_by="operator",
        decided_at=NOW,
    )


def _completed_run(run_number: int = 1, decisions: tuple = ()) -> Run:
    run = _make_run(run_number=run_number, status="completed")
    return dataclasses.replace(run, gate_decisions=decisions)


class TestClassifyWorkloadStranding:
    """The stranded window is resolve_cycle_status rule 3's own words —
    'between gate approval and next-Run creation'. Bug classes guarded: a
    detector that treats an undecided or revision-returned gate as stranded
    would aim auto-recovery at states the operator deliberately owns; one
    keyed on derived status would miss every stranded cycle (derive says
    COMPLETED there)."""

    def test_approved_gate_with_no_successor_is_stranded(self):
        runs = [_completed_run(decisions=(_decided("plan-review", "approved"),))]
        verdict = classify_workload_stranding(_SEQ_GATED, runs, cycle_cancelled=False)
        assert verdict is WorkloadStranding.STRANDED

    def test_approved_with_refinements_also_strands(self):
        """The executor advances on APPROVED_WITH_REFINEMENTS too (#466) —
        so its absence after that decision is the same dead-loop evidence."""
        runs = [_completed_run(decisions=(_decided("plan-review", "approved_with_refinements"),))]
        verdict = classify_workload_stranding(_SEQ_GATED, runs, cycle_cancelled=False)
        assert verdict is WorkloadStranding.STRANDED

    def test_ungated_boundary_with_no_successor_is_stranded(self):
        runs = [_completed_run()]
        verdict = classify_workload_stranding(_SEQ_UNGATED, runs, cycle_cancelled=False)
        assert verdict is WorkloadStranding.STRANDED

    def test_gate_none_entry_is_an_ungated_boundary(self):
        """A literal ``gate: None`` entry (the #682 waiver-specimen shape)
        strands like a missing key, not like a pending gate."""
        runs = [
            _completed_run(1, decisions=(_decided("plan-review", "approved"),)),
            _completed_run(2),
        ]
        verdict = classify_workload_stranding(_SEQ_GATED, runs, cycle_cancelled=False)
        assert verdict is WorkloadStranding.STRANDED

    def test_undecided_gate_is_pending_not_stranded(self):
        runs = [_completed_run()]
        verdict = classify_workload_stranding(_SEQ_GATED, runs, cycle_cancelled=False)
        assert verdict is WorkloadStranding.GATE_PENDING

    def test_decision_for_another_gate_does_not_satisfy_this_one(self):
        runs = [_completed_run(decisions=(_decided("other-gate", "approved"),))]
        verdict = classify_workload_stranding(_SEQ_GATED, runs, cycle_cancelled=False)
        assert verdict is WorkloadStranding.GATE_PENDING

    def test_rejected_gate_is_visibility_only(self):
        runs = [_completed_run(decisions=(_decided("plan-review", "rejected"),))]
        verdict = classify_workload_stranding(_SEQ_GATED, runs, cycle_cancelled=False)
        assert verdict is WorkloadStranding.GATE_REJECTED

    def test_contradictory_decisions_read_conservatively(self):
        runs = [
            _completed_run(
                decisions=(
                    _decided("plan-review", "approved"),
                    _decided("plan-review", "rejected"),
                )
            )
        ]
        verdict = classify_workload_stranding(_SEQ_GATED, runs, cycle_cancelled=False)
        assert verdict is WorkloadStranding.GATE_REJECTED

    def test_returned_for_revision_is_a_deliberate_stop(self):
        """#466: revision requires manual retry BY DESIGN — classifying it as
        stranded would aim auto-recovery at an operator-owned state."""
        runs = [_completed_run(decisions=(_decided("plan-review", "returned_for_revision"),))]
        assert classify_workload_stranding(_SEQ_GATED, runs, cycle_cancelled=False) is None

    def test_unrecognized_decision_value_is_never_stranding(self):
        runs = [_completed_run(decisions=(_decided("plan-review", "shipped_it"),))]
        assert classify_workload_stranding(_SEQ_GATED, runs, cycle_cancelled=False) is None

    @pytest.mark.parametrize("status", ["queued", "running", "paused", "failed"])
    def test_non_completed_latest_run_is_owned_elsewhere(self, status):
        runs = [_make_run(status=status)]
        assert classify_workload_stranding(_SEQ_GATED, runs, cycle_cancelled=False) is None

    def test_exhausted_sequence_is_terminal_not_stranded(self):
        runs = [_completed_run(1), _completed_run(2)]
        assert classify_workload_stranding(_SEQ_UNGATED, runs, cycle_cancelled=False) is None

    def test_cancelled_cycle_is_silent(self):
        runs = [_completed_run(decisions=(_decided("plan-review", "approved"),))]
        assert classify_workload_stranding(_SEQ_GATED, runs, cycle_cancelled=True) is None

    def test_sequenceless_legacy_cycle_is_silent(self):
        assert classify_workload_stranding([], [_completed_run()], cycle_cancelled=False) is None

    def test_runless_cycle_is_not_between_workloads(self):
        assert classify_workload_stranding(_SEQ_GATED, [], cycle_cancelled=False) is None

    def test_cancelled_successor_reopens_the_position(self):
        """A re-roll that cancelled its replacement's predecessor but died
        before creating the replacement: the cancelled run holds no position
        (#257/D14), so the completed run at position 0 is stranded again."""
        cancelled = _make_run(run_number=2, status="cancelled")
        runs = [_completed_run(1, decisions=(_decided("plan-review", "approved"),)), cancelled]
        verdict = classify_workload_stranding(_SEQ_GATED, runs, cycle_cancelled=False)
        assert verdict is WorkloadStranding.STRANDED
