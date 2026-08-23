"""A failed task's emission is banked for triage and used for nothing (#971).

Before this, the one artifact guaranteed absent from a run's vault was the one
that CAUSED the failure: the sequential path raises or ``continue``s before
``_collect_artifacts_and_checkpoint``, so only a later repair's output survived.
13 of the 17 rejected implementation runs in the 08-14→08-23 census are
unreadable for exactly that reason.

The risk the fix introduces is the opposite one — known-bad bytes reaching a
later task or the assembled deliverable — so the exclusion is tested harder than
the capture.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from squadops.cycles.models import ArtifactRef
from squadops.tasks.models import TaskResult

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

TRUNCATED = "export async function POST(req: Request) {\n  const body = await req.js"


@pytest.fixture
def executor(reply_router):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    registry = AsyncMock()
    registry.get_latest_checkpoint.return_value = None
    registry.save_checkpoint.return_value = None
    return DispatchedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=AsyncMock(),
        queue=reply_router.bind(AsyncMock()),
        squad_profile=AsyncMock(),
        project_registry=AsyncMock(),
        reply_router=reply_router,
    )


def _ref(artifact_id: str, filename: str, *, emission_status: str | None = None) -> ArtifactRef:
    metadata: dict = {
        "task_id": "task_1",
        "role": "dev",
        "producing_task_type": "development.develop",
    }
    if emission_status:
        metadata["emission_status"] = emission_status
    return ArtifactRef(
        artifact_id=artifact_id,
        project_id="test",
        artifact_type="source",
        filename=filename,
        content_hash="abc",
        size_bytes=len(TRUNCATED),
        media_type="text/plain",
        created_at=NOW,
        metadata=metadata,
    )


def _envelope(task_type: str = "development.develop"):
    from squadops.tasks.models import TaskEnvelope

    return TaskEnvelope(
        task_id="task_1",
        agent_id="neo",
        cycle_id="cyc_test",
        pulse_id="pulse_1",
        project_id="test",
        task_type=task_type,
        correlation_id="corr_1",
        causation_id="corr_1",
        trace_id="trace_1",
        span_id="span_1",
        inputs={"prd": "test"},
        metadata={"role": "dev"},
    )


def _cycle():
    from squadops.cycles.models import Cycle, TaskFlowPolicy

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
    )


def _failed(artifacts: list[dict] | None) -> TaskResult:
    return TaskResult(
        task_id="task_1",
        status="FAILED",
        outputs={"artifacts": artifacts} if artifacts is not None else {},
        error="tests_pass failed",
    )


ONE_ARTIFACT = [
    {
        "name": "app/api/runs/route.ts",
        "content": TRUNCATED,
        "type": "source",
        "media_type": "text/plain",
    }
]


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


class TestFailedEmissionCapture:
    async def test_failed_emission_is_stored_marked_and_registered(self, executor):
        """The bytes that failed are recoverable, and carry the marker that excludes them."""
        executor._store_artifact = AsyncMock(return_value=_ref("art_f1", "app/api/runs/route.ts"))
        refs: list[str] = []

        await executor._store_failed_emission(
            _failed(ONE_ARTIFACT), _envelope(), _cycle(), "run_1", refs
        )

        kwargs = executor._store_artifact.await_args.kwargs
        assert kwargs["emission_status"] == "failed"
        # provenance stays truthful — a failed develop emission really was develop's
        assert kwargs["producing_task_type"] == "development.develop"
        assert refs == ["art_f1"]
        executor._cycle_registry.append_artifact_refs.assert_awaited_once_with("run_1", ("art_f1",))

    async def test_succeeded_result_stores_nothing(self, executor):
        """The normal path owns successful emissions; double-storing would duplicate them."""
        executor._store_artifact = AsyncMock()
        refs: list[str] = []

        result = TaskResult(
            task_id="task_1", status="SUCCEEDED", outputs={"artifacts": ONE_ARTIFACT}
        )
        await executor._store_failed_emission(result, _envelope(), _cycle(), "run_1", refs)

        executor._store_artifact.assert_not_awaited()
        assert refs == []

    @pytest.mark.parametrize("artifacts", [None, []], ids=["no_outputs", "empty_list"])
    async def test_failure_with_no_artifacts_registers_nothing(self, executor, artifacts):
        """A transport retry emits nothing; it must not write an empty ref tuple."""
        executor._store_artifact = AsyncMock()
        refs: list[str] = []

        await executor._store_failed_emission(
            _failed(artifacts), _envelope(), _cycle(), "run_1", refs
        )

        executor._store_artifact.assert_not_awaited()
        executor._cycle_registry.append_artifact_refs.assert_not_awaited()
        assert refs == []

    async def test_vault_failure_does_not_propagate(self, executor):
        """Banking evidence must never alter the control flow of the failure it records."""
        executor._store_artifact = AsyncMock(side_effect=RuntimeError("vault down"))
        refs: list[str] = []

        await executor._store_failed_emission(
            _failed(ONE_ARTIFACT), _envelope(), _cycle(), "run_1", refs
        )

        assert refs == []
        executor._cycle_registry.append_artifact_refs.assert_not_awaited()


# ---------------------------------------------------------------------------
# Exclusion — the half that carries the risk
# ---------------------------------------------------------------------------


class TestFailedEmissionNeverComposesAWorkspace:
    @pytest.mark.parametrize("include_repair_candidates", [True, False])
    async def test_excluded_regardless_of_the_repair_candidate_flag(
        self, executor, include_repair_candidates
    ):
        """Unconditional, unlike the exclusion beside it.

        A repair candidate is merely unaccepted and the correction loop legitimately
        reads its own accumulation, so that exclusion takes a flag. A failed emission
        is known-bad to every caller, so this one must not.
        """
        good = _ref("art_ok", "app/page.tsx")
        bad = _ref("art_bad", "app/api/runs/route.ts", emission_status="failed")
        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=lambda art_id: {
                "art_ok": (good, b"export default function Page() { return null }"),
                "art_bad": (bad, TRUNCATED.encode()),
            }[art_id]
        )

        contents = await executor._resolve_artifact_contents(
            "qa.test",
            [("art_ok", good), ("art_bad", bad)],
            include_repair_candidates=include_repair_candidates,
        )

        assert "app/api/runs/route.ts" not in contents
        assert contents["app/page.tsx"] == "export default function Page() { return null }"

    async def test_failed_emission_excluded_even_as_the_only_copy(self, executor):
        """The dangerous shape: nothing re-emits the file, so exclusion leaves a hole.

        A hole is correct. Substituting known-bad bytes would hand the next task a
        file that has already been proven not to work.
        """
        bad = _ref("art_bad", "app/api/runs/route.ts", emission_status="failed")
        executor._artifact_vault.retrieve = AsyncMock(return_value=(bad, TRUNCATED.encode()))

        contents = await executor._resolve_artifact_contents("qa.test", [("art_bad", bad)])

        assert contents == {}

    async def test_the_pair_is_banked_but_only_the_good_half_composes(self, executor):
        """A task that fails then succeeds leaves both records; the workspace sees one."""
        bad = _ref("art_bad", "app/api/runs/route.ts", emission_status="failed")
        good = _ref("art_good", "app/api/runs/route.ts")
        executor._artifact_vault.retrieve = AsyncMock(
            side_effect=lambda art_id: {
                "art_bad": (bad, TRUNCATED.encode()),
                "art_good": (good, b"COMPLETE"),
            }[art_id]
        )

        contents = await executor._resolve_artifact_contents(
            "qa.test", [("art_bad", bad), ("art_good", good)]
        )

        assert contents == {"app/api/runs/route.ts": "COMPLETE"}
