"""#3128 (the 2.9 plan's item 4): an artifact a run's record names, and the vault can't return,
ends the run by name. It is never read as "there was none".

What bugs would these catch?
- A reader that catches the failure, logs it and goes on: the run continues without its plan,
  its skeleton, a checkpoint's file, a seed, or with the PRD's artifact id handed over as the
  PRD's text. Each was the behaviour before #3128.
- A failure that ends the run as ``other``, so a fault of the vault is not told from a fault of
  the work.
- A missing artifact reported as the vault not answering, or the other way round.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from adapters.noop.ports import NoOpFailurePatternRecall, NoOpProposalEvidence
from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.failure_attribution import TerminalKind
from squadops.cycles.models import (
    ArtifactNotFoundError,
    ArtifactUnreadableError,
    Cycle,
    Run,
    RunStatus,
    TaskFlowPolicy,
)
from squadops.cycles.vault_reads import ArtifactUnavailable, retrieve_recorded
from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor
from squadops.execution.run_completion import resolve_terminal_outcome
from squadops.execution.source_checkout import task_source_repository
from squadops.projects.checkout import CHECKOUT_MANIFEST_TYPE, CheckoutManifest

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 11, 26, tzinfo=UTC)
LOST = "art_lost"


def _ref(filename: str, artifact_type: str = "document", **metadata):
    return SimpleNamespace(filename=filename, artifact_type=artifact_type, metadata=metadata)


class _Vault:
    """Returns what it holds, and fails for ``LOST`` the way the test says."""

    def __init__(self, held: dict | None = None, error: Exception | None = None):
        self.held = held or {}
        self.error = error or ConnectionError("the vault didn't answer")

    async def retrieve(self, art_id):
        if art_id == LOST:
            raise self.error
        return self.held[art_id]


def _executor(vault) -> DispatchedFlowExecutor:
    executor = DispatchedFlowExecutor.__new__(DispatchedFlowExecutor)
    executor._artifact_vault = vault
    return executor


# ---------------------------------------------------------------------------
# The seam
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (ArtifactNotFoundError(LOST), "artifact_missing"),
        (ArtifactUnreadableError(f"{LOST}: content doesn't match its hash"), "artifact_unreadable"),
        (ConnectionError("the vault didn't answer"), "artifact_unretrieved"),
    ],
)
async def test_a_failed_read_says_how_it_failed_and_what_the_artifact_was(error, kind):
    with pytest.raises(ArtifactUnavailable) as failed:
        await retrieve_recorded(_Vault(error=error), LOST, what="the cycle's PRD")

    assert (failed.value.artifact_id, failed.value.kind, failed.value.what) == (
        LOST,
        kind,
        "the cycle's PRD",
    )
    assert f"the cycle's PRD (artifact {LOST}) couldn't be read from the vault ({kind})" in str(
        failed.value
    )
    assert failed.value.__cause__ is error


async def test_a_read_with_no_vault_fails_by_name_too():
    """A run handed no vault can't have read the artifact. That is never "absent" either."""
    with pytest.raises(ArtifactUnavailable) as failed:
        await retrieve_recorded(None, "art_1", what="the cycle's PRD")

    assert (failed.value.artifact_id, failed.value.kind) == ("art_1", "artifact_unretrieved")


async def test_a_read_that_succeeds_returns_what_the_vault_returned():
    held = (_ref("prd.md"), b"# PRD")

    assert await retrieve_recorded(_Vault({"art_1": held}), "art_1", what="the PRD") == held


# ---------------------------------------------------------------------------
# Each of the executor's reads
# ---------------------------------------------------------------------------


async def _interface_manifest(executor, tmp_path, monkeypatch):
    cycle = SimpleNamespace(execution_overrides={"plan_artifact_refs": [LOST]})
    run = SimpleNamespace(workload_type="implementation", run_id="run_1")
    await executor._load_interface_manifest_for_run(cycle, run)


async def _authored_manifest(executor, tmp_path, monkeypatch):
    cycle = SimpleNamespace(execution_overrides={}, project_id="p", cycle_id="cyc_1")
    stored = [(LOST, _ref("interface_manifest.yaml", "interface_manifest"))]
    await executor._bind_authored_manifest(cycle, "run_1", stored, (None, None))


async def _checkpoint(executor, tmp_path, monkeypatch):
    checkpoint = RunCheckpoint(
        run_id="run_1",
        checkpoint_index=1,
        completed_task_ids=("t1",),
        prior_outputs={},
        artifact_refs=("art_kept", LOST),
        plan_delta_refs=(),
        created_at=NOW,
    )
    await executor._restore_checkpoint_state(
        checkpoint, "run_1", SimpleNamespace(cycle_id="cyc_1"), set(), {}, [], [], [], []
    )


async def _seed(executor, tmp_path, monkeypatch):
    await executor._seed_prior_artifacts(["art_kept", LOST], [], [])


async def _prd_text(executor, tmp_path, monkeypatch):
    cycle = SimpleNamespace(prd_ref=LOST, project_id="p")
    cycle.with_overrides = lambda overrides: cycle
    executor._cycle_registry = SimpleNamespace(get_cycle=AsyncMock(return_value=cycle))
    await executor._prepare_cycle_for_run("cyc_1", "run_1")


async def _prd_on_disk(executor, tmp_path, monkeypatch):
    monkeypatch.setenv("SQUADOPS_RUN_ROOT", str(tmp_path))
    await executor._materialize_run_root(SimpleNamespace(prd_ref=LOST), "run_1")


async def _plan_at_the_gate(executor, tmp_path, monkeypatch):
    cycle = SimpleNamespace(resolved_config=lambda: {"implementation_plan": True})
    stored = [(LOST, _ref("implementation_plan.yaml", "control_implementation_plan"))]
    await executor._reject_unsatisfiable_plan_at_gate(stored, object(), ["plan-review"], cycle)


async def _bound_contract(executor, tmp_path, monkeypatch):
    cycle = SimpleNamespace(execution_overrides={"contract_ref": LOST})
    await executor._load_contract_for_run(cycle, SimpleNamespace(run_id="run_1"))


async def _merge_decisions_at_the_gate(executor, tmp_path, monkeypatch):
    await executor._load_run_merge_decisions(SimpleNamespace(artifact_refs=("art_kept", LOST)))


async def _run_manifest_at_the_gate(executor, tmp_path, monkeypatch):
    run = SimpleNamespace(artifact_refs=(LOST,))
    await executor._run_manifest_content(run, SimpleNamespace(execution_overrides={}))


async def _seeded_manifest_at_the_gate(executor, tmp_path, monkeypatch):
    cycle = SimpleNamespace(execution_overrides={"plan_artifact_refs": ["art_kept", LOST]})
    await executor._run_manifest_content(SimpleNamespace(artifact_refs=()), cycle)


async def _checkout_manifest(executor, tmp_path, monkeypatch):
    stored = [(LOST, _ref(".checkout", CHECKOUT_MANIFEST_TYPE))]
    await task_source_repository(executor._artifact_vault, stored, ())


async def _checkout_file(executor, tmp_path, monkeypatch):
    stored = [
        ("art_kept", _ref(".checkout", CHECKOUT_MANIFEST_TYPE)),
        (LOST, _ref("src/app.py", "source", producing_task_type="development.develop")),
    ]
    await task_source_repository(executor._artifact_vault, stored, ("src/app.py",))


_READS = [
    pytest.param(_interface_manifest, "a planning artifact forwarded to the run", id="manifest"),
    pytest.param(
        _authored_manifest, "the interface manifest the run authored", id="authored-manifest"
    ),
    pytest.param(_checkpoint, "an artifact the run's checkpoint names", id="checkpoint"),
    pytest.param(_seed, "an artifact the run is seeded with", id="seed"),
    pytest.param(_prd_text, "the cycle's PRD", id="prd-text"),
    pytest.param(_prd_on_disk, "the cycle's PRD", id="prd-on-disk"),
    pytest.param(_plan_at_the_gate, "the run's implementation plan", id="plan-at-the-gate"),
    pytest.param(
        _bound_contract, "the verification contract the cycle is bound to", id="bound-contract"
    ),
    pytest.param(
        _merge_decisions_at_the_gate, "an artifact of the run its gate reads", id="gate-merge"
    ),
    pytest.param(
        _run_manifest_at_the_gate, "an artifact of the run its gate reads", id="gate-manifest"
    ),
    pytest.param(
        _seeded_manifest_at_the_gate,
        "a planning artifact forwarded to the run",
        id="gate-seeded-manifest",
    ),
    pytest.param(_checkout_manifest, "the manifest of the product's checkout", id="checkout"),
    pytest.param(_checkout_file, "the current content of src/app.py", id="checkout-file"),
]


@pytest.mark.parametrize(("read", "what"), _READS)
async def test_each_read_of_a_recorded_artifact_fails_by_name(read, what, tmp_path, monkeypatch):
    """The plan's loader and the builder's notes are held the same way where their other tests
    live (``test_executor_plan_loading.py``, ``test_assembly_notes_threading.py``)."""
    manifest = CheckoutManifest(commit="c0ffee", sizes={"src/app.py": 3})
    vault = _Vault(
        {"art_kept": (_ref(".checkout", CHECKOUT_MANIFEST_TYPE), manifest.to_json())},
        error=ArtifactNotFoundError(LOST),
    )

    with pytest.raises(ArtifactUnavailable) as failed:
        await read(_executor(vault), tmp_path, monkeypatch)

    assert (failed.value.artifact_id, failed.value.what, failed.value.kind) == (
        LOST,
        what,
        "artifact_missing",
    )


async def test_a_criterion_file_the_head_check_cant_read_fails_by_name():
    """The head check reads the criterion files the run stored, as delivery would deliver them."""
    from squadops.execution.criterion_head_check import _criterion_tests

    stored = [(LOST, _ref("tests/test_tally.py", "test"))]

    with pytest.raises(ArtifactUnavailable) as failed:
        await _criterion_tests(_Vault(), stored, {"tests/test_tally.py": "C1"}, {})

    assert (failed.value.artifact_id, failed.value.what) == (
        LOST,
        "the criterion file tests/test_tally.py",
    )


async def test_a_stored_baseline_the_vault_cant_return_fails_by_name_and_one_that_doesnt_parse_is_passed_over():
    """Two different facts at one read (#3128). A baseline reading the listing names and the
    vault can't return is the vault's fault. One that is read and isn't JSON is passed over, and
    the baseline is then played, as before."""
    from squadops.execution.product_acceptance import _stored_baselines
    from squadops.remote_execution.models import ASSERTION_RECORDS_ARTIFACT_TYPE

    def listed(art_id):
        return SimpleNamespace(
            artifact_id=art_id,
            created_at=NOW,
            metadata={"side": "baseline", "criterion_id": "S1"},
        )

    class _Listing(_Vault):
        def __init__(self, ids, held):
            super().__init__(held)
            self.ids = ids

        async def list_artifacts(self, *, cycle_id, artifact_type):
            assert artifact_type == ASSERTION_RECORDS_ARTIFACT_TYPE
            return [listed(i) for i in self.ids]

    cycle = SimpleNamespace(cycle_id="cyc_1")

    with pytest.raises(ArtifactUnavailable) as failed:
        await _stored_baselines(cycle, _Listing([LOST], {}))
    assert (failed.value.artifact_id, failed.value.what) == (
        LOST,
        "the stored baseline reading of S1",
    )

    unparsed = _Listing(["art_bad"], {"art_bad": (listed("art_bad"), b"{ not json")})
    assert await _stored_baselines(cycle, unparsed) == {}


async def test_a_plan_that_is_read_and_doesnt_parse_still_defers_to_the_dispatch_net():
    """What #3128 leaves alone: a plan the vault returned whose text doesn't parse is a finding
    about the plan, decided by the validation nets. Only the retrieval moved out of the catch."""
    vault = _Vault({"art_plan": (_ref("implementation_plan.yaml"), b"{{ not yaml")})
    cycle = SimpleNamespace(resolved_config=lambda: {"implementation_plan": True})
    stored = [("art_plan", _ref("implementation_plan.yaml", "control_implementation_plan"))]

    assert (
        await _executor(vault)._reject_unsatisfiable_plan_at_gate(stored, object(), ["g"], cycle)
        is None
    )


# ---------------------------------------------------------------------------
# How the run ends
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind", ["artifact_missing", "artifact_unreadable", "artifact_unretrieved"]
)
def test_the_run_ends_as_a_fault_outside_the_work_classified_by_how_the_read_failed(kind):
    failure = ArtifactUnavailable(LOST, "the cycle's PRD", kind, ConnectionError("down"))

    outcome = resolve_terminal_outcome(failure, "run_1")

    assert outcome.run_status == RunStatus.FAILED
    assert (outcome.terminal.kind, outcome.terminal.failure_classification) == (
        TerminalKind.INFRASTRUCTURE_FAILED,
        kind,
    )
    assert f"the cycle's PRD (artifact {LOST})" in outcome.terminal.termination_reason
    assert outcome.failure_reason.startswith(f"the cycle's PRD (artifact {LOST})")


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        (ArtifactNotFoundError("art_tree_9"), "artifact_missing"),
        (
            ArtifactUnreadableError("art_tree_9: content doesn't match its hash"),
            "artifact_unreadable",
        ),
    ],
)
def test_the_vaults_own_error_from_a_read_outside_the_executor_is_attributed_the_same_way(
    raw, kind
):
    """A run reaches reads in other packages (the increment's tree, a skillset's content) that
    raise the vault's error as it is. Bug caught: that run ending as ``other``."""
    outcome = resolve_terminal_outcome(raw, "run_1")

    assert (outcome.terminal.kind, outcome.terminal.failure_classification) == (
        TerminalKind.INFRASTRUCTURE_FAILED,
        kind,
    )
    assert "art_tree_9" in outcome.terminal.termination_reason


def test_an_unexpected_error_that_isnt_the_vaults_still_ends_the_run_as_other():
    """The edge the mapping must not widen past: a defect is not an infrastructure fault."""
    outcome = resolve_terminal_outcome(KeyError("producing_task_type"), "run_1")

    assert outcome.terminal.kind == TerminalKind.OTHER
    assert outcome.terminal.failure_classification is None


async def test_a_run_whose_prd_the_vault_cant_return_fails_before_any_task_is_dispatched(
    reply_router,
):
    """The wiring, entered at ``execute_run``, the call the runtime makes for every run. Before
    #3128 this run went on with the string ``art_prd_001`` as its PRD's text."""
    cycle = Cycle(
        cycle_id="cyc_001",
        project_id="test",
        created_at=NOW,
        created_by="system",
        prd_ref="art_prd_001",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={},
        execution_overrides={},
    )
    run = Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
    )
    registry = AsyncMock()
    registry.get_cycle = AsyncMock(return_value=cycle)
    registry.get_run = AsyncMock(return_value=run)
    registry.get_latest_checkpoint = AsyncMock(return_value=None)
    vault = AsyncMock()
    vault.store = AsyncMock(side_effect=lambda ref, content: ref)
    vault.retrieve = AsyncMock(side_effect=ArtifactNotFoundError("art_prd_001"))
    dispatched: list = []

    def answer(envelope):
        dispatched.append(envelope)
        raise AssertionError("no task is dispatched for a run that couldn't read its PRD")

    reply_router.responder = answer
    executor = DispatchedFlowExecutor(
        task_timeout=300.0,
        cycle_registry=registry,
        artifact_vault=vault,
        queue=reply_router.bind(AsyncMock()),
        squad_profile=AsyncMock(),
        reply_router=reply_router,
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(),
        proposal_evidence=NoOpProposalEvidence(),
    )

    await executor.execute_run("cyc_001", "run_001")

    failed = [
        call
        for call in registry.update_run_status.call_args_list
        if call.args[:2] == ("run_001", RunStatus.FAILED)
    ]
    assert len(failed) == 1
    assert (
        failed[0]
        .kwargs["failure_reason"]
        .startswith(
            "the cycle's PRD (artifact art_prd_001) couldn't be read from the vault (artifact_missing)"
        )
    )
    assert dispatched == []
