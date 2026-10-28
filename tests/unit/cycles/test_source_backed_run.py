"""A source-backed run, from its product's tree to a verified, captured change (SIP-0112 E.4.3).

Wiring, at the three moments the run is composed, with the shared fixture as the product through
the real managed clone:
- provisioning (``RunProvisioning.seed``, what every run calls before dispatch);
- dispatch-time enrichment (``_enrich_envelope``, what every dispatched task passes);
- the end of the plan (``_execute_sequential``, after its last task), where the change is
  verified by the product's own checks and captured. That part goes through the real sandbox
  service and workspace store, and the one stand-in runs X-3a's disposable copy as local
  processes, where the service would run a container.

Bugs caught:
- a run of an external product starting from no tree, or a stack skeleton;
- a candidate captured that the product's checks never ran on, or one that broke a check the
  baseline passed;
- a captured commit that isn't the tree verified, or that drops the files the squad didn't
  touch (README.md, the binary asset);
- the developer never shown the file its task changes, or shown the checkout's copy after the
  squad already changed it;
- a task from an operator's plan, with no framing documents, refused before any model call for
  want of them (cyc_50354cfc8dbb, live);
- the delivered tree losing every file the squad didn't touch.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import subprocess
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.noop.ports import NoOpFailurePatternRecall, NoOpProposalEvidence
from adapters.tools.git_source import GitSourceRepository
from squadops.campaigns.evaluator_trees import FileTree
from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.cycles.delivered_tree import StoredArtifact, delivered_files
from squadops.cycles.models import ArtifactRef, Cycle, Project, Run, TaskFlowPolicy
from squadops.cycles.run_ledger import RunLedger
from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor, _ExecutionError
from squadops.execution.run_provisioning import RunProvisioning
from squadops.execution.source_delivery import (
    SOURCE_PATCH_TYPE,
    SOURCE_VERIFICATION_TYPE,
    squad_changes,
)
from squadops.projects.baseline import parse_baseline
from squadops.projects.checkout import CHECKOUT_MANIFEST_TYPE, SOURCE_CHECKOUT
from squadops.projects.development_configuration import parse_configuration
from squadops.projects.models import ProjectSource
from squadops.projects.registration import LocatorPolicy
from squadops.projects.source_context import parse_source_context
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.models import CommandOutcome, CommandResult, OperationName, OperationStatus
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import WorkspaceStore
from squadops.tasks.models import TaskEnvelope
from tests.fixtures.shared_contract.repository import build_repository, recorded, tracked_files

NOW = datetime(2026, 10, 18, tzinfo=UTC)


class _Vault:
    def __init__(self):
        self.stored: dict[str, tuple[ArtifactRef, bytes]] = {}

    async def store(self, ref, content):
        self.stored[ref.artifact_id] = (ref, content)
        return ref

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]


class _LocalBackend:
    """X-3a's disposable copy of a pinned revision, its setup and check run as local processes."""

    def __init__(self, store: WorkspaceStore) -> None:
        self.store = store

    async def run_declared_command(
        self, *, revision, command, working_dir=".", setup=(), timeout_seconds=None,
        findings_reader=None,
    ):  # fmt: skip
        with self.store.disposable_copy(revision.cycle_id, revision.revision_id) as copy:
            for step in setup:
                await asyncio.to_thread(subprocess.run, list(step), cwd=copy, check=True)
            done = await asyncio.to_thread(
                subprocess.run,
                list(command),
                cwd=copy / working_dir,
                capture_output=True,
                text=True,
            )
        return CommandResult(
            operation=OperationName.RUN_DECLARED_COMMAND,
            workspace_revision_id=revision.revision_id,
            status=OperationStatus.SUCCEEDED if done.returncode == 0 else OperationStatus.FAILED,
            ran=True,
            command=tuple(command),
            outcome=CommandOutcome.EXITED,
            exit_code=done.returncode,
            stdout_tail=done.stdout[-500:],
            stderr_tail=done.stderr[-500:],
            image_identity="python:3.12-slim",
            environment_contract_id="python3",
        )


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
    registry.get_inherited_baseline.return_value = parse_baseline(
        recorded("inherited_baseline", "valid")
    )
    store = WorkspaceStore(tmp_path / "sandbox")
    sandbox = SandboxService(
        store=store,
        journal=OperationEvidenceJournal(tmp_path / "sandbox"),
        backend=_LocalBackend(store),
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
        proposal_evidence=NoOpProposalEvidence(),
        source_repository=GitSourceRepository(
            tmp_path / "cache",
            LocatorPolicy.of([], [str(tmp_path / "sources")]),
            timeout_seconds=60,
            committer_name="SquadOps",
            committer_email="squadops@squadops.invalid",
        ),
        sandbox=sandbox,
    )
    executor._cycle_event_bus = MagicMock()
    executor._cycle_registry.get_latest_checkpoint.return_value = None
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
    # The binary asset is the manifest's alone: no task's view of the tree is anything but text.
    manifest = json.loads(vault.stored[refs[0].artifact_id][1])
    assert len(files) == 16 and "assets/mark.png" not in files
    assert manifest["binary"] == ["assets/mark.png"] and "assets/mark.png" in manifest["sizes"]
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
    # the product's own checks, from the pinned configuration revision: what verifies the change
    assert [c["id"] for c in repository["checks"]] == [
        "build", "parse", "ledger", "server", "report", "notify"
    ]  # fmt: skip
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


async def test_a_task_from_an_operators_plan_is_not_refused_for_want_of_framing(world):
    """A source-backed run from an operator's plan has no framing documents, so dispatch resolves
    no ``artifact_contents``. The handlers refused such a task before any model call, then twice
    more through correction (cyc_50354cfc8dbb). Its context is the repository view."""
    _, vault, executor, cycle, run = world
    seeded = await _seed(executor, cycle, run)
    stored = [(i, vault.stored[i][0]) for i in seeded]

    envelope = await executor._enrich_envelope(
        _envelope(cycle, ["tally/__main__.py"]), {}, list(seeded), stored
    )
    # the plan's task carries the PRD; enrichment adds the view and nothing from framing
    inputs = {**envelope.inputs, "prd": "add --json"}

    assert "artifact_contents" not in inputs and "source_repository" in inputs
    assert DevelopmentDevelopHandler().validate_inputs(inputs) == []
    assert QATestHandler().validate_inputs(inputs) == []
    # without the view there is nothing to build on, and the refusal says what would do
    bare = {k: v for k, v in inputs.items() if k != "source_repository"}
    assert DevelopmentDevelopHandler().validate_inputs(bare) == [
        "'artifact_contents', 'artifact_vault' or 'source_repository' is required for build tasks"
    ]


async def test_a_run_with_no_pinned_source_is_unchanged(world):
    _, vault, executor, cycle, run = world
    plain = cycle.__class__(**{**cycle.__dict__, "source_context": None})

    seeded = await _seed(executor, plain, run)
    enriched = await executor._enrich_envelope(_envelope(plain, ["x.py"]), {}, [], [])

    assert seeded == [] and vault.stored == {}
    assert "source_repository" not in enriched.inputs


_SUMMARY_LINE = b"""

def summary_line(ledger):
    s = summarize(ledger)
    return f"{s['total']} across {s['counters']} counters"
"""


async def _end_of_plan(executor, cycle, run, vault, changes, task_type="development.develop"):
    """The run's plan done, with ``changes`` the developer's accepted emissions: the point at
    which ``_execute_sequential`` delivers. The emissions arrive as the run's stored artifacts
    do, through the seed set the loop restores. The plan's one task is ``task_type``, already
    run: dispatch is out of this seam."""
    executor._execute_task = AsyncMock()
    seeded = await _seed(executor, cycle, run)
    emitted = []
    for path, content in changes.items():
        ref = ArtifactRef(
            artifact_id=f"art_dev{len(emitted):09d}",
            project_id=cycle.project_id,
            cycle_id=cycle.cycle_id,
            run_id=run.run_id,
            # Typed by extension, as a live emission is (`.md` is a document).
            artifact_type="document" if path.endswith(".md") else "source",
            filename=path,
            content_hash="h",
            size_bytes=len(content),
            media_type="text/x-python",
            created_at=datetime.now(UTC),
            metadata={"producing_task_type": "development.develop", "task_id": "task_dev"},
        )
        vault.stored[ref.artifact_id] = (ref, content)
        emitted.append(ref.artifact_id)
    # #2591: each task also stores its own records, as a live develop and qa.test do. They are
    # the squad's evidence, never the product's files.
    for path, artifact_type, producer in (
        ("typed_check_evaluation_task_0.json", "typed_check_evaluation", "development.develop"),
        ("test_report.md", "test_report", "qa.test"),
    ):
        ref = ArtifactRef(
            artifact_id=f"art_rec{len(emitted):09d}",
            project_id=cycle.project_id,
            cycle_id=cycle.cycle_id,
            run_id=run.run_id,
            artifact_type=artifact_type,
            filename=path,
            content_hash="h",
            size_bytes=2,
            media_type="text/plain",
            created_at=datetime.now(UTC),
            metadata={"producing_task_type": producer, "task_id": "task_dev"},
        )
        vault.stored[ref.artifact_id] = (ref, b"{}")
        emitted.append(ref.artifact_id)
    plan = [dataclasses.replace(_envelope(cycle, list(changes)), task_type=task_type)]
    await executor._execute_sequential(
        plan, run.run_id, cycle, seed_artifact_refs=[*seeded, *emitted], ledger=RunLedger()
    )


def _of_type(vault, artifact_type):
    return [(r, c) for r, c in vault.stored.values() if r.artifact_type == artifact_type]


async def test_an_accepted_change_is_captured_as_one_commit_on_the_pinned_one(world, tmp_path):
    repo, vault, executor, cycle, run = world
    report = tracked_files(repo.path, repo.second_commit)["tally/report.py"]

    await _end_of_plan(executor, cycle, run, vault, {"tally/report.py": report + _SUMMARY_LINE})

    [(_ref, raw)] = _of_type(vault, SOURCE_VERIFICATION_TYPE)
    verification = json.loads(raw)
    assert verification["verdict"] == "accepted"
    assert verification["changed_paths"] == ["tally/report.py"]
    assert [(c["id"], c["result"], c["attribution"]) for c in verification["checks"]] == [
        ("build", "PASS", "inherited"),
        ("parse", "FAIL", "inherited"),
        ("ledger", "PASS", "inherited"),
        ("server", "PASS", "inherited"),
        ("report", "PASS", "inherited"),
        ("notify", "UNVERIFIED", "unverified attribution"),
    ]
    [(patch_ref, patch)] = _of_type(vault, SOURCE_PATCH_TYPE)
    captured = patch_ref.metadata["captured_commit"]
    clone = tmp_path / "cache" / "prj-tally.git"
    parent = subprocess.run(
        ["git", "rev-parse", f"{captured}^"], cwd=clone, capture_output=True, text=True
    ).stdout.strip()
    assert parent == repo.second_commit
    # The commit is the whole product with the one change: the documents and the binary asset
    # the squad never touched are in it, byte for byte.
    expected = {**tracked_files(repo.path, repo.second_commit)}
    expected["tally/report.py"] = report + _SUMMARY_LINE
    assert tracked_files(clone, captured) == expected
    assert FileTree.of(expected).identity == verification["candidate_tree_identity"]
    mappings = [c.args[0] for c in executor._project_registry.record_source_mapping.call_args_list]
    assert [(m.direction, m.commit) for m in mappings] == [
        ("seeded", repo.second_commit),
        ("captured", captured),
    ]
    assert mappings[1].sandbox_revision_id == verification["candidate_revision_id"]
    # patch_export: the patch applies to the pinned commit and gives the captured tree.
    applied = tmp_path / "applied"
    subprocess.run(["git", "clone", "-q", str(repo.path), str(applied)], check=True)
    subprocess.run(["git", "apply", "-"], cwd=applied, input=patch, check=True)
    assert (applied / "tally/report.py").read_bytes() == expected["tally/report.py"]


async def test_a_document_the_product_has_is_delivered_and_the_squads_own_is_named(world, tmp_path):
    """The G4 of #2484, after #2591. Bugs caught: an edit to the product's README dropped, so a
    docs request reads as a run that changed nothing; a note the squad wrote for itself at the
    root committed into the product, or dropped with nothing saying so."""
    repo, vault, executor, cycle, run = world
    readme = tracked_files(repo.path, repo.second_commit)["README.md"]

    await _end_of_plan(
        executor, cycle, run, vault,
        {"README.md": readme + b"\nSee CONTRIBUTING.md to add a counter.\n",
         "implementation_notes.md": b"# What I changed\n"},
    )  # fmt: skip

    [(_ref, raw)] = _of_type(vault, SOURCE_VERIFICATION_TYPE)
    verification = json.loads(raw)
    assert (verification["changed_paths"], verification["left_out"]) == (
        ["README.md"], ["implementation_notes.md"],
    )  # fmt: skip
    [(patch_ref, _patch)] = _of_type(vault, SOURCE_PATCH_TYPE)
    captured = tracked_files(
        tmp_path / "cache" / "prj-tally.git", patch_ref.metadata["captured_commit"]
    )
    assert "implementation_notes.md" not in captured
    assert captured["README.md"].endswith(b"to add a counter.\n")


async def test_a_resumed_runs_delivery_seeds_afresh_after_an_attempt_that_never_tore_down(world):
    """The G4 of #2484. Bug caught: a resumed run's second delivery refused at the seed
    (AlreadySeededError), the first attempt's workspace left behind with its head already that
    attempt's candidate."""
    repo, vault, executor, cycle, run = world
    report = tracked_files(repo.path, repo.second_commit)["tally/report.py"]
    change = {"tally/report.py": report + _SUMMARY_LINE}
    release = executor._sandbox.release_workspace
    executor._sandbox.release_workspace = AsyncMock()  # the first attempt dies before teardown
    await _end_of_plan(executor, cycle, run, vault, change)
    executor._sandbox.release_workspace = release

    await _end_of_plan(executor, cycle, run, vault, change)

    verifications = [json.loads(raw) for _ref, raw in _of_type(vault, SOURCE_VERIFICATION_TYPE)]
    assert [v["verdict"] for v in verifications] == ["accepted", "accepted"]
    assert len(_of_type(vault, SOURCE_PATCH_TYPE)) == 2


@pytest.mark.parametrize(
    ("path", "taken"),
    [("docs/usage.md", True), ("docs/guides/setup.md", True), ("notes.md", False),
     ("scratch/plan.md", False)],
    ids=["beside-a-product-doc-two-levels-down", "in-a-product-directory", "new-at-the-root",
         "in-a-directory-the-product-lacks"],
)  # fmt: skip
def test_a_new_document_is_the_products_where_the_product_has_its_directory(path, taken):
    """The G4 of #2484's low 1. Bug caught: a new doc in an ancestor of a product file's
    directory (docs/, where the product has docs/guides/a.md) left out as the squad's own."""
    checkout = {"docs/guides/a.md": b"a\n", "app/main.py": b"x\n"}
    ref = ArtifactRef(
        artifact_id="art_doc000000001", project_id="prj-tally", cycle_id="cyc_1", run_id="run_1",
        artifact_type="document", filename=path, content_hash="h", size_bytes=2,
        media_type="text/markdown", created_at=datetime.now(UTC),
        metadata={"producing_task_type": "development.develop"},
    )  # fmt: skip

    changes, left_out = squad_changes(
        [(ref.artifact_id, ref)], {ref.artifact_id: b"# d\n"}, checkout
    )

    assert (list(changes), list(left_out)) == (([path], []) if taken else ([], [path]))


async def test_a_failed_delivery_reports_its_own_error_when_the_release_fails_too(world):
    """The G4 of #2484's low 2. Bug caught: the teardown's release, failing as well, raised over
    the delivery's own error, so the run reports a cleanup failure and hides what went wrong."""
    repo, vault, executor, cycle, run = world
    report = tracked_files(repo.path, repo.second_commit)["tally/report.py"]
    executor._sandbox.apply_workspace_patch = AsyncMock(side_effect=RuntimeError("patch broke"))
    release = AsyncMock(side_effect=[None, OSError("sandbox gone")])
    executor._sandbox.release_workspace = release

    with pytest.raises(RuntimeError, match="patch broke"):
        await _end_of_plan(executor, cycle, run, vault, {"tally/report.py": report + _SUMMARY_LINE})

    assert release.await_count == 2  # before seeding, and at the teardown that failed


async def test_a_change_that_breaks_a_passing_check_fails_the_run_and_is_never_captured(
    world, tmp_path
):
    repo, vault, executor, cycle, run = world
    broken = b"def summarize(ledger):\n    return {}\n"

    with pytest.raises(_ExecutionError, match="regressed: report failed where the baseline"):
        await _end_of_plan(executor, cycle, run, vault, {"tally/report.py": broken})

    [(_ref, raw)] = _of_type(vault, SOURCE_VERIFICATION_TYPE)
    report = next(c for c in json.loads(raw)["checks"] if c["id"] == "report")
    assert (report["result"], report["attribution"]) == ("FAIL", "introduced/regressed")
    assert _of_type(vault, SOURCE_PATCH_TYPE) == []
    refs = subprocess.run(
        ["git", "for-each-ref", "refs/squadops/"],
        cwd=tmp_path / "cache" / "prj-tally.git",
        capture_output=True,
        text=True,
    ).stdout
    assert refs == ""
    directions = [
        c.args[0].direction for c in executor._project_registry.record_source_mapping.call_args_list
    ]
    assert directions == ["seeded"]


async def test_a_run_that_changed_nothing_delivers_nothing(world):
    """Bug caught: a feature request that produced no change reported as delivered."""
    _repo, vault, executor, cycle, run = world

    with pytest.raises(_ExecutionError, match="changed no file of the product"):
        await _end_of_plan(executor, cycle, run, vault, {})

    assert _of_type(vault, SOURCE_VERIFICATION_TYPE) == []


async def test_a_framing_run_delivers_nothing_and_completes(world):
    """Found live (cyc_62ec4593f50a): the framing run of a source-backed cycle failed with
    "the run changed no file of the product". Bug caught: delivery at the end of every run of the
    cycle, where only a run that authors the product has a change to deliver."""
    _repo, vault, executor, cycle, run = world

    await _end_of_plan(executor, cycle, run, vault, {}, task_type="governance.review_plan")

    assert _of_type(vault, SOURCE_VERIFICATION_TYPE) == []


async def test_an_increment_is_seeded_at_its_pin_not_at_the_projects_baseline(world):
    """H.4's increment pin (SIP-0109 §24cd point 1), entered at ``RunProvisioning.seed``. A
    repository-backed Campaign's increment builds on its campaign branch's head. Here that's the
    fixture's first commit, while the Project's baseline is its second. Bug caught: the seed
    reading the Project's baseline, so an increment starts from a tree its branch never held."""
    repo, vault, executor, cycle, run = world
    pinned = dataclasses.replace(
        cycle.source_context, pinned_commit=repo.first_commit, pinned_from="campaign_branch"
    )

    seeded = await _seed(executor, dataclasses.replace(cycle, source_context=pinned), run)

    refs = [vault.stored[i][0] for i in seeded]
    assert {r.metadata["checkout_commit"] for r in refs} == {repo.first_commit}
    assert "tally/report.py" not in {r.filename for r in refs}  # added by the second commit
    assert pinned.development_baseline_commit == repo.second_commit  # H.2's gate still keys here


async def test_a_campaign_branch_increment_is_never_compared_with_the_projects_baseline(world):
    """SIP-0109 §24bv point 3: an increment's regression baseline is the verification that made
    its head. Until that comparison is built, delivery refuses rather than reading the Project's
    baseline, which describes a tree the increment wasn't built on. Bug caught: a candidate built
    on the branch's head judged against the wrong baseline, and accepted or refused for it."""
    from squadops.execution.source_delivery import SourceDeliveryRefused, deliver_source_change

    repo, vault, executor, cycle, run = world
    pinned = dataclasses.replace(
        cycle.source_context,
        pinned_commit=repo.first_commit,
        pinned_from="campaign_branch",
        previous_verification_ref="art_verification",
    )

    with pytest.raises(SourceDeliveryRefused, match="§24bv point 3"):
        await deliver_source_change(
            dataclasses.replace(cycle, source_context=pinned), run.run_id, [],
            vault=vault, registry=executor._project_registry,
            repository=executor._source_repository, sandbox=executor._sandbox,
        )  # fmt: skip
    executor._project_registry.get_inherited_baseline.assert_not_awaited()
