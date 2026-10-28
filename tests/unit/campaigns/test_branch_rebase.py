"""A repository-backed campaign's branch when upstream moves (SIP-0109 §24bv point 4, §24cd
points 2–5, §24cm).

Entered at ``CampaignLaunchService.drain()``, as the runtime's sweep and every intent-writing row
call it, with the launcher's ``before_launch`` wired as ``main`` wires it. The Project is the
shared fixture's Tally, in the world ``test_campaign_branch`` builds: a real managed clone, a real
workspace store and sandbox service (X-3a's copy as local processes), real deliveries and a real
baseline capture. Upstream moves by a commit to the fixture's own repository, and the Project is
reconciled there as its owner would: synced, configured and baselined at the new commit.

The increments here are launched with the stack-less ``validate`` profile, standing in for H.4's
source-backed increment profile, as ``test_campaign_launch_head`` does.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime, timedelta
from functools import partial
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.api.campaign_launch import (
    LAUNCHER_ACTOR,
    CampaignLaunchService,
    reconciled_at_pin,
)
from squadops.api.routes.cycles.cycles import CreationPorts
from squadops.campaigns.branch_rebase import (
    INHERITED_BASELINE,
    REBASE_VERIFICATION,
    UPSTREAM_MOVED,
    BranchRebase,
    RebasedHead,
    rebase_transition,
)
from squadops.campaigns.campaign_branch import (
    BranchBase,
    CampaignBranch,
    CampaignHead,
    campaign_ref,
    head,
)
from squadops.campaigns.continuation import (
    CampaignLimit,
    CycleEnding,
    EndedCycle,
    Guard,
    PendingAction,
    TerminalCause,
    campaign_continuation_decision,
)
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignOutcome,
    CampaignState,
    ControlOperation,
    ControlOperationRefused,
    ControlOutcome,
    CycleKind,
    LaunchIntentState,
    LaunchRequest,
    RefusalReason,
)
from squadops.campaigns.progress import CycleRecord, derive_counters
from squadops.contracts.cycle_request_profiles import cycle_request_body
from squadops.cycles.cycle_end import CycleStopReason
from squadops.cycles.models import Run
from squadops.cycles.verification_integrity import RunVerdict
from squadops.execution.source_delivery import SOURCE_VERIFICATION_TYPE, deliver_source_change
from squadops.projects.baseline import FAIL, INTRODUCED
from squadops.projects.derived_profile import Gap
from squadops.projects.development_configuration import parse_configuration
from squadops.projects.models import Rebased
from squadops.projects.workspaces import capture_inherited_baseline
from tests.fixtures.shared_contract.repository import _git, recorded, tracked_files
from tests.unit.api.test_campaign_calibration_record import PROJECT
from tests.unit.api.test_campaign_launch_head import _Deploys, _Executor, _squad
from tests.unit.campaigns.builders import campaign, move, policy, quiet_box
from tests.unit.campaigns.test_campaign_branch import CID, REPORT, _added, _FailsOnce, _restarted
from tests.unit.campaigns.test_campaign_branch import _World as _BranchWorld
from tests.unit.campaigns.test_progress import _assessment
from tests.unit.projects.test_workspaces import _LocalSandbox

S = CampaignState

#: A check upstream adds with its next commit: the report module offers only ``summarize``. An
#: increment that added a function to it regresses this check once rebased, though it passes on
#: upstream alone (§24cd point 5).
_NAMES_CHECK = b"""import unittest

import tally.report as report


class NameChecks(unittest.TestCase):
    def test_the_report_module_offers_only_summarize(self):
        offered = sorted(n for n, v in vars(report).items() if callable(v) and n[0] != "_")
        self.assertEqual(offered, ["summarize"])
"""
_UPSTREAM = {
    "GIT_AUTHOR_NAME": "Tally Maintainer",
    "GIT_AUTHOR_EMAIL": "maintainer@tally.example.invalid",
    "GIT_AUTHOR_DATE": "2026-03-02T10:00:00+00:00",
    "GIT_COMMITTER_NAME": "Tally Maintainer",
    "GIT_COMMITTER_EMAIL": "maintainer@tally.example.invalid",
    "GIT_COMMITTER_DATE": "2026-03-02T10:00:00+00:00",
}


@pytest.fixture(autouse=True)
def _sandbox_provider(monkeypatch):
    """#1568: the create-time sandbox preflight reads the provider from the process env."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


class _World(_BranchWorld):
    """``test_campaign_branch``'s Tally, with upstream that moves and the launcher that sees it."""

    def upstream(self, files: dict[str, bytes], message: str) -> str:
        """A commit upstream, by the product's own maintainer, on its main branch."""
        for path, content in files.items():
            target = self.repo.path / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        _git(self.repo.path, "add", "-A")
        _git(self.repo.path, "commit", "-q", "-m", message, env=_UPSTREAM)
        return _git(self.repo.path, "rev-parse", "HEAD").strip()

    async def reconciled(self, commit: str, *, checks: tuple[dict, ...] = ()) -> None:
        """The Project reconciled at ``commit``, as its owner does it: synced, a Development
        Configuration revision validated there, and the inherited baseline captured there."""
        await self.clones.sync(PROJECT, str(self.repo.path), "refs/heads/main")
        document = recorded("development_configuration", "valid")
        configuration = document["configuration"]
        revision = self.projects.configuration.revision + 1
        configuration["revision"] = revision
        configuration["validated_at_commit"] = commit
        configuration["technical"]["commands"]["checks"] += list(checks)
        self.projects.configuration = parse_configuration(document)
        self.projects.project = dataclasses.replace(
            self.projects.project,
            development_baseline_commit=commit,
            development_configuration_revision=revision,
        )
        await capture_inherited_baseline(
            PROJECT,
            registry=self.projects,
            repository=self.clones,
            sandbox=_LocalSandbox(self.tmp_path / f"baseline-{commit[:8]}"),
            actor="owner",
            idempotency_key=f"b-{commit}",
        )

    def service(
        self, *, propose=None, repository=None, frozen_on_runner=None
    ) -> CampaignLaunchService:
        """The launch service and its rebase, as ``main`` wires them."""
        squads = AsyncMock()
        squads.resolve_snapshot.return_value = (_squad(), "sha256:abc")
        creation = CreationPorts(
            project_registry=self.projects,
            squad_profile=squads,
            cycle_registry=self.cycles,
            deploy_registry=_Deploys(),
            artifact_vault=self.vault,
        )
        clones = repository or self.clones
        rebase = BranchRebase(
            campaigns=self.campaigns,
            projects=self.projects,
            repository=clones,
            sandbox=self.sandbox,
            vault=self.vault,
            branch=CampaignBranch(projects=self.projects, repository=clones),
            reconciled=partial(reconciled_at_pin, creation),
            propose=propose or self.progress.proposal_after_rebase,
            actor=LAUNCHER_ACTOR,
            frozen_on_runner=frozen_on_runner,
        )
        return CampaignLaunchService(
            campaigns=self.campaigns,
            creation=creation,
            flow_executor=_Executor(),
            event_bus=MagicMock(),
            box_verdict=quiet_box,
            before_launch=rebase.before_launch,
        )

    async def accepted(self, cycle_id: str = "cyc_inc000000001") -> str:
        """An increment accepted onto the branch: its capture is the head."""
        cycle, run, captured = await self.delivered(cycle_id, _added("total"))
        await self.progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)
        assert (await self.campaigns.get_campaign(CID)).accepted.commit == captured
        return captured

    async def proposing(self, key: str = "k-propose") -> str:
        """A fresh increment's intent, pending, as the owner's resume writes one (the proposal on
        a product's tree, §24bv point 5, isn't built). Returns its launch id."""
        result = await self.campaigns.transition(
            CID,
            move(S.AT_PROPOSAL, key, operation=ControlOperation.RESUME, launch=_increment()),
        )
        return result.intent.launch_id

    async def repairing(self, continues: str) -> str:
        """A repair of ``continues``'s increment, pending, bound to the head it failed on: the
        failed cycle decided first, as its end is heard."""
        failed = await self.cycles.get_cycle(continues)
        [run] = await self.cycles.list_runs(continues)
        await self.progress.cycle_ended(failed, run, CycleStopReason.SEQUENCE_COMPLETED)
        at = head(await self.campaigns.get_campaign(CID), await self.campaigns.control_log(CID))
        block = {
            "proposal_id": "prop_failed00001",
            "version": 1,
            "baseline_tree": at.tree_identity,
            "continues": continues,
        }
        body = cycle_request_body(
            "validate", squad_profile_id="full-38", user_values={"campaign_proposal": block}
        )
        result = await self.campaigns.transition(
            CID,
            move(
                S.REPAIRING,
                "k-repair",
                operation=ControlOperation.RESUME,
                launch=LaunchRequest(CycleKind.REPAIR, {"body": body}),
            ),
        )
        return result.intent.launch_id

    async def rows(self, operation: ControlOperation) -> list:
        return [
            e
            for e in await self.campaigns.control_log(CID)
            if e.operation is operation and e.outcome is ControlOutcome.APPLIED
        ]


def _increment(proposal_id: str = "prop_fresh000001") -> LaunchRequest:
    body = cycle_request_body(
        "validate",
        squad_profile_id="full-38",
        user_values={"campaign_proposal": {"proposal_id": proposal_id, "version": 1}},
        notes="an increment on the campaign branch",
    )
    return LaunchRequest(CycleKind.INCREMENT, {"body": body})


def _report_plus(name: str, world: _World) -> bytes:
    return tracked_files(world.repo.path, world.repo.second_commit)[REPORT] + _added(name)


async def test_upstream_moving_rebases_the_branch_and_the_next_increment_is_built_on_it(tmp_path):
    """§24bv point 4, the wiring, and #2761's G4 note 2. Upstream changed its README; the Project
    was reconciled there. The next drain rebases the branch, verifies its head, and launches the
    increment pinned at the rebased head, whose delivery is then compared with the rebase's own
    verification. Bugs caught:
    - the launcher launching on the old head, so the increment's capture is built on a base
      upstream has left and its review request carries upstream's change backwards;
    - the rebase verified nowhere ``head()`` reads, so ``require_campaign_head`` refuses every
      increment after it (the G4 note);
    - the verification stored as no run's but read as one, so delivery finds no regression
      baseline and refuses the next increment;
    - the ref left at the old head, so the review request is pushed without upstream's change;
    - the row missing what a reader needs: the bases, heads and replayed commits."""
    world = _World(tmp_path)
    await world.started()
    first = await world.accepted()
    onto = world.upstream({"README.md": b"Tally, as upstream now describes it\n"}, "docs")
    await world.reconciled(onto)
    launch_id = await world.proposing()

    await world.service().drain()

    [rebased] = await world.rows(ControlOperation.BRANCH_REBASED)
    stored = await world.campaigns.get_campaign(CID)
    b = rebased.binding
    clone = tmp_path / "cache" / "prj-tally.git"
    files = tracked_files(clone, b["commit"])
    assert (b["base_before"], b["base"], b["head_before"]) == (
        world.repo.second_commit,
        onto,
        first,
    )
    assert [old for old, _new in b["replayed"]] == [first] and b["dropped"] == []
    assert _git(clone, "rev-parse", f"{b['commit']}^").strip() == onto
    assert files["README.md"] == b"Tally, as upstream now describes it\n"
    assert files[REPORT].endswith(_added("total"))
    assert (b["verification"], b["development_configuration_revision"]) == (REBASE_VERIFICATION, 2)
    assert stored.accepted.commit == b["commit"] == await world.branch()
    assert stored.accepted.identity == FileTree.of(files).identity == b["identity"]
    assert (
        head(stored, await world.campaigns.control_log(CID)).previous_verification_ref
        == (b["verification_ref"])
    )
    _ref, document = await world.vault.retrieve(b["verification_ref"])
    verification = json.loads(document)
    assert (verification["verdict"], verification["baseline_commit"]) == ("accepted", onto)
    assert (verification["cycle_id"], verification["rebase"]["head_before"]) == (None, first)
    [intent] = [i for i in await world.campaigns.launch_intents(CID) if i.launch_id == launch_id]
    assert intent.state is LaunchIntentState.LAUNCHED
    cycle = await world.cycles.get_cycle(intent.cycle_id)
    context = cycle.source_context
    assert (context.pinned_commit, context.previous_verification_ref) == (
        b["commit"],
        b["verification_ref"],
    )
    assert context.development_baseline_commit == onto

    # The increment built on the rebased head delivers against the rebase's verification.
    run = Run(
        run_id="run_afterrebase1", cycle_id=cycle.cycle_id, run_number=1, status="completed",
        initiated_by="system", resolved_config_hash="cfg", workload_type="implementation",
    )  # fmt: skip
    await world.cycles.create_run(run)
    emitted = await world._stored(
        cycle, run, "tally/notes.py", "source", b'"""Notes on the ledger."""\n'
    )
    delivery = await deliver_source_change(
        cycle, run.run_id, [emitted], vault=world.vault, registry=world.projects,
        repository=world.clones, sandbox=world.sandbox,
    )  # fmt: skip
    assert delivery.verification.verdict == "accepted", delivery.verification.summary()
    assert delivery.verification.regression_baseline_ref == b["verification_ref"]
    assert delivery.captured_commit is not None
    assert _git(clone, "rev-parse", f"{delivery.captured_commit}^").strip() == b["commit"]

    _identity, _package, digest_id = await world.progress.materialize_package(CID)
    _ref, digest = await world.vault.retrieve(digest_id)
    assert (
        f"- rebased onto `{onto[:12]}` (revision 2): head `{first[:12]}` → `{b['commit'][:12]}`"
    ) in digest.decode()


async def test_a_pending_repair_is_superseded_and_the_fresh_proposal_launches_on_the_new_head(
    tmp_path,
):
    """§24cd point 2. A repair, bound to the head its increment failed on, was pending when
    upstream moved. The rebase supersedes it in its own row, and row 6's fresh proposal is the
    launch. Bugs caught:
    - the repair launched on the rebased head, continuing a candidate built on a tree the head
      left, so its capture reverts upstream's change;
    - the repair left pending beside the proposal, so a later drain launches both;
    - the abandonment counted toward ``max_unaccepted_increments`` (D10), so upstream's
      activity ends the campaign as no progress;
    - the fresh proposal written and not launched until some other row drains."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted()
    failed, failed_run, _captured = await world.delivered(
        "cyc_inc000000002", _added("count"), evaluation="rejected"
    )
    repair = await world.repairing(failed.cycle_id)
    onto = world.upstream({"README.md": b"Tally, moved on\n"}, "docs")
    await world.reconciled(onto)
    proposed = []

    async def propose(campaign, continued):
        proposed.append((campaign.accepted.commit, continued))
        return _increment("prop_afterrebase")

    await world.service(propose=propose).drain()

    [rebased] = await world.rows(ControlOperation.BRANCH_REBASED)
    intents = {i.launch_id: i for i in await world.campaigns.launch_intents(CID)}
    fresh = intents[rebased.launch_id]
    assert intents[repair].state is LaunchIntentState.SUPERSEDED
    assert (rebased.binding["superseded_launch_id"], rebased.binding["abandoned"]) == (
        repair,
        {"kind": "repair", "abandoned_as": UPSTREAM_MOVED},
    )
    assert (rebased.prior_state, rebased.next_state) == (S.REPAIRING, S.AT_PROPOSAL)
    assert proposed == [(rebased.binding["commit"], failed.cycle_id)]
    assert (fresh.cycle_kind, fresh.state) == (CycleKind.INCREMENT, LaunchIntentState.LAUNCHED)
    cycle = await world.cycles.get_cycle(fresh.cycle_id)
    assert cycle.source_context.pinned_commit == rebased.binding["commit"]
    assert await world.campaigns.pending_launch_intents() == []
    log = await world.campaigns.control_log(CID)
    counters = derive_counters(
        await world.campaigns.get_campaign(CID), log, [], ending=CycleEnding.ASSESSED,
        now=datetime.now(UTC), objective_met=False,
    )  # fmt: skip
    assert counters.unaccepted_increments == 0


async def test_the_supersession_escalates_while_a_products_proposal_is_unbuilt(tmp_path):
    """The real proposal path (``CampaignProgress.proposal_after_rebase``) on a repository-backed
    campaign, where §24bv point 5 isn't built. Bug caught: the superseded repair leaving the
    campaign proposing with no intent, so it sits with nothing pending and nothing escalated."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted()
    failed, _run, _captured = await world.delivered(
        "cyc_inc000000002", _added("count"), evaluation="rejected"
    )
    repair = await world.repairing(failed.cycle_id)
    await world.reconciled(world.upstream({"README.md": b"moved\n"}, "docs"))

    await world.service().drain()

    [rebased] = await world.rows(ControlOperation.BRANCH_REBASED)
    assert rebased.next_state is S.ESCALATED and rebased.launch_id is None
    assert "§24bv point 5" in rebased.binding["unbuilt"]
    assert (await world.campaigns.get_launch_intent(repair)).state is LaunchIntentState.SUPERSEDED
    assert (await world.campaigns.get_campaign(CID)).state is S.ESCALATED


async def test_a_conflicting_upstream_escalates_with_the_intent_pending_and_nothing_moved(
    tmp_path,
):
    """§24bv point 4: a rebase that conflicts refuses the launch, and nothing resolves itself.
    Upstream appended its own function where the accepted increment appended ``total``. Bugs
    caught: one side taken silently; the accepted tree or the ref moved; the intent consumed, so
    the owner's resume after resolving it has nothing to launch."""
    world = _World(tmp_path)
    await world.started()
    first = await world.accepted()
    onto = world.upstream({REPORT: _report_plus("largest", world)}, "upstream's own report")
    await world.reconciled(onto)
    launch_id = await world.proposing()

    await world.service().drain()

    stored = await world.campaigns.get_campaign(CID)
    refused = (await world.campaigns.control_log(CID))[-1]
    assert refused.operation is ControlOperation.LAUNCH_REFUSED
    assert refused.binding["refusal"].startswith("CAMPAIGN_BRANCH_CONFLICT: ")
    assert f"{first[:12]} doesn't apply on {onto[:12]}" in refused.binding["refusal"]
    assert REPORT in refused.binding["refusal"]
    assert stored.state is S.ESCALATED
    assert (stored.accepted.commit, await world.branch()) == (first, first)
    assert await world.rows(ControlOperation.BRANCH_REBASED) == []
    assert (await world.campaigns.get_launch_intent(launch_id)).state is LaunchIntentState.PENDING


async def test_a_rebased_head_whose_checks_regress_escalates_naming_its_verification(tmp_path):
    """§24cd point 5. Upstream added a check that the report module offers only ``summarize``:
    it passes upstream, and the rebased head, which carries the accepted ``total``, fails it.
    Bugs caught: the regression attributed to the next increment, which it would be if the head
    were accepted unverified; the refusal naming no evidence a reader can open."""
    world = _World(tmp_path)
    await world.started()
    first = await world.accepted()
    onto = world.upstream({"checks/check_names.py": _NAMES_CHECK}, "a check on the report's names")
    await world.reconciled(
        onto,
        checks=(
            {
                "id": "names",
                "argv": ["python3", "-m", "unittest", "discover", "-s", "checks", "-p",
                         "check_names.py"],
            },
        ),
    )  # fmt: skip
    launch_id = await world.proposing()

    await world.service().drain()

    refused = (await world.campaigns.control_log(CID))[-1]
    refusal = refused.binding["refusal"]
    assert refusal.startswith("REBASED_HEAD_REGRESSED: ")
    assert "names failed where the baseline did not" in refusal
    ref = refusal.split("(verification ")[1].split(")")[0]
    _stored, document = await world.vault.retrieve(ref)
    checks = {c["id"]: c for c in json.loads(document)["checks"]}
    assert (checks["names"]["result"], checks["names"]["attribution"]) == (FAIL, INTRODUCED)
    assert (
        (await world.campaigns.get_campaign(CID)).accepted.commit == first == await world.branch()
    )
    assert (await world.campaigns.get_launch_intent(launch_id)).state is LaunchIntentState.PENDING


@pytest.mark.parametrize("case", ["no-baseline", "drift-unreconciled", "blocking-gap"])
async def test_the_launcher_never_reconciles_a_project_and_never_rebases_onto_one_unreconciled(
    tmp_path, case
):
    """§24cd point 3. Upstream moved and the Project is part-way: validated at the new commit
    with no baseline captured there; or reconciled, then a sync read relevant drift past it; or
    reconciled with a profile whose blocking gap stops all work. Each refuses the launch before
    any rebase, escalating with the intent pending. Bugs caught: a rebase onto a commit whose
    baseline no one captured, so its verification compares with the wrong tree; the launcher
    capturing it itself; a superseded repair for a rebase that then can't launch."""
    world = _World(tmp_path)
    await world.started()
    first = await world.accepted()
    onto = world.upstream({"README.md": b"moved\n"}, "docs")
    await world.reconciled(onto)
    if case == "no-baseline":
        world.projects.baseline = dataclasses.replace(
            world.projects.baseline, commit=world.repo.second_commit
        )
    elif case == "drift-unreconciled":
        world.projects.syncs.append(_drift(onto, world.upstream({"tally/ledger.py": b"x\n"}, "up")))
    else:
        missing = Gap(
            "missing_toolchain", "blocking", "python3", ("**",),
            "python3 isn't in the checks' image (invented for the test)", "a python3 image",
        )  # fmt: skip
        profile = world.projects.profile
        world.projects.profile = dataclasses.replace(profile, gaps=(*profile.gaps, missing))
    launch_id = await world.proposing()

    await world.service().drain()

    refused = (await world.campaigns.control_log(CID))[-1]
    code = {
        "no-baseline": "PROJECT_STATE_CONFLICT",
        "drift-unreconciled": "STALE_SOURCE_PRECONDITION",
        "blocking-gap": "PROJECT_STATE_CONFLICT",
    }[case]
    assert refused.operation is ControlOperation.LAUNCH_REFUSED
    assert refused.binding["refusal"].startswith(f"{code}: "), refused.binding["refusal"]
    assert await world.rows(ControlOperation.BRANCH_REBASED) == []
    assert await world.branch() == first
    assert (await world.campaigns.get_launch_intent(launch_id)).state is LaunchIntentState.PENDING


def _drift(baseline: str, upstream: str) -> dict:
    """A sync that read upstream past ``baseline`` with drift in a unit's evidence (H.2)."""
    return {
        "baseline_commit": baseline,
        "upstream_commit": upstream,
        "drift": {"relevant": ["tally/ledger.py"]},
        "synced_at": "2026-10-28T12:00:00+00:00",
    }


@pytest.mark.parametrize("merged", [True, False], ids=["the-owners-merge", "nothing-accepted"])
async def test_a_head_upstream_already_holds_rebases_to_the_reconciled_commit_unverified(
    tmp_path, merged
):
    """§24cd point 4, and #2761's G4 note 2's other half. Either the owner merged the branch's
    review request, or the Project reconciled before any increment was accepted. Either way the
    rebased head is the reconciled commit itself, whose baseline is the inherited one, so no
    verification is run or named and the next increment is pinned there. Bugs caught: the head
    refused for naming no verification (G4 note 2); the branch's commits replayed on the merge
    as empty commits; a needless run of the checks the baseline already ran."""
    world = _World(tmp_path)
    await world.started()
    before = await world.accepted() if merged else world.repo.second_commit
    if merged:
        clone = str(tmp_path / "cache" / "prj-tally.git")
        _git(world.repo.path, "fetch", "-q", clone, f"{campaign_ref(CID)}:refs/heads/review")
        _git(
            world.repo.path, "merge", "-q", "--no-ff", "-m", "Merge review", "review", env=_UPSTREAM
        )
        onto = _git(world.repo.path, "rev-parse", "HEAD").strip()
    else:
        onto = world.upstream({"README.md": b"moved\n"}, "docs")
    await world.reconciled(onto)
    launch_id = await world.proposing()

    await world.service().drain()

    [rebased] = await world.rows(ControlOperation.BRANCH_REBASED)
    b = rebased.binding
    assert (b["head_before"], b["commit"], b["replayed"]) == (before, onto, [])
    assert (b["verification"], b["verification_ref"]) == (INHERITED_BASELINE, None)
    assert b["dropped"] == ([before] if merged else [])
    verifications = await world.vault.list_artifacts(artifact_type=SOURCE_VERIFICATION_TYPE)
    assert [a for a in verifications if a.metadata.get("branch_rebase")] == []
    intent = await world.campaigns.get_launch_intent(launch_id)
    cycle = await world.cycles.get_cycle(intent.cycle_id)
    assert (cycle.source_context.pinned_commit, cycle.source_context.previous_verification_ref) == (
        onto,
        None,
    )


async def test_a_restart_between_the_rebase_row_and_its_ref_moves_the_ref_at_startup(tmp_path):
    """§24cd point 2: the row commits first and the ref follows. The follow failed (the clone's
    lock), and at startup ``_resume_campaigns`` moves the ref to the row. Bugs caught: the ref
    left at the pre-rebase head for good, so the review request pushes a branch without
    upstream; a second rebase at the next drain, from a base the row already moved."""
    from squadops.api.runtime.main import _resume_campaigns
    from squadops.projects.models import SourceUnavailable

    world = _World(tmp_path)
    await world.started()
    first = await world.accepted()
    onto = world.upstream({"README.md": b"moved\n"}, "docs")
    await world.reconciled(onto)
    await world.proposing()
    flaky = _FailsOnce(world.clones, 1, SourceUnavailable("cannot lock ref", reason="update_ref"))

    await world.service(repository=flaky).drain()
    behind = await world.branch()
    await _resume_campaigns(_restarted(world, world.progress_on(world.clones)))
    await world.proposing("k-propose-2")
    await world.service().drain()

    [rebased] = await world.rows(ControlOperation.BRANCH_REBASED)
    assert behind == first
    assert await world.branch() == rebased.binding["commit"]


async def _rebased_five_times(max_unaccepted: int = 1, **limits) -> tuple:
    """A repository-backed campaign whose upstream moved five times, each time while a repair was
    pending: each rebase's row, from ``rebase_transition``, superseded the repair and wrote a
    fresh proposal. Six increment cycles were launched in all. Returns the registry and the
    campaign as its policy reads."""
    registry = MemoryCampaignRegistry()
    on_tally = campaign(
        CID,
        project_id=PROJECT,
        policy=policy(max_unaccepted_increments=max_unaccepted, **limits),
    )
    await registry.create_campaign(
        on_tally, actor="owner", actor_role="owner", reason="r", idempotency_key="create"
    )
    await registry.transition(CID, move(S.CALIBRATING, "start", operation=ControlOperation.START))
    commits = [f"{i:x}" * 40 for i in range(1, 12)]
    record = AcceptedTree("t" * 64, calibration_record_id="cal_tally00001", commit=commits[0])
    await registry.transition(
        CID,
        move(
            S.CALIBRATING, "promote", operation=ControlOperation.PROMOTE, accepted=record,
            binding={"calibration_record_id": "cal_tally00001", "commit": commits[0],
                     "development_configuration_revision": 1, "identity": "t" * 64},
        ),
    )  # fmt: skip
    base = BranchBase(commits[0], 1)
    for i in range(5):
        await registry.transition(CID, move(S.ESCALATED, f"hold-{i}"))
        repair = await registry.transition(
            CID,
            move(
                S.REPAIRING, f"repair-{i}", operation=ControlOperation.RESUME,
                launch=LaunchRequest(CycleKind.REPAIR, {"body": {}}),
            ),
        )  # fmt: skip
        current = await registry.get_campaign(CID)
        onto = BranchBase(commits[2 * i + 1], i + 2)
        made = RebasedHead(Rebased(commits[2 * i + 2], (), ()), f"{i}" * 64, None, "inherited")
        await registry.transition(
            CID,
            rebase_transition(
                current, repair.intent, base=base,
                before=CampaignHead(current.accepted.commit, current.accepted.identity, None),
                onto=onto, made=made, launch=_increment(f"prop_fresh{i:06d}"),
                unbuilt=None, actor=LAUNCHER_ACTOR,
            ),
        )  # fmt: skip
        base = onto
    return registry, await registry.get_campaign(CID)


@pytest.mark.parametrize("limit", ["cycles", "tokens", "time"])
async def test_repeated_upstream_movement_still_exhausts_cycles_tokens_and_time(limit):
    """D10: ``upstream_moved`` is exempt from ``max_unaccepted_increments`` only. Five rebases
    each superseded a repair, under a policy that allows one unaccepted increment, and the sixth
    increment's end is decided. Entered at the decision's own readers (``derive_counters`` over
    the registry's log, then ``campaign_continuation_decision``), as ``cycle_ended`` calls them.
    Bugs caught: the exemption reaching cycles, tokens or time, so a busy upstream runs the
    campaign without bound; or the abandonments counted as no progress (row 4's
    ``unaccepted_increments``), so upstream's activity fails a campaign whose squad didn't."""
    limits = {
        "cycles": dict(max_cycles=6),
        "tokens": dict(budget_tokens=600, max_cycles=100),
        "time": dict(max_elapsed_s=3600, max_cycles=100),
    }[limit]
    registry, at = await _rebased_five_times(**limits)
    log = await registry.control_log(CID)
    intents = await registry.launch_intents(CID)
    launched = [CycleRecord(CycleKind.INCREMENT, 100) for _ in range(6)]
    elapsed = timedelta(hours=2) if limit == "time" else timedelta(minutes=1)
    ended = EndedCycle(
        "cyc_last00000001", CycleKind.INCREMENT, CycleEnding.ASSESSED, RunVerdict.REJECTED, False
    )

    counters = derive_counters(
        at, log, launched, ending=CycleEnding.ASSESSED, now=log[0].committed_at + elapsed,
        objective_met=False,
    )  # fmt: skip
    decision = campaign_continuation_decision(
        at, counters, ended, _assessment("cyc_last00000001", RunVerdict.REJECTED)
    )

    assert [i.state for i in intents if i.cycle_kind is CycleKind.REPAIR] == [
        LaunchIntentState.SUPERSEDED
    ] * 5
    assert counters.unaccepted_increments == 0
    if limit == "cycles":
        assert (decision.row, decision.outcome, decision.cause) == (
            4,
            CampaignOutcome.EXHAUSTED,
            TerminalCause.TOTAL_CYCLES,
        )
    else:
        assert (decision.action, decision.guard, decision.paused_by) == (
            PendingAction.REPAIR,
            Guard.PAUSED,
            {"tokens": CampaignLimit.BUDGET, "time": CampaignLimit.ELAPSED_TIME}[limit],
        )


async def test_a_rebase_superseding_a_repair_launched_meanwhile_is_refused_and_moves_nothing():
    """The race §24cd point 2's one transaction closes: another launcher launched the repair
    between this launcher's read and its rebase. Bugs caught: the rebase applied anyway, so the
    campaign proposes while the repair runs, two cycles on one increment; or the accepted tree
    moved by a refused row."""
    registry, at = await _rebased_five_times(max_unaccepted=2)
    await registry.transition(CID, move(S.ESCALATED, "hold-race"))
    repair = await registry.transition(
        CID,
        move(
            S.REPAIRING, "repair-race", operation=ControlOperation.RESUME,
            launch=LaunchRequest(CycleKind.REPAIR, {"body": {}}),
        ),
    )  # fmt: skip
    current = await registry.get_campaign(CID)
    await registry.mark_launch_intent_launched(
        repair.intent.launch_id, "cyc_repair000001", actor="another-launcher"
    )
    made = RebasedHead(Rebased("e" * 40, (), ()), "9" * 64, None, "inherited")

    with pytest.raises(ControlOperationRefused) as refused:
        await registry.transition(
            CID,
            rebase_transition(
                current, repair.intent, base=BranchBase("b" * 40, 6),
                before=CampaignHead(current.accepted.commit, current.accepted.identity, None),
                onto=BranchBase("d" * 40, 7), made=made, launch=_increment(),
                unbuilt=None, actor=LAUNCHER_ACTOR,
            ),
        )  # fmt: skip

    after = await registry.get_campaign(CID)
    assert refused.value.entry.refusal is RefusalReason.STALE_STATE
    assert (after.state, after.accepted) == (S.REPAIRING, current.accepted)
    assert (await registry.get_launch_intent(repair.intent.launch_id)).state is (
        LaunchIntentState.LAUNCHED
    )
    assert [i.cycle_kind for i in await registry.pending_launch_intents()] == [
        CycleKind.INCREMENT
    ] * 5


async def test_a_revision_only_reconciliation_reverifies_the_head_where_it_stands(tmp_path):
    """§24bv point 4 as built (§24cm): a Project re-configured at the same commit gets a new
    Development Configuration revision, and the head's verification ran at the old one, which
    delivery refuses to compare with (FR-20). So the head is re-verified at the new revision, and
    stays the same commit. Bugs caught: the base compared by commit alone, so every increment
    after a re-configuration is refused for a verification at another revision; or the head
    rewritten for nothing."""
    world = _World(tmp_path)
    await world.started()
    first = await world.accepted()
    await world.reconciled(world.repo.second_commit)
    launch_id = await world.proposing()

    await world.service().drain()

    [rebased] = await world.rows(ControlOperation.BRANCH_REBASED)
    b = rebased.binding
    assert (b["base_before"], b["base"], b["commit"]) == (
        world.repo.second_commit,
        world.repo.second_commit,
        first,
    )
    assert (
        b["development_configuration_revision_before"],
        b["development_configuration_revision"],
    ) == (1, 2)
    _ref, document = await world.vault.retrieve(b["verification_ref"])
    assert json.loads(document)["development_configuration_revision"] == 2
    intent = await world.campaigns.get_launch_intent(launch_id)
    context = (await world.cycles.get_cycle(intent.cycle_id)).source_context
    assert (context.pinned_commit, context.previous_verification_ref) == (
        first,
        b["verification_ref"],
    )
    assert context.development_configuration_revision == 2


async def test_upstream_moving_twice_rebases_from_where_the_last_rebase_left_the_branch(tmp_path):
    """§24bv point 4, twice. Upstream moved, the branch was rebased and an increment launched;
    upstream moved again. Bugs caught: the branch's base read from the calibration record for
    good, so the second rebase replays upstream's own first commit as the branch's, and its row
    names a base the branch left; or the second rebase skipped as a replay of the first."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted()
    first_onto = world.upstream({"README.md": b"first move\n"}, "docs")
    await world.reconciled(first_onto)
    await world.proposing()
    await world.service().drain()
    second_onto = world.upstream({"CONTRIBUTING.md": b"second move\n"}, "contributing")
    await world.reconciled(second_onto)
    await world.proposing("k-propose-2")

    await world.service().drain()

    first, second = await world.rows(ControlOperation.BRANCH_REBASED)
    assert (second.binding["base_before"], second.binding["head_before"]) == (
        first_onto,
        first.binding["commit"],
    )
    assert [old for old, _new in second.binding["replayed"]] == [first.binding["commit"]]
    assert (second.binding["base"], await world.branch()) == (second_onto, second.binding["commit"])


class _RebaseRefuses:
    """The managed clone, whose rebase refuses ``times`` times with ``reason``, as the Git adapter
    refuses: then rebases for real."""

    def __init__(self, clones, reason: str, times: int = 1) -> None:
        self._clones, self._reason, self._left = clones, reason, times

    def __getattr__(self, name):
        return getattr(self._clones, name)

    async def rebase(self, *args, **kwargs):
        from squadops.projects.models import SourceUnavailable

        if self._left:
            self._left -= 1
            raise SourceUnavailable(f"invented refusal ({self._reason})", reason=self._reason)
        return await self._clones.rebase(*args, **kwargs)


async def _one_sweep(world: _World, service) -> None:
    """One pass of the runtime's campaign sweep (``main._sweep_campaigns``), with this launch
    service and the world's own progress."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import patch

    from squadops.api.runtime import main

    progress = SimpleNamespace(
        sweep_ruling_bounds=AsyncMock(),
        rehear_ended=AsyncMock(return_value=[]),
        rehear_calibration_records=AsyncMock(return_value=[]),
        resync_campaign_branches=AsyncMock(return_value=[]),
    )
    with (
        patch.object(
            main.asyncio, "sleep", AsyncMock(side_effect=[None, asyncio.CancelledError()])
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await main._sweep_campaigns(
            SimpleNamespace(campaign_launch=service, campaign_progress=progress)
        )


@pytest.mark.parametrize(
    ("reason", "code"),
    [
        ("not_linear", "CAMPAIGN_BRANCH_UNREBASEABLE"),
        ("not_an_ancestor", "CAMPAIGN_BRANCH_UNREBASEABLE"),
        ("commit_missing", "CAMPAIGN_BRANCH_UNAVAILABLE"),
    ],
)
async def test_a_branch_the_clone_cant_rebase_escalates_with_the_intent_pending(
    tmp_path, reason, code
):
    """#2770's second review, P2: the clone's refusals that no retry gets past (a merge commit on
    the branch, a base not in its history, a commit the clone lacks) escalate by name, as a
    conflict does. Bugs caught: the refusal escaping the launcher's escalation as a fault, so the
    campaign repeats it at every drain and no one is told; the intent consumed or the branch
    moved by a rebase that never happened."""
    world = _World(tmp_path)
    await world.started()
    first = await world.accepted()
    await world.reconciled(world.upstream({"README.md": b"moved\n"}, "docs"))
    launch_id = await world.proposing()

    await world.service(repository=_RebaseRefuses(world.clones, reason)).drain()

    refused = (await world.campaigns.control_log(CID))[-1]
    assert refused.operation is ControlOperation.LAUNCH_REFUSED
    assert refused.binding["refusal"].startswith(f"{code}: "), refused.binding["refusal"]
    assert f"({reason})" in refused.binding["refusal"]
    assert (await world.campaigns.get_campaign(CID)).state is S.ESCALATED
    assert await world.rows(ControlOperation.BRANCH_REBASED) == []
    assert await world.branch() == first
    assert (await world.campaigns.get_launch_intent(launch_id)).state is LaunchIntentState.PENDING


async def test_a_lost_managed_clone_escalates_as_unavailable(tmp_path):
    """The real clone moved aside (the only way it is lost, #2761's G4 note 3): the Git adapter
    refuses ``not_cloned``. Bug caught: a missing clone read as a transient fault, repeated every
    drain while nothing can bring it back."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted()
    await world.reconciled(world.upstream({"README.md": b"moved\n"}, "docs"))
    launch_id = await world.proposing()
    (tmp_path / "cache" / "prj-tally.git").rename(tmp_path / "cache" / "moved-aside.git")

    await world.service().drain()

    refused = (await world.campaigns.control_log(CID))[-1]
    assert refused.binding["refusal"].startswith("CAMPAIGN_BRANCH_UNAVAILABLE: ")
    assert "(not_cloned)" in refused.binding["refusal"]
    assert (await world.campaigns.get_launch_intent(launch_id)).state is LaunchIntentState.PENDING


async def test_an_infrastructure_fault_writes_nothing_and_the_sweeps_drain_repeats_it(tmp_path):
    """#2770's second review, P2: a fault a retry can get past (git timing out) is not the
    operator's. Nothing is written, the campaign stays where it was with its intent pending, and
    the sweep's drain (``main._sweep_campaigns``) repeats the launch. Bugs caught: a timeout
    escalated to the owner, who has nothing to resolve; or the launch left until the next row
    that writes an intent, which a waiting campaign never writes."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted()
    await world.reconciled(world.upstream({"README.md": b"moved\n"}, "docs"))
    launch_id = await world.proposing()
    state_before = (await world.campaigns.get_campaign(CID)).state
    rows_before = len(await world.campaigns.control_log(CID))
    service = world.service(repository=_RebaseRefuses(world.clones, "timeout"))

    await service.drain()
    after_fault = await world.campaigns.get_campaign(CID)
    rows_after_fault = len(await world.campaigns.control_log(CID))
    await _one_sweep(world, service)

    assert (after_fault.state, rows_after_fault) == (state_before, rows_before)
    [rebased] = await world.rows(ControlOperation.BRANCH_REBASED)
    assert await world.branch() == rebased.binding["commit"]
    assert (await world.campaigns.get_launch_intent(launch_id)).state is LaunchIntentState.LAUNCHED


async def test_a_runtime_with_no_sandbox_escalates_its_rebased_head_as_unverifiable(tmp_path):
    """The edge: the runtime has no sandbox client, so the rebased head's checks can't run.
    Bug caught: the head accepted unverified, or the refusal repeated every drain as a fault."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted()
    await world.reconciled(world.upstream({"README.md": b"moved\n"}, "docs"))
    await world.proposing()
    world.sandbox = None

    await world.service().drain()

    refused = (await world.campaigns.control_log(CID))[-1]
    assert refused.binding["refusal"].startswith("REBASED_HEAD_UNVERIFIABLE: ")
    assert await world.rows(ControlOperation.BRANCH_REBASED) == []


async def _with_a_frozen_criterion(world: _World) -> None:
    """The accepted increment's promotion, as if its evaluation had frozen one criterion."""
    stored = await world.campaigns.get_campaign(CID)
    at = head(stored, await world.campaigns.control_log(CID))
    await world.campaigns.transition(
        CID,
        move(
            stored.state, "k-freeze", operation=ControlOperation.PROMOTE, accepted=stored.accepted,
            binding={"cycle_id": stored.accepted.cycle_id, "identity": at.tree_identity,
                     "commit": at.commit, "verification_ref": at.previous_verification_ref,
                     "frozen_criteria": [{"criterion_id": "crit_total", "test_file": "t.py"}]},
        ),
    )  # fmt: skip


@pytest.mark.parametrize(
    ("readings", "refused"),
    [(None, None), ({"crit_total": "held"}, None), ({"crit_total": "broken"}, "crit_total (broken)"),
     ({}, "crit_total (unread)")],
    ids=["no-runner-wired", "held", "broken", "unread"],
)  # fmt: skip
async def test_the_frozen_criteria_run_through_one_seam_and_any_not_held_regresses(
    tmp_path, readings, refused
):
    """The integration point for #2774's ``frozen_on_runner`` (§24cm): one call, given the
    rebase's own key, the rebased head's tree and the frozen criteria. Bugs caught: a criterion
    the runner didn't read accepted as held; a broken one accepted; the row claiming bundles ran
    when no runner is wired; the runner given the old head's tree."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted()
    await _with_a_frozen_criterion(world)
    onto = world.upstream({"README.md": b"moved\n"}, "docs")
    await world.reconciled(onto)
    await world.proposing()
    seen = []

    async def runner(at):
        seen.append(at)
        return readings

    service = world.service(frozen_on_runner=None if readings is None else runner)
    await service.drain()

    rows = await world.rows(ControlOperation.BRANCH_REBASED)
    if refused is not None:
        refusal = (await world.campaigns.control_log(CID))[-1].binding["refusal"]
        assert refusal.startswith("REBASED_HEAD_REGRESSED: ") and refused in refusal
        assert rows == []
        return
    [rebased] = rows
    assert rebased.binding["frozen_criteria_unrun"] == ([] if readings else ["crit_total"])
    if readings:
        [at] = seen
        assert at.subject_id == rebased.idempotency_key
        assert (at.pin.commit, [c["criterion_id"] for c in at.frozen]) == (onto, ["crit_total"])
        assert at.tree.commit == rebased.binding["commit"]
