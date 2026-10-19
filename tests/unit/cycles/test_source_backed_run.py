"""A source-backed run starts from its product's tree (SIP-0112 E.4.3).

Wiring, at the two moments the run is composed, with the shared fixture as the product through
the real managed clone:
- provisioning (``RunProvisioning.seed``, what every run calls before dispatch);
- dispatch-time enrichment (``_enrich_envelope``, what every dispatched task passes).

Bugs caught:
- a run of an external product starting from no tree, or a stack skeleton;
- the developer never shown the file its task changes, or shown the checkout's copy after the
  squad already changed it;
- the delivered tree losing every file the squad didn't touch.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.noop.ports import NoOpFailurePatternRecall
from adapters.tools.git_source import GitSourceRepository
from squadops.cycles.delivered_tree import StoredArtifact, delivered_files
from squadops.cycles.models import ArtifactRef, Cycle, Project, Run, TaskFlowPolicy
from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor
from squadops.execution.run_provisioning import RunProvisioning
from squadops.projects.checkout import CHECKOUT_MANIFEST_TYPE, SOURCE_CHECKOUT
from squadops.projects.development_configuration import parse_configuration
from squadops.projects.models import ProjectSource
from squadops.projects.registration import LocatorPolicy
from squadops.projects.source_context import parse_source_context
from squadops.tasks.models import TaskEnvelope
from tests.fixtures.shared_contract.repository import build_repository, recorded

NOW = datetime(2026, 10, 18, tzinfo=UTC)


class _Vault:
    def __init__(self):
        self.stored: dict[str, tuple[ArtifactRef, bytes]] = {}

    async def store(self, ref, content):
        self.stored[ref.artifact_id] = (ref, content)
        return ref

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]


@pytest.fixture
def world(tmp_path):
    repo = build_repository(tmp_path / "sources" / "tally")
    context = parse_source_context(recorded("project_source_context", "valid"))
    context = context.__class__(**{**context.__dict__, "repo_uri": str(repo.path)})
    registry = AsyncMock()
    registry.get_project.return_value = Project(
        project_id="prj-tally",
        name="Tally",
        description="",
        created_at=NOW,
        source=ProjectSource(str(repo.path), "refs/heads/main", "review_request"),
    )
    registry.get_development_configuration.return_value = parse_configuration(
        recorded("development_configuration", "valid")
    )
    vault = _Vault()
    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=vault,
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        project_registry=registry,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(),
        source_repository=GitSourceRepository(
            tmp_path / "cache",
            LocatorPolicy.of([], [str(tmp_path / "sources")]),
            timeout_seconds=60,
        ),
    )
    executor._cycle_event_bus = MagicMock()
    cycle = Cycle(
        cycle_id="cyc_2407a0000002",
        project_id="prj-tally",
        created_at=NOW,
        created_by="t",
        prd_ref="Add a --json flag to the counters listing.",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:x",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        source_context=context,
    )
    run = Run(
        run_id="run_src000000001",
        cycle_id=cycle.cycle_id,
        run_number=1,
        status="running",
        initiated_by="api",
        resolved_config_hash="h",
    )
    return repo, vault, executor, cycle, run


async def _seed(executor, cycle, run):
    seeded, _manifest = await RunProvisioning(executor=lambda: executor).seed(
        SimpleNamespace(cycle=cycle),
        SimpleNamespace(run=run, existing_checkpoint=None),
        run.run_id,
    )
    return seeded


async def test_provisioning_seeds_the_products_tree_at_the_pinned_commit(world):
    repo, vault, executor, cycle, run = world

    seeded = await _seed(executor, cycle, run)

    refs = [vault.stored[i][0] for i in seeded]
    assert refs[0].artifact_type == CHECKOUT_MANIFEST_TYPE
    files = {r.filename: vault.stored[r.artifact_id][1] for r in refs[1:]}
    assert len(files) == 17 and files["assets/mark.png"].startswith(b"\x89PNG")
    assert all(r.metadata["producing_task_type"] == SOURCE_CHECKOUT for r in refs)
    assert {r.metadata["checkout_commit"] for r in refs} == {repo.second_commit}


async def test_a_resumed_run_is_not_seeded_again(world):
    """#881: a resume restores its seed set from the checkpoint."""
    _, _, executor, cycle, run = world

    seeded, _ = await RunProvisioning(executor=lambda: executor).seed(
        SimpleNamespace(cycle=cycle),
        SimpleNamespace(run=run, existing_checkpoint=object()),
        run.run_id,
    )

    assert seeded == []


def _envelope(cycle, expected):
    return TaskEnvelope(
        task_id="task_dev",
        agent_id="neo",
        cycle_id=cycle.cycle_id,
        pulse_id="p",
        project_id=cycle.project_id,
        task_type="development.develop",
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
        inputs={"expected_artifacts": expected, "subtask_focus": "--json"},
    )


async def test_the_developer_sees_the_files_its_task_names_as_they_are_now(world):
    repo, vault, executor, cycle, run = world
    seeded = await _seed(executor, cycle, run)
    stored = [(i, vault.stored[i][0]) for i in seeded]

    before = await executor._enrich_envelope(
        _envelope(cycle, ["tally/__main__.py"]), {}, list(seeded), stored
    )
    repository = before.inputs["source_repository"]
    assert repository["commit"] == repo.second_commit
    assert set(repository["existing_files"]) == {"tally/__main__.py"}
    assert "argparse" in repository["existing_files"]["tally/__main__.py"]
    assert set(repository["instructions"]) == {"CONTRIBUTING.md"}
    assert "`tally/report.py`" in repository["map"]
    # the checkout reaches the prompt only through this bounded view
    assert "tally/ledger.py" not in before.inputs.get("artifact_contents", {})

    changed = ArtifactRef(
        artifact_id="art_dev000000001",
        project_id=cycle.project_id,
        cycle_id=cycle.cycle_id,
        run_id=run.run_id,
        artifact_type="source",
        filename="tally/__main__.py",
        content_hash="h",
        size_bytes=9,
        media_type="text/x-python",
        # after the seed, as a live run's emission always is: the delivered tree orders by it
        created_at=datetime.now(UTC),
        metadata={"producing_task_type": "development.develop"},
    )
    vault.stored[changed.artifact_id] = (changed, b"# --json\n")
    after = await executor._enrich_envelope(
        _envelope(cycle, ["tally/__main__.py"]),
        {},
        [*seeded, changed.artifact_id],
        [*stored, (changed.artifact_id, changed)],
    )

    assert after.inputs["source_repository"]["existing_files"] == {
        "tally/__main__.py": "# --json\n"
    }
    delivered = delivered_files(
        StoredArtifact.from_record(dataclasses.asdict(vault.stored[i][0]))
        for i in [*seeded, changed.artifact_id]
    )
    assert delivered["tally/__main__.py"] == changed.artifact_id
    # Every workspace-typed file the squad didn't touch is delivered as it was. The delivered tree
    # holds source, test and config only: README.md and CONTRIBUTING.md (documents) are not in
    # it, which is why capture starts from the clone at the pinned commit, never from this tree.
    workspace = {
        vault.stored[i][0].filename
        for i in seeded[1:]
        if vault.stored[i][0].artifact_type in ("source", "test", "config")
    }
    assert set(delivered) == workspace and "README.md" not in delivered


async def test_a_run_with_no_pinned_source_is_unchanged(world):
    _, vault, executor, cycle, run = world
    plain = cycle.__class__(**{**cycle.__dict__, "source_context": None})

    seeded = await _seed(executor, plain, run)
    enriched = await executor._enrich_envelope(_envelope(plain, ["x.py"]), {}, [], [])

    assert seeded == [] and vault.stored == {}
    assert "source_repository" not in enriched.inputs
