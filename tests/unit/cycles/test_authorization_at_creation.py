"""#1323: a producer's write grants are enforced wherever the executor admits its bytes into
a tree it evaluates — not only at the success path's storage.

1.7.2 React roll 1 (`cyc_eafdc918e8b0`): the builder's failed attempt emitted a net-new
``docker/serve.py`` it may not author. The failed-attempt bank stored it unguarded, the
repair overlay was built on the failed result's artifacts (so the file was in the tree the
verifier saw), the repair that fixed it verified against that overlay and PASSED, and then
storage — the one place that enforced — dropped the fix as ``unauthorized_slot_emission``.
The failing row was superseded; the defect stayed in the delivered file.

Two seams, one rule: the failed result is authorized before it is held (it is the overlay's
base and the bank's source), and the repair is authorized before it is verified (the
verified set must be the set that will be stored). Same grants, same evidence record, with
``stage`` naming where enforcement ran.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.execution_errors import _ExecutionError
from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.bound_scaffold_record import build_bound_record
from squadops.cycles.implementation_plan import TypedCheck
from squadops.cycles.models import ArtifactRef, Cycle, TaskFlowPolicy
from squadops.cycles.scaffold_enforcement import enforce_frozen_ownership, name_producer
from squadops.cycles.scaffold_integrity_evidence import (
    STAGE_ARTIFACT_STORAGE,
    STAGE_FAILED_EMISSION,
    STAGE_PATCH_VERIFICATION,
)
from squadops.cycles.task_outcome import TaskOutcome
from squadops.tasks.models import TaskEnvelope, TaskResult

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 9, 6, 6, 30, 0, tzinfo=UTC)
_MANIFEST = Path(__file__).parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"

#: The roll-1 shape: a net-new source file outside the builder's fill surface (dropped by
#: the #649 builder grant), beside a deliverable the builder may write.
UNAUTHORIZED = {"name": "start.py", "content": "from backend.main import app\n"}
AUTHORIZED = {"name": "start.sh", "content": "#!/bin/sh\nexec uvicorn backend.main:app\n"}


def _record():
    manifest = InterfaceManifest.from_yaml(_MANIFEST.read_text())
    return build_bound_record(manifest, run_id="run_1", attempt_id="run_1", created_at="t")


def _repair_by(task_type: str, *artifacts: dict) -> list[dict]:
    """Repair artifacts as the correction runner hands them over (#1350): naming the step
    that emitted them, whose grants — not the failed task's — are the ones that apply."""
    step = SimpleNamespace(task_id=f"repair-run_1-00-{task_type}", task_type=task_type)
    return name_producer(artifacts, step)


def _builder_envelope() -> TaskEnvelope:
    return TaskEnvelope(
        task_id="task-run_1-m004-builder.assemble",
        agent_id="bob",
        cycle_id="cyc_test",
        pulse_id="p",
        project_id="test",
        task_type="builder.assemble",
        correlation_id="corr",
        causation_id=None,
        trace_id="t",
        span_id="s",
        inputs={
            "resolved_config": {},
            # #1312: the deliverable set is the builder repair's blocking criterion; the
            # handoff and its `sections_present` row are retired.
            "expected_artifacts": ["start.sh"],
            "acceptance_criteria": [
                TypedCheck(
                    check="container_packaging",
                    params={"file": "Dockerfile"},
                    severity="warning",
                    description="packaging findings",
                    id="packaging:Dockerfile",
                )
            ],
        },
        metadata={"role": "builder"},
    )


def _failed(artifacts: list[dict]) -> TaskResult:
    return TaskResult(
        task_id="task-run_1-m004-builder.assemble",
        status="FAILED",
        outputs={"artifacts": artifacts, "outcome_class": TaskOutcome.SEMANTIC_FAILURE},
        error="acceptance failed",
    )


def _cycle(**resolved) -> Cycle:
    return Cycle(
        cycle_id="cyc_test",
        project_id="test",
        created_at=NOW,
        created_by="system",
        prd_ref="prd",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        execution_overrides=resolved,
    )


def _ref(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"art_{name}",
        project_id="test",
        artifact_type="source",
        filename=name,
        content_hash="abc",
        size_bytes=1,
        media_type="text/plain",
        created_at=NOW,
        metadata={"emission_status": "failed"},
    )


@pytest.fixture
def executor(reply_router):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    registry = AsyncMock()
    registry.get_latest_checkpoint.return_value = None
    ex = DispatchedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=AsyncMock(),
        queue=reply_router.bind(AsyncMock()),
        squad_profile=AsyncMock(),
        project_registry=AsyncMock(),
        reply_router=reply_router,
    )
    ex._store_artifact = AsyncMock(side_effect=lambda art, *a, **k: _ref(art["name"]))
    ex._emit_scaffold_integrity_evidence = MagicMock()
    return ex


def _stored_names(executor) -> list[str]:
    return [call.args[0]["name"] for call in executor._store_artifact.await_args_list]


def _evidence(executor) -> list:
    return [call.args[0] for call in executor._emit_scaffold_integrity_evidence.call_args_list]


# --- the failed attempt: authorized before it is held ------------------------------------


class TestTheFailedAttemptIsAuthorizedBeforeItIsHeld:
    """Entry point: ``_admit_failed_emission`` — the one call ``_route_outcome`` makes on
    every failed attempt, whose return value it holds as the repair overlay's base."""

    async def test_the_unauthorized_file_reaches_neither_the_bank_nor_the_held_result(
        self, executor
    ):
        """Bug caught: the roll-1 chain. ``docker/serve.py`` banked as triage evidence AND
        present in the result the overlay is built from, so a repair of it verifies green."""
        refs: list[str] = []
        held = await executor._admit_failed_emission(
            _failed([UNAUTHORIZED, AUTHORIZED]),
            _builder_envelope(),
            _cycle(),
            "run_1",
            refs,
            bound_record=_record(),
            compliance_counter={"n": 0},
        )
        assert [a["name"] for a in held.outputs["artifacts"]] == ["start.sh"]
        assert _stored_names(executor) == ["start.sh"]
        assert refs == ["art_start.sh"]
        # The failed marker still travels with what IS banked (#971 unchanged).
        assert executor._store_artifact.await_args.kwargs["emission_status"] == "failed"
        # Evidence names where enforcement ran, so a record can tell the bank's drop from
        # storage's — before this, every drop read as artifact_storage.
        (record,) = _evidence(executor)
        assert record.normalized_path == "start.py"
        assert record.violation_code == "unauthorized_slot_emission"
        assert record.stage == STAGE_FAILED_EMISSION
        assert record.siblings_retained == 1

    async def test_the_held_result_is_the_same_object_when_nothing_was_dropped(self, executor):
        """Bug caught: a copy made on every failure would break identity-keyed holders and
        the #389 swap that compares against the held result."""
        result = _failed([AUTHORIZED])
        held = await executor._admit_failed_emission(
            result, _builder_envelope(), _cycle(), "run_1", [], bound_record=_record()
        )
        assert held is result
        assert _stored_names(executor) == ["start.sh"]
        assert _evidence(executor) == []

    async def test_an_unbound_run_admits_everything_as_before(self, executor):
        """No scaffold record → no grants exist → nothing is dropped (SIP-0100 no-op when
        unbound); the failed bank keeps its #971 contract untouched."""
        result = _failed([UNAUTHORIZED, AUTHORIZED])
        held = await executor._admit_failed_emission(
            result, _builder_envelope(), _cycle(), "run_1", [], bound_record=None
        )
        assert held is result
        assert _stored_names(executor) == ["start.py", "start.sh"]

    async def test_a_succeeded_result_is_never_touched(self, executor):
        succeeded = TaskResult(
            task_id="t", status="SUCCEEDED", outputs={"artifacts": [UNAUTHORIZED]}
        )
        held = await executor._admit_failed_emission(
            succeeded, _builder_envelope(), _cycle(), "run_1", [], bound_record=_record()
        )
        assert held is succeeded
        executor._store_artifact.assert_not_awaited()

    async def test_the_drop_counts_against_the_compliance_budget_after_the_bank(self, executor):
        """The budget (SIP-0100 3.4a) is the only thing that stops a producer chronically
        overstepping its lane; a failed attempt overstepping is the same behaviour. Past
        the bound it terminates the run — but only after the evidence is banked, so the
        terminal failure never costs the triage copy."""
        refs: list[str] = []
        counter = {"n": 3}  # at the default bound of 3 — this drop crosses it
        with pytest.raises(_ExecutionError, match="Contract-compliance budget"):
            await executor._admit_failed_emission(
                _failed([UNAUTHORIZED, AUTHORIZED]),
                _builder_envelope(),
                _cycle(),
                "run_1",
                refs,
                bound_record=_record(),
                compliance_counter=counter,
            )
        assert counter["n"] == 4
        assert refs == ["art_start.sh"]


# --- the repair: authorized before it is verified ----------------------------------------


class TestTheRepairIsAuthorizedBeforeItIsVerified:
    """Entry point: ``_try_accept_patch`` — the accept-patch caller ``_handle_task_outcome``
    uses on a live cycle — with the real verifier, so the verdict is over the authorized
    set and not over an overlay storage will later disagree with."""

    async def test_the_verified_set_is_the_set_that_will_be_stored(self, executor):
        """Bug caught: the roll-1 false green. The repair rewrites a path the producer may
        not write beside the fix it may; verification must run on — and the corrected
        result must carry — only the authorized part."""
        holder: dict = {}
        action = await executor._try_accept_patch(
            _builder_envelope(),
            _failed([{"name": "Dockerfile", "content": "FROM python:3.12\n"}]),
            _repair_by("builder.assemble_repair", UNAUTHORIZED, AUTHORIZED),
            holder,
            bound_record=_record(),
            compliance_counter={"n": 0},
        )
        assert action == "accept_patch"
        names = [a["name"] for a in holder["patched_result"].outputs["artifacts"]]
        assert "start.sh" in names
        assert "start.py" not in names
        (record,) = _evidence(executor)
        assert record.normalized_path == "start.py"
        assert record.stage == STAGE_PATCH_VERIFICATION
        # #1350: the record names the step that overstepped, not the task it repaired.
        assert record.producer_task_type == "builder.assemble_repair"

    async def test_a_repair_is_judged_by_the_grants_of_the_step_that_made_it(self, executor):
        """Bug caught: ``cyc_375bdea6e140`` (#1350). The same two files, emitted by a DEV
        repair step of this builder failure: ``start.py`` is outside the builder's fill
        surface, but a dev step may author source — so nothing is dropped, the real
        verifier accepts the handoff fix, and the corrected result carries both."""
        holder: dict = {}
        action = await executor._try_accept_patch(
            _builder_envelope(),
            _failed([]),
            _repair_by("development.correction_repair", UNAUTHORIZED, AUTHORIZED),
            holder,
            bound_record=_record(),
            compliance_counter={"n": 0},
        )
        assert action == "accept_patch"
        names = [a["name"] for a in holder["patched_result"].outputs["artifacts"]]
        assert {"start.py", "start.sh"} <= set(names)
        assert _evidence(executor) == []

    async def test_a_repair_artifact_naming_no_producer_is_refused_before_any_grant_is_derived(
        self, executor, monkeypatch
    ):
        """Bug caught: the silent fallback. Judged under the failed task's grants, an unnamed
        dev repair is #1350 again — so an artifact that names no step fails the run naming
        the seam, before a grant is derived or a verifier runs."""
        import adapters.cycles.patch_acceptance as mod

        verifier = AsyncMock()
        monkeypatch.setattr(mod, "verify_patched_artifacts", verifier)
        with pytest.raises(_ExecutionError, match=r"name no producer \(start\.py\).*#1350"):
            await executor._try_accept_patch(
                _builder_envelope(),
                _failed([]),
                [UNAUTHORIZED, *_repair_by("builder.assemble_repair", AUTHORIZED)],
                {},
                bound_record=_record(),
            )
        verifier.assert_not_awaited()
        assert _evidence(executor) == []

    async def test_a_repair_that_is_entirely_unauthorized_is_refused_not_verified(
        self, executor, monkeypatch
    ):
        """Bug caught: verifying nothing and reporting the patch passed. With every repaired
        path dropped there is no patch — the loop continues, the failed rows stand."""
        import adapters.cycles.patch_acceptance as mod

        verifier = AsyncMock()
        monkeypatch.setattr(mod, "verify_patched_artifacts", verifier)
        holder: dict = {}
        action = await executor._try_accept_patch(
            _builder_envelope(),
            _failed([]),
            _repair_by("builder.assemble_repair", UNAUTHORIZED),
            holder,
            bound_record=_record(),
        )
        assert action == "continue"
        assert "patched_result" not in holder
        verifier.assert_not_awaited()

    async def test_without_a_bound_record_the_repair_is_verified_as_before(self, executor):
        """The unbound path is unchanged: no grants, nothing dropped, the real verifier
        accepts the handoff fix."""
        holder: dict = {}
        action = await executor._try_accept_patch(
            _builder_envelope(), _failed([]), [UNAUTHORIZED, AUTHORIZED], holder
        )
        assert action == "accept_patch"
        names = [a["name"] for a in holder["patched_result"].outputs["artifacts"]]
        assert {"start.py", "start.sh"} <= set(names)
        assert _evidence(executor) == []


# --- the re-store: the same producer the verifier read ----------------------------------


class TestTheReStoreReadsTheSameProducerTheVerifierDid:
    """Entry point: ``_collect_artifacts_and_checkpoint`` — where an accepted patch's corrected
    result is stored under the FAILED task's envelope. #1323's rule (the verified set is the
    stored set) holds only if storage judges each artifact by the producer the verifier did."""

    async def test_the_dev_repair_in_a_corrected_result_is_stored_under_the_devs_grants(
        self, executor
    ):
        """Bug caught: verification (fixed) accepts the dev's ``start.py``, storage (unfixed)
        drops it as the builder's write and counts a violation — the roll-1 shape moved one
        seam later."""
        refs: list[str] = []
        counter = {"n": 0}
        corrected = TaskResult(
            task_id="task-run_1-m004-builder.assemble",
            status="SUCCEEDED",
            outputs={
                "artifacts": _repair_by("development.correction_repair", UNAUTHORIZED, AUTHORIZED)
            },
        )
        await executor._collect_artifacts_and_checkpoint(
            corrected,
            _builder_envelope(),
            _cycle(),
            "run_1",
            {},
            refs,
            [],
            [],
            [],
            bound_record=_record(),
            compliance_counter=counter,
        )
        assert _stored_names(executor) == ["start.py", "start.sh"]
        assert _evidence(executor) == []
        assert counter["n"] == 0

    async def test_the_producers_own_unnamed_emission_is_judged_as_before(self, executor):
        """The paired control: the same files as the builder's OWN emission (no step named)
        are judged under the builder's grants — ``start.py`` dropped and counted."""
        counter = {"n": 0}
        own = TaskResult(
            task_id="task-run_1-m004-builder.assemble",
            status="SUCCEEDED",
            outputs={"artifacts": [UNAUTHORIZED, AUTHORIZED]},
        )
        await executor._collect_artifacts_and_checkpoint(
            own,
            _builder_envelope(),
            _cycle(),
            "run_1",
            {},
            [],
            [],
            [],
            [],
            bound_record=_record(),
            compliance_counter=counter,
        )
        assert _stored_names(executor) == ["start.sh"]
        (record,) = _evidence(executor)
        assert record.normalized_path == "start.py"
        assert record.stage == STAGE_ARTIFACT_STORAGE
        assert counter["n"] == 1


# --- the stage rides the evidence record -------------------------------------------------


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        (None, STAGE_ARTIFACT_STORAGE),
        (STAGE_FAILED_EMISSION, STAGE_FAILED_EMISSION),
        (STAGE_PATCH_VERIFICATION, STAGE_PATCH_VERIFICATION),
    ],
    ids=["default-is-storage", "failed-emission", "patch-verification"],
)
def test_the_evidence_record_names_where_enforcement_ran(stage, expected):
    """Bug caught: three enforcement points all reporting ``artifact_storage`` — a record
    could not say whether a drop happened at the bank, before verification, or at storage,
    which is the whole attribution #1323's chain turns on."""
    kwargs = {"stage": stage} if stage else {}
    _, evidence = enforce_frozen_ownership([UNAUTHORIZED], _record(), _builder_envelope(), **kwargs)
    assert [e.stage for e in evidence] == [expected]
