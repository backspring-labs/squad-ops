"""An increment's acceptance on a product's own runner, run in the sandbox (SIP-0109 §24cd point 6,
§24bv point 3, §24cl).

Every run here is real: the workspace store and the sandbox service are the deploy's, and the one
stand-in is the backend, which runs X-3a's disposable copy as local processes and reads the whole
output with the declared findings reader, as the container backend does. The product is invented:
a small Python package tested by pytest, with a conftest, its own test and a ``pyproject.toml``.

What bugs would these catch?
- an overlay holding the candidate's product code on the baseline side, so nothing ever fails
  there and no criterion discriminates; or holding the candidate's own test files, so a candidate's
  conftest decides how a frozen criterion runs (§8.1's isolation);
- a criterion read as discriminating because it failed on the baseline by an import, the failure
  §24ci (a) rules out;
- a runner with no test-id reader read whole, and a criterion accepted on it;
- a frozen criterion's bundle run by the candidate's copy of its file, or by the current profile's
  argv instead of its own frozen invocation;
- a bundle that can't round-trip through the document a promotion stores it from;
- an overlay judged on a candidate other than the one delivery verified;
- a product's declared routes passed because nothing rendered them.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import subprocess
import sys

import pytest

from squadops.campaigns.acceptance import DiscriminationReason, Held, IncrementVerdict
from squadops.campaigns.acceptance_run import (
    FrozenCriterion,
    NewCriterion,
    evaluation_document,
    frozen_criteria_from,
)
from squadops.campaigns.evaluator_trees import BundleIncomplete, FileTree
from squadops.campaigns.runner_acceptance import (
    CandidateNotDelivered,
    ProductTestSurface,
    RunnerAcceptance,
    RunnerSetup,
    SandboxTree,
    evaluate_on_runner,
    freeze_product_bundle,
    frozen_on_runner,
    single_file_argv,
)
from squadops.projects.derived_profile import parse_profile
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.findings import read
from squadops.sandbox.models import (
    CommandOutcome,
    CommandResult,
    OperationName,
    OperationStatus,
    RevisionOrigin,
    WorkspaceRevision,
)
from squadops.sandbox.noop import NoOpExecutionSandbox
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import WorkspaceStore

PY = sys.executable
CRITERION = "tests/test_criterion_C1.py"
FROZEN = "tests/test_criterion_F1.py"

#: The accepted tree: ``count`` counts every item.
HEAD = {
    "pyproject.toml": b'[tool.pytest.ini_options]\npythonpath = ["."]\n',
    "shelf/__init__.py": b"",
    "shelf/count.py": b"def count(items):\n    return len(items)\n",
    "tests/conftest.py": (
        b"import pytest\n\n\n@pytest.fixture\ndef doubled():\n    return ['a', 'a', 'b']\n"
    ),
    "tests/test_count.py": b"from shelf.count import count\n\n\ndef test_empty():\n"
    b"    assert count([]) == 0\n",
}
#: The squad's change: ``count`` counts distinct items.
DISTINCT = {"shelf/count.py": b"def count(items):\n    return len(set(items))\n"}


def _test(body: str) -> bytes:
    return f"from shelf.count import count\n\n\ndef test_it(doubled):\n{body}".encode()


#: A criterion that asserts the new behaviour on the package's public surface.
ASSERTS_DISTINCT = _test("    assert count(doubled) == 2\n")


def _profile(*, test_ids: str | None = "pytest", client_routes=None, single=True):
    return parse_profile(
        {
            "schema": "derived-profile/v1",
            "project_id": "prj-shelf",
            "commit": "a" * 40,
            "development_configuration_revision": 1,
            "environment": {"image": "python:3.12-slim"},
            "languages": [{"name": "python", "package_manager": "pip", "manifests": []}],
            "test_runners": [
                {
                    "runner": "pytest",
                    "checks": ["tests"],
                    "covers": ["shelf/**"],
                    "roots": ["tests"],
                    "file_pattern": "test_*.py",
                    "suite_argv": [PY, "-m", "pytest", "tests"],
                    "single_file_argv": [PY, "-m", "pytest", "{path}"] if single else None,
                    "test_ids": test_ids,
                    "support_files": ["tests/conftest.py"],
                }
            ],
            "lint": [],
            "toolchains": [],
            "start_declared": False,
            "public_surfaces": [{"kind": "package", "name": "shelf"}],
            "blueprint": None,
            "client_routes": client_routes,
            "files": {"test": ["tests/test_*.py"], "test_support": ["tests/conftest.py"]},
            "gaps": [],
        }
    )


class _ReadingBackend:
    """X-3a's disposable copy of a pinned revision, its setup and command run as local processes,
    the whole output read by the declared reader (#2609), as the container backend does."""

    def __init__(self, store: WorkspaceStore) -> None:
        self.store = store
        self.ran: list[tuple[str, tuple[str, ...], dict[str, bytes]]] = []

    async def run_declared_command(
        self, *, revision, command, working_dir=".", setup=(), timeout_seconds=None,
        findings_reader=None,
    ):  # fmt: skip
        # The outer run's own pytest settings never reach the product's.
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST", "COV_"))}
        with self.store.disposable_copy(revision.cycle_id, revision.revision_id) as copy:
            seen = {
                str(p.relative_to(copy)): p.read_bytes() for p in copy.rglob("*") if p.is_file()
            }
            self.ran.append((revision, tuple(command), seen))
            for step in setup:
                await asyncio.to_thread(subprocess.run, list(step), cwd=copy, check=True, env=env)
            done = await asyncio.to_thread(
                subprocess.run, list(command), cwd=copy / working_dir, capture_output=True,
                text=True, env=env,
            )  # fmt: skip
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
            findings=read(findings_reader, done.stdout, done.stderr, done.returncode).as_dict()
            if findings_reader
            else None,
        )


@pytest.fixture
def sandbox(tmp_path):
    store = WorkspaceStore(tmp_path / "sandbox")
    backend = _ReadingBackend(store)
    service = SandboxService(
        store=store, journal=OperationEvidenceJournal(tmp_path / "sandbox"), backend=backend
    )
    service.backend = backend
    service.store = store
    return service


def _runs(sandbox, profile=None, verified=None) -> RunnerAcceptance:
    return RunnerAcceptance(
        sandbox=sandbox,
        profile=profile or _profile(),
        setup=RunnerSetup(),
        workspace_prefix="acc-run_t-",
        verified_candidate_revision=verified,
    )


def _trees(criterion: bytes | None = ASSERTS_DISTINCT, change=DISTINCT, **extra):
    accepted = SandboxTree(HEAD)
    changes = {**change, **({CRITERION: criterion} if criterion is not None else {}), **extra}
    return accepted, SandboxTree(HEAD, changes=changes)


async def _evaluate(sandbox, accepted, candidate, *, profile=None, frozen=(), new=None, **kw):
    new = [NewCriterion("C1", CRITERION)] if new is None else new
    evaluation, runs = await evaluate_on_runner(
        _runs(sandbox, profile),
        increment_id="prop_shelf0001",
        accepted=accepted,
        candidate=candidate,
        new=new,
        frozen=frozen,
        retired=kw.get("retired", ()),
        replaced=kw.get("replaced", ()),
    )
    document = evaluation_document(
        evaluation,
        increment_id="prop_shelf0001",
        accepted=accepted.file_tree,
        candidate=candidate.file_tree,
        new=new,
        retired=kw.get("retired", ()),
        replaced=kw.get("replaced", ()),
    )
    return evaluation, runs, document


async def test_a_criterion_that_asserts_the_change_discriminates_and_its_bundle_is_frozen(sandbox):
    """§8.2 on the product's runner, end to end. Bugs caught: the baseline overlay built from the
    candidate's product code, so the criterion passes on both sides; the product's own tests run
    beside the criterion's; the bundle frozen without the conftest its fixture comes from, so it
    can't run alone later; its invocation left with ``{path}`` unfilled."""
    accepted, candidate = _trees()

    evaluation, runs, document = await _evaluate(sandbox, accepted, candidate)

    assert document["verdict"] == "accepted"
    assert document["discriminations"] == [
        {
            "criterion_id": "C1",
            "met": True,
            "reason": "discriminates",
            "discriminating": [f"{CRITERION}::test_it"],
        }
    ]
    bundle = document["new_bundles"]["C1"]
    assert bundle["invocation"] == [PY, "-m", "pytest", CRITERION]
    assert sorted(bundle["files"]) == ["tests/conftest.py", CRITERION]
    assert bundle["test_path"] == CRITERION
    # Each side ran the one file, on an overlay with no test file but the bundle's.
    assert [(r.side, r.exit_code) for r in runs] == [("baseline", 1), ("candidate", 0)]
    [(_r1, _a1, on_baseline), (_r2, _a2, on_candidate)] = sandbox.backend.ran
    assert on_baseline["shelf/count.py"] == HEAD["shelf/count.py"]
    assert on_candidate["shelf/count.py"] == DISTINCT["shelf/count.py"]
    for seen in (on_baseline, on_candidate):
        assert "tests/test_count.py" not in seen
        assert seen[CRITERION] == ASSERTS_DISTINCT
    # Each overlay is a revision of its tree: the baseline's cut on the head's checkout, the
    # candidate's on the candidate, which is the checkout with the squad's changes.
    head = WorkspaceRevision.cut(cycle_id="x", origin=RevisionOrigin.GIT_CHECKOUT, files=HEAD)
    cut = WorkspaceRevision.cut(
        cycle_id="x", origin=RevisionOrigin.AGENT_PATCH, files=candidate.content
    )
    assert [(rev.origin, rev.parent_revision_id) for rev, _a, _s in sandbox.backend.ran] == [
        (RevisionOrigin.ACCEPTANCE_ASSEMBLY, head.revision_id),
        (RevisionOrigin.ACCEPTANCE_ASSEMBLY, cut.revision_id),
    ]
    assert [r.revision_id for r in runs] == [rev.revision_id for rev, _a, _s in sandbox.backend.ran]
    assert runs[1].reading is not None and runs[1].reading.collected == 1


@pytest.mark.parametrize(
    ("criterion", "change", "reason", "verdict"),
    [
        (
            _test("    from shelf.unique import distinct\n    assert distinct(doubled) == 2\n"),
            {**DISTINCT, "shelf/unique.py": b"def distinct(items):\n    return len(set(items))\n"},
            DiscriminationReason.ONLY_SETUP_FAILURES,
            IncrementVerdict.REJECTED,
        ),
        (_test("    assert count([]) == 0\n"), DISTINCT, DiscriminationReason.NO_BASELINE_FAILURE,
         IncrementVerdict.REJECTED),
        (_test("    assert count(doubled) == 5\n"), DISTINCT, DiscriminationReason.FAILS_ON_CANDIDATE,
         IncrementVerdict.REJECTED),
    ],
    ids=["fails-on-the-baseline-only-by-an-import", "passes-on-the-baseline", "fails-on-both"],
)  # fmt: skip
async def test_a_criterion_that_does_not_discriminate_is_unmet_by_why(
    sandbox, criterion, change, reason, verdict
):
    """§8.2 and §24ci (a), each reason read from a real run. Bugs caught: a test that fails on the
    baseline only because the module it imports is the candidate's read as discriminating (the
    #2602 failure); a criterion the accepted product already meets read as met; one the candidate
    fails read as met."""
    accepted, candidate = _trees(criterion, change)

    evaluation, _runs, document = await _evaluate(sandbox, accepted, candidate)

    [d] = evaluation.discriminations
    assert (d.met, d.reason) == (False, reason)
    assert document["verdict"] == str(verdict)
    assert document["unmet"] == [f"criterion C1: {reason}"]


async def test_a_runner_with_no_test_id_reader_blocks_and_runs_nothing(sandbox):
    """§24ci (a): unread, never unmet, and never read whole. Bugs caught: the criterion counted
    unmet, so a correct increment is repaired; or its file read by exit status, so a file that
    fails to import on the baseline counts as discriminating. Its bundle is still frozen, so a
    later increment holds it."""
    accepted, candidate = _trees()

    _evaluation, runs, document = await _evaluate(
        sandbox, accepted, candidate, profile=_profile(test_ids=None)
    )

    assert (document["verdict"], document["unmet"]) == ("blocked_unverified", [])
    assert document["blocked"] == ["criterion C1: its runner names no test"]
    assert runs == () and sandbox.backend.ran == []
    assert sorted(document["new_bundles"]["C1"]["files"]) == ["tests/conftest.py", CRITERION]


async def test_a_criterion_whose_file_cannot_collect_on_the_baseline_is_blocked_not_met(sandbox):
    """§8.2: a collection error is not behavioural evidence, and pytest ends one at exit 2,
    which its reader can't read. So the criterion is unread on the baseline and blocks: never
    counted as discriminating (#2602's failure). A sample stack reads the same file as
    ``only_setup_failures``, which unmeets it with its reason. That difference is
    ``discrimination_on_runner``'s, named in §24cl item 9. Bug caught: a file that can't import on
    the baseline read as failing there for the intended reason."""
    criterion = (
        b"from shelf.unique import distinct\n\n\ndef test_it():\n    assert distinct([1, 1]) == 1\n"
    )
    unique = {"shelf/unique.py": b"def distinct(items):\n    return len(set(items))\n"}
    accepted, candidate = _trees(criterion, {**DISTINCT, **unique})

    evaluation, runs, document = await _evaluate(sandbox, accepted, candidate)

    assert [(r.side, r.exit_code) for r in runs] == [("baseline", 2), ("candidate", 0)]
    assert runs[0].reading is not None and runs[0].reading.readable is False
    [d] = evaluation.discriminations
    assert (d.met, d.reason) == (False, DiscriminationReason.NOT_RUN)
    assert (document["verdict"], document["blocked"]) == (
        "blocked_unverified",
        ["criterion C1: not run"],
    )


@pytest.mark.parametrize(
    ("new", "candidate_has_it", "reason"),
    [
        ([NewCriterion("C1", CRITERION)], False, "not run"),
        ([NewCriterion("C1", "checks/test_criterion_C1.py")], True, "not run"),
    ],
    ids=["the-candidate-lacks-its-file", "no-runner-holds-its-file"],
)
async def test_a_criterion_nothing_could_run_is_blocked(sandbox, new, candidate_has_it, reason):
    """§8.4's missing input, for discrimination: blocked, and no bundle frozen. Bugs caught: a
    qa role that wrote no test for the criterion read as a criterion the product fails; a file
    the profile's runners don't hold run by a guessed argv."""
    accepted, candidate = _trees(
        None, DISTINCT, **({"checks/test_criterion_C1.py": ASSERTS_DISTINCT} if candidate_has_it else {})
    )  # fmt: skip

    _evaluation, runs, document = await _evaluate(sandbox, accepted, candidate, new=new)

    assert document["blocked"] == [f"criterion C1: {reason}"]
    assert document["new_bundles"] == {} and runs == ()


def _frozen_from(document: dict, criterion_id: str, test_path: str) -> FrozenCriterion:
    """A criterion frozen as a promotion freezes it (``CampaignProgress._freeze_bundles``): its
    bundle stored from the document, read back by the next launch's pin."""
    stored = {"criterion_id": criterion_id, **document["new_bundles"][criterion_id]}
    pin = {
        "criterion_id": criterion_id,
        "test_path": test_path,
        "bundle_address": stored["address"],
    }
    [criterion] = frozen_criteria_from([pin], {criterion_id: stored})
    return criterion


async def _frozen_f1(sandbox) -> FrozenCriterion:
    """F1, accepted by an earlier increment: ``count`` counts distinct items."""
    accepted, candidate = _trees(None, DISTINCT, **{FROZEN: ASSERTS_DISTINCT})
    _e, _r, document = await _evaluate(
        sandbox, accepted, candidate, new=[NewCriterion("F1", FROZEN)]
    )
    assert document["verdict"] == "accepted", document
    return _frozen_from(document, "F1", FROZEN)


#: The tree after the increment that froze F1.
F1_HEAD = {**HEAD, **DISTINCT, FROZEN: ASSERTS_DISTINCT}


@pytest.mark.parametrize(
    ("change", "held", "detail"),
    [
        ({"README.md": b"# shelf\n"}, Held.HELD, ""),
        (
            {"shelf/count.py": b"def count(items):\n    return len(items)\n"},
            Held.BROKEN,
            f"{FROZEN}::test_it",
        ),
        (
            # A candidate conftest that skips every test: it never reaches the frozen run.
            {"tests/conftest.py": b"import pytest\n\n\n@pytest.fixture\ndef doubled():\n"
             b"    pytest.skip('no')\n", "shelf/count.py": b"def count(items):\n    return 0\n"},
            Held.BROKEN,
            f"{FROZEN}::test_it",
        ),
        (
            {FROZEN: _test("    assert True\n")},
            Held.BLOCKED_UNVERIFIED,
            "its test file changed in the candidate without a retires entry (§8.1)",
        ),
    ],
    ids=["kept", "undone", "the-candidates-conftest-skips-it", "its-file-rewritten"],
)  # fmt: skip
async def test_a_frozen_criterion_runs_its_own_bundle_on_the_candidate(
    sandbox, change, held, detail
):
    """§8.1 on the product's runner, its bundle round-tripped through the stored document. Bugs
    caught: the candidate's copy of the frozen file run in place of the bundle, so a rewrite
    passes it; the candidate's conftest overriding the bundle's, so a skip reads as held; a
    candidate that undoes the behaviour read as held."""
    f1 = await _frozen_f1(sandbox)
    candidate = SandboxTree(F1_HEAD, changes=change)

    evaluation, _runs, document = await _evaluate(
        sandbox, SandboxTree(F1_HEAD), candidate, new=[], frozen=[f1]
    )

    [result] = evaluation.frozen
    assert (result.held, result.detail) == (held, detail)
    assert result.bundle_address == f1.bundle.address
    assert document["verdict"] == {
        Held.HELD: "accepted", Held.BROKEN: "rejected", Held.BLOCKED_UNVERIFIED: "blocked_unverified"
    }[held]  # fmt: skip


async def test_a_frozen_bundle_runs_by_its_own_invocation_after_the_profile_changes(sandbox):
    """§8.1: "by the bundle's frozen invocation". Bug caught: the frozen criterion run by the
    current profile's argv, so a reconfigured runner changes what was frozen. Here the runner can
    no longer be scoped to one file, and the bundle still runs alone, as frozen."""
    f1 = await _frozen_f1(sandbox)
    sandbox.backend.ran.clear()

    evaluation, runs, _doc = await _evaluate(
        sandbox,
        SandboxTree(F1_HEAD),
        SandboxTree(F1_HEAD, changes={"README.md": b"x\n"}),
        profile=_profile(single=False),
        new=[],
        frozen=[f1],
    )

    assert [r.held for r in evaluation.frozen] == [Held.HELD]
    assert [argv for _rev, argv, _seen in sandbox.backend.ran] == [(PY, "-m", "pytest", FROZEN)]
    assert runs[0].reader == "pytest"


async def test_the_rebases_verification_runs_the_frozen_bundles_on_its_head(sandbox):
    """§24cd point 5, the entry the rebase calls (#2770's ``frozen_criteria_unrun``): the frozen
    half alone, on a tree with no changes, keyed by the rebase. Bugs caught: a missing bundle run
    or passed; the half usable only with an increment's two trees."""
    f1 = await _frozen_f1(sandbox)
    lost = FrozenCriterion("F2", "tests/test_criterion_F2.py", None)
    upstream = {**F1_HEAD, "shelf/count.py": b"def count(items):\n    return len(items)\n"}
    tree = SandboxTree(upstream)

    results, runs = await frozen_on_runner(
        _runs(sandbox),
        subject_id="rebase:abc",
        tree=tree,
        frozen=[f1, lost],
        surface=ProductTestSurface.of(_profile(), [FROZEN]),
    )

    assert [(r.increment_id, r.criterion_id, r.held, r.detail) for r in results] == [
        ("rebase:abc", "F1", Held.BROKEN, f"{FROZEN}::test_it"),
        ("rebase:abc", "F2", Held.BLOCKED_UNVERIFIED, "the verifier bundle is missing"),
    ]  # fmt: skip
    assert [r.side for r in runs] == ["candidate"]
    assert {r.candidate_identity for r in results} == {tree.file_tree.identity}


async def test_a_candidate_other_than_the_verified_one_is_refused(sandbox):
    """The tree judged is the tree delivered. Bug caught: an evaluation of a tree delivery never
    verified, so an accepted verdict names a candidate nobody checked. The verified revision is
    the one the sandbox cuts for the same checkout and changes, as delivery cuts it."""
    accepted, candidate = _trees()
    verified = WorkspaceRevision.cut(
        cycle_id="x", origin=RevisionOrigin.AGENT_PATCH, files=candidate.content
    )
    runs = _runs(sandbox, verified=verified.revision_id)
    other = _runs(sandbox, verified="0" * 64)

    evaluation, _r = await evaluate_on_runner(
        runs, increment_id="p", accepted=accepted, candidate=candidate,
        new=[NewCriterion("C1", CRITERION)], frozen=(), retired=(),
    )  # fmt: skip
    with pytest.raises(CandidateNotDelivered, match="the tree judged isn't the tree delivered"):
        await evaluate_on_runner(
            other, increment_id="p", accepted=accepted, candidate=candidate,
            new=[NewCriterion("C1", CRITERION)], frozen=(), retired=(),
        )  # fmt: skip

    assert evaluation.acceptance.verdict is IncrementVerdict.ACCEPTED


async def test_a_sandbox_that_runs_nothing_blocks_every_criterion():
    """``sandbox_client.provider: none``: every operation is not run (SIP-0102 §4.4). Bug caught:
    a run that never reached an exit read as a pass, or as a failure the product owns."""
    accepted, candidate = _trees()
    runs = RunnerAcceptance(
        sandbox=NoOpExecutionSandbox(), profile=_profile(), setup=RunnerSetup(),
        workspace_prefix="acc-run_t-",
    )  # fmt: skip
    f1 = FrozenCriterion(
        "F1", FROZEN, freeze_product_bundle(
            "F1", FileTree.of(F1_HEAD), FROZEN, ProductTestSurface.of(_profile(), [FROZEN]),
            _profile().runners[0],
        ),
    )  # fmt: skip

    evaluation, _runs = await evaluate_on_runner(
        runs, increment_id="p", accepted=accepted, candidate=candidate,
        new=[NewCriterion("C1", CRITERION)], frozen=[f1], retired=(),
    )  # fmt: skip

    assert evaluation.acceptance.verdict is IncrementVerdict.BLOCKED_UNVERIFIED
    assert evaluation.acceptance.blocked[0] == "criterion C1: not run"
    assert evaluation.acceptance.blocked[1].startswith("frozen F1: the bundle never executed")


async def test_a_profiles_client_routes_are_blocked_never_passed(sandbox):
    """§24bv point 3 and §24cl item 6: rendering a product's routes isn't built. Bug caught: a
    route nothing read counted as rendered, so a blueprint product's increment is accepted with
    its pages unread. With no routes named, none is judged (not applicable)."""
    accepted, candidate = _trees()

    _e, _r, routed = await _evaluate(
        sandbox, accepted, candidate, profile=_profile(client_routes=["/shelves"])
    )
    _e2, _r2, unrouted = await _evaluate(sandbox, accepted, candidate, profile=_profile())

    assert routed["routes"] == [
        {"path": "/shelves", "held": "blocked_unverified", "missing": [], "not_shown": []}
    ]
    assert (routed["verdict"], routed["blocked"]) == (
        "blocked_unverified",
        ["route /shelves: not rendered"],
    )
    assert (unrouted["routes"], unrouted["verdict"]) == ([], "accepted")


class _VitestSandbox:
    """A sandbox that seeds and patches as content addresses do, and answers each run with real
    vitest 2.1.9 output read by the reader it was asked for: the fixture's failing run on the
    baseline overlay (the accepted ``count``), and a passing run of as many tests on the
    candidate's. The vitest toolchain isn't on this box, so the output is the recorded one."""

    def __init__(self) -> None:
        self.asked: list[dict] = []
        self.trees: dict[str, dict] = {}

    async def release_workspace(self, workspace_id):
        return None

    async def seed_workspace(self, workspace_id, files, *, origin, executable=(), created_at=None):
        revision = WorkspaceRevision.cut(cycle_id=workspace_id, origin=origin, files=files)
        self.trees[revision.revision_id] = dict(files)
        return revision

    async def apply_workspace_patch(self, *, base, files, origin):
        from squadops.sandbox.models import PatchResult

        merged = {**self.trees[base.revision_id]}
        for path, content in files.items():
            merged.pop(path, None) if content is None else merged.__setitem__(path, content)
        revision = WorkspaceRevision.cut(cycle_id=base.cycle_id, origin=origin, files=merged)
        self.trees[revision.revision_id] = merged
        return PatchResult(
            operation=OperationName.APPLY_WORKSPACE_PATCH,
            workspace_revision_id=base.revision_id,
            status=OperationStatus.SUCCEEDED,
            ran=True,
            new_revision_id=revision.revision_id,
        )

    async def run_declared_command(self, *, revision, command, working_dir, setup, findings_reader):
        from tests.unit.campaigns.test_runner_acceptance import _out

        self.asked.append(
            {"argv": command, "working_dir": working_dir, "setup": setup, "reader": findings_reader}
        )
        on_baseline = self.trees[revision.revision_id]["shelf/count.py"] == HEAD["shelf/count.py"]
        stdout, stderr, code = (
            (_out("vitest-2.1.9-asserting.stdout.txt"), _out("vitest-2.1.9-asserting.stderr.txt"), 1)
            if on_baseline
            else (" Tests  6 passed (6)\n", "", 0)
        )  # fmt: skip
        return CommandResult(
            operation=OperationName.RUN_DECLARED_COMMAND,
            workspace_revision_id=revision.revision_id,
            status=OperationStatus.SUCCEEDED if code == 0 else OperationStatus.FAILED,
            ran=True,
            command=tuple(command),
            outcome=CommandOutcome.EXITED,
            exit_code=code,
            findings=read(findings_reader, stdout, stderr, code).as_dict(),
        )


async def test_a_vitest_criterion_runs_by_its_name_in_its_package_and_reads_by_test_id():
    """H.7's vitest runner under a package: its one-file argv names the file by ``{name}``, and
    it runs in the configuration's working directory after its setup, read by ``vitest``. Bugs
    caught: the repository path handed to vitest's package-relative filter, which runs no test;
    the setup or working directory dropped, so the product's own command can't run; the reading
    asked of no reader, so a vitest-only criterion reads unread for ever (§24ci (a), #2757)."""
    path = "frontend/src/__tests__/criterion_C1.test.jsx"
    base = _profile().runners[0]
    vitest = dataclasses.replace(
        base, runner="vitest", roots=("frontend/src",), file_pattern="*.test.*",
        single_file_argv=("npm", "--prefix", "frontend", "test", "--", "{name}"),
        test_ids="vitest", support_files=(),
    )  # fmt: skip
    profile = dataclasses.replace(_profile(), runners=(vitest,), test_files=("frontend/src/**",))
    sandbox = _VitestSandbox()
    setup = RunnerSetup(".", (("npm", "--prefix", "frontend", "ci"),))
    runs = RunnerAcceptance(
        sandbox=sandbox, profile=profile, setup=setup, workspace_prefix="acc-run_v-"
    )
    accepted = SandboxTree(HEAD)
    candidate = SandboxTree(HEAD, changes={**DISTINCT, path: b"it('counts', () => {})\n"})

    evaluation, _runs = await evaluate_on_runner(
        runs, increment_id="p", accepted=accepted, candidate=candidate,
        new=[NewCriterion("C1", path)], frozen=(), retired=(),
    )  # fmt: skip

    assert [a["argv"] for a in sandbox.asked] == [
        ("npm", "--prefix", "frontend", "test", "--", "criterion_C1.test.jsx")
    ] * 2
    assert {(a["working_dir"], a["setup"], a["reader"]) for a in sandbox.asked} == {
        (".", (("npm", "--prefix", "frontend", "ci"),), "vitest")
    }
    [d] = evaluation.discriminations
    assert (d.met, d.reason) == (True, DiscriminationReason.DISCRIMINATES)
    assert (
        "src/__tests__/asserting.test.js > Book form > refuses an empty title" in d.discriminating
    )


@pytest.mark.parametrize(
    ("argv", "path", "expected"),
    [
        (("pytest", "{path}"), "tests/test_criterion_C1.py", ("pytest", "tests/test_criterion_C1.py")),
        (("npm", "--prefix", "web", "test", "--", "{name}"), "web/src/criterion_C1.test.jsx",
         ("npm", "--prefix", "web", "test", "--", "criterion_C1.test.jsx")),
    ],
    ids=["path", "name"],
)  # fmt: skip
def test_a_runners_one_file_argv_names_the_file_as_its_placeholder_says(argv, path, expected):
    """H.6's placeholders. Bug caught: a vitest runner under a package given the repository path,
    which its filter matches against the package-relative path and so runs no test (H.7)."""
    runner = dataclasses.replace(_profile().runners[0], single_file_argv=argv)

    assert single_file_argv(runner, path) == expected


def test_an_unscopable_runner_has_no_one_file_argv_and_a_missing_import_freezes_nothing():
    """The two refusals of a bundle's freeze. Bugs caught: an unscopable runner given a whole-
    suite argv as a criterion's; a bundle frozen without a helper the test imports."""
    unscopable = _profile(single=False).runners[0]
    surface = ProductTestSurface.of(_profile(), [CRITERION])
    tree = FileTree.of({**HEAD, CRITERION: b"from .helpers import x\n"})

    with pytest.raises(ValueError, match="runner_not_scopable"):
        single_file_argv(unscopable, CRITERION)
    with pytest.raises(BundleIncomplete, match="imports tests/helpers, which is not in the tree"):
        freeze_product_bundle("C1", tree, CRITERION, surface, _profile().runners[0])


def test_a_bundle_under_a_test_package_carries_its_package_markers():
    """§8.1: what the test needs to import as written. Bug caught: a test under a package
    directory frozen without its ``__init__.py``, which the overlay drops with the candidate's test
    files, so pytest imports it as a top-level module and the product may not be on its path."""
    surface = ProductTestSurface(("tests/**",), frozenset({"tests/unit/test_criterion_C1.py"}))
    runner = _profile().runners[0]
    tree = FileTree.of(
        {
            "tests/__init__.py": b"",
            "tests/unit/__init__.py": b"",
            "tests/unit/test_criterion_C1.py": b"def test_x():\n    pass\n",
            "shelf/__init__.py": b"",
        }
    )

    bundle = freeze_product_bundle("C1", tree, "tests/unit/test_criterion_C1.py", surface, runner)

    assert bundle.files.paths() == (
        "tests/__init__.py",
        "tests/unit/__init__.py",
        "tests/unit/test_criterion_C1.py",
    )
