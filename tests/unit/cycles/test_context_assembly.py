"""#663 registry behavior — the B1 exit criteria, mechanized.

The byte-level equivalence of the extraction lives in
``test_context_assembly_golden.py``; these tests pin the registry's load-
bearing behaviors: a new capability enrichment is a REGISTRY edit (the
executor threads it with zero changes), and the RC3 default filter lane
serves build-landing filters only.
"""

from __future__ import annotations

import dataclasses
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


def test_repair_contract_threads_the_same_anchor_inventory_under_both_keys():
    """S2/#667: both testid key variants on a repair envelope must carry the
    SAME derivation. Bug caught: mapping SURFACE_DOM_TESTID to a different
    deriver would hand the dev and qa repair handlers divergent anchor
    surfaces — repairs and retests would then disagree on the DOM contract."""
    from pathlib import Path

    from squadops.capabilities.scaffold import InterfaceManifest, testid_surface_instructions

    manifest_path = (
        Path(__file__).resolve().parents[3]
        / "examples"
        / "03_group_run"
        / "interface_manifest.yaml"
    )
    manifest = InterfaceManifest.from_yaml(manifest_path.read_text(encoding="utf-8"))
    expected_lines = testid_surface_instructions(manifest)
    assert expected_lines, "group_run manifest lost its testid inventory — scenario broken"

    fragments = ca.manifest_surface_fragments(ca.REPAIR_CONTEXT_CONTRACT, manifest)

    assert fragments == {
        ca.SURFACE_TESTID: expected_lines,
        ca.SURFACE_DOM_TESTID: expected_lines,
    }
    # No manifest → no keys (the presence-gated shape repairs rely on).
    assert ca.manifest_surface_fragments(ca.REPAIR_CONTEXT_CONTRACT, None) == {}


def test_retest_forwarding_is_presence_keyed():
    """S2: a presence key absent (or empty) on the failed envelope must stay
    absent on the retest. Bug caught: forwarding an empty value would flip the
    qa handler's presence-gated sections (probe execution, workspace
    evaluation, anchor instructions) from 'not applicable' to 'applicable with
    nothing in it'."""
    failed = {
        "resolved_config": {"build_profile": "p"},
        "artifact_contents": {"a.py": "x"},
        "subtask_focus": "focus",
        "expected_artifacts": ["t.py"],
        "acceptance_criteria": [{"check": "c"}],
        "contract_probes": [{"probe": "GET /x"}],
        "acceptance_workspace_files": {},  # present but EMPTY → not forwarded
        # dom_testid_surface entirely absent
    }

    forwarded = ca.retest_forwarded_inputs(failed)

    assert forwarded["contract_probes"] == [{"probe": "GET /x"}]
    assert "acceptance_workspace_files" not in forwarded
    assert "dom_testid_surface" not in forwarded
    # #734: pre-stamp envelopes forward no identity — a fabricated id would
    # claim provenance the failed dispatch never recorded.
    assert "workspace_revision_id" not in forwarded
    assert forwarded["resolved_config"] == {"build_profile": "p"}
    assert forwarded["artifact_contents"] == {"a.py": "x"}

    stamped = ca.retest_forwarded_inputs({**failed, "workspace_revision_id": "c" * 64})
    assert stamped["workspace_revision_id"] == "c" * 64

    # Unconditional keys default rather than disappear on a bare envelope.
    bare = ca.retest_forwarded_inputs({})
    assert bare == {
        "resolved_config": {},
        "artifact_contents": {},
        "subtask_focus": None,
        "expected_artifacts": [],
        "acceptance_criteria": [],
    }


def _source_ref(artifact_id, filename):
    ref = _ref(artifact_id, filename, "development.develop")
    return dataclasses.replace(ref, artifact_type="source", metadata=dict(ref.metadata))


def _executor_with(reply_router, universe):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    by_id = {aid: (ref, body) for aid, ref, body in universe}
    vault = AsyncMock()

    async def retrieve(art_id):
        return by_id[art_id]

    vault.retrieve = AsyncMock(side_effect=retrieve)
    return DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=vault,
        queue=reply_router.bind(AsyncMock()),
        squad_profile=AsyncMock(),
        project_registry=AsyncMock(),
        reply_router=reply_router,
    )


async def _stamped_id(reply_router, universe):
    executor = _executor_with(reply_router, universe)
    envelope = TaskEnvelope(
        task_id="t1",
        agent_id="a",
        cycle_id="cyc_734",
        pulse_id="p",
        project_id="proj",
        task_type="development.develop",
        correlation_id="x",
        causation_id="x",
        trace_id="x",
        span_id="x",
    )
    enriched = await executor._enrich_envelope(
        envelope, {}, [], [(aid, ref) for aid, ref, _ in universe]
    )
    return enriched.inputs["workspace_revision_id"]


class TestWorkspaceRevisionStamp:
    """#734 Slice A acceptance criterion 2 at the dispatch surface: the id is
    content-addressed over the exact post-filter mapping — resolution order
    must not matter, content must."""

    async def test_permuted_store_order_yields_the_same_id(self, reply_router):
        a = ("art_a", _source_ref("art_a", "backend/a.py"), b"a-body")
        b = ("art_b", _source_ref("art_b", "backend/b.py"), b"b-body")

        assert await _stamped_id(reply_router, [a, b]) == await _stamped_id(reply_router, [b, a])

    async def test_content_change_yields_a_new_id(self, reply_router):
        a = ("art_a", _source_ref("art_a", "backend/a.py"), b"a-body")
        b1 = ("art_b", _source_ref("art_b", "backend/b.py"), b"b-body")
        b2 = ("art_b", _source_ref("art_b", "backend/b.py"), b"b-body CHANGED")

        assert await _stamped_id(reply_router, [a, b1]) != await _stamped_id(reply_router, [a, b2])

    async def test_empty_workspace_context_is_still_named(self, reply_router):
        """Evaluation runs even with no workspace context (the task's own
        artifacts overlay an empty tree) — the verdict must name that state,
        not carry null (#734 criterion 1)."""
        from squadops.sandbox.models import compute_revision_id

        assert await _stamped_id(reply_router, []) == compute_revision_id({})
