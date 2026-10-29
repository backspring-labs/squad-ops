"""A repository-backed Campaign's accepted tree is its campaign branch (SIP-0109 §24bv point 2,
§24cd point 2, §24ce).

Entered at ``CampaignProgress.cycle_ended``, as the completion boundary calls it, after a real
``deliver_source_change``. The Project is the shared fixture's Tally, with its baseline really
captured:
- the managed clone is real (``GitSourceRepository``), and so are the workspace store and the
  sandbox service, whose one stand-in runs X-3a's disposable copy as local processes;
- the campaign starts by its calibration record (§24cc), which creates the branch;
- each increment is launched as the owner's word would launch it, since the proposal on such a
  Project (§24bv point 5) isn't built.

The restarts are entered at ``main._resume_campaigns``, the startup the runtime runs.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.tools.git_source import GitSourceRepository
from squadops.campaigns.calibration_record import record_for
from squadops.campaigns.campaign_branch import (
    CampaignBranch,
    CampaignHead,
    campaign_ref,
    head,
)
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.increment_tree import INCREMENT_EVALUATION_ARTIFACT_TYPE
from squadops.campaigns.launch_requests import start_transition
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    ControlOperation,
    ControlOutcome,
    CycleKind,
    LaunchRequest,
)
from squadops.campaigns.progress import CampaignProgress, decision_key
from squadops.cycles.cycle_end import CycleStopReason, RecordedEnd
from squadops.cycles.models import ArtifactRef, Cycle, Run, TaskFlowPolicy
from squadops.cycles.verification_integrity import RunVerdict
from squadops.execution.source_delivery import SOURCE_VERIFICATION_TYPE, deliver_source_change
from squadops.projects.development_configuration import parse_configuration
from squadops.projects.models import SourceUnavailable
from squadops.projects.registration import LocatorPolicy
from squadops.projects.source_context import parse_source_context
from squadops.projects.workspaces import capture_inherited_baseline
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import WorkspaceStore
from tests.fixtures.shared_contract.repository import build_repository, recorded, tracked_files
from tests.unit.api.test_campaign_calibration_record import PROJECT, _Projects, _tally
from tests.unit.campaigns.builders import campaign, move, policy
from tests.unit.campaigns.test_progress import _assessment
from tests.unit.cycles.test_source_backed_run import _LocalBackend
from tests.unit.projects.test_workspaces import _LocalSandbox

CID = "cmp_branch000001"
NOW = datetime(2026, 10, 24, tzinfo=UTC)
REPORT = "tally/report.py"


def _added(name: str) -> bytes:
    """A function the squad adds to the report module, which the product's checks accept."""
    return f"\n\ndef {name}(ledger):\n    return len(ledger)\n".encode()


class _World:
    """Tally's managed clone, sandbox and records, and a campaign on it."""

    def __init__(self, tmp_path) -> None:
        self.tmp_path = tmp_path
        self.repo = build_repository(tmp_path / "sources" / "tally")
        self.projects = _Projects(
            _tally(str(self.repo.path)),
            parse_configuration(recorded("development_configuration", "valid")),
        )
        self.clones = GitSourceRepository(
            tmp_path / "cache",
            LocatorPolicy.of([], [str(tmp_path / "sources")]),
            timeout_seconds=60,
            committer_name="SquadOps",
            committer_email="squadops@squadops.invalid",
        )
        store = WorkspaceStore(tmp_path / "sandbox")
        self.sandbox = SandboxService(
            store=store,
            journal=OperationEvidenceJournal(tmp_path / "sandbox"),
            backend=_LocalBackend(store),
        )
        self.vault = FilesystemArtifactVault(tmp_path / "vault")
        self.campaigns = MemoryCampaignRegistry()
        self.cycles = MemoryCycleRegistry()
        self.verdicts: dict[str, RunVerdict] = {}
        self.progress = self.progress_on(self.clones)

    def progress_on(self, repository) -> CampaignProgress:
        """The completion path as the runtime builds it, over ``repository`` as its clone."""
        return CampaignProgress(
            campaigns=self.campaigns,
            cycles=self.cycles,
            vault=self.vault,
            assess=self._assess,
            launch=AsyncMock(),
            evaluate_outcome=None,
            evaluate_baseline=None,
            outcome_section=None,
            intervention_section=None,
            campaign_branch=CampaignBranch(projects=self.projects, repository=repository),
        )

    async def _assess(self, cycle_id):
        return _assessment(cycle_id, self.verdicts.get(cycle_id, RunVerdict.ACCEPTED))

    async def started(self) -> None:
        """The baseline captured, and the campaign started by its record: promoted and decided
        (§24cc). Row 5's proposal escalates: its profile is one the deploy doesn't hold, so the
        owner's word launches each increment here (``delivered``), as these tests are about the
        promotion, not the proposal (§24bv point 5 is ``test_campaign_calibration_record``'s)."""
        await capture_inherited_baseline(
            PROJECT,
            registry=self.projects,
            repository=self.clones,
            sandbox=_LocalSandbox(self.tmp_path / "baseline"),
            actor="owner",
            idempotency_key="b-1",
        )
        draft = campaign(
            CID,
            project_id=PROJECT,
            policy=policy(
                calibration_profile="validated-fullstack",
                squad_profile="full-38",
                proposal_profile="no-such-profile",
            ),
        )
        await self.campaigns.create_campaign(
            draft, actor="owner", actor_role="admin", reason="r", idempotency_key="create"
        )
        record = await record_for(self.projects, self.projects.project, campaign_id=CID)
        await self.campaigns.transition(
            CID,
            start_transition(
                draft,
                actor="owner",
                actor_role="admin",
                reason="go",
                idempotency_key="start",
                record=record,
            ),
        )
        await self.progress.calibration_recorded(CID)

    async def delivered(
        self, cycle_id: str, change: bytes, evaluation: str = "accepted"
    ) -> tuple[Cycle, Run, str]:
        """An increment launched on the campaign (the owner's word, standing in for the proposal
        point 5 adds), pinned as today's cycle-create path pins it, at the Project's baseline. Its
        run's change to the report module is delivered for real: verified by the product's
        checks and captured in the clone. Its own evaluation is ``evaluation``. Returns the cycle,
        its run and the captured commit."""
        result = await self.campaigns.transition(
            CID,
            move(
                CampaignState.BUILDING,
                f"launch-{cycle_id}",
                operation=ControlOperation.RESUME,
                launch=LaunchRequest(CycleKind.INCREMENT, {}),
            ),
        )
        await self.campaigns.mark_launch_intent_launched(
            result.intent.launch_id, cycle_id, actor="launcher"
        )
        context = parse_source_context(recorded("project_source_context", "valid"))
        cycle = Cycle(
            cycle_id=cycle_id,
            project_id=PROJECT,
            created_at=NOW,
            created_by="campaign-launcher",
            prd_ref=None,
            squad_profile_id="full-38",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            source_context=dataclasses.replace(context, repo_uri=str(self.repo.path)),
            campaign_id=CID,
            kind="increment",
        )
        run = Run(
            run_id=f"run_{cycle_id.removeprefix('cyc_')}",
            cycle_id=cycle_id,
            run_number=1,
            status="completed",
            initiated_by="system",
            resolved_config_hash="cfg",
            workload_type="implementation",
        )
        await self.cycles.create_cycle(cycle)
        await self.cycles.create_run(run)
        original = tracked_files(self.repo.path, self.repo.second_commit)[REPORT]
        emitted = await self._stored(cycle, run, REPORT, "source", original + change)
        delivery = await deliver_source_change(
            cycle,
            run.run_id,
            [emitted],
            vault=self.vault,
            registry=self.projects,
            repository=self.clones,
            sandbox=self.sandbox,
        )
        assert delivery.captured_commit is not None, delivery.verification.to_document()
        await self._stored(
            cycle,
            run,
            "increment_evaluation.json",
            INCREMENT_EVALUATION_ARTIFACT_TYPE,
            json.dumps({"verdict": evaluation}).encode(),
        )
        return cycle, run, delivery.captured_commit

    async def _stored(self, cycle, run, filename, artifact_type, content):
        ref = ArtifactRef(
            artifact_id=f"art_{uuid4().hex[:12]}",
            project_id=PROJECT,
            cycle_id=cycle.cycle_id,
            run_id=run.run_id,
            artifact_type=artifact_type,
            filename=filename,
            content_hash="h",
            size_bytes=len(content),
            media_type="text/plain",
            created_at=datetime.now(UTC),
            metadata={"producing_task_type": "development.develop", "task_id": "task_dev"},
        )
        await self.vault.store(ref, content)
        return ref.artifact_id, ref

    async def branch(self) -> str | None:
        return await self.clones.ref_commit(PROJECT, campaign_ref(CID))

    async def promotions(self, cycle_id: str) -> list:
        return [
            e
            for e in await self.campaigns.control_log(CID)
            if e.operation is ControlOperation.PROMOTE
            and e.outcome is ControlOutcome.APPLIED
            and e.target == cycle_id
        ]

    async def decisions(self, cycle_id: str) -> list:
        """The cycle's continuation decisions (§10), never its move to ``evaluating``."""
        return [
            e
            for e in await self.campaigns.control_log(CID)
            if e.idempotency_key == decision_key(cycle_id) and e.outcome is ControlOutcome.APPLIED
        ]


def _restarted(world: _World, progress: CampaignProgress, *ended: str) -> SimpleNamespace:
    """The runtime's state at a startup: the launch service's three reads, and the progress."""
    launch = SimpleNamespace(
        drain=AsyncMock(), launched_cycles=AsyncMock(return_value=list(ended)), reattach=AsyncMock()
    )
    return SimpleNamespace(campaign_launch=launch, campaign_progress=progress)


async def test_an_accepted_increment_moves_the_branch_to_its_capture(tmp_path):
    """§24bv point 2, the wiring: the increment's run delivers for real, and the completion
    boundary hears its cycle end. Bugs caught:
    - a repository-backed increment promoted by composing a tree from the vault, which holds only
      the files the squad changed, so the accepted tree drops the rest of the product;
    - an accepted tree with no commit, or an identity other than the captured commit's own tree;
    - the branch's ref never following the row, so the clone's branch misses the increment;
    - a promotion that names no verification, so the next increment has no regression baseline;
    - the package reading the promotion as a partial one, since it has no vault tree, so the
      campaign's safety guarantees never all hold (§14).
    The tree's identity is read back from Git independently of the code under test."""
    world = _World(tmp_path)
    await world.started()
    cycle, run, captured = await world.delivered("cyc_inc000000001", _added("total"))

    await world.progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)

    stored = await world.campaigns.get_campaign(CID)
    log = await world.campaigns.control_log(CID)
    [promote] = await world.promotions(cycle.cycle_id)
    [decide] = await world.decisions(cycle.cycle_id)
    [verification] = await world.vault.list_artifacts(
        cycle_id=cycle.cycle_id, run_id=run.run_id, artifact_type=SOURCE_VERIFICATION_TYPE
    )
    identity = FileTree.of(tracked_files(tmp_path / "cache" / "prj-tally.git", captured)).identity
    assert stored.accepted == AcceptedTree(identity, cycle.cycle_id, commit=captured)
    assert (promote.binding["commit"], promote.binding["parent_commit"]) == (
        captured,
        world.repo.second_commit,
    )
    assert promote.binding["verification_ref"] == verification.artifact_id
    assert "tree_ref" not in promote.binding
    assert await world.branch() == captured
    assert head(stored, log) == CampaignHead(captured, identity, verification.artifact_id)
    # Row 7 proposes. Its profile is none the deploy holds here (``started``), so it escalates.
    assert (decide.binding["row"], decide.binding["verdict"]) == (7, "accepted")
    assert "proposal profile cannot be loaded" in decide.binding["unbuilt"]
    assert "promotion_refused" not in decide.binding
    _identity, _package, digest_id = await world.progress.materialize_package(CID)
    _ref, digest = await world.vault.retrieve(digest_id)
    assert "- held: no partial promotion" in digest.decode()
    assert (
        f"- increment `{cycle.cycle_id}`: tree `{identity[:12]}`, commit `{captured[:12]}` on "
        "the campaign branch"
    ) in digest.decode()


async def test_a_capture_built_on_another_commit_than_the_head_is_refused(tmp_path):
    """§24bv point 2's order, and §24ce. The second increment is pinned as today's cycle-create
    path pins every cycle, at the Project's baseline, so its capture's parent is the record's
    commit while the branch's head is the first increment's. Bugs caught: the second capture
    promoted over the first, so the branch and the accepted tree lose the first increment's
    change (§24bv's stacking gap); or the refusal silent, so the campaign proposes on a tree that
    never took the increment the squad was told it accepted."""
    world = _World(tmp_path)
    await world.started()
    first, first_run, accepted = await world.delivered("cyc_inc000000001", _added("total"))
    await world.progress.cycle_ended(first, first_run, CycleStopReason.SEQUENCE_COMPLETED)
    second, second_run, refused = await world.delivered("cyc_inc000000002", _added("count"))

    await world.progress.cycle_ended(second, second_run, CycleStopReason.SEQUENCE_COMPLETED)

    stored = await world.campaigns.get_campaign(CID)
    [decide] = await world.decisions(second.cycle_id)
    assert await world.promotions(second.cycle_id) == []
    assert (stored.accepted.cycle_id, stored.accepted.commit) == (first.cycle_id, accepted)
    assert await world.branch() == accepted
    assert refused[:12] in decide.binding["promotion_refused"]
    assert accepted[:12] in decide.binding["promotion_refused"]
    assert decide.binding["unbuilt"].startswith(f"cycle {second.cycle_id} was accepted and not")
    assert stored.state is CampaignState.ESCALATED
    assert await world.campaigns.pending_launch_intents() == []


async def test_a_failed_increment_leaves_the_branch_and_keeps_its_capture_off_it(tmp_path):
    """§7.5. The product's checks accepted the change and it was captured, but the increment's
    own evaluation rejected it. Bugs caught: a rejected increment's capture moved onto the
    branch; or its candidate commit lost, when it is the failure's evidence."""
    world = _World(tmp_path)
    await world.started()
    cycle, run, captured = await world.delivered(
        "cyc_inc000000001", _added("total"), evaluation="rejected"
    )

    await world.progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)

    stored = await world.campaigns.get_campaign(CID)
    assert await world.promotions(cycle.cycle_id) == []
    assert stored.accepted.commit == world.repo.second_commit
    assert await world.branch() == world.repo.second_commit
    capture_ref = f"refs/squadops/{cycle.cycle_id}/{run.run_id}"
    assert await world.clones.ref_commit(PROJECT, capture_ref) == captured


class _FailsOnce:
    """The managed clone, whose ref move fails once at the ``at``-th call: with the clone's own
    error (``SourceUnavailable``, a lock held), or with the process stopping (``ConnectionError``)
    after the promotion's row has committed."""

    def __init__(self, clones: GitSourceRepository, at: int, error: Exception) -> None:
        self._clones, self._at, self._error = clones, at, error
        self.calls = 0

    def __getattr__(self, name):
        return getattr(self._clones, name)

    async def update_ref(self, *args, **kwargs):
        self.calls += 1
        if self.calls == self._at:
            raise self._error
        return await self._clones.update_ref(*args, **kwargs)


async def test_a_restart_moves_a_ref_its_failed_follow_left_behind_the_row(tmp_path):
    """§24cd point 2: the row is the authority and the ref its projection. The increment's follow
    failed in the clone (logged, never raised), so the campaign decided with its branch's ref
    still at the record's commit. Bugs caught: a ref left behind its row for good, so the clone's
    branch (and any review request read from it) misses an accepted increment; or a re-sync that
    moves a ref already at its row, every startup."""
    from squadops.api.runtime.main import _resume_campaigns

    world = _World(tmp_path)
    flaky = _FailsOnce(world.clones, 2, SourceUnavailable("cannot lock ref", reason="update_ref"))
    world.progress = world.progress_on(flaky)
    await world.started()
    cycle, run, captured = await world.delivered("cyc_inc000000001", _added("total"))
    await world.progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)
    behind = await world.branch()
    progress = world.progress_on(world.clones)

    await _resume_campaigns(_restarted(world, progress))

    assert behind == world.repo.second_commit
    assert (await world.campaigns.get_campaign(CID)).accepted.commit == captured
    assert await world.branch() == captured
    assert await progress.resync_campaign_branches() == []


async def test_a_restart_between_the_promotion_and_its_ref_promotes_once_and_decides_once(
    tmp_path,
):
    """§12a across the gap §24cd point 2 opens. The process stopped after the increment's PROMOTE
    row committed and before its ref moved or its decision was written. At startup the ref is
    moved to the row, and the cycle is heard again from its recorded ending. Bugs caught: the
    re-hearing refusing the capture as built on a commit other than the head, which its own
    promotion had just made it; a second PROMOTE row; or no decision, so the campaign sits."""
    from squadops.api.runtime.main import _resume_campaigns

    world = _World(tmp_path)
    world.progress = world.progress_on(_FailsOnce(world.clones, 2, ConnectionError("stopped")))
    await world.started()
    cycle, run, captured = await world.delivered("cyc_inc000000001", _added("total"))
    await world.cycles.record_cycle_end(
        RecordedEnd(cycle.cycle_id, run.run_id, CycleStopReason.SEQUENCE_COMPLETED)
    )
    with pytest.raises(ConnectionError):
        await world.progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)
    state = _restarted(world, world.progress_on(world.clones), cycle.cycle_id)

    await _resume_campaigns(state)
    await _resume_campaigns(state)

    [decide] = await world.decisions(cycle.cycle_id)
    assert len(await world.promotions(cycle.cycle_id)) == 1
    assert "promotion_refused" not in decide.binding
    assert (await world.campaigns.get_campaign(CID)).accepted.commit == captured
    assert await world.branch() == captured
