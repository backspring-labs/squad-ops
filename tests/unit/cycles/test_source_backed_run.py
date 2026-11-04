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
- the delivered tree losing every file the squad didn't touch;
- a removal the squad emits (#2612) that leaves the file in the captured commit, goes unnamed in
  ``changed_paths``, or stays in the views of the tasks after it.
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
from adapters.prompts.factory import DEFAULT_TEMPLATES_PATH, create_prompt_asset_source
from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from adapters.tools.git_source import GitSourceRepository
from squadops.campaigns.evaluator_trees import FileTree
from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.impl.repair_handlers import (
    DevelopmentCorrectionRepairHandler,
)
from squadops.capabilities.handlers.source_repository import source_repository_section
from squadops.contracts.cycle_request_profiles import load_profile
from squadops.cycles.deletions import DELETION_ARTIFACT_TYPE, deleted_paths
from squadops.cycles.delivered_tree import StoredArtifact, delivered_files
from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    DerivedProfileNotFoundError,
    Project,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.run_ledger import RunLedger
from squadops.execution import source_delivery
from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor, _ExecutionError
from squadops.execution.run_provisioning import RunProvisioning
from squadops.execution.source_delivery import (
    SOURCE_PATCH_TYPE,
    SOURCE_VERIFICATION_TYPE,
    squad_changes,
)
from squadops.llm.models import ChatMessage
from squadops.projects.baseline import parse_baseline
from squadops.projects.checkout import CHECKOUT_MANIFEST_TYPE, SOURCE_CHECKOUT
from squadops.projects.derived_profile import parse_profile
from squadops.projects.development_configuration import parse_configuration
from squadops.projects.models import ProjectSource
from squadops.projects.registration import LocatorPolicy
from squadops.projects.source_context import parse_source_context
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.models import CommandOutcome, CommandResult, OperationName, OperationStatus
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import WorkspaceStore
from squadops.tasks.models import TaskEnvelope, TaskResult, TaskResultStatus
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
    registry.get_derived_profile.return_value = parse_profile(recorded("derived_profile", "valid"))
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


async def test_every_task_is_shown_the_products_runners_as_its_projects_pin_derives_them(world):
    """SIP-0112 H.4 point 3, entered at ``RunProvisioning.seed`` and the envelope a live task is
    dispatched with. An increment pinned at its branch's head reads the profile at the Project's
    pin, as SIP-0109 §24cd point 3 rules. Bugs caught: the runners never reaching the task, so a
    test is written where no product check runs it; or read at the increment's own commit, so one
    Campaign's increments are shown different runners between reconciliations."""
    repo, vault, executor, cycle, run = world
    pinned = dataclasses.replace(
        cycle.source_context, pinned_commit=repo.first_commit, pinned_from="campaign_branch"
    )
    cycle = dataclasses.replace(cycle, source_context=pinned)
    seeded = await _seed(executor, cycle, run)

    envelope = await executor._enrich_envelope(
        _envelope(cycle, []), {}, list(seeded), [(i, vault.stored[i][0]) for i in seeded]
    )

    executor._project_registry.get_derived_profile.assert_awaited_once_with(
        cycle.project_id,
        at=(pinned.development_baseline_commit, pinned.development_configuration_revision),
    )
    assert envelope.inputs["source_repository"]["runners"] == [
        {
            "runner": "unittest",
            "checks": ["parse", "ledger", "server", "report", "notify"],
            "roots": ["checks"],
            "file_pattern": "check_*.py",
            "covers": ["tally/**"],
        }
    ]
    renderer = RequestTemplateRenderer(
        asset_source=create_prompt_asset_source(
            provider="filesystem", templates_path=DEFAULT_TEMPLATES_PATH
        )
    )
    section = await source_repository_section(renderer, envelope.inputs)
    assert "a file named `check_*.py` under `checks`, testing `tally/**`" in section


async def test_a_pin_with_no_derived_profile_is_shown_its_checks_alone(world):
    """Contract 8's absence (H.6): a baseline captured before 2.5 has no profile. Bug caught: the
    seed failing, where create only warned (``derived_profile_absent``)."""
    _repo, vault, executor, cycle, run = world
    executor._project_registry.get_derived_profile.side_effect = DerivedProfileNotFoundError(
        "prj-tally"
    )
    seeded = await _seed(executor, cycle, run)

    envelope = await executor._enrich_envelope(
        _envelope(cycle, []), {}, list(seeded), [(i, vault.stored[i][0]) for i in seeded]
    )

    repository = envelope.inputs["source_repository"]
    assert repository["runners"] == [] and len(repository["checks"]) == 6


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


async def _end_of_plan(
    executor,
    cycle,
    run,
    vault,
    changes,
    task_type="development.develop",
    *,
    profile=None,
    rounds_spent=0,
):
    """The run's plan done, with ``changes`` the developer's accepted emissions: the point at
    which ``_execute_sequential`` delivers. The emissions arrive as the run's stored artifacts
    do, through the seed set the loop restores. The plan's one task is ``task_type``, already
    run: dispatch is out of this seam. ``rounds_spent`` is the correction rounds the plan's own
    failures spent, on the run's counter, as a task's correction loop bills them."""

    async def _task(state, *_args, **_kwargs):
        state.correction.counter["n"] += rounds_spent

    executor._execute_task = AsyncMock(side_effect=_task)
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
        plan,
        run.run_id,
        cycle,
        seed_artifact_refs=[*seeded, *emitted],
        ledger=RunLedger(),
        profile=profile,
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


async def test_a_change_that_breaks_a_passing_check_fails_the_run_once_the_budget_is_spent(
    world, tmp_path
):
    """#2613: a regression's repair round spends the run's correction budget, so once the plan's
    own rounds spent it the run fails as before, its record naming the check, with no round."""
    repo, vault, executor, cycle, run = world
    broken = b"def summarize(ledger):\n    return {}\n"
    executor._task_dispatcher.dispatch_task = AsyncMock()

    with pytest.raises(
        _ExecutionError,
        match=r"regressed: report failed where the baseline did not; no repair round: the run's "
        r"correction budget \(2\) is spent",
    ):
        await _end_of_plan(executor, cycle, run, vault, {"tally/report.py": broken}, rounds_spent=2)

    executor._task_dispatcher.dispatch_task.assert_not_awaited()

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


# --- #2613 (SIP-0112 H.20): a regression found at the end of the plan gets one repair round ----

_BROKEN_REPORT = b"def summarize(ledger):\n    return {}\n"
_SQUAD = SquadProfile(
    profile_id="full",
    name="Full",
    description="",
    version=1,
    agents=tuple(
        AgentProfileEntry(agent_id=a, role=r, model="m", enabled=True, serves_roles=(r,))
        for a, r in (("neo", "dev"), ("eve", "qa"), ("data", "data"), ("max", "lead"))
    ),
    created_at=NOW,
)


def _implementation(cycle):
    """The cycle on the `implementation` request profile's own defaults: its declared correction
    steps (analyze, decide, repair) and its budget of two rounds."""
    return dataclasses.replace(
        cycle, applied_defaults=dict(load_profile("implementation").defaults)
    )


def _squad_answers(executor, repaired: bytes | None, *, decision: str = "patch"):
    """The squad's correction steps, answered as the agents would, each envelope kept. The repair
    rewrites ``tally/report.py`` to ``repaired`` (``None``: it writes nothing)."""
    dispatched: list[TaskEnvelope] = []

    async def _dispatch(envelope, run_id, **_kw):
        dispatched.append(envelope)
        outputs = {
            "data.analyze_failure": {"classification": "work_product", "analysis_summary": "x"},
            "governance.correction_decision": {
                "correction_path": decision,
                "decision_rationale": "the report's summary lost its fields",
                "affected_task_types": ["development.develop"],
            },
        }.get(envelope.task_type)
        if outputs is None:
            artifacts = (
                [{"name": "tally/report.py", "content": repaired.decode(), "type": "source"}]
                if repaired is not None
                else []
            )
            outputs = {"artifacts": artifacts, "summary": "repaired"}
        return TaskResult(
            task_id=envelope.task_id, status=TaskResultStatus.SUCCEEDED, outputs=outputs
        )

    executor._task_dispatcher.dispatch_task = _dispatch
    executor._task_dispatcher.create_task_run_if_enabled = AsyncMock(return_value=None)
    return dispatched


def _verifications(vault):
    stored = sorted(_of_type(vault, SOURCE_VERIFICATION_TYPE), key=lambda rc: rc[0].created_at)
    return [(ref.artifact_id, json.loads(raw)) for ref, raw in stored]


async def test_a_regression_is_repaired_in_one_round_from_the_product_runners_reading(
    world, tmp_path
):
    """The wiring test (anti-pattern 6a), entered at ``_execute_sequential``'s end of plan, the
    live delivery, through the real correction runner to the agents' queue. Bugs caught: a
    regression that ends the run with budget left; the analysis or the repair handed anything but
    the product runner's reading of the failing check (#2913: never an agent image's); a round
    outside the run's budget; the repaired candidate captured unverified, or the regressed one
    captured at all."""
    repo, vault, executor, cycle, run = world
    report = tracked_files(repo.path, repo.second_commit)["tally/report.py"]
    dispatched = _squad_answers(executor, report + _SUMMARY_LINE)

    await _end_of_plan(
        executor, _implementation(cycle), run, vault, {"tally/report.py": _BROKEN_REPORT},
        profile=_SQUAD, rounds_spent=1,
    )  # fmt: skip

    (first_id, first), (_second_id, second) = _verifications(vault)
    assert (first["verdict"], second["verdict"]) == ("regressed", "accepted")
    # One round: analyze, decide, repair, each once, on the plan's developer task.
    assert [e.task_type for e in dispatched] == [
        "data.analyze_failure",
        "governance.correction_decision",
        "development.correction_repair",
    ]
    # What the analysis and the repair read is the product's runner's reading, as stored.
    runner = first["evidence"]["report"]
    for envelope in (dispatched[0], dispatched[2]):
        evidence = envelope.inputs["failure_evidence"]
        assert evidence["failed_task_id"] == "task_dev"
        [row] = evidence["validation_result"]["checks"]
        assert row == {
            "check": "report",
            "passed": False,
            "executed": True,
            "status": "failed",
            "judged_on": "product_runner",
            "attribution": "introduced/regressed",
            "reason": "report failed where the baseline did not",
            "exit_code": runner["exit_code"],
            "stdout_tail": runner["stdout_tail"],
            "stderr_tail": runner["stderr_tail"],
        }
        assert runner["exit_code"] == 1 and "FAIL" in runner["stderr_tail"]
        assert "image python:3.12-slim" in evidence["error"]
        # parse failed at the baseline too: named, and never a row the repair is aimed at
        assert "failing before the run too, not its to repair: parse." in evidence["error"]
    assert dispatched[2].inputs["max_correction_attempts"] == 2
    # The repaired candidate is verified again, owing a passing run of what regressed.
    assert second["repair_of"] == {"ref": first_id, "checks": ["report"]}
    assert next(c for c in second["checks"] if c["id"] == "report")["result"] == "PASS"
    [(patch_ref, _patch)] = _of_type(vault, SOURCE_PATCH_TYPE)
    captured = patch_ref.metadata["captured_commit"]
    clone = tmp_path / "cache" / "prj-tally.git"
    assert tracked_files(clone, captured)["tally/report.py"] == report + _SUMMARY_LINE


async def test_a_repair_that_regresses_again_fails_the_run_after_its_one_round(world):
    """Bugs caught: a second round (the budget has room for one more), or a regressed repair
    captured. The record of each delivery names the check."""
    _repo, vault, executor, cycle, run = world
    dispatched = _squad_answers(executor, b"def summarize(ledger):\n    return None\n")

    with pytest.raises(_ExecutionError, match="regressed: report failed where the baseline"):
        await _end_of_plan(
            executor, _implementation(cycle), run, vault, {"tally/report.py": _BROKEN_REPORT},
            profile=_SQUAD,
        )  # fmt: skip

    assert [d["verdict"] for _id, d in _verifications(vault)] == ["regressed", "regressed"]
    assert sum(e.task_type == "development.correction_repair" for e in dispatched) == 1
    assert _of_type(vault, SOURCE_PATCH_TYPE) == []


async def test_a_regressed_check_the_repaired_candidate_cant_run_is_not_repaired(world):
    """Bug caught: a repair that makes the regressed check time out (UNVERIFIED blocks nothing on
    its own) accepted and captured. Missing evidence grants no waiver."""
    repo, vault, executor, cycle, run = world
    report = tracked_files(repo.path, repo.second_commit)["tally/report.py"]
    _squad_answers(executor, report + _SUMMARY_LINE)
    backend = executor._sandbox._backend
    real = backend.run_declared_command
    runs = {"report": 0}

    async def _times_out_on_the_repaired_candidate(*, revision, command, **kw):
        if "check_report.py" in command:
            runs["report"] += 1
            if runs["report"] == 2:
                return CommandResult(
                    operation=OperationName.RUN_DECLARED_COMMAND,
                    workspace_revision_id=revision.revision_id,
                    status=OperationStatus.FAILED,
                    ran=True,
                    command=tuple(command),
                    outcome=CommandOutcome.TIMEOUT,
                )
        return await real(revision=revision, command=command, **kw)

    backend.run_declared_command = _times_out_on_the_repaired_candidate

    with pytest.raises(
        _ExecutionError,
        match="report regressed, and the repaired candidate's run of it is UNVERIFIED: timed out",
    ):
        await _end_of_plan(
            executor, _implementation(cycle), run, vault, {"tally/report.py": _BROKEN_REPORT},
            profile=_SQUAD,
        )  # fmt: skip

    assert [d["verdict"] for _id, d in _verifications(vault)] == ["regressed", "regressed"]
    assert _of_type(vault, SOURCE_PATCH_TYPE) == []


@pytest.mark.parametrize(
    ("decision", "repaired", "said"),
    [
        ("abort", None, "the repair round decided 'abort'"),
        ("patch", None, "the repair round wrote no file of the product"),
    ],
)
async def test_a_round_that_repairs_nothing_fails_the_run_naming_the_checks(
    world, decision, repaired, said
):
    _repo, vault, executor, cycle, run = world
    _squad_answers(executor, repaired, decision=decision)

    with pytest.raises(_ExecutionError, match=f"regressed: report failed .*; {said}"):
        await _end_of_plan(
            executor, _implementation(cycle), run, vault, {"tally/report.py": _BROKEN_REPORT},
            profile=_SQUAD,
        )  # fmt: skip

    assert [d["verdict"] for _id, d in _verifications(vault)] == ["regressed"]


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


def _parse_fixed(repo) -> bytes:
    """Tally's parse with the inherited failure fixed: names lose the spaces around them."""
    parse = tracked_files(repo.path, repo.second_commit)["tally/parse.py"]
    assert b"return name, int(amount)" in parse
    return parse.replace(b"return name, int(amount)", b"return name.strip(), int(amount)")


async def _first_increment(world):
    """A repository-backed Campaign's first increment, pinned at the head the calibration record
    leaves (the Project's baseline commit, no verification), fixing parse's inherited failure. Its
    capture and its verification are what a promotion makes the next head (``CampaignHead``)."""
    repo, vault, executor, cycle, run = world
    at_record = dataclasses.replace(
        cycle,
        source_context=dataclasses.replace(cycle.source_context, pinned_from="campaign_branch"),
    )
    await _end_of_plan(executor, at_record, run, vault, {"tally/parse.py": _parse_fixed(repo)})
    [(ref, raw)] = _of_type(vault, SOURCE_VERIFICATION_TYPE)
    [(patch_ref, _patch)] = _of_type(vault, SOURCE_PATCH_TYPE)
    first = json.loads(raw)
    assert first["regression_baseline"] == {"kind": "inherited_baseline", "ref": None}
    parse = next(c for c in first["checks"] if c["id"] == "parse")
    assert (parse["result"], parse["attribution"]) == ("PASS", "resolved")
    return patch_ref.metadata["captured_commit"], ref.artifact_id


def _second(world, head: str, verification: str):
    """The next increment's cycle and run, pinned at ``head`` with ``verification`` behind it."""
    _repo, _vault, _executor, cycle, run = world
    context = dataclasses.replace(
        cycle.source_context,
        pinned_commit=head,
        pinned_from="campaign_branch",
        previous_verification_ref=verification,
    )
    return (
        dataclasses.replace(cycle, cycle_id="cyc_2407a0000003", source_context=context),
        dataclasses.replace(run, run_id="run_src000000002", cycle_id="cyc_2407a0000003"),
    )


@pytest.mark.parametrize(
    ("change", "parse_read_as", "verdict"),
    [("report", ("PASS", "inherited"), "accepted"), ("parse", ("FAIL", "introduced/regressed"), None)],
    ids=["another-change-keeps-the-fix", "the-fix-undone"],
)  # fmt: skip
async def test_an_increment_on_a_head_is_compared_with_the_verification_that_made_it(
    world, change, parse_read_as, verdict
):
    """SIP-0109 §24bv point 3, entered at ``_execute_sequential``'s end of plan, the live delivery
    seam, twice: the first increment fixes parse's inherited failure; the second, pinned at its
    capture with its verification behind it, either changes another file or undoes the fix.

    Read against the Project's inherited baseline (parse FAIL), the first second increment would
    read parse ``resolved`` and the undo ``inherited``, and be accepted. Against the head's own
    verification (parse PASS) they read ``inherited`` and ``introduced/regressed``. Bugs caught:
    the candidate compared with upstream, never the tree it was built on, so an increment that
    undoes an accepted one is accepted; the Project's baseline read for a head past it."""
    repo, vault, executor, _cycle, _run = world
    head, made_it = await _first_increment(world)
    cycle, run = _second(world, head, made_it)
    executor._project_registry.get_inherited_baseline.reset_mock()
    upstream = tracked_files(repo.path, repo.second_commit)  # the head changed parse.py alone
    changes = (
        {"tally/report.py": upstream["tally/report.py"] + _SUMMARY_LINE}
        if change == "report"
        else {"tally/parse.py": upstream["tally/parse.py"]}
    )

    if verdict is None:
        with pytest.raises(_ExecutionError, match="regressed: parse failed where the baseline"):
            # The plan's rounds spent the budget, so the undo fails as it reads (#2613).
            await _end_of_plan(executor, cycle, run, vault, changes, rounds_spent=2)
    else:
        await _end_of_plan(executor, cycle, run, vault, changes)

    second = json.loads(
        next(raw for ref, raw in _of_type(vault, SOURCE_VERIFICATION_TYPE) if ref.run_id == run.run_id)
    )  # fmt: skip
    assert second["regression_baseline"] == {"kind": "previous_verification", "ref": made_it}
    assert second["baseline_commit"] == head
    parse = next(c for c in second["checks"] if c["id"] == "parse")
    assert (parse["result"], parse["attribution"]) == parse_read_as
    assert second["verdict"] == (verdict or "regressed")
    executor._project_registry.get_inherited_baseline.assert_not_awaited()


@pytest.mark.parametrize(
    ("stored", "refused"),
    [
        (None, "the vault holds no source verification there"),
        ({"verdict": "regressed"}, "only an accepted one made a head"),
        ({"development_configuration_revision": 2}, "ran at Development Configuration revision 2"),
        ({"candidate_tree_identity": "f" * 64}, "verified tree ffffffffffff"),
        ({"project_id": "prj-other"}, "is Project prj-other's"),
        ({"schema": "source-verification/v2"}, "is no source-verification/v1"),
    ],
    ids=["missing", "not-accepted", "another-revision", "another-tree", "another-project",
         "unknown-schema"],
)  # fmt: skip
async def test_a_head_whose_verification_cant_be_its_baseline_is_refused_before_anything_runs(
    world, stored, refused
):
    """The edges of §24bv point 3's baseline. Bugs caught: a candidate compared with a
    verification that was never accepted, describes another tree or Project, or ran its checks
    at another configuration revision, so attributions compare unlike runs; any of them falling
    back to the Project's baseline."""
    from squadops.execution.source_delivery import SourceDeliveryRefused, deliver_source_change

    repo, vault, executor, cycle, run = world
    first = tracked_files(repo.path, repo.first_commit)
    document = {
        "schema": "source-verification/v1",
        "project_id": "prj-tally",
        "verdict": "accepted",
        "development_configuration_revision": cycle.source_context.development_configuration_revision,
        "candidate_tree_identity": FileTree.of(first).identity,
        "checks": [{"id": "build", "result": "PASS", "attribution": "inherited"}],
    }
    if stored is not None:
        ref = ArtifactRef(
            artifact_id="art_madethehead", project_id="prj-tally", cycle_id="cyc_x",
            run_id="run_x", artifact_type=SOURCE_VERIFICATION_TYPE,
            filename="source_verification.json", content_hash="h", size_bytes=1,
            media_type="application/json", created_at=NOW,
        )  # fmt: skip
        vault.stored[ref.artifact_id] = (ref, json.dumps({**document, **stored}).encode())
    pinned, _run = _second(world, repo.first_commit, "art_madethehead")

    with pytest.raises(SourceDeliveryRefused, match=refused):
        await deliver_source_change(
            pinned, run.run_id, [], vault=vault, registry=executor._project_registry,
            repository=executor._source_repository, sandbox=executor._sandbox,
        )  # fmt: skip
    executor._project_registry.get_inherited_baseline.assert_not_awaited()
    executor._project_registry.record_source_mapping.assert_not_awaited()  # nothing was seeded


# --- a removal (#2612, SIP-0112 H.23) -------------------------------------------------------------

_PROMPTS = DEFAULT_TEMPLATES_PATH.parent
#: notify has no reader but its own check, which reads UNVERIFIED either way, so removing the pair
#: regresses nothing the product's checks can see.
_REMOVE_NOTIFY = "```delete:tally/notify.py\n```\n```delete:checks/check_notify.py\n```\n"


def _answering(reply: str) -> MagicMock:
    """An execution context whose model answers ``reply``, through the real prompt assets."""
    ctx = MagicMock()
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        return_value=ChatMessage(role="assistant", content=reply, completion_tokens=40)
    )
    ctx.ports.llm.default_model = "test-model"
    ctx.ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ctx.ports.llm_observability = None
    ctx.ports.request_renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", DEFAULT_TEMPLATES_PATH)
    )
    ctx.correlation_context = None
    ctx.disputed_checks = []
    ctx.task_id = "task_dev"
    ctx.role_id = "dev"
    return ctx


async def _the_developer_answers(executor, cycle, run, emission, *, named=(), profile=None):
    """The plan's one task, run as a live one is from its dispatch: enriched, read by the real
    develop handler from the model's ``emission``, and collected. The plan ends there, at the
    point ``_execute_sequential`` delivers."""

    async def _task(state, envelope, **_kwargs):
        produced = state.produced
        enriched = await executor._enrich_envelope(
            envelope,
            produced.prior_outputs,
            produced.all_artifact_refs,
            produced.stored_artifacts,
        )
        handled = await DevelopmentDevelopHandler().handle(
            _answering(emission), {**enriched.inputs, "prd": cycle.prd_ref}
        )
        assert handled.success, handled.error
        await executor._collect_artifacts_and_checkpoint(
            TaskResult(
                task_id=envelope.task_id,
                status=TaskResultStatus.SUCCEEDED,
                outputs=handled.outputs,
            ),
            enriched,
            cycle,
            run.run_id,
            produced.prior_outputs,
            produced.all_artifact_refs,
            produced.stored_artifacts,
            state.checkpoint.completed_task_ids,
            state.checkpoint.plan_delta_refs,
        )

    executor._execute_task = AsyncMock(side_effect=_task)
    seeded = await _seed(executor, cycle, run)
    await executor._execute_sequential(
        [_envelope(cycle, list(named))],
        run.run_id,
        cycle,
        seed_artifact_refs=list(seeded),
        ledger=RunLedger(),
        profile=profile,
    )


async def test_a_removal_the_developer_emits_is_absent_from_the_captured_commit(world, tmp_path):
    """The wiring test (anti-pattern 6a), entered where the live run does: the task's dispatch
    envelope, through the real develop handler, storage, ``_execute_sequential``'s end of plan and
    source delivery, to the commit in the real managed clone. Bugs caught: a removal that never
    reaches the candidate, leaves the file in the capture, goes unnamed in ``changed_paths``, or
    takes a file the emission never named with it."""
    repo, vault, executor, cycle, run = world
    report = tracked_files(repo.path, repo.second_commit)["tally/report.py"]
    written = (report + _SUMMARY_LINE).decode()

    await _the_developer_answers(
        executor,
        cycle,
        run,
        f"```python:tally/report.py\n{written}```\n{_REMOVE_NOTIFY}",
        named=("tally/report.py", "tally/notify.py"),
    )

    [(_ref, raw)] = _of_type(vault, SOURCE_VERIFICATION_TYPE)
    verification = json.loads(raw)
    assert verification["verdict"] == "accepted"
    assert verification["changed_paths"] == [
        "checks/check_notify.py",
        "tally/notify.py",
        "tally/report.py",
    ]
    [(patch_ref, patch)] = _of_type(vault, SOURCE_PATCH_TYPE)
    captured = patch_ref.metadata["captured_commit"]
    clone = tmp_path / "cache" / "prj-tally.git"
    expected = tracked_files(repo.path, repo.second_commit)
    del expected["tally/notify.py"], expected["checks/check_notify.py"]
    expected["tally/report.py"] = report + _SUMMARY_LINE
    assert tracked_files(clone, captured) == expected
    assert FileTree.of(expected).identity == verification["candidate_tree_identity"]
    # The contribution says so too: the patch applied to the pinned commit removes both.
    applied = tmp_path / "applied"
    subprocess.run(["git", "clone", "-q", str(repo.path), str(applied)], check=True)
    subprocess.run(["git", "apply", "-"], cwd=applied, input=patch, check=True)
    assert not (applied / "tally/notify.py").exists()
    assert not (applied / "checks/check_notify.py").exists()
    # Each removal is on the run's record, under the task that made it.
    removals = _of_type(vault, DELETION_ARTIFACT_TYPE)
    assert sorted(r.filename for r, _c in removals) == ["checks/check_notify.py", "tally/notify.py"]
    assert {r.metadata["producing_task_type"] for r, _c in removals} == {"development.develop"}


async def test_a_run_whose_one_change_is_a_removal_is_delivered(world, tmp_path):
    """Bug caught: a removal counted as no change, so the run is refused as having changed no
    file of the product, or the emission refused as having no fence."""
    repo, vault, executor, cycle, run = world

    await _the_developer_answers(executor, cycle, run, _REMOVE_NOTIFY)

    [(patch_ref, _patch)] = _of_type(vault, SOURCE_PATCH_TYPE)
    clone = tmp_path / "cache" / "prj-tally.git"
    captured = tracked_files(clone, patch_ref.metadata["captured_commit"])
    assert "tally/notify.py" not in captured and "tally/report.py" in captured


async def test_a_removal_that_breaks_a_check_regresses_like_any_change(world):
    """The product's own checks judge the tree without the file. Bug caught: a candidate verified
    with the file still in it, so removing a module a check needs is captured."""
    _repo, vault, executor, cycle, run = world
    _squad_answers(executor, None)

    with pytest.raises(_ExecutionError, match="report failed where the baseline did not"):
        await _the_developer_answers(
            executor,
            _implementation(cycle),
            run,
            "```delete:tally/report.py\n```\n",
            profile=_SQUAD,
        )

    [(_ref, raw)] = _of_type(vault, SOURCE_VERIFICATION_TYPE)
    assert json.loads(raw)["changed_paths"] == ["tally/report.py"]
    assert _of_type(vault, SOURCE_PATCH_TYPE) == []


async def test_a_removed_executable_file_is_the_candidate_the_sandbox_cut(world, monkeypatch):
    """A patch drops a removed file's mode with it. Bug caught: the run's own reckoning of the
    candidate keeping that mode, so every removal of an executable script is refused as a tree
    the sandbox didn't cut."""
    _repo, vault, executor, cycle, run = world
    real = source_delivery.baseline_tree

    async def _with_a_script(*args, **kwargs):
        tree = await real(*args, **kwargs)
        return dataclasses.replace(tree, executable=frozenset({"tally/notify.py"}))

    monkeypatch.setattr(source_delivery, "baseline_tree", _with_a_script)

    await _the_developer_answers(executor, cycle, run, _REMOVE_NOTIFY)

    [(_ref, raw)] = _of_type(vault, SOURCE_VERIFICATION_TYPE)
    assert json.loads(raw)["verdict"] == "accepted"


async def test_a_refused_removal_stores_nothing_and_never_reaches_delivery(world):
    """A path the view doesn't hold, entered at the dispatch envelope the live run builds: the
    view the handler judges against is the one enrichment hands it. Bug caught: the judgment
    reading the map, which collapses past its limit, or nothing at all."""
    _repo, vault, executor, cycle, run = world
    seeded = await _seed(executor, cycle, run)
    enriched = await executor._enrich_envelope(
        _envelope(cycle, []), {}, list(seeded), [(i, vault.stored[i][0]) for i in seeded]
    )

    handled = await DevelopmentDevelopHandler().handle(
        _answering("```delete:tally/absent.py\n```\n"), {**enriched.inputs, "prd": cycle.prd_ref}
    )

    assert handled.success is False
    assert "tally/absent.py" in handled.error and "no such file" in handled.error
    assert _of_type(vault, DELETION_ARTIFACT_TYPE) == []


def _stored(artifact_id, path, artifact_type, producer="development.develop", **metadata):
    ref = ArtifactRef(
        artifact_id=artifact_id,
        project_id="prj-tally",
        cycle_id="cyc_x",
        run_id="run_x",
        artifact_type=artifact_type,
        filename=path,
        content_hash="h",
        size_bytes=0,
        media_type="text/plain",
        created_at=NOW,
        metadata={"producing_task_type": producer, **metadata},
    )
    return artifact_id, ref


_CHECKOUT = {"tally/notify.py": b"old\n", "tally/report.py": b"r\n"}
_REMOVED = _stored("art_rm", "tally/notify.py", DELETION_ARTIFACT_TYPE)
_REWRITTEN = _stored("art_w", "tally/notify.py", "source")


@pytest.mark.parametrize(
    ("entries", "changes", "left_out"),
    [
        ([_REMOVED], {"tally/notify.py": None}, ()),
        ([_REWRITTEN, _REMOVED], {"tally/notify.py": None}, ()),
        # a later write brings it back: the list is a log, and the latest entry stands
        ([_REMOVED, _REWRITTEN], {"tally/notify.py": b"new\n"}, ()),
        # a repair's candidate is unaccepted until it is re-stored as the task's own
        ([_stored("art_rm", "tally/notify.py", DELETION_ARTIFACT_TYPE, "qa.test_repair")], {}, ()),
        (
            [
                _stored(
                    "art_rm",
                    "tally/notify.py",
                    DELETION_ARTIFACT_TYPE,
                    emission_status="failed",
                )
            ],
            {},
            (),
        ),
        # what the checkout doesn't hold isn't removed from the product, and is named
        (
            [_stored("art_rm", "tally/ghost.py", DELETION_ARTIFACT_TYPE)],
            {},
            ("tally/ghost.py",),
        ),
    ],
    ids=[
        "removed",
        "written-then-removed",
        "removed-then-written",
        "repair-candidate",
        "failed-emission",
        "not-the-products",
    ],
)
def test_the_change_is_each_paths_latest_accepted_entry(entries, changes, left_out):
    contents = {"art_rm": b"", "art_w": b"new\n"}

    assert squad_changes(entries, contents, _CHECKOUT) == (changes, left_out)


@pytest.mark.parametrize(
    ("entries", "gone"),
    [
        ([_REMOVED], {"tally/notify.py"}),
        ([_REMOVED, _REWRITTEN], set()),
        ([_REWRITTEN, _REMOVED], {"tally/notify.py"}),
        (
            [
                _stored(
                    "art_rm", "tally/notify.py", DELETION_ARTIFACT_TYPE, emission_status="failed"
                )
            ],
            set(),
        ),
    ],
    ids=["removed", "brought-back", "removed-last", "failed-emission"],
)
def test_a_paths_removal_stands_until_something_writes_it_again(entries, gone):
    assert deleted_paths(entries) == gone


async def test_the_tasks_after_a_removal_are_shown_a_tree_without_the_file(world):
    """Entered at dispatch-time enrichment, what every task passes. Bugs caught: the next task
    shown the removed file's content as current, handed it in its workspace, or told it can be
    removed again."""
    _repo, vault, executor, cycle, run = world
    seeded = await _seed(executor, cycle, run)
    art_id, removal = _stored("art_rm", "tally/notify.py", DELETION_ARTIFACT_TYPE)
    vault.stored[art_id] = (removal, b"")
    stored = [*((i, vault.stored[i][0]) for i in seeded), (art_id, removal)]

    enriched = await executor._enrich_envelope(
        _envelope(cycle, ["tally/notify.py"]), {}, [*seeded, art_id], stored
    )

    repository = enriched.inputs["source_repository"]
    assert repository["existing_files"] == {}
    assert repository["deleted"] == ["tally/notify.py"]
    assert "- `tally/notify.py` (removed by this run)" in repository["map"]
    assert "tally/notify.py" not in enriched.inputs["acceptance_workspace_files"]
    assert "tally/report.py" in enriched.inputs["acceptance_workspace_files"]


def _squad_repairs_with(executor, reply: str):
    """The correction steps as ``_squad_answers``, the repair read by the real repair handler
    from the model's ``reply`` and the envelope the runner built."""
    dispatched = _squad_answers(executor, None)
    answered = executor._task_dispatcher.dispatch_task

    async def _dispatch(envelope, run_id, **kw):
        if envelope.task_type != "development.correction_repair":
            return await answered(envelope, run_id, **kw)
        dispatched.append(envelope)
        handled = await DevelopmentCorrectionRepairHandler().handle(
            _answering(reply), dict(envelope.inputs)
        )
        return TaskResult(
            task_id=envelope.task_id, status=TaskResultStatus.SUCCEEDED, outputs=handled.outputs
        )

    executor._task_dispatcher.dispatch_task = _dispatch
    return dispatched


_FIX_THE_REPORT = """```edit:tally/report.py
<<<<<<< SEARCH
    return {}
=======
    counters = ledger.counters()
    top = max(counters, key=counters.get) if counters else None
    return {"total": ledger.total(), "counters": len(counters), "top": top}
>>>>>>> REPLACE
```
"""


async def test_a_removal_a_regressions_repair_makes_is_delivered_with_it(world, tmp_path):
    """PR #2918's round, entered at ``_execute_sequential``'s end of plan through the real
    correction runner and the real repair handler. Bugs caught: the repair judged with no view,
    so its removal is refused for want of a product; its removal lost between the round and the
    re-delivery; the file left in the repaired candidate's capture."""
    _repo, vault, executor, cycle, run = world
    _squad_repairs_with(executor, _FIX_THE_REPORT + _REMOVE_NOTIFY)

    await _end_of_plan(
        executor, _implementation(cycle), run, vault, {"tally/report.py": _BROKEN_REPORT},
        profile=_SQUAD,
    )  # fmt: skip

    (_first_id, first), (_second_id, second) = _verifications(vault)
    assert (first["verdict"], second["verdict"]) == ("regressed", "accepted")
    assert first["changed_paths"] == ["tally/report.py"]
    assert second["changed_paths"] == [
        "checks/check_notify.py",
        "tally/notify.py",
        "tally/report.py",
    ]
    [(patch_ref, _patch)] = _of_type(vault, SOURCE_PATCH_TYPE)
    clone = tmp_path / "cache" / "prj-tally.git"
    captured = tracked_files(clone, patch_ref.metadata["captured_commit"])
    assert "tally/notify.py" not in captured and "checks/check_notify.py" not in captured


async def test_a_refused_removal_in_a_regressions_repair_fails_the_run_naming_it(world):
    """A deletion in that round is refused with a reason. Bug caught: the refusal read as a
    round that wrote nothing, so the run's error never says which path or why."""
    _repo, vault, executor, cycle, run = world
    _squad_repairs_with(executor, "```delete:tally/absent.py\n```\n")

    with pytest.raises(_ExecutionError, match="tally/absent.py: removal refused: .*no such file"):
        await _end_of_plan(
            executor, _implementation(cycle), run, vault, {"tally/report.py": _BROKEN_REPORT},
            profile=_SQUAD,
        )  # fmt: skip

    assert [d["verdict"] for _id, d in _verifications(vault)] == ["regressed"]
    assert _of_type(vault, DELETION_ARTIFACT_TYPE) == []
