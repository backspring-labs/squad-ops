"""#663 registry behavior — the B1 exit criteria, mechanized.

The byte-level equivalence of the extraction lives in
``test_context_assembly_golden.py``; these tests pin the registry's load-
bearing behaviors: a new capability enrichment is a REGISTRY edit (the
executor threads it with zero changes), and the RC3 default filter lane
serves build-landing filters only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from squadops.capabilities import context_assembly as ca
from squadops.cycles.models import ArtifactRef
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _ref(artifact_id, filename, producing_task_type):
    return ArtifactRef(
        artifact_id=artifact_id,
        project_id="test",
        artifact_type="document",
        filename=filename,
        content_hash="abc",
        size_bytes=10,
        media_type="text/markdown",
        created_at=NOW,
        metadata={"task_id": "t", "role": "dev", "producing_task_type": producing_task_type},
    )


async def test_new_enrichment_is_a_registry_edit_only(reply_router, monkeypatch):
    """B1 exit criterion 2: adding a capability's context declaration must not
    touch the executor. Bug caught: someone reintroduces a task-type branch in
    ``_enrich_envelope``, and new declarations silently need executor edits
    again (the accretion pattern #663 exists to end)."""
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    monkeypatch.setitem(
        ca.CONTEXT_CONTRACTS,
        "future.capability",
        ca.ContextAssemblyContract(
            artifact_filter=ca.ArtifactFilter(by_producing_task=("data.research_context",)),
        ),
    )

    stored_ref = _ref("art_1", "context_research.md", "data.research_context")
    vault = AsyncMock()
    vault.retrieve = AsyncMock(return_value=(stored_ref, b"research body"))
    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=vault,
        queue=reply_router.bind(AsyncMock()),
        squad_profile=AsyncMock(),
        project_registry=AsyncMock(),
        reply_router=reply_router,
    )
    envelope = TaskEnvelope(
        task_id="t1",
        agent_id="a",
        cycle_id="c",
        pulse_id="p",
        project_id="proj",
        task_type="future.capability",
        correlation_id="x",
        causation_id="x",
        trace_id="x",
        span_id="x",
    )

    enriched = await executor._enrich_envelope(envelope, {}, [], [("art_1", stored_ref)])

    assert enriched.inputs["artifact_contents"] == {"context_research.md": "research body"}


def test_rc3_default_filter_lane_is_build_landing_only():
    """The RC3 re-resolution default must select the same universe dispatch
    selected. Bug caught: a planning filter (PRIOR_OUTPUTS landing) leaking
    into the default lane would change correction-loop drift evidence for
    planning task types from empty to populated."""
    assert ca.dispatch_artifact_filter_spec("development.develop") is not None
    assert ca.dispatch_artifact_filter_spec("qa.test") == ca.ACCEPTANCE_WORKSPACE_FILTER.to_spec()
    assert ca.dispatch_artifact_filter_spec("qa.propose_plan_tasks") is None  # planning landing
    assert ca.dispatch_artifact_filter_spec("strategy.frame_objective") is None  # undeclared
