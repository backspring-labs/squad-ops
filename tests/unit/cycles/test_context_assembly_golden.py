"""#663 golden envelope-equivalence harness (the B1 acceptance gate).

Pins the EXACT enriched-envelope inputs the dispatch path produces for every
task-type class, as canonical JSON goldens captured BEFORE the context-assembly
extraction. Every #663 slice must keep these byte-identical — a deliberate
context change must regenerate the golden in the same PR and read as a
behavior change, never ride silently inside a refactor (the plan's replay-
equivalence rule; the #452 pinned-hash pattern scaled up).

Regenerate: UPDATE_CONTEXT_GOLDENS=1 pytest tests/unit/cycles/test_context_assembly_golden.py
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.models import ArtifactRef
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_orchestration]

_GOLDEN_PATH = Path(__file__).parent / "goldens" / "context_assembly.json"
_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)
NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _ref(artifact_id, filename, artifact_type="document", producing_task_type=""):
    metadata = {"task_id": "task_1", "role": "dev"}
    if producing_task_type:
        metadata["producing_task_type"] = producing_task_type
    return ArtifactRef(
        artifact_id=artifact_id,
        project_id="test",
        artifact_type=artifact_type,
        filename=filename,
        content_hash="abc",
        size_bytes=100,
        media_type="text/markdown",
        created_at=NOW,
        metadata=metadata,
    )


# One stored-artifact universe covering every filter's selection axes: framing
# documents (planning filters), dev source/config emissions (build + workspace
# filters), a qa validation report, and an out-of-map artifact that no filter
# may select.
_STORED = [
    _ref("art_research", "context_research.md", producing_task_type="data.research_context"),
    _ref("art_frame", "objective_frame.md", producing_task_type="strategy.frame_objective"),
    _ref("art_design", "technical_design.md", producing_task_type="development.design_plan"),
    _ref("art_strategy", "test_strategy.md", producing_task_type="qa.define_test_strategy"),
    _ref(
        "art_brief",
        "plan_authoring_brief.yaml",
        producing_task_type="governance.prepare_plan_authoring_brief",
    ),
    _ref(
        "art_dev_prop",
        "proposed_plan_tasks.yaml",
        producing_task_type="development.propose_plan_tasks",
    ),
    _ref("art_analyze", "requirements.md", producing_task_type="strategy.analyze_prd"),
    _ref(
        "art_routes",
        "backend/routes.py",
        artifact_type="source",
        producing_task_type="development.develop",
    ),
    _ref(
        "art_config",
        ".env.example",
        artifact_type="config",
        producing_task_type="development.develop",
    ),
    _ref(
        "art_qa_report",
        "validation_report.md",
        producing_task_type="qa.validate",
    ),
    _ref("art_outside", "unrelated_notes.md", producing_task_type="comms.broadcast"),
]
_STORED_PAIRS = [(r.artifact_id, r) for r in _STORED]


def _envelope(task_type: str, inputs: dict | None = None) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=f"task-{task_type}",
        agent_id="agent",
        cycle_id="cyc_golden",
        pulse_id="p1",
        project_id="proj",
        task_type=task_type,
        correlation_id="corr",
        causation_id="cause",
        trace_id="trace",
        span_id="span",
        inputs=dict(inputs or {}),
        metadata={"role": "dev"},
    )


@pytest.fixture
def executor(reply_router):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    vault = AsyncMock()
    by_id = {aid: (ref, f"body of {ref.filename}".encode()) for aid, ref in _STORED_PAIRS}

    async def retrieve(art_id):
        return by_id[art_id]

    vault.retrieve = AsyncMock(side_effect=retrieve)
    ex = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=vault,
        queue=reply_router.bind(AsyncMock()),
        squad_profile=AsyncMock(),
        project_registry=AsyncMock(),
        reply_router=reply_router,
    )
    return ex


@pytest.fixture(scope="module")
def manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST_PATH.read_text(encoding="utf-8"))


_PRIOR = {"dev": {"summary": "[dev] designed"}}
_REFS = ["art_routes", "art_config"]

# scenario name → (task_type, prior_outputs, artifact_refs, use_manifest, envelope_inputs)
_SCENARIOS: dict[str, tuple[str, dict, list, bool, dict]] = {
    "develop_with_manifest": ("development.develop", _PRIOR, _REFS, True, {"prd": "PRD"}),
    "develop_no_manifest": ("development.develop", _PRIOR, _REFS, False, {"prd": "PRD"}),
    "builder_assemble": ("builder.assemble", _PRIOR, _REFS, False, {}),
    "qa_test": ("qa.test", _PRIOR, _REFS, True, {"prd": "PRD"}),
    "planning_brief_author": ("governance.prepare_plan_authoring_brief", _PRIOR, [], False, {}),
    "planning_dev_proposer": ("development.propose_plan_tasks", _PRIOR, [], False, {}),
    "planning_qa_proposer": ("qa.propose_plan_tasks", _PRIOR, [], False, {}),
    "planning_strat_guidance": ("strategy.propose_plan_guidance", _PRIOR, [], False, {}),
    "planning_merger_excluded": ("governance.merge_plan", _PRIOR, [], False, {}),
    "untabled_base_only": ("data.research_context", _PRIOR, ["art_frame"], False, {}),
    # dispatch keys shadow plan-time keys of the same name (merge semantics)
    "dispatch_shadows_plan_keys": (
        "development.develop",
        _PRIOR,
        _REFS,
        True,
        {"prior_outputs": {"stale": True}, "artifact_refs": ["stale"]},
    ),
}


async def _run_scenario(executor, manifest, name):
    task_type, prior, refs, use_manifest, env_inputs = _SCENARIOS[name]
    enriched = await executor._enrich_envelope(
        _envelope(task_type, env_inputs),
        dict(prior),
        list(refs),
        _STORED_PAIRS,
        interface_manifest=manifest if use_manifest else None,
    )
    return enriched.inputs


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, indent=1, default=str)


@pytest.mark.parametrize("scenario", sorted(_SCENARIOS))
async def test_enriched_inputs_match_golden(executor, manifest, scenario):
    inputs = await _run_scenario(executor, manifest, scenario)
    rendered = _canonical(inputs)

    goldens = json.loads(_GOLDEN_PATH.read_text()) if _GOLDEN_PATH.exists() else {}
    if os.environ.get("UPDATE_CONTEXT_GOLDENS"):
        goldens[scenario] = json.loads(rendered)
        _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN_PATH.write_text(json.dumps(goldens, sort_keys=True, indent=1) + "\n")
        return

    assert scenario in goldens, (
        f"no golden for {scenario!r} — run UPDATE_CONTEXT_GOLDENS=1 pytest {__file__}"
    )
    assert rendered == _canonical(goldens[scenario]), (
        f"enriched inputs for {scenario!r} drifted from the pre-#663 golden — if this "
        "context change is DELIBERATE, regenerate the golden in the same PR so it "
        "reads as a behavior change, never a silent refactor side effect"
    )
