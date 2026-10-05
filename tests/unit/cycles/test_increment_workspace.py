"""An increment builds on the accepted tree (SIP-0109 §7.1, §7.3; #1705 step c1).

Entered at ``RunProvisioning.seed`` — what ``execute_run`` calls before dispatch — on the real
executor, with a vault holding the accepted cycle's stored artifacts and the increment's
candidate manifest. The seeded list is then handed to the real workspace composer, so what the
test reads is what the development task would be given.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.run_provisioning import ProvisionedRun, RunInProgress
from adapters.noop.ports import NoOpFailurePatternRecall
from squadops.cycles.models import ArtifactRef, Cycle, Run, TaskFlowPolicy

NOW = datetime(2026, 10, 2, 13, 0, tzinfo=UTC)
_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "campaigns"
    / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml"
).read_text()


def _ref(art_id, filename, kind, *, cycle_id, created, **meta):
    return ArtifactRef(
        artifact_id=art_id,
        project_id="group_run",
        artifact_type=kind,
        filename=filename,
        content_hash="h",
        size_bytes=1,
        media_type="text/plain",
        created_at=NOW + timedelta(seconds=created),
        cycle_id=cycle_id,
        run_id=f"run_{cycle_id}",
        metadata=meta,
    )


class _Vault:
    def __init__(self) -> None:
        self.stored: dict[str, tuple] = {}

    def put(self, ref, content: str) -> None:
        self.stored[ref.artifact_id] = (ref, content.encode())

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]

    async def store(self, ref, content):
        self.stored[ref.artifact_id] = (ref, content)
        return ref

    async def list_artifacts(self, *, cycle_id=None, **_):
        return [r for r, _ in self.stored.values() if cycle_id is None or r.cycle_id == cycle_id]


@pytest.fixture
def vault():
    v = _Vault()
    # The accepted (calibration) cycle's stored routes: the accepted implementation, and a
    # repair candidate the framework rejected, which is newer.
    v.put(
        _ref(
            "art_routes",
            "backend/routes.py",
            "source",
            cycle_id="cyc_cal",
            created=1,
            producing_task_type="development.develop",
        ),
        "# the accepted routes\n",
    )
    v.put(
        _ref(
            "art_cand",
            "backend/routes.py",
            "source",
            cycle_id="cyc_cal",
            created=9,
            producing_task_type="development.correction_repair",
        ),
        "# a rejected repair\n",
    )
    # The increment's candidate manifest, seeded at its approval (#1840).
    v.put(
        _ref(
            "art_candidate_manifest",
            "interface_manifest.yaml",
            "interface_manifest",
            cycle_id="cyc_inc",
            created=0,
        ),
        _MANIFEST,
    )
    return v


def _cycle(
    kind: str | None, accepted_cycle_id: str | None = "cyc_cal", *, block: bool = True
) -> Cycle:
    proposal = {"proposal_id": "p", "version": 1}
    if accepted_cycle_id:
        proposal["accepted_cycle_id"] = accepted_cycle_id
    overrides: dict = {"plan_artifact_refs": ["art_candidate_manifest"]}
    if block:
        overrides["campaign_proposal"] = proposal
    return Cycle(
        cycle_id="cyc_inc",
        project_id="group_run",
        created_at=NOW,
        created_by="campaign-launcher",
        prd_ref=None,
        squad_profile_id="full-38",
        squad_profile_snapshot_ref="x",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        execution_overrides=overrides,
        campaign_id="cmp_1" if kind else None,
        kind=kind,
    )


async def _seed_and_compose(vault, cycle: Cycle) -> tuple[list[str], dict[str, str]]:
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=vault,
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(),
    )
    executor._cycle_event_bus = MagicMock()
    run = Run("run_impl", "cyc_inc", 2, "running", "system", "cfg", workload_type="implementation")
    seeds, _manifest = await executor._run_provisioning.seed(
        RunInProgress(cycle=cycle),
        ProvisionedRun(run=run, run_root=None, profile=None, existing_checkpoint=None),
        run.run_id,
    )
    stored = [(art_id, vault.stored[art_id][0]) for art_id in seeds]
    contents = await executor._resolve_artifact_contents("development.develop", stored)
    return seeds, contents


async def _workspace(vault, seeds: list[str], task_type: str) -> dict[str, str]:
    """The files ``task_type`` is composed from the seeded set, as dispatch composes them."""
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=vault,
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(),
    )
    stored = [(art_id, vault.stored[art_id][0]) for art_id in seeds]
    return await executor._resolve_artifact_contents(task_type, stored)


async def test_an_increment_s_developer_is_given_the_accepted_implementation_not_a_stub(vault):
    """§7.3. Bugs caught: an increment rebuilding the whole app from stubs (greenfield, the
    accepted work discarded), or the accepted tree taken with a rejected repair in it."""
    seeds, contents = await _seed_and_compose(vault, _cycle("increment"))

    assert "art_routes" in seeds and "art_cand" not in seeds
    assert contents["backend/routes.py"] == "# the accepted routes\n"


@pytest.mark.parametrize(
    ("kind", "accepted", "block"),
    [(None, None, False), ("calibration", None, False), ("increment", None, True)],
    ids=["ordinary-cycle", "calibration", "increment-without-accepted-cycle"],
)
async def test_any_other_cycle_builds_from_the_skeleton_as_before(vault, kind, accepted, block):
    """Bug caught: a calibration (or any ordinary cycle) seeded with another cycle's files."""
    seeds, contents = await _seed_and_compose(vault, _cycle(kind, accepted, block=block))

    assert "art_routes" not in seeds
    assert contents.get("backend/routes.py") != "# the accepted routes\n"


async def test_the_reference_increment_builds_on_its_baseline_outside_any_campaign(vault):
    """§11a, #1804: the reference increment carries the same block a campaign's increment does,
    with no campaign. Bug caught: its build started from stubs because the accepted tree was
    keyed on the campaign's cycle kind, so the scenario measured a greenfield build."""
    seeds, contents = await _seed_and_compose(vault, _cycle(None, "cyc_cal"))

    assert "art_routes" in seeds
    assert contents["backend/routes.py"] == "# the accepted routes\n"


async def test_a_repair_continues_the_failed_candidate_on_top_of_the_accepted_tree(vault):
    """§10a, entered at the run's seeding and composition. Bugs caught: a repair seeded from the
    accepted tree alone, discarding the failed cycle's work it exists to repair; one seeded from
    the failed candidate alone, losing the accepted files the change never touched; or the two
    composed in the wrong order, so the accepted version overwrites the failed one."""
    import dataclasses as _dc

    vault.put(
        _ref(
            "art_failed_routes",
            "backend/routes.py",
            "source",
            cycle_id="cyc_failed",
            created=20,
            producing_task_type="development.develop",
        ),
        "# the failed increment's routes\n",
    )
    vault.put(
        _ref(
            "art_view",
            "frontend/src/views/RunListView.jsx",
            "source",
            cycle_id="cyc_cal",
            created=2,
            producing_task_type="development.develop",
        ),
        "// the accepted view\n",
    )
    repair = _cycle("repair")
    block = {**repair.execution_overrides["campaign_proposal"], "repair_of": "cyc_failed"}
    repair = _dc.replace(
        repair, execution_overrides={**repair.execution_overrides, "campaign_proposal": block}
    )

    seeds, contents = await _seed_and_compose(vault, repair)

    assert contents["backend/routes.py"] == "# the failed increment's routes\n"
    assert contents["frontend/src/views/RunListView.jsx"] == "// the accepted view\n"
    assert "art_cand" not in seeds


async def test_an_increment_s_frozen_files_are_its_candidate_s_not_the_accepted_tree_s(vault):
    """#1876, entered at the run's seeding and composition. The reference increment's routes
    read ``payload.capacity`` (the candidate manifest's ``RunCreate``) against the accepted
    tree's ``models.py`` (the baseline's, without it): the accepted tree, seeded last, won over
    the skeleton the candidate regenerated, and no repair can rewrite a frozen file. Bugs
    caught: a carried-over frozen file shadowing the regenerated one; or the accepted tree's
    implementation lost with it."""
    from squadops.capabilities.scaffold import InterfaceManifest, frozen_paths

    assert "backend/models.py" in frozen_paths(InterfaceManifest.from_yaml(_MANIFEST))
    # As the accepted cycle stored it: its own skeleton's model, seeded by the scaffold.
    vault.put(
        _ref(
            "art_baseline_models",
            "backend/models.py",
            "source",
            cycle_id="cyc_cal",
            created=3,
            producing_task_type="scaffold.expand",
            scaffold_seeded=True,
        ),
        "# the baseline's model\n",
    )

    seeds, _contents = await _seed_and_compose(vault, _cycle("increment"))
    # The tree the qa suite runs on: the acceptance workspace, every source file seeded.
    tree = await _workspace(vault, seeds, "qa.test")

    assert "art_baseline_models" not in seeds
    assert "class " in tree["backend/models.py"]  # the candidate skeleton's model
    assert tree["backend/models.py"] != "# the baseline's model\n"
    assert tree["backend/routes.py"] == "# the accepted routes\n"


def _put(vault, art_id, filename, cycle_id, created, content, **meta):
    vault.put(
        dataclasses.replace(
            _ref(art_id, filename, "source", cycle_id=cycle_id, created=created, **meta),
            run_id=f"run_{cycle_id}",
        ),
        content,
    )


async def test_an_increments_tree_is_the_app_it_built_on_overlaid_with_its_change(vault):
    """#1887, the composition every reader of the accepted tree now shares. Shakeout 3's first
    increment stored only its own outputs and the skeleton's stubs; its promoted tree held a
    stub ``RunListView`` the calibration had implemented, and the second increment built against
    it. Bugs caught: an untouched slot's stub shadowing the accepted implementation; the
    increment's own change lost under the accepted copy; or the candidate's regenerated frozen
    file losing to the baseline's (#1876)."""
    from squadops.campaigns.increment_tree import compose_accepted_tree

    view = "frontend/src/views/RunListView.jsx"
    _put(
        vault,
        "c_view",
        view,
        "cyc_cal",
        2,
        "// the accepted list view\n",
        producing_task_type="development.develop",
    )
    _put(
        vault,
        "c_models",
        "backend/models.py",
        "cyc_cal",
        0,
        "# baseline models\n",
        producing_task_type="scaffold.expand",
        scaffold_seeded=True,
    )
    # The increment: its change, its skeleton's stub for the slot it did not touch, and its
    # skeleton's regenerated model.
    _put(
        vault,
        "i_routes",
        "backend/routes.py",
        "cyc_inc1",
        30,
        "# the increment's routes\n",
        producing_task_type="development.develop",
    )
    _put(
        vault,
        "i_view_stub",
        view,
        "cyc_inc1",
        20,
        "// stub\n",
        producing_task_type="scaffold.expand",
        scaffold_seeded=True,
    )
    _put(
        vault,
        "i_models",
        "backend/models.py",
        "cyc_inc1",
        20,
        "# regenerated models\n",
        producing_task_type="scaffold.expand",
        scaffold_seeded=True,
    )

    tree = await compose_accepted_tree(
        vault, "cyc_cal", await vault.list_artifacts(cycle_id="cyc_inc1")
    )

    assert tree[view] == "c_view"
    assert tree["backend/routes.py"] == "i_routes"
    assert tree["backend/models.py"] == "i_models"


async def test_the_next_increment_seeds_from_the_recorded_whole_tree(vault):
    """#1887, entered at the run's seeding and composition: increment 2 builds on increment 1,
    whose promotion recorded the whole tree. Bug caught: the seed read from increment 1's own
    artifacts, handing the developer a stub where the accepted app had an implementation."""
    import json

    from squadops.campaigns.increment_tree import ACCEPTED_TREE_ARTIFACT_TYPE

    view = "frontend/src/views/RunListView.jsx"
    _put(
        vault,
        "c_view",
        view,
        "cyc_cal",
        2,
        "// the accepted list view\n",
        producing_task_type="development.develop",
    )
    _put(
        vault,
        "i_view_stub",
        view,
        "cyc_inc1",
        20,
        "// stub\n",
        producing_task_type="scaffold.expand",
        scaffold_seeded=True,
    )
    tree = {view: "c_view", "backend/routes.py": "art_routes"}
    vault.put(
        dataclasses.replace(
            _ref(
                "i_tree",
                "accepted_tree.json",
                ACCEPTED_TREE_ARTIFACT_TYPE,
                cycle_id="cyc_inc1",
                created=40,
            ),
            run_id="run_cyc_inc1",
        ),
        json.dumps(tree),
    )

    seeds, _ = await _seed_and_compose(vault, _cycle("increment", "cyc_inc1"))
    workspace = await _workspace(vault, seeds, "qa.test")

    assert workspace[view] == "// the accepted list view\n"
    assert "i_view_stub" not in seeds
