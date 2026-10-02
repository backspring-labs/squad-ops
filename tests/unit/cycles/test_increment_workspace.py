"""An increment builds on the accepted tree (SIP-0109 §7.1, §7.3; #1705 step c1).

Entered at ``RunProvisioning.seed`` — what ``execute_run`` calls before dispatch — on the real
executor, with a vault holding the accepted cycle's stored artifacts and the increment's
candidate manifest. The seeded list is then handed to the real workspace composer, so what the
test reads is what the development task would be given.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.run_provisioning import ProvisionedRun, RunInProgress
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
